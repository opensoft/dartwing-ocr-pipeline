# Implementation Plan: OCR Semantic Quality Gate

**Branch**: `022-ocr-semantic-quality-gate` | **Date**: 2026-05-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/022-ocr-semantic-quality-gate/spec.md`

> **Governing input**: Subordinate to OpenSpec change `openspec/changes/add-ocr-semantic-quality-gate/`. Where this plan and the OpenSpec capability spec disagree, the OpenSpec capability spec wins and this plan is corrected.

## Summary

Feature 022 adds a **deterministic, evaluator/harness-owned semantic table quality gate** for invoice body/table OCR. The gate is triggered by the presence of an optional new authored sidecar `semantic_table_truth.json` in a per-document folder; when present, the evaluator reads observed body OCR from the existing `preprocess_output.json`, normalizes it once per document into a single body-OCR search string (excluding the feature-020 page-1 header band), and evaluates four deterministic checks per sidecar row — `malformed-currency-shape`, `missing-required-content`, `row-text-coverage-gap`, `row-alignment-failure` — in a fixed order, with no short-circuiting. The verdict is aggregated by an any-fail rule into a closed status enum {`passed`, `failed`, `not_applicable`, `unevaluable`} and surfaced in three places: a `semantic_table_quality` object on `evaluation_document.json`, a new top-level `semantic_table_quality_metrics` namespace on `evaluation_run_summary.json`, and a new sibling `document_pass_fail.semantic_table_quality_passed` field (boolean | null) on every newly-written evaluation document.

The gate is **pure-Python, CPU-only, dependency-additive-free**: no model call, no network I/O, no Paddle import, no new pinned dependency. It uses stdlib (`unicodedata`, `re`, `json`, `decimal`, `pathlib`, `dataclasses`) plus existing `jsonschema>=4.22` and `pydantic>=2.7`. Sidecar truth and the four artifacts are governed by a contract-set minor bump **1.2.0 → 1.3.0** with a corresponding `AMENDMENTS.md` entry. Vendor-identity behavior (features 019/020/021 and `document_pass_fail.vendor_identity_passed`) is preserved byte-identical (SC-006). Runtime pipeline integration is explicitly out of scope (Clarifications Q3 / FR-033) — the verdict is evaluator/report-only.

The US2 independent test runs against a committed **synthetic CPU-only fixture** at `tests/stage1_semantic_quality/inv_001_hard/` containing a hand-authored `preprocess_output.json` + matching `semantic_table_truth.json`, with no `source.pdf` and no preprocessing run (Clarifications Q25). Calibration folders (e.g. `inv_024_hard_degraded_body`) are recognized via a canonical-pattern allowlist `^inv_\d{3}_(easy|medium|hard)$` (Clarifications Q23) — they are excluded from scored aggregation but, when carrying a sidecar, the gate still runs on them and emits per-document semantic status (Clarifications Q39).

## Technical Context

**Language/Version**: Python 3.12 (matches `.devcontainer/Dockerfile` base image and `pyproject.toml requires-python = ">=3.12"`; consistent with features 001–021)
**Primary Dependencies**: existing only — `jsonschema>=4.22,<5` (Draft 2020-12 validator), `pydantic>=2.7,<3` (typed result models, contract loader), Python stdlib (`unicodedata` for Q32 Unicode category lookup, `re` for Q10/Q32/Q35 regex, `json` for Q34 stable serialization, `decimal.Decimal` with `ROUND_HALF_EVEN` for Q34 6-dp ratio formatting, `pathlib`, `dataclasses`, `argparse`). **No new pinned dependency.** No Paddle, no `paddlepaddle-dcu`, no `httpx`, no model runtime, no network.
**Storage**: filesystem only. Reads `<per-doc-folder>/preprocess_output.json` and `<per-doc-folder>/semantic_table_truth.json`; writes `<per-doc-folder>/evaluation_document.json` (extended with semantic fields per Q12/Q29/Q30/Q31/Q37/Q43) and `<corpus-root>/evaluation_run_summary.json` (extended with the Q19/Q36 `semantic_table_quality_metrics` namespace). Reads optional pre-feature reports for backward-compat (FR-019 / Q43). Sidecar schemas under `contracts/stage1_vendor_identity/v1.3.0/`.
**Testing**: pytest. All gate-logic tests CPU-only and Paddle-free. One synthetic US2 fixture committed under `tests/stage1_semantic_quality/inv_001_hard/`. Vendor-identity-baseline non-regression (SC-006) runs against the existing 20-document corpus under `tests/stage1_vendor_identity/`.
**Target Platform**: Linux server / dev container (Python 3.12). The gate has no GPU dependency; it runs identically on any host that can run the existing evaluator.
**Project Type**: library + CLI extension. Extends the existing `dartwing-ocr` package (`src/dartwing_ocr/evaluator/` for the gate, `src/dartwing_ocr/validator/` for sidecar contract validation, `src/dartwing_ocr/contract_versions.py` for the version bump). No new top-level package, no new CLI entry point introduced (per Clarifications Q13 — sidecar presence is the opt-in).
**Performance Goals**: **N/A — explicitly out of scope per Clarifications Q38** and the Out of Scope section. The gate is a deterministic in-memory comparison over the body-OCR text of a single document; no latency budget, throughput target, or runtime envelope is defined.
**Constraints**: byte-identical reproducibility on identical inputs (FR-014, SC-007); no network I/O (FR-008, FR-029); no model call (FR-008); OCR confidence recorded only as document-aggregate supporting evidence (FR-013, Q30); no new configuration surface (Q38 — no CLI flags, env vars, config files, tunable thresholds).
**Scale/Scope**: 34 functional requirements (FR-001…FR-034 — FR-034 added 2026-05-23 per security-clarify Q-SEC-7/B for air-gapped operation), 10 success criteria, 5 user stories, 6 key entities, 44 clarifications (Q1–Q44 across two recorded sessions in `spec.md` — 2026-05-22 and 2026-05-23) + 7 security-clarify questions (Q-SEC-1…Q-SEC-7). Contract-set advancement 1.2.0 → 1.3.0 with one new schema (`semantic_table_truth.schema.json`) and three schema extensions (`evaluation_document.schema.json`, `evaluation_run_summary.schema.json`, `folder.schema.json`); seven other v1.2.0 schemas copied unchanged. ~12 new module files under `src/dartwing_ocr/evaluator/` and `src/dartwing_ocr/validator/`. ~20 new test files. One new synthetic fixture under `tests/stage1_semantic_quality/inv_001_hard/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md` v1.3.0 (Ratified 2026-04-12 / Last Amended 2026-05-01).

### Principle I — One Repo, Clear Runtime Boundaries

**PASS.** The gate is owned by the **test harness / evaluator** layer per the constitution's required boundary, not by the pipeline. The feature touches `src/dartwing_ocr/evaluator/` and `src/dartwing_ocr/validator/`; it does NOT touch `src/dartwing_ocr/preprocessing/`, `src/dartwing_ocr/extract/`, `src/dartwing_ocr/router/`, or `src/dartwing_ocr/assembler/`. FR-033 / Clarifications Q3 explicitly forbid runtime pipeline integration. Container/runtime boundaries are unaffected — the gate has no Paddle/GPU/network dependency and runs in the standard pipeline-dev container with no orchestration change.

### Principle II — Evidence-First, Schema-First Design

**PASS.** The gate is built around the existing `preprocess_output` artifact contract and the new authored `semantic_table_truth.json` sidecar contract. The four authoritative stage 1 artifacts (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`) are unchanged in shape; the only schema deltas land additively on the two evaluation-report artifacts (`evaluation_document.schema.json`, `evaluation_run_summary.schema.json`) and on `folder.schema.json` (sidecar listed as optional). The full delta is governed by a contract-set minor bump 1.2.0 → 1.3.0 with an `AMENDMENTS.md` entry per Clarifications Q14. `docs/stage1-vendor-identity/schemas.md` will be updated in the same body of work per Quality Gate #2.

### Principle III — Deterministic Control Over Model Output

**PASS.** This is the entire point of the feature. The gate is fully deterministic code: no model call (FR-008), no learned classifier (FR-029), no fuzzy similarity / edit-distance threshold (FR-009 / Q5). All check predicates are explicit regex + normalized exact comparison. OCR detector confidence is recorded **only** as document-aggregate supporting evidence (FR-013 / Q30) and explicitly cannot promote a failing row to a pass. The verdict aggregation rule is a pure any-fail (FR-016 / Q4) — no per-category severity tiers, no weighted score.

### Principle IV — Provenance and Review Safety

**PASS.** The feature does NOT change `vendor_identity_passed` semantics or any field's explicit-vs-inferred treatment (FR-024). The new `document_pass_fail.semantic_table_quality_passed` field is a **sibling**, not a replacement (Clarifications Q12). The whole-invoice/table-quality claim cannot be inferred from vendor-identity metrics (FR-025 / SC-005 — `null` for `not_applicable`). The 20-document vendor-identity baseline corpus is byte-identical before and after the feature lands (SC-006).

### Principle V — Benchmarkable and Reproducible Delivery

**PASS.** SC-007 requires byte-identical reproducibility from `preprocess_output.json` + `semantic_table_truth.json` alone, with no model call and no network access. FR-014 + Q34 pin sorted-keys + 6-dp round-half-to-even float serialization, making byte-identity testable. The US2 independent test runs against a committed synthetic fixture under `tests/stage1_semantic_quality/inv_001_hard/` (Clarifications Q25 — hand-authored `preprocess_output.json` + sidecar, no `source.pdf`, no preprocessing run). One-document execution and corpus-based evaluation paths are both supported via the existing evaluator surface — no new orchestration mode required.

### Stage 1 Scope Constraints

**PASS.** PDF input only ✓ (the gate consumes `preprocess_output.json`, which is produced from a PDF). Vendor identity focus only ✓ (the gate adds *evaluation* of body OCR quality, not line-item extraction — explicit FR-030). No line-item extraction ✓ (FR-030). No remote cloud execution ✓ (FR-008/FR-029 forbid network). No latency target as a release gate ✓ (Clarifications Q38 makes the absence explicit in Out of Scope). Minimal review output preserved ✓ (vendor-identity review path unchanged; semantic verdict is a separate report surface).

### Quality Gates

**PASS, with planned doc updates.** (1) Pipeline/harness boundary preserved (the gate lives in the harness layer). (2) Output contracts → `docs/stage1-vendor-identity/schemas.md` will be updated during implementation to document the v1.3.0 delta. (3) Runtime behavior unchanged — no `architecture.md` update required for the gate itself. (4) Concrete local execution path exists (single-document evaluator run on the synthetic fixture). (5) No new container/runtime changes. (6) Evaluation comparison against `expected.json` preserved unchanged (`expected.json` remains vendor-identity-only per FR-006). (7) **QG #7 alignment with `docs/stage1-vendor-identity/architecture.md`** — the target architecture in `architecture.md` enumerates Trijunction ingestion + triple-model ensemble extraction + deterministic consensus/routing at the **pipeline layer**; it does not enumerate a harness-side semantic-quality evaluation layer. Per QG #7 this is a **declared deviation with reason**: this feature adds a harness/evaluator-side capability that complements (does not replace) the pipeline-side consensus/routing layers, and the underlying evidence — the `inv_024_hard_degraded_body` calibration finding documented in `docs/stage1-vendor-identity/ocr-semantic-quality-observations.md` — predates `architecture.md`'s next revision. The alignment trail will be made explicit when T065 promotes `docs/stage1-vendor-identity/prd-ocr-semantic-quality-gate.md` from draft seed to active feature PRD; an `architecture.md` cross-reference to the new evaluator-side layer is a follow-up clean-up, not a blocker.

**Result:** **No constitution violations. No items in the Complexity Tracking table.**

## Project Structure

### Documentation (this feature)

```text
specs/022-ocr-semantic-quality-gate/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # Feature spec (44 clarifications integrated)
├── research.md          # Phase 0 output — R-022.1 … R-022.15
├── data-model.md        # Phase 1 output — entities, regex constants, algorithm specs
├── quickstart.md        # Phase 1 output — operator-facing walkthroughs
├── contracts/           # Phase 1 output — narrative contracts (not JSON Schemas)
│   ├── module-invariants.md        # MI-1 … MI-N gate code invariants
│   ├── schema-amendments.md        # v1.2.0 → v1.3.0 schema delta
│   ├── validator-cli-contract.md   # validator subcommand surface
│   └── evaluator-output-contract.md # newly-written report shape
├── checklists/          # release-gate requirements-quality checklists (11 files; contract / corpus-governance / data-model / determinism / failure-handling / observability / requirements / scope / security / semantic-gate-policy / testing-strategy)
├── clarify-questions.md # Rounds 2-4 question record
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/dartwing_ocr/
├── evaluator/
│   ├── semantic_quality.py                # NEW — gate entry point. Public API: SEMANTIC_QUALITY_GATE_VERSION = "v1", run_semantic_quality_gate(preprocess_output_path: Path, sidecar_path: Path | None, folder_basename: str) -> SemanticQualityResult. Orchestrates: load preprocess_output (Q31 cause classification on failure), load sidecar (None → status="not_applicable"), build body-OCR search string (Q22/Q33), normalize once (Q5/Q32), anchor rows (Q7/Q24), evaluate four checks in Q17 order (no short-circuit), aggregate verdict (Q4), build report (Q29/Q30/Q31/Q37). CPU-safe, stdlib + re + unicodedata only.
│   ├── semantic_quality_normalize.py      # NEW — FR-009 normalization pipeline. Pure function `normalize(text: str) -> str` applying: unicodedata.normalize("NFKC", text) → str.casefold() → whitespace-collapse (every Unicode whitespace → single ASCII space, then merge consecutive spaces) → strip every code point whose unicodedata.category begins with "P" (Q32: Pc/Pd/Pe/Pf/Pi/Po/Ps). Deterministic, closed under the four steps.
│   ├── semantic_quality_body_ocr.py       # NEW — Q22 body-OCR selection. Reads `preprocess_output.json` lines from all pages, filters out the page-1 header band by reusing feature-020's Y_THRESHOLD_FRACTION = 0.25 (imported as `EVIDENCE_GATE_Y_THRESHOLD_FRACTION` from `preprocessing.evidence_gate`). Returns `BodyOcrEvidence` with the ordered list of body-OCR lines (in `preprocess_output.json` serialization order — Q24), each with raw text + per-line detector confidence. `header_band_excluded: bool` is True iff at least one line was filtered out. Builds the single normalized body-OCR search string via `semantic_quality_normalize.normalize` (Q33).
│   ├── semantic_quality_anchor.py         # NEW — FR-012 row-to-OCR anchoring. For each sidecar row, compute the candidate anchor spans by finding contiguous spans of body-OCR tokens whose normalized text contains the maximum number of the row's `required_row_text_tokens` (Q7 "best" = most-token match, NOT fuzzy edit distance). Tie-break: earliest preprocess_output.json serialization-order position (Q24), then sidecar declaration order. Returns RowAnchor with span coordinates (start_line_index, end_line_index) for downstream checks.
│   ├── semantic_quality_currency.py       # NEW — FR-010 currency-shape check. Q35 per-field digit-sequence matching: locate_currency_token(span_raw_tokens, expected_digit_seq) -> str | None scans span tokens in Q24 order, returning the first not-yet-matched raw token whose digit-only representation equals `expected_digit_seq`. Q10 canonical money regex `^\$?\d{1,3}(,\d{3})*\.\d{2}$` compiled at module load. Q16: matched token is the RAW token before FR-009 punctuation stripping; the regex is anchored. Missing candidate → defer to missing-required-content; matched-but-fails-regex → malformed-currency-shape.
│   ├── semantic_quality_checks.py         # NEW — the four check predicates (Q18 predicate-based attribution, all may coexist on one row): evaluate_missing_required_content (FR-009 normalized exact containment in body-OCR search string), evaluate_currency_shape (FR-010 / Q35 / Q16), evaluate_row_text_coverage (FR-011 / Q6 binary token-presence), evaluate_row_alignment (FR-012 / Q7 — span exists but required values not in order or split). Each returns a list of FailedCheck or empty. Q17 deterministic ordering: malformed-currency-shape, missing-required-content, row-text-coverage-gap, row-alignment-failure; sidecar row declaration order is the outer loop. No short-circuit.
│   ├── semantic_quality_report.py         # NEW — builds the `semantic_table_quality` object (Q29 two-view + Q30 supporting_evidence + Q31 unevaluable cause + Q37 supporting_evidence closed shape). `failed_checks` is the flat ordered array (source of truth, Q29). `row_reasons` is derived per-row aggregation keyed by row_id with the row's failed-category set + a short human-readable reason (required when status==failed). `supporting_evidence` is the closed shape `{body_confidence_mean, body_confidence_min, body_line_count, body_token_count, header_band_excluded}` (Q37); means/mins computed across body-OCR lines only. `cause` + optional `cause_detail` populated when status==unevaluable (Q31 closed enum).
│   ├── semantic_quality_metrics.py        # NEW — FR-018 / Q36 / Q19 / Q39 run-summary aggregation. Builds the top-level `semantic_table_quality_metrics` namespace with `semantic_applicable_document_count`, `semantic_not_applicable_document_count`, `semantic_evaluable_document_count`, `semantic_passed_document_count`, `semantic_failed_document_count`, `semantic_unevaluable_document_count`, `semantic_table_quality_pass_rate` (nullable when evaluable==0; 6-dp round-half-to-even per Q34), and `semantic_failed_check_counts` (object keyed by the four kebab-case categories). Plus per-document semantic status entries `{document_id, semantic_table_quality_status, semantic_table_quality_passed}` in deterministic run-document order. Calibration folders (Q23 non-matching names) appear in per-document entries but are EXCLUDED from the aggregate counters and pass rate (Q39).
│   ├── stable_json.py                     # NEW — Q34 byte-identical serialization. `dump_stable(obj, path)`: json.dumps with sort_keys=True, ensure_ascii=False (UTF-8), indent=2, plus a custom Decimal-based float encoder that emits derived ratios/confidence values as fixed-precision JSON numbers (6 decimal places, ROUND_HALF_EVEN). Writes LF line endings + trailing newline; no trailing whitespace. Used by the existing `evaluator/document.py` (per-document writer) and `evaluator/report.py` (run-summary writer) for newly-written semantic outputs.
│   ├── document.py                        # CHANGED (small) — extend the existing evaluator's per-doc writer (this file already exists; it is NOT a new module): always include `document_pass_fail.semantic_table_quality_passed` (Q20 — true only when status==passed, false for failed/unevaluable, null for not_applicable); include the `semantic_table_quality` object when sidecar present OR status==unevaluable; omit `semantic_table_quality` when sidecar absent (Q12/Q20). Routes serialization through `stable_json.dump_stable`.
│   ├── report.py                          # CHANGED (small) — extend the existing evaluator's run-summary writer (this file already exists; it is NOT a new module): emit `semantic_table_quality_metrics` and the `semantic_document_statuses` array as top-level sibling keys (Q36); always include per-document semantic status entries in `semantic_document_statuses`; sort per-document entries by deterministic run-document order; emit via `stable_json.dump_stable`. Existing vendor-identity / feature-020 fields untouched (FR-020, FR-022).
│   ├── exceptions.py                      # NEW (small) — `SemanticGateInvariantError` raised on gate-time invariant violation per Q42 (e.g. anchor function returns inconsistent span, internal aggregation produces unknown status). The hard-error path bypasses `unevaluable` recording.
│   └── (existing evaluator modules untouched: scoring.py, comparison.py, field_results.py, etc.)
├── validator/
│   ├── semantic_table_truth.py            # NEW — sidecar contract validator. Loads `contracts/stage1_vendor_identity/v1.3.0/semantic_table_truth.schema.json` via jsonschema. Validates: top-level shape `{document_id, rows[], schema_version?}` (Q27); `document_id` matches folder basename (FR-003); rows non-empty array, every row conforms to row contract (FR-004); `row_id` non-empty string + unique across sidecar (Q11); `required_row_text_tokens` non-empty array of non-empty strings (Q28); optional cell fields, `unit_price`/`amount` match decimal regex `^\d+\.\d{2}$` (Q9). Mismatch error names declared `document_id` + folder basename (Q41). Row-violation error names `row_id` (or row-array index) + failed field + one-line reason (Q41).
│   ├── corpus_pattern.py                  # NEW — Q23 canonical-pattern allowlist. Module-level constant `CANONICAL_FOLDER_PATTERN = re.compile(r"^inv_\d{3}_(easy|medium|hard)$")`; helper `is_scored_corpus_folder(folder_basename: str) -> bool`. Shared by `validate corpus` (Q23 + SC-009) and `semantic_quality_metrics.py` (Q39 calibration exclusion).
│   ├── folder.py                          # CHANGED (small) — folder-contract v1.3.0: `semantic_table_truth.json` listed as optional alongside mandatory `source.pdf` + `expected.json`. Validation gates `semantic_table_truth.json` only when present.
│   ├── cli.py                             # CHANGED (small) — add `validate semantic-truth <folder>` subcommand (sidecar-only validation); extend `validate folder` to accept optional sidecar; `validate corpus` excludes non-matching-pattern folders from scored aggregation but validates their per-doc artifacts. No new top-level CLI entry point (Q13 — sidecar presence is the gate's opt-in, not a CLI flag).
│   └── (existing artifact validator extended to load v1.3.0 schemas when contract_set_version is "1.3.0"; v1.2.0 reads remain valid for FR-019 backward-compat)
├── contract_versions.py                   # CHANGED — bump `CURRENT_CONTRACT_SET_VERSION` 1.2.0 → 1.3.0. Keep v1.2.0 loader available for backward-compat reads of pre-feature `evaluation_document.json` / `evaluation_run_summary.json` per FR-019 / Q43.
└── (everything else unchanged)

contracts/stage1_vendor_identity/
├── AMENDMENTS.md                          # CHANGED — append v1.3.0 amendment entry (date 2026-05-23, summary: optional `semantic_table_truth.json` sidecar + additive `semantic_table_quality` / `document_pass_fail.semantic_table_quality_passed` on `evaluation_document.json` + additive `semantic_table_quality_metrics` namespace on `evaluation_run_summary.json` + `folder.json` accepts optional sidecar, justification: Clarifications Q14).
└── v1.3.0/                                 # NEW directory — full v1.3.0 contract set
    ├── contract_set.json                  # NEW — `contract_set_version = "1.3.0"`, lists all schemas (new + carried).
    ├── semantic_table_truth.schema.json   # NEW — Draft 2020-12 JSON Schema for the sidecar. Shape: `{document_id: string, rows: array of row, schema_version?: string}`. Row: `{row_id: non-empty string, required_row_text_tokens: non-empty array of non-empty string, quantity?: string, description?: string, unit_price?: pattern ^\d+\.\d{2}$, amount?: pattern ^\d+\.\d{2}$}`. additionalProperties: false on the row and on the sidecar. `row_id` uniqueness enforced at validator-layer (jsonschema does not natively support array-uniqueness-by-key).
    ├── evaluation_document.schema.json    # CHANGED — adds optional `semantic_table_quality` object (closed shape per Q29/Q30/Q31/Q37) and `document_pass_fail.semantic_table_quality_passed: boolean | null` (Q20). Existing vendor-identity properties unchanged.
    ├── evaluation_run_summary.schema.json # CHANGED — adds top-level `semantic_table_quality_metrics` object (closed shape per Q19/Q36) and per-document semantic status entries.
    ├── folder.schema.json                 # CHANGED — `semantic_table_truth.json` listed as optional in the folder contract.
    ├── preprocess_output.schema.json      # COPIED unchanged from v1.2.0.
    ├── edge_extraction_output.schema.json # COPIED unchanged.
    ├── routing_decision.schema.json       # COPIED unchanged.
    ├── final_structured_payload.schema.json # COPIED unchanged.
    ├── evidence_packet.schema.json        # COPIED unchanged.
    ├── expected.schema.json               # COPIED unchanged (FR-006 — vendor-identity truth file shape preserved).
    └── README.md                          # CHANGED — note the v1.3.0 delta + AMENDMENTS.md link.

tests/
├── contract_tests/
│   ├── test_semantic_table_truth_schema.py     # NEW — accept/reject sidecar shapes (good shape, missing document_id, mismatched document_id, empty rows, row missing row_id, row with non-unique row_id, row with empty required_row_text_tokens, row with malformed unit_price/amount).
│   ├── test_evaluation_document_v1_3.py        # NEW — semantic_table_quality optional + closed-shape validation; `document_pass_fail.semantic_table_quality_passed` boolean | null.
│   ├── test_evaluation_run_summary_v1_3.py     # NEW — semantic_table_quality_metrics top-level namespace + per-document status entries validation; pass_rate nullable when evaluable==0.
│   ├── test_folder_contract_v1_3.py            # NEW — optional sidecar accepted; mandatory artifacts unchanged.
│   └── test_backward_compat_v1_2.py            # NEW — pre-feature evaluation_document.json / evaluation_run_summary.json still validate against v1.3.0 reader (FR-019 / SC-008); absent `document_pass_fail.semantic_table_quality_passed` interpreted as null on read (Q43).
├── unit/evaluator/
│   ├── test_semantic_quality_normalize.py     # NEW — FR-009/Q5/Q32 unit tests: NFKC examples (full-width digits, accented characters), casefold (Turkish I, German ß), whitespace collapse (Unicode whitespace varieties), Pc/Pd/Pe/Pf/Pi/Po/Ps stripping; idempotence of normalize(normalize(x)) == normalize(x).
│   ├── test_semantic_quality_body_ocr.py      # NEW — Q22 page-1 header-band exclusion: fixture with tokens above and below Y_THRESHOLD_FRACTION boundary; multi-page document — page 2..N OCR fully included; `header_band_excluded` flag computed correctly.
│   ├── test_semantic_quality_anchor.py        # NEW — FR-012 / Q7 / Q24 anchoring: row anchored by most-token match; tie-break by earliest serialization-order index then sidecar declaration order; ambiguous tie-break deterministic.
│   ├── test_semantic_quality_currency.py      # NEW — FR-010 / Q10 / Q35 / Q16: digit-sequence matching across `unit_price`/`amount`; quantity tokens NOT misclassified; canonical money regex passes `$21.00` / `21.00` / `$1,234.00`; flags `$21:00` / `$22:` / `21.0` / `$1234,00`; missing-candidate → missing-required-content not malformed-currency-shape.
│   ├── test_semantic_quality_checks.py        # NEW — FR-009 / FR-011 / FR-012 / Q17 / Q18 predicate-based attribution; no short-circuit; deterministic check ordering across the four categories.
│   ├── test_semantic_quality_aggregate.py     # NEW — FR-016 / Q4 / Q26 any-fail aggregation; closed status enum literal values; `unevaluable` non-passing.
│   ├── test_semantic_quality_report.py        # NEW — FR-017 / Q29 / Q30 / Q31 / Q37 report-object shape; `failed_checks` source of truth, `row_reasons` derived; `supporting_evidence` closed shape; `cause` closed enum for unevaluable.
│   ├── test_semantic_quality_metrics.py       # NEW — FR-018 / Q36 / Q19 / Q39 aggregation; top-level sibling location; calibration folder exclusion from aggregate counts but inclusion in per-document entries; pass_rate nullable.
│   ├── test_stable_json.py                    # NEW — FR-014 / Q34: sort_keys=True at every nesting level; UTF-8 + LF + trailing newline; 6-dp round-half-to-even floats emitted as JSON numbers (not strings); integer counts as JSON numbers.
│   ├── test_semantic_quality_determinism.py   # NEW — SC-007 byte-identical re-run on the synthetic fixture (run gate twice, hash outputs).
│   └── test_semantic_quality_unevaluable.py   # NEW — Q31 closed cause vocabulary: preprocess_output_missing (file absent), preprocess_output_invalid_json (JSON parse error), preprocess_output_schema_invalid (jsonschema failure), body_ocr_unreadable (parses but no pages/lines).
├── unit/validator/
│   ├── test_semantic_table_truth_validator.py # NEW — FR-003 mismatch error names both document_id and folder basename (Q41); FR-004 row-violation error names row_id (or array index) + failed field + one-line reason (Q41); row_id uniqueness enforced; schema_version optional acceptance.
│   └── test_corpus_pattern.py                 # NEW — Q23 allowlist regex: `inv_001_easy`/`inv_001_medium`/`inv_001_hard` match; `inv_024_hard_degraded_body`/`inv_001`/`inv_001_extra` reject; SC-009 calibration exclusion verified end-to-end.
├── integration/
│   ├── test_us1_sidecar_validation.py         # NEW — US1 acceptance scenarios AS1-AS5 on synthetic fixtures (good sidecar, mismatched document_id, malformed row, absent sidecar, expected.json unchanged shape).
│   ├── test_us2_independent_test.py           # NEW — US2 on the synthetic fixture: status==failed, ≥1 concrete failed check, re-run byte-identical (SC-001 / SC-002 / SC-007).
│   ├── test_us3_evaluator_reports.py          # NEW — US3 AS1-AS4: per-doc `semantic_table_quality` shape; run-summary aggregation across mixed corpus (with-sidecar + without-sidecar); pre-feature report still loads (FR-019 / SC-008); vendor-identity metrics unchanged (FR-020).
│   ├── test_us4_non_regression.py             # NEW — US4 AS1-AS6: 20-document vendor-identity baseline byte-identical before/after (SC-006); `vendor_identity_passed` unchanged; failing-semantic + passing-vendor reports `semantic_table_quality_passed: false`; no-sidecar reports `null`; features 019/021 untouched.
│   └── test_us5_calibration_handling.py       # NEW — US5 + Q39: calibration folder `inv_024_hard_degraded_body` with sidecar → gate runs, per-doc status emitted, EXCLUDED from `semantic_table_quality_metrics` counts; SC-009 zero noncanonical folders in scored output.
└── stage1_semantic_quality/                   # NEW corpus root (Q15)
    └── inv_001_hard/                          # NEW synthetic fixture (Q25 / Q40)
        ├── preprocess_output.json             # NEW — hand-authored, schema-valid against v1.3.0 preprocess_output.schema.json. Reproduces the inv_024_hard_degraded_body calibration evidence: 8 body rows with high mean detector confidence (≈ 0.97) but materially wrong content (colon-for-decimal currency, missing quantity, mutated descriptions). NO source.pdf.
        └── semantic_table_truth.json          # NEW — matching authored sidecar with 8 rows. document_id = "inv_001_hard"; rows include required_row_text_tokens for description coverage; unit_price + amount declared per row as normalized decimal strings.

docs/
└── stage1-vendor-identity/
    ├── schemas.md                             # CHANGED — document v1.3.0 delta: new `semantic_table_truth.json` sidecar; additive `semantic_table_quality` / `document_pass_fail.semantic_table_quality_passed` / `semantic_table_quality_metrics` fields.
    └── prd-ocr-semantic-quality-gate.md       # CHANGED — promote draft seed to active feature PRD; record landed decisions Q1-Q44.
```

**Structure Decision**: Single-project Python library + CLI (extends existing `dartwing-ocr` package). The gate code lives under the harness-side `src/dartwing_ocr/evaluator/` directory (the constitutional "test harness" boundary); the sidecar contract is enforced under `src/dartwing_ocr/validator/`. No new top-level package, no new CLI entry point, no new container, no new runtime dependency.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

**No violations.** Table omitted intentionally.

## Phase 0 — Outline & Research

See `research.md` in this directory. The Phase 0 record consolidates 15 plan-level research decisions (R-022.1 … R-022.15) — module placement, Unicode-category detection in stdlib, stable JSON serialization mechanics, header-band-helper reuse from feature 020, contract-set bump procedure, synthetic fixture composition strategy, validator CLI surface extension, backward-compat read path, failed-check record shape, supporting-evidence computation, `unevaluable` cause detection, hard-error vs unevaluable boundary mechanics, and calibration-folder exclusion implementation. Every spec-level decision is already pinned by Clarifications Q1–Q44 in `spec.md`; research.md does NOT re-litigate any of them.

## Phase 1 — Design & Contracts

See `data-model.md`, `contracts/module-invariants.md`, `contracts/schema-amendments.md`, `contracts/validator-cli-contract.md`, `contracts/evaluator-output-contract.md`, and `quickstart.md` in this directory.

`data-model.md` enumerates the 8 entities the gate code manipulates (Semantic Table Truth Sidecar, Semantic Table Row Truth, Body OCR Evidence, Failed Check, Row Reason, Supporting Evidence, Semantic Quality Verdict, Semantic Quality Metrics + per-document status entries) with field tables, validation rules, and value-domain pins.

The `contracts/` narrative documents pin the cross-cutting invariants:
- **module-invariants.md** lists MI-1 … MI-N gate code invariants (Q17 deterministic check order, Q4 any-fail aggregation, Q34 stable JSON serialization, no Paddle import at module load, no network call ever, OCR confidence never per-row).
- **schema-amendments.md** records the v1.2.0 → v1.3.0 schema delta verbatim and the matching `AMENDMENTS.md` entry text.
- **validator-cli-contract.md** records the `python -m dartwing_ocr.validator` subcommand surface for sidecar and corpus validation.
- **evaluator-output-contract.md** records the exact shape of every newly-written semantic-quality field on both `evaluation_document.json` and `evaluation_run_summary.json`.

`quickstart.md` records seven operator-facing paths (author + validate a sidecar, run the gate on the synthetic US2 fixture, run the evaluator over a mixed corpus, re-read a pre-feature report, run the gate on a calibration folder, trigger each `unevaluable` cause, demonstrate SC-006 byte-identical vendor-identity baseline).

### Post-design Constitution re-check

After completing the Phase 1 artifacts, the constitution check re-evaluates as **PASS unchanged**:

- The data model and contracts confirm the harness-side boundary (Principle I) — no entity, no schema, no module path touches `src/dartwing_ocr/preprocessing/`, `src/dartwing_ocr/extract/`, `src/dartwing_ocr/router/`, or `src/dartwing_ocr/assembler/`.
- The schema delta is fully additive and contract-set-versioned (Principle II), with the planned `AMENDMENTS.md` entry recorded in `contracts/schema-amendments.md`.
- Every check predicate in `data-model.md` is explicit code, no model (Principle III).
- `document_pass_fail.semantic_table_quality_passed` is a sibling of `vendor_identity_passed` with byte-identical preservation of vendor-identity values (Principle IV); SC-006 is the gate.
- `quickstart.md` includes the byte-identical reproducibility walkthrough (Principle V); the synthetic fixture is CPU-only and committed.

No new violations surfaced by the Phase 1 design. The plan is ready for `/speckit.tasks`.
