# SeedGrid Audit

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
[![CI](https://github.com/qys1523867834/seedgrid-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/qys1523867834/seedgrid-audit/actions/workflows/ci.yml)

**Check whether every planned machine learning experiment has the expected checkpoints and valid metrics — without importing PyTorch, downloading a model, or rerunning training.**

SeedGrid Audit is a tiny, dependency-free (at runtime), read-only CLI for researchers who run many datasets × models × random seeds. It discovers missing experiment outputs, suspiciously small checkpoints, malformed metrics JSON, metric values outside expected ranges, and accidental filename collisions. It can produce a Markdown coverage matrix, JSON evidence, and CSV for CI or manual review.

> **Project stage:** v0.1.1, newly created. This is a useful foundation and is *not* claimed to have existing downloads, external users, or independent adoption. Contributions and real-world testing are welcome.

## Why this tool?

Imagine a paper with 5 datasets, 6 models, and 5 seeds: that's 150 training runs. One incomplete seed or wrong metric file is easy to miss when results are stored in different folders. This tool answers: **What actually exists and passes basic validation?**

It is **not** a model-performance validator: the presence of a checkpoint does not establish correct code, experimental fairness, absence of data leakage, or scientific reproducibility. It never opens PyTorch pickle checkpoints, so it cannot tell whether weights belong to the intended architecture.

## Install

Python 3.9 or newer. No deep-learning dependencies are required.

```bash
git clone https://github.com/qys1523867834/seedgrid-audit.git
cd seedgrid-audit
python -m pip install -e .
```

Alternatively, download the source ZIP and run `python -m pip install -e .` from the extracted project root.

## Try the working demo

```bash
seedgrid demo my_demo
seedgrid check --manifest my_demo/manifest.json \
  --json my_demo/audit.json \
  --markdown my_demo/audit.md \
  --csv my_demo/audit.csv
```

The demo makes **synthetic text bytes** named `checkpoint.bin`; they are deliberately *not real model weights*. The demo should report `8/8 complete`. You can then delete `my_demo/runs/ours/sample-a/seed-1/checkpoint.bin`, rerun the check, and see `7/8 complete` and exit code `1`.

## Audit your experiment

Define a JSON manifest (see [`examples/manifest.example.json`](examples/manifest.example.json)):

```json
{
  "schema_version": 1,
  "project": "Paper benchmark",
  "root": "runs",
  "axes": {
    "model": ["baseline", "ours"],
    "dataset": ["dataset-a", "dataset-b"],
    "seed": [13, 21, 42]
  },
  "artifacts": {
    "checkpoint": {
      "path": "{model}/{dataset}/seed-{seed}/best.pt",
      "min_bytes": 1024
    },
    "metrics": {
      "path": "{model}/{dataset}/seed-{seed}/metrics.json",
      "kind": "json",
      "required_numeric": {
        "accuracy": {"min": 0, "max": 1},
        "macro_f1": {"min": 0, "max": 1}
      }
    }
  }
}
```

All paths below `artifacts` are **relative to `root`**, which itself is relative to the JSON manifest file (absolute roots also work). The sample above expects 12 runs × 2 artifacts = 24 files. You can use any number of axes or artifacts, up to 100,000 run combinations. Supported metric files are UTF-8 JSON objects with *top-level numeric keys*. File existence/size checking works on any artifact type. File extensions do not determine behavior: add `"kind": "json"` to validate JSON.

Run:

```bash
seedgrid check -m manifest.json --markdown report.md --json report.json --csv report.csv
```

Sample output:

```text
Paper benchmark: 11/12 complete; 1 missing, 0 invalid artifacts
```

The actual numbers depend on your real files. The JSON report includes `by_axis` completion counts for every model, dataset, and seed. The Markdown report adds **Coverage by axis** tables, making it easier to spot partial experiment groups. Counts measure file validation coverage, **not** model accuracy or reproducibility. CSV retains its per-run format. `--sha256` also hashes every existing artifact, which is useful for provenance but may take a long time with large checkpoints.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | All declared runs pass basic checks |
| `1` | At least one run has a missing or invalid artifact |
| `2` | Invalid manifest, unsafe path, or I/O error |

### Validations and safety

- Tests the Cartesian product of declared axes; detects missing or undersized output files.
- Optionally validates JSON syntax and declared finite numeric metrics, including ranges.
- Detects filename-template collisions between experiment runs or artifact types.
- Rejects path traversal and symlinks resolving outside the declared root.
- Reads metrics JSON only up to 2 MiB each; never deserializes checkpoint formats such as `.pt` or `.pth`.
- Does **not** upload files, invoke models, alter experiment directories, or make network requests.
- Reports may include your local paths. **Sanitize reports before publishing**, and never publish private datasets, model weights, or tokens.
- A `complete` run indicates files were found and passed configured checks, not that a model was correctly trained.

## Running tests

```bash
python -m unittest discover -s tests -v
```

The GitHub Actions workflow exercises three Python versions. This repository includes unit tests for corrupt JSON, unsafe paths, missing files, metric validation, filename collisions, and CLI behavior.

## Project layout

```text
src/seedgrid_audit/     # Read-only audit core and CLI
examples/               # Example experiment manifest
tests/                  # Python unittest suite
docs/                   # Chinese guide and roadmap
.github/workflows/       # Automated test configuration
```

## Contributing and roadmap

Issues and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/ROADMAP.md](docs/ROADMAP.md). Potential extensions include multiple folder layouts, summarizing run coverage by dimension, richer metric parsing, and integrations with experiment trackers. Actual user requests should determine priorities.

## License

MIT; see [LICENSE](LICENSE).
