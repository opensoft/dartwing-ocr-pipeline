# CLI Contract: `dartwing_ocr.router`

This file documents the external interface this slice exposes. The **artifact
shape** (`routing_decision.json`) is not redefined here — it is the frozen
JSON Schema at
`contracts/stage1_vendor_identity/v1.0.0/routing_decision.schema.json` in the
repository root. This contract only covers the CLI surface, exit codes, and
I/O behavior.

## Invocation

```bash
python -m dartwing_ocr.router route <PATH> \
    [--input-file <NAME>] \
    [--pipeline-version <STRING>] \
    [--policy-version <STRING>]
```

### Arguments

| Flag                     | Type   | Required | Default                             | Notes |
|--------------------------|--------|----------|-------------------------------------|-------|
| `<PATH>`                 | path   | yes      | —                                   | Positional. Per-document folder (e.g. `tests/stage1_vendor_identity/inv_001_easy`). `document_id` in the output equals the `document_id` in the input `edge_extraction_output.json`. Folder must exist. |
| `--input-file`           | string | no       | `edge_extraction_output.json`       | Name of the input JSON inside `<PATH>`. |
| `--pipeline-version`     | string | no       | `stage1-routing-v0.1.0`             | Override for experiments. Shipped default is the canonical value. Recorded verbatim in the artifact's `pipeline_version`. |
| `--policy-version`       | string | no       | `stage1-routing-policy-v1.0.0`      | Override for experiments (e.g., A/B runs during a policy bump). Shipped default is the canonical value. Recorded verbatim in the artifact's `policy_version`. |

No `--output-file` flag: the output is always written to
`<PATH>/routing_decision.json` (FR-001).

### Subcommand design

The module exposes a single subcommand: `route`. Additional subcommands
(e.g., `route-corpus`) are deferred to the harness (research Decision 12).
The subcommand-style invocation parallels
`python -m dartwing_ocr.validator validate …` and leaves room for future
subcommands without renaming the module.

### Stdout / Stderr

- **stdout**: a single JSON line on success of the form
  `{"status": "ok", "document_id": "...", "decision": "edge_accept" | "edge_review_required", "artifact": "<abs path>"}`.
  Intended for machine-readability by future harness scripts.
- **stderr**: human-readable progress messages and any errors.

### Exit codes

| Code | Meaning                                                                   | Artifact written? |
|------|---------------------------------------------------------------------------|-------------------|
| `0`  | Success. Schema-valid `routing_decision.json` written atomically.         | yes               |
| `2`  | Malformed input. Cases: folder missing; input file missing; file is not valid JSON; input fails `edge_extraction_output.schema.json` validation; input reports `contract_set_version != "1.0.0"`. | **no** |
| `3`  | Internal error. Notably: assembled output failed `routing_decision.schema.json` validation (a bug — contracts and code disagree). | **no** |
| `1`  | Any unexpected exception (stack trace on stderr).                          | no                |

Exit code `2` MUST be emitted before any output is assembled when the reason
is a structural input problem. This lets callers distinguish "bad input" from
"bad policy" cleanly.

## I/O invariants

1. **Read set**: `<PATH>/<input-file>` only. No other file in the folder is
   read — in particular, `preprocess_output.json` is NOT re-read by the router
   (FR-019).
2. **Write set on success**: `<PATH>/routing_decision.json` is written
   atomically (via temp-file + `os.replace`). The containing directory's
   file descriptor is `fsync`'d after the rename so that a host crash between
   the rename and the kernel's next directory flush cannot surface a partial
   or zero-byte `routing_decision.json` to readers — the FR-002 "no partial
   or dangling artifact" guarantee holds across crashes, not only across
   clean shutdowns.
3. **Write set on failure**: nothing is written. In particular, no partial
   `routing_decision.json` is persisted (FR-003).
4. **Overwrite**: an existing `routing_decision.json` is replaced on success.
   Prior content is not merged.
5. **Network**: none. No HTTP calls, no model server calls (FR-019).
6. **Side effects outside the folder**: none.
7. **Inputs never mutated**: the router does NOT modify
   `edge_extraction_output.json`, `preprocess_output.json`, `expected.json`,
   `source.pdf`, `notes.md`, or any other file in the folder (FR-022).
8. **Reserved names not overwritten**: the router does NOT create or overwrite
   `final_structured_payload.json`, `evaluation_document.json`, or the
   `votes/` subdirectory (US1 AC#7). These are reserved for downstream slices.

## Determinism guarantee

Two invocations with:
- identical input JSON contents at `<PATH>/<input-file>`,
- identical `--pipeline-version` (or both defaulted),
- identical `--policy-version` (or both defaulted),

MUST produce byte-identical `routing_decision.json` contents **except for the
`processed_at` field** (SC-004, FR-021). This is enforced by a dedicated
integration test that runs the CLI twice against the same fixture and diffs
the outputs with `processed_at` normalized.

## Schema-validation contract

Two layers of validation:

1. **Input validation** — before any rule fires, `<PATH>/<input-file>` is
   validated against
   `contracts/stage1_vendor_identity/v1.0.0/edge_extraction_output.schema.json`
   using the in-repo validator (`dartwing_ocr.validator`). Failure → exit
   code `2`, no artifact. Input's `contract_set_version` MUST equal `"1.0.0"`
   exactly; drift → exit code `2`, no artifact.

2. **Output validation** — before the atomic write, the assembled artifact is
   validated against
   `contracts/stage1_vendor_identity/v1.0.0/routing_decision.schema.json`
   using the in-repo validator. A validation failure produces exit code `3`
   and no artifact — this is intentionally loud because a schema-invalid
   artifact means the code and the frozen contract have drifted and must be
   fixed (never hidden).

## Canonical string vocabulary (part of `policy_version`)

The router emits only the following strings in `reasons` and
`review_status.review_reason`. Adding, removing, or renaming any requires a
`policy_version` bump.

**Forcing-rule reasons** (can appear in either `reasons` or `review_reason`):

- `"company_name_inferred"` — missing-name gate fired (priority 1).
- `"post_extraction_spam_gate_failed"` — spam gate fired (priority 2).
- `"secondary_identifiers_insufficient"` — floor-of-2 not met (priority 3).
- `"upstream_extraction_failed"` — input `status == "failure"` (priority 4).

**Affirmative reasons** (only in `reasons`, only when `decision ==
"edge_accept"`):

- `"company_name_explicit"`
- `"spam_gate_passed"`
- `"secondary_identifier_floor_met"`
- `"upstream_extraction_ok"`

**Informational reasons** (only in `reasons`, never in `review_reason`):

- `"upstream_status_partial"` — input reported `status == "partial"`.
- `"contract_violation_detected"` — input violates an extractor FR-013
  invariant (FR-024).

## Out-of-scope surface (explicit)

This CLI does **not**:

- accept any input format other than an `edge_extraction_output.json`
  conforming to `v1.0.0`;
- accept cloud credentials, endpoints, or API keys;
- invoke any model, any OCR library, or host Ollama — the router is pure rule
  evaluation (FR-019);
- re-read or otherwise consume `preprocess_output.json` — the extractor owns
  that artifact (FR-019);
- emit any of the other stage 1 artifacts
  (`preprocess_output.json`, `edge_extraction_output.json`,
  `final_structured_payload.json`, `evaluation_document.json`) — FR-022 /
  FR-023;
- operate on more than one per-document folder per invocation — corpus
  orchestration is the harness's concern (research Decision 12);
- modify the frozen contract set under
  `contracts/stage1_vendor_identity/v1.0.0/` in any way.
