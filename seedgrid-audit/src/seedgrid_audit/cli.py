"""Command-line interface for SeedGrid Audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .core import ManifestError, audit, csv_report, load_manifest, markdown_report


def _write(path_str: str | None, text: str) -> None:
    if path_str:
        target = Path(path_str)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        print(f"Wrote {target}")


def _make_demo(directory: Path) -> None:
    """Build a tiny, synthetic complete 2x2x2 fixture (not a real model)."""
    if directory.exists() and any(directory.iterdir()):
        raise ManifestError(f"Refusing to overwrite non-empty directory: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "project": "synthetic-example-not-real-weights",
        "root": "runs",
        "axes": {"model": ["baseline", "ours"], "dataset": ["sample-a", "sample-b"], "seed": [1, 2]},
        "artifacts": {
            "checkpoint": {"path": "{model}/{dataset}/seed-{seed}/checkpoint.bin", "min_bytes": 4},
            "metrics": {"path": "{model}/{dataset}/seed-{seed}/metrics.json", "kind": "json", "required_numeric": {"accuracy": {"min": 0, "max": 1}, "macro_f1": {"min": 0, "max": 1}}},
        },
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for model in manifest["axes"]["model"]:
        for dataset in manifest["axes"]["dataset"]:
            for seed in manifest["axes"]["seed"]:
                base = directory / "runs" / model / dataset / f"seed-{seed}"
                base.mkdir(parents=True, exist_ok=True)
                (base / "checkpoint.bin").write_bytes(b"DEMO_ONLY_NOT_A_MODEL\n")
                (base / "metrics.json").write_text(
                    json.dumps({"accuracy": 0.71, "macro_f1": 0.69}, indent=2) + "\n",
                    encoding="utf-8",
                )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="seedgrid", description="Read-only ML experiment matrix checkpoint/metrics audit"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="Audit runs declared in JSON manifest")
    check.add_argument("--manifest", "-m", required=True, help="Path to JSON manifest")
    check.add_argument("--json", dest="json_output", help="Write machine-readable JSON report")
    check.add_argument("--markdown", help="Write Markdown coverage report")
    check.add_argument("--csv", help="Write CSV coverage report")
    check.add_argument("--sha256", action="store_true", help="Also calculate SHA256 for each existing artifact (potentially slow)")
    demo = sub.add_parser("demo", help="Create a synthetic 2x2x2 example with fake data")
    demo.add_argument("directory", nargs="?", default="seedgrid_demo")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            folder = Path(args.directory)
            _make_demo(folder)
            print(f"Created synthetic demo in '{folder}'")
            print(f"Now run: seedgrid check -m {folder / 'manifest.json'}")
            return 0
        if args.command == "check":
            manifest = load_manifest(args.manifest)
            report = audit(manifest, compute_hash=args.sha256)
            _write(args.json_output, json.dumps(report, indent=2, ensure_ascii=False) + "\n")
            _write(args.markdown, markdown_report(report))
            _write(args.csv, csv_report(report))
            s = report["summary"]
            print(
                f"{report['project']}: {s['complete_runs']}/{s['expected_runs']} complete; "
                f"{s['missing_artifacts']} missing, {s['invalid_artifacts']} invalid artifacts"
            )
            return 0 if s["incomplete_runs"] == 0 else 1
    except ManifestError as e:
        print(f"seedgrid: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"seedgrid: cannot write output: {e}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
