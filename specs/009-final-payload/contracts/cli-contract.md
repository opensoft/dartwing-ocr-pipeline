# Contract: `python -m dartwing_ocr.assembler` CLI

This document pins the command-line surface of the assembler. Shell scripts and orchestrators
depending on this CLI can rely on the stability guarantees below.

## Invocation

```bash
python -m dartwing_ocr.assembler --document-folder <path> [--pipeline-version <str>]
```

Installed-entry-point equivalent (added alongside `dartwing-preprocess` and
`dartwing-pipeline` in `pyproject.toml`):

```bash
dartwing-assemble --document-folder <path> [--pipeline-version <str>]
```

## Flags

| Flag | Type | Required | Default | Purpose |
|---|---|---|---|---|
| `--document-folder` | path | yes | — | The per-document folder containing `edge_extraction_output.json` and `routing_decision.json`. Output is written here. |
| `--pipeline-version` | string | no | `"009-final-payload@0.1.0"` | Override for testing. Not intended for production use. |
| `--help` / `-h` | flag | no | — | Print argparse help and exit 0. |

**Stability**:
- `--document-folder` is pinned. Any rename is a contract break (bumps the CLI's own semver).
- New optional flags may be added without a bump. New required flags require a bump.
- No positional arguments. The CLI is flag-only to match `dartwing-preprocess`.

## Exit codes

| Code | Meaning | When it fires |
|---|---|---|
| `0` | Success | `final_structured_payload.json` was written and validated against v1.0.0. |
| `1` | Unexpected | Any uncaught exception inside `run()`. Should never fire in normal use. |
| `2` | Input rejected | Any of the 6 cross-input invariants failed (see `data-model.md` §Cross-input invariant table, rows 1–6). Emits the stderr JSON contract below. |
| `2` | argparse usage error | `argparse` rejects the invocation itself (missing `--document-folder`, unknown flag, bad value). Exit code coincides with "input rejected" by argparse convention but the stderr shape differs: argparse writes its own multi-line usage message, **not** the single-line JSON object. Downstream orchestrators distinguish the two by checking whether stderr parses as one JSON line. |
| `3` | Internal error | Assembled output failed its own schema validation (row 7). Indicates a code/contract mismatch. |

## stderr contract

On any non-zero exit, one JSON object is printed to stderr (no trailing shell text). Shape:

```json
{"status": "error", "kind": "<kind>", "message": "<human-readable>"}
```

Permitted `kind` values (stable — new kinds may be added but existing ones may not be removed or renamed):

- `missing_input` — one of the two input files is absent.
- `unreadable_input` — an input file exists but cannot be read or JSON-parsed.
- `schema_invalid_input` — an input file parses but fails its own v1.0.0 schema.
- `contract_drift` — one input reports `contract_set_version != "1.0.0"`.
- `document_id_mismatch` — the two inputs disagree on `document_id`.
- `routing_contradiction` — routing's `decision` and `review_status` are inconsistent (FR-016).
- `output_schema_invalid` — the assembled payload failed output-side validation (exit 3).
- `unexpected` — uncaught exception (exit 1).

**Message guarantees**:
- Human-readable. Includes enough context for a developer to locate the failure (file path, conflicting values, schema error pointer).
- Does NOT include absolute paths outside the per-document folder where avoidable.
- Does NOT include raw exception tracebacks on exit 2 (those are for exit 1).

## Side effects on success

On exit 0, exactly one file is written: `<document-folder>/final_structured_payload.json`.
Any prior copy at that path is **overwritten** (spec Edge Case §7). No other files in the
folder are created, modified, or deleted. No stdout output (the file is the output).

## Side effects on failure

No file is written. No existing file in the folder is modified. Only stderr receives output.

## What is NOT part of the contract

- The exact wording of `message` strings (only the `kind` taxonomy is pinned).
- Internal logging, env vars, or debug output behind future `--verbose` / `--debug` flags (to be added without a bump when needed).
- stdout output (currently empty; reserved for future use).
