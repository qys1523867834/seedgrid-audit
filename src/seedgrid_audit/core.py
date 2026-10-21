"""Safe, read-only experiment coverage checker (Python standard library only)."""

from __future__ import annotations

import csv
import hashlib
import io
import itertools
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from string import Formatter
from typing import Any

SCHEMA_VERSION = 1
MAX_CELLS = 100_000
MAX_METRICS_BYTES = 2 * 1024 * 1024
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


class ManifestError(ValueError):
    """Invalid manifest or unsafe experiment path specification."""


def _object(value: Any, field: str) -> dict:
    if not isinstance(value, dict):
        raise ManifestError(f"{field} must be an object")
    return value


def _list(value: Any, field: str) -> list:
    if not isinstance(value, list) or not value:
        raise ManifestError(f"{field} must be a non-empty list")
    return value


def _axis_value(value: Any, name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ManifestError(f"Axis '{name}' values must be strings or integers")
    s = str(value)
    if s.strip() != s or not s or s in (".", ".."):
        raise ManifestError(f"Unsafe or empty value for axis '{name}': {s!r}")
    if any(ch in s for ch in ('/', '\\', ':', '\n', '\r', '\0', '|')):
        raise ManifestError(f"Axis '{name}' value cannot contain path separators or reserved characters: {s!r}")
    return s


def _safe_relative_path(path: str, label: str) -> Path:
    if not isinstance(path, str) or not path.strip():
        raise ManifestError(f"{label} must be a non-empty path string")
    if "\\" in path or "\0" in path or Path(path).is_absolute() or re.match(r"^[A-Za-z]:", path):
        raise ManifestError(f"{label} must be a relative POSIX-style path: {path!r}")
    parts = Path(path).parts
    if ".." in parts or not parts or any(part == "." for part in path.split("/")):
        raise ManifestError(f"{label} must not contain '.' or '..' segments: {path!r}")
    return Path(path)


def _fields(template: str, axis_names: set[str], artifact_name: str) -> None:
    try:
        parsed = list(Formatter().parse(template))
    except ValueError as e:
        raise ManifestError(f"Bad format template in '{artifact_name}': {e}") from e
    used = set()
    for _, field_name, fmt_spec, conversion in parsed:
        if field_name is None:
            continue
        if field_name not in axis_names or fmt_spec or conversion:
            raise ManifestError(
                f"Artifact '{artifact_name}' has unsupported placeholder '{field_name}'"
            )
        used.add(field_name)
    if not used:
        raise ManifestError(f"Artifact '{artifact_name}' path must reference at least one axis")


def load_manifest(path: str | Path) -> dict:
    """Load and validate a JSON manifest. Relative root is relative to manifest file."""
    manifest_path = Path(path).expanduser().resolve()
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"), parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
    except (OSError, ValueError, UnicodeDecodeError) as e:
        raise ManifestError(f"Cannot load manifest '{manifest_path}': {e}") from e
    data = _object(raw, "Manifest")
    if type(data.get("schema_version")) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise ManifestError(f"schema_version must be {SCHEMA_VERSION}")
    axes_raw = _object(data.get("axes"), "axes")
    if not axes_raw:
        raise ManifestError("axes must contain at least one axis")
    axes = {}
    cells = 1
    for name, values in axes_raw.items():
        if not isinstance(name, str) or not IDENTIFIER.fullmatch(name):
            raise ManifestError(f"Invalid axis name {name!r}")
        normalized = [_axis_value(v, name) for v in _list(values, f"axes.{name}")]
        if len(set(normalized)) != len(normalized):
            raise ManifestError(f"Duplicate values in axis '{name}'")
        axes[name] = normalized
        cells *= len(normalized)
        if cells > MAX_CELLS:
            raise ManifestError(f"Too many experiment combinations (>{MAX_CELLS:,})")
    artifacts_raw = _object(data.get("artifacts"), "artifacts")
    if not artifacts_raw:
        raise ManifestError("artifacts must include at least one named artifact")
    artifacts = {}
    for name, spec in artifacts_raw.items():
        if not isinstance(name, str) or not IDENTIFIER.fullmatch(name):
            raise ManifestError(f"Invalid artifact name {name!r}")
        spec = _object(spec, f"artifacts.{name}")
        path_pattern = spec.get("path")
        _safe_relative_path(path_pattern, f"artifacts.{name}.path")
        _fields(path_pattern, set(axes), name)
        min_bytes = spec.get("min_bytes", 1)
        if type(min_bytes) is not int or min_bytes < 0:
            raise ManifestError(f"artifacts.{name}.min_bytes must be an integer >= 0")
        kind = spec.get("kind", "file")
        if kind not in ("file", "json"):
            raise ManifestError(f"artifacts.{name}.kind must be 'file' or 'json'")
        rules = _object(spec.get("required_numeric", {}), f"artifacts.{name}.required_numeric")
        if rules and kind != "json":
            raise ManifestError(f"artifacts.{name}.required_numeric requires kind='json'")
        normalized_rules = {}
        for metric, limits in rules.items():
            if not isinstance(metric, str) or not metric or any(c in metric for c in '\r\n'):
                raise ManifestError(f"Invalid metric name {metric!r}")
            limits = _object(limits, f"required_numeric.{metric}")
            for bound in ("min", "max"):
                if bound in limits and (isinstance(limits[bound], bool) or not isinstance(limits[bound], (int, float)) or not math.isfinite(limits[bound])):
                    raise ManifestError(f"Invalid {bound} bound for metric '{metric}'")
            if "min" in limits and "max" in limits and limits["min"] > limits["max"]:
                raise ManifestError(f"Metric '{metric}' has min > max")
            normalized_rules[metric] = {k: limits[k] for k in ("min", "max") if k in limits}
        artifacts[name] = {"path": path_pattern, "min_bytes": min_bytes, "kind": kind, "required_numeric": normalized_rules}
    root_raw = data.get("root", ".")
    if not isinstance(root_raw, str) or not root_raw.strip():
        raise ManifestError("root must be a path string")
    root = Path(root_raw).expanduser()
    if not root.is_absolute():
        root = manifest_path.parent / root
    root = root.resolve()
    return {"schema_version": SCHEMA_VERSION, "project": str(data.get("project", manifest_path.stem)), "root": root, "axes": axes, "artifacts": artifacts, "manifest": str(manifest_path)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_artifact(path: Path, spec: dict, compute_hash: bool) -> dict:
    entry: dict[str, Any] = {"path": str(path), "status": "ok", "issues": []}
    try:
        if not path.is_file():
            entry["status"] = "missing"
            entry["issues"].append("file does not exist or is not a regular file")
            return entry
        size = path.stat().st_size
        entry["bytes"] = size
        if size < spec["min_bytes"]:
            entry["issues"].append(f"file too small: {size} < {spec['min_bytes']} bytes")
        if spec["kind"] == "json":
            if size > MAX_METRICS_BYTES:
                entry["issues"].append(f"JSON file exceeds {MAX_METRICS_BYTES} byte safety limit")
            else:
                try:
                    parsed = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda v: (_ for _ in ()).throw(ValueError(f"non-finite JSON literal: {v}")))
                    if not isinstance(parsed, dict):
                        entry["issues"].append("JSON top-level value must be an object")
                    else:
                        for metric, limits in spec["required_numeric"].items():
                            value = parsed.get(metric)
                            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                                entry["issues"].append(f"missing or non-finite numeric metric '{metric}'")
                            else:
                                if "min" in limits and value < limits["min"]:
                                    entry["issues"].append(f"metric '{metric}'={value} is below {limits['min']}")
                                if "max" in limits and value > limits["max"]:
                                    entry["issues"].append(f"metric '{metric}'={value} is above {limits['max']}")
                except (ValueError, UnicodeDecodeError) as e:
                    entry["issues"].append(f"invalid JSON: {e}")
        if compute_hash:
            entry["sha256"] = _sha256(path)
        if entry["issues"]:
            entry["status"] = "invalid"
    except OSError as e:
        entry["status"] = "invalid"
        entry["issues"].append(f"could not inspect file: {e}")
    return entry


def audit(manifest: dict, compute_hash: bool = False) -> dict:
    """Read-only audit. Never loads or executes model checkpoints."""
    root: Path = manifest["root"]
    axis_names = list(manifest["axes"])
    combos = list(itertools.product(*(manifest["axes"][axis] for axis in axis_names)))
    # Resolve all paths first to avoid partial audits when a manifest is unsafe.
    planned: list[tuple[dict, dict[str, Path]]] = []
    seen: dict[Path, str] = {}
    for values in combos:
        axes = dict(zip(axis_names, values))
        paths = {}
        for artifact, spec in manifest["artifacts"].items():
            rel = spec["path"].format_map(axes)
            _safe_relative_path(rel, f"Resolved artifact '{artifact}'")
            resolved = (root / rel).resolve()
            if not resolved.is_relative_to(root):
                # Python 3.9 compatibility: replace is_relative_to below if necessary.
                raise ManifestError(f"Artifact '{artifact}' escapes root directory: {resolved}")
            label = f"{axes} / {artifact}"
            if resolved in seen:
                raise ManifestError(f"Path collision: {resolved} assigned to both {seen[resolved]} and {label}")
            seen[resolved] = label
            paths[artifact] = resolved
        planned.append((axes, paths))
    summary = {"expected_runs": len(planned), "complete_runs": 0, "incomplete_runs": 0, "missing_artifacts": 0, "invalid_artifacts": 0}
    rows = []
    by_axis = {
        axis: {
            value: {"expected_runs": 0, "complete_runs": 0, "incomplete_runs": 0}
            for value in values
        }
        for axis, values in manifest["axes"].items()
    }
    for axes, paths in planned:
        checked = {}
        for artifact, path in paths.items():
            entry = _check_artifact(path, manifest["artifacts"][artifact], compute_hash)
            checked[artifact] = entry
            if entry["status"] == "missing":
                summary["missing_artifacts"] += 1
            elif entry["status"] == "invalid":
                summary["invalid_artifacts"] += 1
        status = "complete" if all(item["status"] == "ok" for item in checked.values()) else "incomplete"
        summary[f"{status}_runs"] += 1
        for axis, value in axes.items():
            counts = by_axis[axis][value]
            counts["expected_runs"] += 1
            counts[f"{status}_runs"] += 1
        rows.append({"axes": axes, "status": status, "artifacts": checked})
    return {
        "schema_version": SCHEMA_VERSION,
        "project": manifest["project"],
        "manifest": manifest["manifest"],
        "root": str(root),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "by_axis": by_axis,
        "axes": axis_names,
        "artifact_names": list(manifest["artifacts"]),
        "runs": rows,
    }


def markdown_report(report: dict) -> str:
    """Readable coverage table suitable for GitHub issue or CI artifact."""
    summary = report["summary"]
    headers = report["axes"] + report["artifact_names"] + ["run"]
    lines = [
        f"# Experiment audit: {report['project']}",
        "",
        f"**Complete:** {summary['complete_runs']}/{summary['expected_runs']} runs; "
        f"**missing files:** {summary['missing_artifacts']}; "
        f"**invalid files:** {summary['invalid_artifacts']}.",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in report["runs"]:
        cells = [str(row["axes"][axis]) for axis in report["axes"]]
        cells += [row["artifacts"][name]["status"] for name in report["artifact_names"]]
        cells.append(row["status"])
        lines.append("| " + " | ".join(cells) + " |")
    details = []
    for row in report["runs"]:
        for name, item in row["artifacts"].items():
            if item["issues"]:
                label = ", ".join(f"{key}={value}" for key, value in row["axes"].items())
                details.append(f"- **{label} / {name}:** " + "; ".join(item["issues"]))
    if details:
        lines += ["", "## Findings", ""] + details
    if report.get("by_axis"):
        lines += ["", "## Coverage by axis"]
        for axis, values in report["by_axis"].items():
            lines += [
                "", f"### {axis}", "",
                "| value | complete | expected | incomplete |",
                "| --- | ---: | ---: | ---: |",
            ]
            for value, counts in values.items():
                lines.append(
                    f"| {value} | {counts['complete_runs']} | "
                    f"{counts['expected_runs']} | {counts['incomplete_runs']} |"
                )
    lines += ["", "_Reports are about artifact coverage and basic data integrity, not scientific validity._", ""]
    return "\n".join(lines)


def csv_report(report: dict) -> str:
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(report["axes"] + report["artifact_names"] + ["run"])
    for row in report["runs"]:
        writer.writerow([row["axes"][axis] for axis in report["axes"]] + [row["artifacts"][name]["status"] for name in report["artifact_names"]] + [row["status"]])
    return out.getvalue()
