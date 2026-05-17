# CLI Contract: `dartwing_ocr.preprocessing`

This file documents the external interface this slice exposes. The **artifact
shape** (`preprocess_output.json`) is not redefined here — it is the frozen
JSON Schema at
`contracts/stage1_vendor_identity/v1.0.0/preprocess_output.schema.json` in the
repository root. This contract only covers the CLI surface, exit codes, and
I/O behavior.

## Invocation

```bash
python -m dartwing_ocr.preprocessing \
    --document-folder <PATH> \
    [--source-file <NAME>] \
    [--write-page-images] \
    [--pipeline-version <STRING>]
```

### Arguments

| Flag                     | Type   | Required | Default                     | Notes |
|--------------------------|--------|----------|-----------------------------|-------|
| `--document-folder`      | path   | yes      | —                           | Per-document folder (e.g. `tests/stage1_vendor_identity/inv_001_easy`). `document_id` is derived from the folder's basename. Folder must exist. |
| `--source-file`          | string | no       | `source.pdf`                | Name of the PDF inside `--document-folder`. Recorded verbatim in the artifact's `source_file` field. |
| `--write-page-images`    | flag   | no       | off                         | When set, write `page_{N}.png` files next to the artifact as debug output. These files are NOT part of the contract — downstream code MUST NOT depend on them. |
| `--pipeline-version`     | string | no       | `stage1-preprocess-v0.1`    | Override for experiments. Shipped default is the canonical value. |

### Stdout / Stderr

- **stdout**: a single JSON line on success of the form
  `{"status": "ok", "document_id": "...", "artifact": "<abs path>", "warnings": <int>}`.
  Intended for machine-readability by future harness scripts.
- **stderr**: human-readable progress messages and any errors.

### Exit codes

| Code | Meaning                                                                   | Artifact written? |
|------|---------------------------------------------------------------------------|-------------------|
| `0`  | Success. Schema-valid `preprocess_output.json` written atomically.        | yes               |
| `2`  | Malformed input. Cases: folder missing; PDF missing; file is not a PDF; PDF encrypted; PDF has zero pages; PDF bytes unreadable. | **no** |
| `3`  | Internal error. Notably: assembled artifact failed schema validation (a bug — contracts and code disagree). | **no** |
| `1`  | Any unexpected exception (stack trace on stderr).                          | no                |

Exit code `2` MUST be emitted before any page is rasterized when the reason is
a structural input problem. This lets callers distinguish "bad input" from
"bad pipeline" cleanly.

## I/O invariants

1. **Read set**: `--document-folder/<source-file>` only. No other file in the
   folder is read.
2. **Write set on success**: `<document-folder>/preprocess_output.json` is
   written atomically (via temp-file + rename). When `--write-page-images` is
   passed, `<document-folder>/page_{N}.png` files are also written (debug
   only, not part of the contract).
3. **Write set on failure**: nothing is written. In particular, no partial
   `preprocess_output.json` is persisted (FR-019).
4. **Overwrite**: an existing `preprocess_output.json` is replaced on success.
   Prior content is not merged.
5. **Network**: none. No HTTP calls, no model server calls.
6. **Side effects outside the folder**: none.

## Determinism guarantee

Two invocations with:
- identical PDF bytes at `--document-folder/<source-file>`,
- identical `--pipeline-version` (or both defaulted),
- identical PaddleOCR / pypdfium2 versions installed,

MUST produce byte-identical `preprocess_output.json` contents (FR-012,
SC-002). This is enforced by a dedicated integration test that runs the CLI
twice against the same fixture and diffs the outputs.

## Schema-validation contract

Before writing, the assembled artifact is validated against
`contracts/stage1_vendor_identity/v1.0.0/preprocess_output.schema.json` using
the in-repo validator (`dartwing_ocr.validator`). A validation failure
produces exit code `3` and no artifact — this is intentionally loud because
a schema-invalid artifact means our code is out of sync with the frozen
contract and must be fixed (never hidden).

## Out-of-scope surface (explicit)

This CLI does **not**:

- accept any input format other than a single PDF;
- accept cloud credentials, endpoints, or API keys;
- take a `--dpi` flag — 300 DPI is a project constant, not a runtime setting
  (FR-004, research.md Decision 3);
- emit any of the other stage 1 artifacts
  (`edge_extraction_output.json`, `routing_decision.json`,
  `final_structured_payload.json`, or anything under `votes/`) — FR-022;
- invoke any model for consensus, routing, voting, or business-field
  extraction — FR-022;
- modify the frozen contract set under
  `contracts/stage1_vendor_identity/v1.0.0/` in any way (FR-018).
