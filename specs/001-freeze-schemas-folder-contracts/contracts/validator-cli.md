# Validator CLI Contract

**Feature**: `001-freeze-schemas-folder-contracts`
**Surface**: `python -m dartwing_ocr.validator`

This document pins the externally observable behavior of the validator CLI. Callers — humans, the harness, CI, regression gates — depend on this contract; it is frozen at contract-set `1.0.0` and changed only via the amendment path.

## Invocation

```text
python -m dartwing_ocr.validator <subcommand> [options]
```

## Subcommands

### `validate artifact <path> --contract <name>`

Validate a single JSON file against a named artifact contract.

| Argument / Flag | Type | Required | Description |
|---|---|---|---|
| `<path>` | path | yes | Path to a JSON file on disk. |
| `--contract <name>` | enum | yes | One of `preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`, `expected`, `evaluation_document`, `evaluation_run_summary`. |
| `--contract-set-version <ver>` | semver | no | Defaults to the version stamped inside the artifact. If the flag is given and disagrees with the stamped version, the CLI emits `CONTRACT_SET_VERSION_INCOMPATIBLE`. |
| `--json` / `--text` | flag | no | Report format. Default: `--text`. Mutually exclusive. |

### `validate folder <path>`

Validate a per-document folder against the folder contract.

| Argument / Flag | Type | Required | Description |
|---|---|---|---|
| `<path>` | path | yes | Path to an `inv_<NNN>_<difficulty>/` folder. |
| `--contract-set-version <ver>` | semver | no | Defaults to the version stamped on `expected.json` inside the folder. |
| `--json` / `--text` | flag | no | Report format. |

### `validate corpus <root>`

Validate the corpus root (default `tests/stage1_vendor_identity/`) in bulk: every subfolder validated as a document folder, plus the root-level `evaluation_run_summary.json` if present.

| Argument / Flag | Type | Required | Description |
|---|---|---|---|
| `<root>` | path | yes | Corpus root directory. |
| `--contract-set-version <ver>` | semver | no | Defaults to each artifact's stamped version; incompatibilities are reported per artifact. |
| `--json` / `--text` | flag | no | Report format. |
| `--fail-fast` | flag | no | Stop after the first folder with `error`-severity violations. Default: off (aggregate all). |

### `show contract-set [--version <ver>]`

Print the loaded contract-set metadata (version, artifact-to-schema map, closed challenge-tags vocabulary, active cross-artifact rules). Never performs validation. Useful for developers and labelers who want to see what the current contract covers.

| Flag | Type | Required | Description |
|---|---|---|---|
| `--version <ver>` | semver | no | Defaults to the latest version directory under `contracts/stage1_vendor_identity/`. |
| `--json` / `--text` | flag | no | Output format. |

## Output

### Text (default)

Human-readable rendering of the same underlying `ValidationOutcome`:

```text
Target: artifact:edge_extraction_output (tests/stage1_vendor_identity/inv_003_hard/edge_extraction_output.json)
Contract set: 1.0.0
Result: FAIL (2 errors, 0 warnings)

  error  TAX_ID_TYPE_INVALID
         at /vendor_candidate/tax_ids/sales_tax
         reason: "sales_tax" is not an allowed tax-ID type.
         expected: FR-012 tax_ids enum (ein, state_tax_id, vat_id, other_tax_id)

  error  VOTE_METADATA_MISSING
         at /vote_metadata
         reason: vote_metadata block is required even in single-voter mode.
         expected: FR-010
```

### JSON (`--json`)

Structured report conforming to `specs/001-freeze-schemas-folder-contracts/contracts/report.schema.json`. Written to stdout. No log noise on stderr when `--json` is used; errors internal to the validator itself go to stderr with exit code 3.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All targets validated; no `error`-severity violations (warnings may be present). |
| `1` | Validation failed: one or more `error`-severity violations. |
| `2` | Usage error: bad flag, missing required argument, unknown subcommand, unreadable file. |
| `3` | Internal validator error: e.g. malformed contract-set directory. Should never occur against a shipped contract set. |

## Stability guarantees

- Subcommand names, flag names, and exit codes are frozen at contract-set version `1.0.0`.
- Violation codes (`TAX_ID_TYPE_INVALID`, etc.) are frozen; new codes may be added in later contract-set versions, but existing codes MUST NOT be renamed or removed without a major-version bump.
- The `--json` structured report schema (`report.schema.json`) is frozen.
- Human-readable text output is *not* a stable contract — format may improve, phrasing may change; the harness MUST use `--json`.
