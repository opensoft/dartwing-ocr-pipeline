# Failure-Handling Checklist: PDF Preprocessing (Stage 1)

**Purpose**: Release-gate validation that the spec covers failure branches —
malformed inputs, partial page failures, ingestion-source failures,
recoverable anomalies — with enough clarity and coverage to build against.
Every item validates the requirements, not the implementation.
**Created**: 2026-04-20
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + QA)

## Input-Level Rejection (non-recoverable)

- [ ] CHK001 Is the behavior for a non-PDF input specified (reject before rasterization, clear error)? [Completeness, Spec §FR-001]
- [ ] CHK002 Is the behavior for an encrypted / password-protected PDF specified (treated as malformed, no artifact)? [Clarity, Spec §Edge Cases §Clarifications 2026-04-20]
- [ ] CHK003 Is the behavior for a zero-page PDF specified (treated as malformed)? [Clarity, Spec §Edge Cases §US3 AC#3]
- [ ] CHK004 Is the behavior for a PDF whose bytes cannot be opened at all specified (non-zero exit, explicit error)? [Completeness, Spec §US3 AC#3]
- [ ] CHK005 Does the spec require that input-rejection produces a clear, human-readable error mentioning the cause? [Clarity, Spec §US3 AC#3]
- [ ] CHK006 Does the spec forbid writing any `preprocess_output.json` (even partial) when input is rejected? [Completeness, Spec §US3 AC#3 §FR-019]
- [ ] CHK007 Is the exit-code semantic for input rejection specified (non-zero)? [Clarity, Spec §US3 AC#3]

## Page-Level Failure (recoverable)

- [ ] CHK008 Is "one unreadable page among readable ones" defined as recoverable, not fatal? [Clarity, Spec §US3 §US3 AC#1]
- [ ] CHK009 Does the spec require the run to exit successfully when at least one page processed? [Clarity, Spec §US3 §US3 AC#1]
- [ ] CHK010 Is the shape of a failed page record specified (empty `blocks`, empty `raw_ocr_lines`, still schema-valid)? [Completeness, Spec §US3 AC#1]
- [x] CHK011 Are the required per-page fields (`width`, `height`, `rotation_detected`) specified for the failure case where rasterization itself failed? [Resolved — Spec §FR-005a: PDF-metadata fallback at 300 DPI; `0/0/0` sentinel when metadata unreadable]
- [ ] CHK012 Is the distinction between rasterization failure and layout-extraction failure preserved in the warnings? [Completeness, Spec §US3 AC#4]
- [ ] CHK013 Is the case "layout failed but OCR succeeded" handled (empty `blocks`, populated `raw_ocr_lines`)? [Clarity, Spec §US3 AC#4]
- [x] CHK014 Is the case "OCR failed but layout succeeded" addressed? [Resolved — Spec §US3 AC#4: symmetric rule — successful step retained, failed step is empty array, warning records which step failed]

## Blank-Page Handling

- [ ] CHK015 Is a blank page defined as recoverable with empty `blocks` / `raw_ocr_lines`? [Clarity, Spec §US3 AC#2]
- [ ] CHK016 Is the rule "blankness alone does not downgrade `scan_quality` to poor" stated? [Clarity, Spec §US3 AC#2]
- [x] CHK017 Is the rule "no warning is emitted when blankness is expected content" specified, along with how "expected" is determined? [Resolved — Spec §US3 AC#2: blankness reframed — a successful run with zero content is silent regardless of "expectation"; only actual failures warn]

## Rotation Normalization

- [ ] CHK018 Is normalization of out-of-vocabulary rotation angles required (snap to nearest of `{0, 90, 180, 270}`)? [Completeness, Spec §FR-006]
- [ ] CHK019 Is a warning on rotation normalization required? [Completeness, Spec §FR-006 §FR-014]
- [x] CHK020 Is the warning's content (page number, original angle, snapped value) specified? [Resolved — Spec §FR-006: fixed format `"page {N}: rotation {orig}° normalized to {snapped}°"`, covered by FR-012]

## Warnings Contract

- [ ] CHK021 Is `warnings` required to be an empty list when no anomalies occurred? [Completeness, Spec §FR-014]
- [ ] CHK022 Does the spec require each warning to be a non-empty string (matching the schema's `minLength`)? [Consistency, Spec §FR-014]
- [ ] CHK023 Does the spec enumerate the categories of anomaly that must produce a warning (rotation normalization, unreadable page, layout failure, ingestion-source failure)? [Completeness, Spec §FR-014]
- [ ] CHK024 Are warnings required to identify the affected `page_number` when the anomaly is page-scoped? [Clarity, Spec §US3 AC#1 §SC-005]

## Ingestion-Source Failure

- [ ] CHK025 Is the behavior when PaddleOCR-VL fails entirely specified (`ingestion_sources.paddleocr_vl.status == "failure"`, artifact still validates, warning recorded)? [Completeness, Spec §US3 AC#5]
- [ ] CHK026 Does the spec state that ingestion-source failure does not, by itself, prevent artifact persistence (as long as schema validity holds)? [Clarity, Spec §US3 AC#5]
- [x] CHK027 Is the interaction between per-page failures and document-level ingestion-source status specified (e.g., one page fails vs. all pages fail)? [Resolved — Spec §FR-015a: `success` if ≥1 page produced output; `failure` only if all pages failed]
- [ ] CHK028 Is the handling for Falcon-source "failure" events (if ever wired on later) described, or explicitly deferred? [Assumption, Spec §FR-015 §FR-016]

## Schema-Validity Invariant Under Failure

- [ ] CHK029 Does the spec require that every persisted artifact validates against the schema, even under partial failure? [Completeness, Spec §FR-019]
- [ ] CHK030 Is the rule "an invocation that cannot produce a schema-valid artifact MUST fail loudly without persisting a partial artifact" explicit? [Clarity, Spec §FR-019]
- [ ] CHK031 Is the distinction between "fail loudly" (input rejection, exit non-zero) and "degrade gracefully" (partial pages, exit zero + warnings) unambiguous? [Consistency, Spec §FR-019 §US3]

## Overwrite / Re-run Semantics

- [ ] CHK032 Is the behavior when `preprocess_output.json` already exists in the folder specified (overwrite, no merge)? [Completeness, Spec §Edge Cases]
- [x] CHK033 Is the atomicity of the overwrite (no partial file visible on crash) specified? [Resolved — Spec §FR-019: temp-file + rename (`preprocess_output.json.tmp-{pid}` → `preprocess_output.json`)]
- [ ] CHK034 Is the behavior when `source.pdf` filename differs from default specified (`source_file` records actual filename; `document_id` from folder)? [Clarity, Spec §Edge Cases §FR-002 §FR-003]

## Edge Cases

- [ ] CHK035 Is the PDF-as-image-wrapper case (a single raster page wrapped in a PDF) addressed (still accepted as PDF, rasterized normally)? [Completeness, Spec §Edge Cases]
- [ ] CHK036 Is the embedded-text-layer case addressed (rasterize + OCR; do not shortcut through the text layer)? [Clarity, Spec §Edge Cases]
- [ ] CHK037 Is the oversized-document case addressed (many pages, very large dimensions — still one artifact)? [Clarity, Spec §Edge Cases]

## Measurable Acceptance

- [ ] CHK038 Is there a measurable success criterion for graceful degradation (seeded-failure case, exit 0 + warning in 100% of cases)? [Measurability, Spec §SC-005]
- [ ] CHK039 Is there a measurable success criterion for hard failure (malformed PDF, non-zero exit, no artifact in 100% of cases)? [Measurability, Spec §SC-006]
- [ ] CHK040 Is there a measurable success criterion for whole-corpus success rate (≥ 90%)? [Measurability, Spec §SC-004]

## Notes

- Check items off as completed: `[x]`
- `[Gap]` items here are frequent bug sources — prefer tightening the spec over relying on "obvious" behavior
- Any divergence between "exit zero + warning" and "exit non-zero + no artifact" must be explicit, not contextual
