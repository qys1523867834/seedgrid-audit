# Roadmap

This document proposes areas for community discussion. Items are **not** commitments or claims of existing usage.

## v0.1: implemented in source bundle

- [x] Deterministic Cartesian run matrix from JSON manifest
- [x] Checkpoint and metric presence, file sizes
- [x] JSON metric validation and finite/range checks
- [x] Optional SHA256 checksums
- [x] JSON, CSV, Markdown reports and CLI exit codes
- [x] Safe path resolution and regression tests

## Proposed improvements (prioritize from real user feedback)

- [x] Per-dataset, per-model, and per-seed completion summary in JSON/Markdown (v0.1.1)
- [ ] Support nested JSON metric keys (e.g., `eval.macro_f1`)
- [ ] Allow optional artifacts and optional cells (e.g., deliberately skipped baselines)
- [ ] Better outputs and file search for legacy folders
- [ ] GitHub Action integration for public reproductions
- [ ] More OS and Python version compatibility reports from users
- [ ] Metadata sidecar validation without deserializing untrusted checkpoints

## How to help

Open a feature request describing a concrete experiment folder layout (without disclosing private files), or submit a PR with unit tests for a reproducible bug. Review proposals before introducing new runtime dependencies.
