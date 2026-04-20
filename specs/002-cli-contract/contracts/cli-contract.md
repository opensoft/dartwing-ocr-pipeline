# CLI Contract: Stage 1 One-Document Pipeline

**Contract set version**: 1.0.0
**CLI contract version**: 1.0.0
**Frozen**: 2026-04-20

This document defines the frozen command surface for the stage 1 one-document pipeline CLI. Changes to this surface require an amendment through the contract-set governance path (`contracts/stage1_vendor_identity/AMENDMENTS.md`).

---

## Invocation

```bash
# Contract-stable form (harness targets this)
python -m ledgerlinc_ocr.pipeline run [REQUIRED] [OPTIONS]

# Convenience alias (same behavior)
ledgerlinc-pipeline run [REQUIRED] [OPTIONS]
```

Without a subcommand, the CLI prints help and exits with code `10` (usage error).

---

## Arguments

### Required (one of)

| Argument | Type | Description |
|----------|------|-------------|
| `--input PATH` | file path | Path to a single PDF file. Mutually exclusive with `--document-folder`. |
| `--document-folder PATH` | directory path | Path to a per-document folder containing `source.pdf`. Mutually exclusive with `--input`. |

Exactly one of `--input` or `--document-folder` must be provided. Providing both exits with `USAGE_ERROR` (10). Providing neither exits with `USAGE_ERROR` (10).

### Optional

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--output-dir PATH` | directory path | See below | Destination per-document folder for artifacts. |
| `--document-id ID` | string | Derived from folder name | Document identifier stamped into all artifacts. |
| `--overwrite` | flag | `false` | Replace existing reserved artifact files. |
| `--pipeline-version VER` | string | Package default | Semver stamped into pipeline-versioned artifacts. |
| `--policy-version VER` | string | Package default | Stamped into `routing_decision` only. |
| `--contract-set-version VER` | string | Installed latest | Must name an installed version. |
| `--ollama-url URL` | string | `$OLLAMA_BASE_URL` or `http://localhost:11434` | Ollama endpoint for model inference. |
| `--log-level LEVEL` | string | `warning` | One of: `error`, `warning`, `info`, `debug`. |
| `--timeout SECONDS` | integer | `300` | Wall-clock timeout for processing stages. |

### `--output-dir` default resolution

- If `--document-folder` was provided: output-dir defaults to the document folder itself.
- If `--input` was provided: output-dir defaults to the parent directory of the input PDF.

### `--document-id` derivation

- If the destination folder name matches `^(inv_\d{3})_(easy|medium|hard|missing_name)$`: document_id is capture group 1 (e.g., `inv_001_easy` → `inv_001`).
- If the folder name does not match: the CLI exits with `USAGE_ERROR` (10) directing the caller to pass `--document-id`.

### Environment variables

| Variable | Purpose | Fallback |
|----------|---------|----------|
| `OLLAMA_BASE_URL` | Ollama endpoint | `http://localhost:11434` |

Priority: `--ollama-url` flag > `OLLAMA_BASE_URL` env > default.

---

## Frozen argument set

The arguments listed above are the complete stage 1 argument set. The following are explicitly **not present** and must not be added without a contract amendment:

- Image input flags (PNG, JPG, TIFF)
- Batch/multi-document flags
- HTTP service mode flags
- Cloud execution flags
- Line-item extraction flags
- Latency/SLA gate flags
- Voter selection flags

---

## Output behavior

### On success (exit 0)

1. Exactly four artifact files written to destination folder (see `exit-codes.md`).
2. One JSON line emitted to stdout (see `stdout-summary.md`).
3. No output to stderr (except log messages at configured `--log-level`).

### On failure (exit non-zero)

1. One JSON line emitted to stderr (see `stderr-failure-record.md`).
2. Any artifacts already written remain on disk.
3. No output to stdout.
