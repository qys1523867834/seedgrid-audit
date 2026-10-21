"""Functional and safety tests. Run with python -m unittest discover -s tests -v."""

import csv
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from seedgrid_audit.cli import main
from seedgrid_audit.core import ManifestError, audit, csv_report, load_manifest, markdown_report


class MatrixTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.data = {
            "schema_version": 1,
            "project": "test-matrix",
            "root": "runs",
            "axes": {"model": ["a", "b"], "seed": [1, 2]},
            "artifacts": {
                "weight": {"path": "{model}/seed-{seed}/best.pt", "min_bytes": 2},
                "scores": {"path": "{model}/seed-{seed}/metrics.json", "kind": "json", "required_numeric": {"f1": {"min": 0, "max": 1}}},
            },
        }
        self.manifest_path = self.base / "manifest.json"
        self.populate()

    def populate(self):
        for model in ["a", "b"]:
            for seed in [1, 2]:
                base = self.base / "runs" / model / f"seed-{seed}"
                base.mkdir(parents=True, exist_ok=True)
                (base / "best.pt").write_bytes(b"FAKE")
                (base / "metrics.json").write_text('{"f1":0.8}', encoding="utf-8")
        self.write_manifest()

    def write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.data), encoding="utf-8")

    def report(self, sha=False):
        self.write_manifest()
        return audit(load_manifest(self.manifest_path), compute_hash=sha)

    def test_complete_matrix(self):
        result = self.report()
        self.assertEqual(result["summary"]["expected_runs"], 4)
        self.assertEqual(result["summary"]["complete_runs"], 4)
        self.assertEqual(result["summary"]["incomplete_runs"], 0)

    def test_by_axis_complete(self):
        breakdown = self.report()["by_axis"]
        self.assertEqual(
            breakdown["model"]["a"],
            {"expected_runs": 2, "complete_runs": 2, "incomplete_runs": 0},
        )
        self.assertEqual(breakdown["model"]["b"]["complete_runs"], 2)
        self.assertEqual(breakdown["seed"]["1"]["expected_runs"], 2)
        self.assertEqual(breakdown["seed"]["2"]["incomplete_runs"], 0)

    def test_by_axis_one_missing(self):
        (self.base / "runs/a/seed-1/best.pt").unlink()
        result = self.report()
        breakdown = result["by_axis"]
        self.assertEqual(breakdown["model"]["a"]["complete_runs"], 1)
        self.assertEqual(breakdown["model"]["a"]["incomplete_runs"], 1)
        self.assertEqual(breakdown["model"]["b"]["complete_runs"], 2)
        self.assertEqual(breakdown["seed"]["1"]["incomplete_runs"], 1)
        self.assertEqual(breakdown["seed"]["2"]["incomplete_runs"], 0)
        self.assertEqual(
            sum(item["complete_runs"] for item in breakdown["model"].values()),
            result["summary"]["complete_runs"],
        )

    def test_by_axis_markdown(self):
        (self.base / "runs/a/seed-1/best.pt").unlink()
        output = markdown_report(self.report())
        self.assertIn("## Coverage by axis", output)
        self.assertIn("### model", output)
        self.assertIn("| a | 1 | 2 | 1 |", output)
        self.assertIn("| b | 2 | 2 | 0 |", output)
        self.assertIn("### seed", output)

    def test_missing_weight(self):
        (self.base / "runs/a/seed-1/best.pt").unlink()
        result = self.report()
        self.assertEqual(result["summary"]["missing_artifacts"], 1)
        self.assertEqual(result["summary"]["incomplete_runs"], 1)

    def test_empty_weight_invalid(self):
        (self.base / "runs/a/seed-1/best.pt").write_bytes(b"")
        self.assertEqual(self.report()["summary"]["invalid_artifacts"], 1)

    def test_bad_json_invalid(self):
        (self.base / "runs/a/seed-1/metrics.json").write_text("{", encoding="utf-8")
        self.assertEqual(self.report()["summary"]["invalid_artifacts"], 1)

    def test_missing_metric_invalid(self):
        (self.base / "runs/a/seed-1/metrics.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self.report()["summary"]["invalid_artifacts"], 1)

    def test_boolean_metric_invalid(self):
        (self.base / "runs/a/seed-1/metrics.json").write_text('{"f1": true}', encoding="utf-8")
        self.assertEqual(self.report()["summary"]["invalid_artifacts"], 1)

    def test_nan_metric_invalid(self):
        (self.base / "runs/a/seed-1/metrics.json").write_text('{"f1": NaN}', encoding="utf-8")
        self.assertEqual(self.report()["summary"]["invalid_artifacts"], 1)

    def test_out_of_range_invalid(self):
        (self.base / "runs/a/seed-1/metrics.json").write_text('{"f1": 2.0}', encoding="utf-8")
        result = self.report()
        self.assertIn("above", result["runs"][0]["artifacts"]["scores"]["issues"][0])

    def test_sha256(self):
        result = self.report(True)
        digest = hashlib.sha256(b"FAKE").hexdigest()
        self.assertEqual(result["runs"][0]["artifacts"]["weight"]["sha256"], digest)

    def test_absent_sha_by_default(self):
        self.assertNotIn("sha256", self.report()["runs"][0]["artifacts"]["weight"])

    def test_csv(self):
        rows = list(csv.reader(csv_report(self.report()).splitlines()))
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0], ["model", "seed", "weight", "scores", "run"])

    def test_markdown(self):
        output = markdown_report(self.report())
        self.assertIn("Complete:** 4/4", output)
        self.assertIn("| model | seed | weight | scores | run |", output)

    def test_collision_detected(self):
        self.data["artifacts"]["weight"]["path"] = "{model}/best.pt"
        with self.assertRaisesRegex(ManifestError, "collision"):
            self.report()

    def test_unknown_placeholder(self):
        self.data["artifacts"]["weight"]["path"] = "{unknown}/weights.pt"
        with self.assertRaisesRegex(ManifestError, "unsupported placeholder"):
            self.report()

    def test_absolute_artifact_rejected(self):
        self.data["artifacts"]["weight"]["path"] = "/tmp/data/{seed}.pt"
        with self.assertRaisesRegex(ManifestError, "relative"):
            self.report()

    def test_traversal_rejected(self):
        self.data["artifacts"]["weight"]["path"] = "../secrets/{seed}.pt"
        with self.assertRaisesRegex(ManifestError, "must not"):
            self.report()

    def test_duplicate_axis_values(self):
        self.data["axes"]["model"] = ["a", "a"]
        with self.assertRaisesRegex(ManifestError, "Duplicate"):
            self.report()

    def test_axis_slash_rejected(self):
        self.data["axes"]["model"] = ["a/x"]
        with self.assertRaisesRegex(ManifestError, "reserved"):
            self.report()

    def test_bad_version(self):
        self.data["schema_version"] = 99
        with self.assertRaisesRegex(ManifestError, "schema_version"):
            self.report()

    def test_bad_metric_range(self):
        self.data["artifacts"]["scores"]["required_numeric"]["f1"] = {"min": 3, "max": 0}
        with self.assertRaisesRegex(ManifestError, "min > max"):
            self.report()

    def test_no_json_kind_with_numeric(self):
        self.data["artifacts"]["scores"]["kind"] = "file"
        with self.assertRaisesRegex(ManifestError, "requires kind"):
            self.report()

    def test_json_top_level_must_be_object(self):
        (self.base / "runs/a/seed-1/metrics.json").write_text("[]", encoding="utf-8")
        self.assertEqual(self.report()["summary"]["invalid_artifacts"], 1)

    def test_large_json_refused(self):
        (self.base / "runs/a/seed-1/metrics.json").write_bytes(b" " * (2 * 1024 * 1024 + 1))
        self.assertIn("safety limit", self.report()["runs"][0]["artifacts"]["scores"]["issues"][0])

    def test_max_cells(self):
        self.data["axes"]["seed"] = list(range(100_000))
        with self.assertRaisesRegex(ManifestError, "Too many"):
            self.report()

    def test_cli_exit_status(self):
        self.write_manifest()
        self.assertEqual(main(["check", "-m", str(self.manifest_path)]), 0)
        (self.base / "runs/a/seed-1/best.pt").unlink()
        self.assertEqual(main(["check", "-m", str(self.manifest_path)]), 1)

    def test_cli_reports(self):
        self.write_manifest()
        path = self.base / "audit.json"
        md = self.base / "audit.md"
        csv_out = self.base / "audit.csv"
        self.assertEqual(main(["check", "-m", str(self.manifest_path), "--json", str(path), "--markdown", str(md), "--csv", str(csv_out)]), 0)
        recorded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(recorded["summary"]["complete_runs"], 4)
        self.assertEqual(recorded["by_axis"]["model"]["a"]["expected_runs"], 2)
        self.assertTrue(md.exists())
        self.assertTrue(csv_out.exists())

    def test_cli_demo(self):
        destination = self.base / "demo"
        self.assertEqual(main(["demo", str(destination)]), 0)
        self.assertEqual(main(["check", "-m", str(destination / "manifest.json")]), 0)
        self.assertEqual(main(["demo", str(destination)]), 2)

    @unittest.skipUnless(hasattr(os, "symlink"), "OS does not support symlinks")
    def test_escaped_symlink_rejected(self):
        root = self.base / "runs"
        try:
            (root / "link").symlink_to(self.base, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Cannot make symlinks on this system")
        self.data["axes"]["model"] = ["link"]
        with self.assertRaisesRegex(ManifestError, "escapes root"):
            self.report()


if __name__ == "__main__":
    unittest.main()
