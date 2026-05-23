# Alignment-Verification Checklist: OCR Semantic Quality Gate

**Purpose**: Unit-tests-for-English that re-verify requirement-quality alignment ACROSS all feature artifacts after the 2026-05-23 `/speckit.analyze` remediation cycle (findings F1–F12). Each item asks whether a specific requirement is now consistently, completely, and unambiguously written across `spec.md`, `plan.md`, `data-model.md`, `research.md`, `contracts/*.md`, and `tasks.md`. This is **not** an implementation test — it does not execute code, run schemas, or verify behavior. It verifies the **prose contract** holds together as one coherent story.

**Created**: 2026-05-23
**Feature**: [spec.md](../spec.md)
**Scope mode**: maximum-coverage (per CLAUDE.md `/speckit-checklist` no-arg-equivalent rule)
**Depth**: formal release-gate rigor; no item-count cap
**Audience**: reviewer (PR), pre-implementation
**Maps to**: every `/speckit.analyze` finding F1–F12, every FR-001…FR-033, every SC-001…SC-010, every Clarification Q1–Q44, every Module Invariant MI-1…MI-25, all five Constitution Principles + 7 Quality Gates

---

## Cross-Artifact Consistency — CRITICAL Findings (F1 resolution)

- [ ] CHK001 Is `row_reasons` consistently declared as a JSON **object keyed by `row_id`** (NOT an array) in every artifact that references it — spec.md FR-017, spec.md Key Entities §"Semantic Quality Report Fields", data-model.md §5, data-model.md §7, contracts/evaluator-output-contract.md §`semantic_table_quality`, contracts/schema-amendments.md `evaluation_document.schema.json` definition, and tasks.md T029/T039/T043/T048? [Consistency, Post-Fix F1]
- [ ] CHK002 Is the per-row-record shape `{categories, reason}` (NOT `{row_id, failed_categories, reason_text}`) the pinned vocabulary in every artifact — spec.md FR-017, data-model.md §5, contracts/evaluator-output-contract.md, contracts/schema-amendments.md, and tasks.md T029/T039/T043/T048? [Consistency, Post-Fix F2]
- [ ] CHK003 Does at least one artifact explicitly state that the `row_id` is the PARENT DICT KEY (and therefore must NOT appear redundantly as a field inside the value record)? [Clarity, Post-Fix F1]
- [ ] CHK004 Is the `categories` field constraint (non-empty array of unique kebab-case enum values in the fixed Q17 order: `malformed-currency-shape` → `missing-required-content` → `row-text-coverage-gap` → `row-alignment-failure`) defined identically in spec.md FR-017, data-model.md §5, and tasks.md T029/T039? [Consistency, Post-Fix F1+F2]
- [ ] CHK005 Are the `reason` field semantics (short one-line human-readable summary string) defined identically in spec.md FR-017, data-model.md §5, contracts/evaluator-output-contract.md Example B, and tasks.md T029/T039? [Consistency, Post-Fix F2]
- [ ] CHK006 Does any artifact still describe `row_reasons` as an array or use the legacy field names `failed_categories` / `reason_text`? [Gap-test for incomplete F1/F2 fix; expected answer: NO]

## Cross-Artifact Consistency — HIGH Findings (F2, F3, F4 resolution)

- [ ] CHK007 Is `body_confidence_min` typed as JSON `number` (never `null`, never nullable) in every artifact — data-model.md §6, research.md R-022.12, contracts/evaluator-output-contract.md Example C, contracts/schema-amendments.md `semantic_table_quality.properties.supporting_evidence.properties.body_confidence_min`, and tasks.md T029/T039/T043/T048? [Consistency, Post-Fix F3]
- [ ] CHK008 Is the empty-band rule "when `body_line_count == 0`, both `body_confidence_mean` and `body_confidence_min` emit as `0.0`" stated symmetrically in data-model.md §6, research.md R-022.12, and the relevant tasks (T029/T039)? [Consistency, Post-Fix F3]
- [ ] CHK009 Has every reference to `evaluation_document_writer.py` been replaced with `document.py` in plan.md Project Structure, data-model.md §7 Module (writer), and any task description? [Completeness, Post-Fix F4]
- [ ] CHK010 Has every reference to `run_summary_serializer.py` been replaced with `report.py` in plan.md Project Structure and any task description? [Completeness, Post-Fix F4]
- [ ] CHK011 Do plan.md and data-model.md explicitly label the renamed files as "EXISTING modules, NOT new" so an implementer does not create duplicates alongside them? [Clarity, Post-Fix F4]

## Cross-Artifact Consistency — MEDIUM Findings (F5, F6, F7 resolution)

- [ ] CHK012 Is the `failed_checks` always-present rule (present when `status ∈ {passed, failed, unevaluable}`; non-empty when failed; `[]` for passed/unevaluable; omitted only for not_applicable) defined identically in data-model.md §7, tasks.md T039, and tasks.md T043/T048? [Consistency, Post-Fix F5]
- [ ] CHK013 Does the contracts/evaluator-output-contract.md Example C (status==unevaluable) showing `"failed_checks": []` align with the post-fix rule that `failed_checks` is always an empty array (not omitted) for unevaluable? [Consistency, Post-Fix F5]
- [ ] CHK014 Is the top-level sibling key name **`semantic_document_statuses`** pinned in every artifact that documents the per-document status entries — spec.md FR-018, data-model.md §8, contracts/evaluator-output-contract.md, contracts/schema-amendments.md, and tasks.md T044/T047/T049/T052? [Consistency, Post-Fix F6]
- [ ] CHK015 Does any artifact still describe per-document status entries as "alongside" or "as a companion field" without naming the key? [Gap-test for incomplete F6/F7 fix; expected answer: NO]
- [ ] CHK016 Is it explicit in spec.md FR-018, data-model.md §8, and tasks.md T049 that `semantic_document_statuses` is **parallel to** `semantic_table_quality_metrics` (NOT nested inside it)? [Clarity, Post-Fix F6]
- [ ] CHK017 Is the per-entry shape `{document_id, semantic_table_quality_status, semantic_table_quality_passed}` pinned identically in spec.md FR-018, data-model.md §8, contracts/evaluator-output-contract.md, and tasks.md T044/T049? [Consistency, Post-Fix F6]

## Cross-Artifact Consistency — LOW Findings (F8, F9, F10, F11, F12 resolution)

- [ ] CHK018 Is the FR-030 (no line-item extraction) negative assertion explicitly named in tasks.md T056 — grep for `line_item` / `line-item` / `extract_lines`, schema absence of `line_items`, and `final_structured_payload.schema.json` byte-identity v1.3.0 ≡ v1.2.0? [Completeness, Post-Fix F8]
- [ ] CHK019 Does tasks.md T014 explicitly assert SHA-256 byte-identity for `expected.schema.json` between v1.2.0 and v1.3.0 (FR-006 / MI-23 guard)? [Completeness, Post-Fix F9]
- [ ] CHK020 Does plan.md report 11 checklist files (matching reality) with the file names enumerated, instead of the prior "12 files, 586 items" wording? [Clarity, Post-Fix F10]
- [ ] CHK021 Is the clarifications-session count consistent — "two recorded sessions in `spec.md` — 2026-05-22 and 2026-05-23" — across plan.md and any artifact that previously said "four rounds"? [Consistency, Post-Fix F11]
- [ ] CHK022 Does plan.md Constitution Check QG #7 contain an EXPLICIT declared deviation with reason for the architecture.md gap, instead of the prior one-liner? [Completeness, Post-Fix F12]
- [ ] CHK023 Does the QG #7 declared deviation cite (a) which architecture.md layers exist, (b) why the harness-side semantic-quality layer is absent from architecture.md, (c) the alignment trail (the OCR semantic-quality observations doc), and (d) the planned follow-up (T065 PRD promotion + architecture.md cross-reference as future clean-up)? [Clarity, Post-Fix F12]

---

## Schema-Layer Consistency (v1.3.0 contract set)

- [ ] CHK024 Is the contract-set version bump `1.2.0 → 1.3.0` cited identically across spec.md FR-031, plan.md Summary, plan.md Project Structure §`contracts/`, research.md R-022.5, contracts/schema-amendments.md, contracts/AMENDMENTS.md (planned via T063), and tasks.md T004/T005/T006/T010? [Consistency]
- [ ] CHK025 Is the list of **changed** schemas in the v1.3.0 bump (`evaluation_document.schema.json`, `evaluation_run_summary.schema.json`, `folder.schema.json`, plus the new `semantic_table_truth.schema.json`) identical across spec.md FR-031, plan.md, contracts/schema-amendments.md, and tasks.md T004/T005/T019/T048/T049? [Consistency]
- [ ] CHK026 Are the seven **carried-unchanged** schemas (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`, `evidence_packet`, `expected`, `README.md`) enumerated identically across plan.md, research.md R-022.5, contracts/schema-amendments.md, and tasks.md T004/T014? [Completeness, Consistency]
- [ ] CHK027 Is the AMENDMENTS.md entry format prescribed in research.md R-022.10 consistent with the entry text drafted in contracts/schema-amendments.md and the task description in tasks.md T063? [Consistency]
- [ ] CHK028 Does the sidecar JSON Schema (`semantic_table_truth.schema.json`) match the row-truth contract described in spec.md FR-002 across (a) top-level `{document_id, rows, schema_version?}`, (b) row required-fields `{row_id, required_row_text_tokens}`, (c) optional cells `{quantity, description, unit_price, amount}`, (d) `unit_price`/`amount` pattern `^\d+\.\d{2}$`, (e) `additionalProperties: false` at every level, (f) row_id uniqueness enforced at validator layer (NOT schema)? [Consistency, Completeness]
- [ ] CHK029 Is the closed `cause` enum for `unevaluable` status `{preprocess_output_missing, preprocess_output_invalid_json, preprocess_output_schema_invalid, body_ocr_unreadable}` defined identically in spec.md Q31, data-model.md §7, contracts/evaluator-output-contract.md, contracts/schema-amendments.md, research.md R-022.13, MI-13, and tasks.md T030/T039/T040/T043/T048? [Consistency]
- [ ] CHK030 Is the closed verdict status enum `{passed, failed, not_applicable, unevaluable}` (verbatim snake_case strings) used identically in spec.md Q26/FR-016, data-model.md §7, contracts/evaluator-output-contract.md, contracts/schema-amendments.md, MI-11, and tasks.md T028/T040/T043/T046/T049? [Consistency]
- [ ] CHK031 Is the closed failed-check category set `{malformed-currency-shape, missing-required-content, row-text-coverage-gap, row-alignment-failure}` (verbatim kebab-case strings) used identically in spec.md Q17/Q18/FR-015, data-model.md §4, contracts/evaluator-output-contract.md, contracts/schema-amendments.md, MI-12, and tasks.md T027/T038/T043/T046? [Consistency]

---

## FR ↔ Task ↔ Test Coverage (SC-010 / FR-032)

- [ ] CHK032 Is every functional requirement FR-001 through FR-033 mentioned by at least one implementation task in tasks.md (per `/speckit.analyze` Coverage Summary)? [Coverage, FR-032]
- [ ] CHK033 Is every functional requirement FR-001 through FR-033 mentioned by at least one test task in tasks.md? [Coverage, FR-032]
- [ ] CHK034 Is every Success Criterion SC-001 through SC-010 mapped to at least one task in tasks.md? [Coverage]
- [ ] CHK035 Is FR-006 (`expected.json` shape immutability) now covered by an EXPLICIT byte-identity test (post-F9), not just implicit via T018 AS5? [Coverage, Post-Fix F9]
- [ ] CHK036 Is FR-030 (no line-item extraction) now covered by an EXPLICIT negative assertion (post-F8) instead of implicit absence? [Coverage, Post-Fix F8]
- [ ] CHK037 Is the FR↔task↔test coverage matrix output (tasks.md T070 → `coverage-fr-task-test.md`) defined as a release-gate artifact and not just a documentation nicety? [Acceptance Criteria, SC-010]

## Clarifications Q1–Q44 Propagation

- [ ] CHK038 Is every Clarification Q1–Q44 from spec.md §Clarifications referenced by at least one downstream artifact (data-model.md, plan.md, contracts/*.md, tasks.md, or research.md) that pins its decision into prose, schema, or code shape? [Coverage]
- [ ] CHK039 Has the post-fix `row_reasons` shape decision (object-keyed-by-row_id with `{categories, reason}`) been added as an explicit cross-reference to Q29, so a future reader following Q29 lands on the pinned shape without ambiguity? [Clarity, Post-Fix F1+F2]
- [ ] CHK040 Has the post-fix `body_confidence_min: 0.0 (never null)` decision been added as an explicit cross-reference to Q37, so a future reader following Q37 lands on the pinned numeric typing? [Clarity, Post-Fix F3]
- [ ] CHK041 Has the post-fix `semantic_document_statuses` top-level-sibling key decision been added as an explicit cross-reference to Q19 and Q36, so a future reader following either clarification lands on the pinned key name? [Clarity, Post-Fix F6]
- [ ] CHK042 Is the `failed_checks` always-present rule (post-F5) cross-referenced from Q29 (which originated the two-view model)? [Clarity, Post-Fix F5]
- [ ] CHK043 Does any Clarification Q1–Q44 now CONFLICT with the post-remediation prose (i.e., the fix moved past a clarification's stated decision without amending the clarification)? [Conflict-test; expected answer: NO]

## Module Invariants MI-1 through MI-25 Coverage

- [ ] CHK044 Is every Module Invariant MI-1 through MI-25 from contracts/module-invariants.md mapped to at least one tasks.md test task that exercises it? [Coverage]
- [ ] CHK045 Is MI-14 (`failed_checks` source of truth; `row_reasons` derived) still consistent with the post-F1/F2 `row_reasons` object-keyed shape, or does MI-14 need its own amendment? [Consistency, Post-Fix F1+F2]
- [ ] CHK046 Is MI-15 (`supporting_evidence` closed shape) still consistent with the post-F3 ruling that `body_confidence_min` is always JSON `number` (never null)? [Consistency, Post-Fix F3]
- [ ] CHK047 Is MI-20 (calibration folder exclusion from aggregates but inclusion in per-document entries) consistent with the post-F6 pinned key name `semantic_document_statuses` as the location of those per-document entries? [Consistency, Post-Fix F6]
- [ ] CHK048 Does any Module Invariant MI-1…MI-25 now CONFLICT with the post-remediation prose (i.e., the fix moved past an invariant's stated rule without amending the invariant)? [Conflict-test; expected answer: NO]

---

## Constitution Alignment (Principles I–V + 7 Quality Gates)

- [ ] CHK049 Is Principle I (Pipeline/harness boundary) preserved by the post-fix artifact set — specifically, do NO post-fix edits introduce code paths from `src/dartwing_ocr/evaluator/` or `src/dartwing_ocr/validator/` into `src/dartwing_ocr/preprocessing/`, `src/dartwing_ocr/extract/`, `src/dartwing_ocr/router/`, or `src/dartwing_ocr/assembler/`? [Constitution]
- [ ] CHK050 Is Principle II (Evidence-First, Schema-First) preserved by the post-fix artifact set — specifically, does the post-fix `row_reasons` object-keyed shape have a corresponding schema-amendments.md definition AND a tasks.md schema-enforcement task (T048)? [Constitution]
- [ ] CHK051 Is Principle III (Deterministic Control) preserved — does any post-fix edit accidentally make a check predicate non-deterministic or move authority from code to model? [Constitution; expected answer: NO]
- [ ] CHK052 Is Principle IV (Provenance and Review Safety) preserved — does the post-fix `document_pass_fail.semantic_table_quality_passed` value-domain mapping (true/false/false/null) still cleanly separate explicit vs. inferred for the semantic verdict? [Constitution]
- [ ] CHK053 Is Principle V (Benchmarkable and Reproducible Delivery) preserved — does the post-F5 `failed_checks: []` rule for passed/unevaluable still preserve byte-identical reproducibility for re-runs on the same inputs (SC-007)? [Constitution]
- [ ] CHK054 Is Quality Gate #7 (consistency with `docs/stage1-vendor-identity/architecture.md`) now satisfied either by an explicit alignment citation OR by a declared deviation with one-line reason in plan.md Constitution Check? [Constitution, Post-Fix F12]
- [ ] CHK055 Are Quality Gates #1–#6 from the constitution explicitly addressed in plan.md Constitution Check, with no gate left unmentioned? [Constitution, Completeness]

---

## Out-of-Scope Boundary Integrity

- [ ] CHK056 Is the runtime pipeline integration boundary (Q3 / FR-033) consistently restated as out-of-scope in spec.md §Out of Scope, plan.md Summary, plan.md Constitution Check, tasks.md (no implementation task), and the OpenSpec change cross-link? [Consistency]
- [ ] CHK057 Is the "no new configuration surface" boundary (Q13 / Q38 / FR-007 / FR-029) consistently restated as out-of-scope across spec.md §Out of Scope, plan.md Technical Context, plan.md Constitution Check, and contracts/validator-cli-contract.md Notes? [Consistency]
- [ ] CHK058 Is the "no performance/latency target" boundary (Q38 / Out of Scope bullet) consistently restated across spec.md §Out of Scope, plan.md Performance Goals, and plan.md Constitution Check Stage 1 Scope Constraints? [Consistency]
- [ ] CHK059 Is the "no line-item extraction" boundary (FR-030) reinforced in spec.md, plan.md Constitution Check, AND now in tasks.md T056 (post-F8)? [Consistency, Post-Fix F8]
- [ ] CHK060 Is the "no Paddle/GPU dependency for the gate" boundary (MI-1) consistently restated in plan.md Technical Context, plan.md Constitution Check, data-model.md §13, MI-1, and tasks.md T031/T040? [Consistency]
- [ ] CHK061 Is the "no `source.pdf` in the US2 fixture" boundary (Q25 / MI-25 / FR-026) consistently restated in spec.md FR-026, plan.md, data-model.md (implied), MI-25, and tasks.md T041? [Consistency]

---

## Backward-Compat Read Path (FR-019 / Q43 / SC-008)

- [ ] CHK062 Is the absent-field interpretation rule (pre-feature `evaluation_document.json` lacking `document_pass_fail.semantic_table_quality_passed` is interpreted as `null`) defined identically in spec.md FR-019, research.md R-022.9, contracts/evaluator-output-contract.md, MI-24, and tasks.md T045/T053? [Consistency]
- [ ] CHK063 Is the writer obligation (newly written reports MUST always include semantic fields even though readers tolerate their absence) stated unambiguously in spec.md FR-017 + FR-018, contracts/evaluator-output-contract.md §"Writer obligations", and tasks.md T051/T052? [Clarity, Consistency]
- [ ] CHK064 Is the two-schema model (v1.3.0 schema enforces write shape; v1.2.0 schema loader used for backward-compat read tolerance) consistently described in research.md R-022.9, tasks.md T010 (version bump), tasks.md T053 (read-path implementation), and contracts/schema-amendments.md? [Consistency]
- [ ] CHK065 Does the schema task T048 explicitly mark `semantic_table_quality` as OPTIONAL at the schema level (so pre-feature reports validate) WHILE the writer obligation (T051) keeps it conditionally REQUIRED at write time? [Clarity, Consistency, FR-019]

---

## Stable JSON Serialization (Q34 / FR-014 / MI-16 / SC-007)

- [ ] CHK066 Is the stable-JSON convention set (sorted keys at every nesting level; UTF-8; LF; trailing newline; no trailing whitespace; 6-dp ROUND_HALF_EVEN for ratios/confidence; integers as JSON ints; emitted as JSON numbers not strings) defined identically in spec.md Q34/FR-014, research.md R-022.3, contracts/evaluator-output-contract.md §"Stable JSON serialization", MI-16, data-model.md §10 + §13, and tasks.md T008/T012/T039/T051/T052? [Consistency]
- [ ] CHK067 Is the 6-decimal-place ROUND_HALF_EVEN precision constant pinned with the same value across data-model.md §10 (`SUPPORTING_EVIDENCE_FLOAT_PRECISION = 6`), research.md R-022.3 (Decimal-based encoder), and tasks.md T008/T012 (banker's-rounding test cases `0.1234565 → 0.123456` and `0.1234575 → 0.123458`)? [Consistency]
- [ ] CHK068 Are the SC-007 byte-identity acceptance criteria (re-run produces byte-identical `semantic_table_quality` object, failed-check set, failed-check ordering, row-level reasons) testable using only the artifacts a reviewer has — `preprocess_output.json` + `semantic_table_truth.json`? [Measurability, Consistency]

---

## Calibration vs Scored Corpus (FR-026 / FR-027 / Q23 / Q39 / Q40 / SC-009 / MI-20 / MI-21)

- [ ] CHK069 Is the canonical-pattern allowlist regex `^inv_\d{3}_(easy|medium|hard)$` pinned identically across spec.md Q23/FR-027, data-model.md §9, research.md R-022.15, contracts/validator-cli-contract.md, MI-21, and tasks.md T007/T011/T058/T060? [Consistency]
- [ ] CHK070 Is the default-exclude semantics (unrecognized folder name is NEVER silently scored) stated unambiguously in spec.md Q23, contracts/validator-cli-contract.md §`validate corpus`, MI-21, and tasks.md T058/T060? [Clarity]
- [ ] CHK071 Is the calibration-folder rule (gate runs and emits per-document entry, but excluded from `semantic_table_quality_metrics` aggregates) defined identically in spec.md Q39/FR-018, data-model.md §8, contracts/evaluator-output-contract.md, MI-20, research.md R-022.15, and tasks.md T046/T050/T052/T058? [Consistency]
- [ ] CHK072 Is the new corpus root `tests/stage1_semantic_quality/` and its subfolder pattern (Q15/Q40) pinned identically across spec.md FR-026, plan.md, contracts/, and tasks.md T002/T041/T042/T061/T062? [Consistency]
- [ ] CHK073 Is the PII/license screening obligation for the new corpus root (Q44/FR-026) cross-referenced from spec.md FR-026 to tasks.md T061 and to the existing `docs/stage1-vendor-identity/labeling-guide.md`? [Consistency, Coverage]

---

## Sidecar Validator Error Surface (FR-003 / FR-004 / Q41)

- [ ] CHK074 Is the document_id-mismatch error message content rule (MUST name BOTH the declared `document_id` and the folder basename) defined identically in spec.md FR-003/Q41, data-model.md §1, contracts/validator-cli-contract.md §"Error message content", and tasks.md T016/T020? [Consistency]
- [ ] CHK075 Is the row-violation error message content rule (MUST name `row_id` OR `[<array_index>]`, the failed field, and a one-line machine-readable reason) defined identically in spec.md FR-004/Q41, data-model.md §1, contracts/validator-cli-contract.md, and tasks.md T016/T020? [Consistency]
- [ ] CHK076 Is the "all row violations reported, not just the first" rule stated in contracts/validator-cli-contract.md, and tested by tasks.md T016 (f)? [Coverage]

---

## Sidecar Schema & Row-Truth Contract (FR-002 / Q2 / Q8 / Q9 / Q11 / Q27 / Q28)

- [ ] CHK077 Is the sidecar top-level shape `{document_id, rows, schema_version?}` with `additionalProperties: false` pinned identically across spec.md FR-002, data-model.md §1, contracts/schema-amendments.md, and tasks.md T005/T015? [Consistency]
- [ ] CHK078 Is the mandatory-row-fields rule (only `row_id` and `required_row_text_tokens` are mandatory; `quantity`/`description`/`unit_price`/`amount` are optional) defined identically in spec.md FR-002/Q8, data-model.md §2, contracts/schema-amendments.md, and tasks.md T015/T016? [Consistency]
- [ ] CHK079 Is the optional-field-becomes-required-content-check rule (Q8 — every present optional cell becomes a required-content check for that row) stated in spec.md FR-002 AND echoed in data-model.md §2 row-text-optionality-rule AND in tasks.md T027/T038? [Consistency, Clarity]
- [ ] CHK080 Is the row_id uniqueness rule (Q11 — non-empty string, unique within the sidecar, enforced at validator layer NOT schema) defined identically in spec.md FR-002, data-model.md §1+§2, and tasks.md T015/T016/T020? [Consistency]
- [ ] CHK081 Is the decimal-string currency representation rule (Q9 — `unit_price`/`amount` authored as `^\d+\.\d{2}$`, no currency symbol) pinned identically in spec.md FR-002, data-model.md §2 + §9 (`EXPECTED_CELL_DECIMAL_REGEX`), contracts/schema-amendments.md, and tasks.md T005/T015? [Consistency]
- [ ] CHK082 Is `required_row_text_tokens` consistently described as a non-empty array of non-empty token strings (Q28) — spec.md FR-002, data-model.md §2, contracts/schema-amendments.md, tasks.md T015? [Consistency]

---

## Body-OCR Selection & Normalization (FR-007 / FR-009 / Q5 / Q22 / Q24 / Q32 / Q33 / R-022.4)

- [ ] CHK083 Is the body-OCR selection rule "every page's OCR content EXCEPT the feature-020 page-1 header-band region, with `Y_THRESHOLD_FRACTION = 0.25`" defined identically in spec.md Q22/FR-007, data-model.md §3, MI-7, research.md R-022.4, and tasks.md T024/T035? [Consistency]
- [ ] CHK084 Is the lane-robustness rule (rule applies identically to OCR-only-lane and PPStructureV3 `preprocess_output.json` artifacts, MUST NOT depend on table-block detection) stated in spec.md Q22/FR-007, data-model.md §3, MI-7, and tasks.md T024? [Consistency]
- [ ] CHK085 Is the FR-009 normalization pipeline (NFKC → casefold → whitespace collapse → strip every `P*` Unicode category code point) defined identically in spec.md Q5/Q32/FR-009, data-model.md §11, research.md R-022.2, and tasks.md T023/T034? [Consistency]
- [ ] CHK086 Is the single-normalized-concatenation rule (Q33 — body-OCR search string built ONCE per document, "found anywhere" checks operate against it) defined identically in spec.md Q33/FR-009, data-model.md §3 + §11, MI-6, and tasks.md T023/T035/T038? [Consistency]
- [ ] CHK087 Is the Q24 "earliest observed-OCR position" tie-break definition (`preprocess_output.json` serialization order — page array order, then line/token array order; no geometry, no coordinate tolerance) defined identically in spec.md Q24/FR-012, data-model.md §12, MI-6, and tasks.md T025/T036? [Consistency]
- [ ] CHK088 Is the normalization idempotence invariant (`normalize(normalize(x)) == normalize(x)`) stated in data-model.md §11 AND tested by tasks.md T023(e)? [Coverage]

---

## Currency-Shape Check (FR-010 / Q10 / Q16 / Q35)

- [ ] CHK089 Is the canonical money regex `^\$?\d{1,3}(,\d{3})*\.\d{2}$` (anchored) pinned identically across spec.md Q10/FR-010, data-model.md §9 (`CANONICAL_MONEY_REGEX`), MI-8, research.md, and tasks.md T026/T037? [Consistency]
- [ ] CHK090 Is the raw-token-before-normalization rule (Q16 — currency-shape check evaluates RAW OCR token text BEFORE FR-009 punctuation stripping) defined identically in spec.md Q16/FR-010, data-model.md §11 currency-shape-exception, MI-8, and tasks.md T026(d)/T037/T038? [Consistency]
- [ ] CHK091 Is the per-field digit-sequence matching rule (Q35 — scan raw tokens in serialization order, return first not-yet-matched token whose digit-only representation equals expected field's digit sequence) defined identically in spec.md Q35/FR-010, data-model.md §9 + §12, MI-9, research.md, and tasks.md T026/T037? [Consistency]
- [ ] CHK092 Is the defer-to-missing-required-content rule (when no candidate currency token exists, the failure is `missing-required-content` NOT `malformed-currency-shape`) stated identically in spec.md Q35/FR-010, data-model.md §12, MI-9, and tasks.md T026(c)/T038? [Consistency]

---

## Row Anchoring (FR-012 / Q7 / Q24)

- [ ] CHK093 Is the "best span = most matched `required_row_text_tokens` (NOT fuzzy edit distance)" rule (Q7) pinned identically across spec.md Q7/FR-012, data-model.md §12, and tasks.md T025/T036? [Consistency]
- [ ] CHK094 Is the deterministic tie-break order (1: earliest serialization-order position, 2: sidecar declaration order) pinned identically across spec.md Q7/Q24/FR-012, data-model.md §12, and tasks.md T025/T036? [Consistency]
- [ ] CHK095 Is the empty-evidence anchor-failure behavior (no included body lines → anchor span is `None` → all dependent checks fall through to `missing-required-content`) stated in data-model.md §12 AND tasks.md T025(d)? [Coverage]

---

## Verdict Aggregation & Hard-Error Boundary (FR-016 / Q4 / Q42 / MI-10 / MI-19)

- [ ] CHK096 Is the any-fail aggregation rule (`failed` if ≥1 failed_checks entry; `passed` only when zero across all rows) pinned identically across spec.md Q4/FR-016, data-model.md §7, MI-10, and tasks.md T028/T040? [Consistency]
- [ ] CHK097 Is the no-short-circuit invariant (every applicable check evaluated for every row before aggregation) pinned identically across spec.md Q17/FR-015, MI-3, and tasks.md T027(a)/T038/T040? [Consistency]
- [ ] CHK098 Is the gate-time-invariant-violation hard-error rule (Q42 — `SemanticGateInvariantError` raised, NOT recorded as `unevaluable`, document excluded from metrics) defined identically in spec.md Q42/FR-016, data-model.md §7 + §13, research.md R-022.14, MI-19, and tasks.md T009/T013/T030(e)/T040? [Consistency]
- [ ] CHK099 Is the `unevaluable`-reserved-for-input-failures rule (Q31 — closed cause enum + four-step cascade) defined identically in spec.md Q31/FR-016/FR-017, data-model.md §7, research.md R-022.13, MI-13, and tasks.md T030/T040? [Consistency]

---

## Run-Summary Metrics (FR-018 / Q19 / Q36 / Q39)

- [ ] CHK100 Are all eight `semantic_table_quality_metrics` fields enumerated identically across spec.md FR-018, data-model.md §8, contracts/evaluator-output-contract.md, contracts/schema-amendments.md, and tasks.md T044/T046/T049/T050? Names: `semantic_applicable_document_count`, `semantic_not_applicable_document_count`, `semantic_evaluable_document_count`, `semantic_passed_document_count`, `semantic_failed_document_count`, `semantic_unevaluable_document_count`, `semantic_table_quality_pass_rate`, `semantic_failed_check_counts`. [Consistency, Completeness]
- [ ] CHK101 Is the pass-rate nullability rule (`semantic_table_quality_pass_rate: null` when `semantic_evaluable_document_count == 0`) defined identically across all artifacts that reference it? [Consistency]
- [ ] CHK102 Is the `semantic_failed_check_counts` always-present-four-keys rule (not sparse; all four kebab-case keys present with integer counts, defaulting to `0`) pinned in contracts/evaluator-output-contract.md AND echoed in data-model.md §8 AND tasks.md T046/T050? [Clarity, Consistency]
- [ ] CHK103 Is the deterministic per-document-entry ordering rule ("evaluator's canonical document iteration order for the run") defined identically across spec.md FR-018, data-model.md §8, and tasks.md T050/T052? [Consistency]

---

## Synthetic US2 Fixture (Q25 / MI-25 / FR-026)

- [ ] CHK104 Is the US2 fixture composition rule (hand-authored `preprocess_output.json` + matching `semantic_table_truth.json`; NO `source.pdf`; NOT pipeline-produced; CPU-only; deterministic) pinned identically across spec.md Q25/FR-026/US2 Independent Test, plan.md Summary, research.md R-022.6, MI-25, and tasks.md T041/T042? [Consistency]
- [ ] CHK105 Is the fixture content rule (reproduces `inv_024_hard_degraded_body` calibration pattern — high mean detector confidence ≈ 0.97, materially wrong rows, including colon-for-decimal currency and missing quantity values) defined identically in spec.md US2/FR-026, plan.md, research.md R-022.6, and tasks.md T041? [Consistency]
- [ ] CHK106 Is the fixture folder name `tests/stage1_semantic_quality/inv_001_hard/` (matching the Q40 canonical pattern) pinned identically in plan.md, tasks.md T002/T041/T042, and the corpus-governance checklist? [Consistency]

---

## Cross-Cutting: Completeness

- [ ] CHK107 Does every active functional requirement FR-001 through FR-033 have a corresponding entry in the FR↔task↔test coverage matrix (planned via T070)? [Completeness, FR-032 / SC-010]
- [ ] CHK108 Does spec.md document EVERY edge case from the bulleted "Edge Cases" section with at least one corresponding task or test? [Completeness]
- [ ] CHK109 Is every claim in the spec.md §Assumptions section either (a) verifiable, (b) testable, or (c) explicitly out-of-scope? [Completeness]
- [ ] CHK110 Does plan.md Constitution Check explicitly address all 5 Principles AND all 7 Quality Gates with PASS/PASS-WITH-DOCS/FAIL? [Completeness, Constitution]
- [ ] CHK111 Does the contracts/schema-amendments.md AMENDMENTS.md entry text cover the four files changed (sidecar added + 3 amended) AND the seven files carried unchanged? [Completeness]

## Cross-Cutting: Clarity

- [ ] CHK112 Is every vague term in spec.md ("best", "reasonable", "appropriate") either (a) absent, (b) quantified, or (c) explicitly out-of-scope? [Clarity]
- [ ] CHK113 Is every term-of-art used by spec.md (e.g., "header band", "calibration folder", "scored corpus folder", "lane-robust", "found anywhere", "anchored span") defined exactly once and then referenced consistently? [Clarity]
- [ ] CHK114 Does data-model.md use the same field names as contracts/schema-amendments.md for every entity surface (no synonyms, no aliases)? [Clarity, Consistency]
- [ ] CHK115 Does tasks.md describe each test task with enough specificity that an implementer can write the test without re-reading spec.md? [Clarity]

## Cross-Cutting: Consistency

- [ ] CHK116 Do spec.md, plan.md, data-model.md, contracts/*.md, research.md, and tasks.md all use `1.3.0` (with explicit dots) — never `1_3_0` or `v13` — for the contract-set version? [Consistency]
- [ ] CHK117 Do all artifacts use the same module path conventions — `src/dartwing_ocr/evaluator/<file>.py` and `src/dartwing_ocr/validator/<file>.py` — without abbreviation or path drift? [Consistency]
- [ ] CHK118 Do all artifacts use the same date convention `YYYY-MM-DD` for the AMENDMENTS.md entry date and the spec.md Clarifications session headings? [Consistency]

## Cross-Cutting: Acceptance Criteria Quality

- [ ] CHK119 Is every Success Criterion SC-001…SC-010 worded so that a reviewer can answer "did we meet it? yes/no" without ambiguity? [Measurability]
- [ ] CHK120 Is SC-006 (vendor-identity byte-identical baseline) supported by an actual baseline-capture mechanism (tasks.md T057) so the criterion is testable not aspirational? [Measurability, Coverage]
- [ ] CHK121 Is SC-010 (FR↔task↔test coverage) supported by a deliverable artifact (tasks.md T070 → `coverage-fr-task-test.md`)? [Measurability, Coverage]

## Cross-Cutting: Dependencies & Assumptions

- [ ] CHK122 Are all assumed external states (e.g. "feature 020 evidence-gate behavior is stable", "the v1.2.0 contract set is frozen") documented as explicit assumptions in spec.md §Assumptions OR plan.md? [Completeness]
- [ ] CHK123 Is the dependency on feature 020's `Y_THRESHOLD_FRACTION` constant import (MI-7 / R-022.4) documented as a cross-feature dependency in plan.md AND tasks.md T035? [Completeness, Consistency]

## Cross-Cutting: Ambiguities & Conflicts

- [ ] CHK124 Re-running `/speckit.analyze` after the F1–F12 fixes — does it report zero CRITICAL findings, zero HIGH findings, and only the previously-known LOW items? [Conflict-test; expected answer: YES (zero CRITICAL/HIGH)]
- [ ] CHK125 Does any post-fix prose introduce a NEW conflict that did not exist in the pre-fix snapshot (e.g., the `failed_checks: []` rule for unevaluable conflicts with some other artifact)? [Conflict-test; expected answer: NO]
- [ ] CHK126 Are all `[Post-Fix F#]` traceability markers in this checklist accurate — i.e., the cited finding's resolution does land in the cited artifact? [Traceability]

---

## Pre-Implementation Readiness Gates

- [ ] CHK127 Has the `/speckit.analyze` report been re-run AFTER the F1–F12 fixes and shows zero CRITICAL findings? [Release Gate]
- [ ] CHK128 Has the `/speckit.analyze` report been re-run AFTER the F1–F12 fixes and shows zero HIGH findings? [Release Gate]
- [ ] CHK129 Are all LOW findings from the original `/speckit.analyze` either (a) resolved by the F1–F12 fixes, or (b) folded into a Phase 8 polish task with explicit traceability? [Release Gate]
- [ ] CHK130 Is every artifact in the feature directory (`spec.md`, `plan.md`, `data-model.md`, `research.md`, `quickstart.md`, `contracts/*.md`, `tasks.md`, `clarify-questions.md`) committed or staged for commit so the next `/speckit.implement` run starts from a clean, auditable state? [Release Gate]
- [ ] CHK131 Is there a documented, single, authoritative source for each contested decision (`row_reasons` shape, `body_confidence_min` nullability, `semantic_document_statuses` location, `failed_checks` always-present rule) — so an implementer never has to guess which artifact wins? [Release Gate, Single-Source-of-Truth]

---

## Notes

- Check items off as completed: `[x]`
- Add comments inline for failed items: which artifact is misaligned, what specifically must change
- An item that **cannot be answered from the artifacts alone** is itself a requirement-quality defect — either the prose is missing or it is too vague
- This checklist is a **release-gate filter**: every CRITICAL/HIGH-resolution item (CHK001–CHK023) MUST be checked before `/speckit.implement`; cross-cutting and constitution items SHOULD be checked; pre-implementation-readiness items (CHK127–CHK131) MUST be checked as the final commit-or-implement gate
- Items are numbered sequentially (CHK001…CHK131) for easy cross-reference
- Total: **131 items** across **18 categories**, no soft cap (per max-coverage mode)
