# Phase 0 Research: OCR Semantic Quality Gate

Every spec-level decision for feature 022 is already pinned by Clarifications Q1–Q44 across two sessions (2026-05-22 and 2026-05-23), recorded verbatim in `spec.md`. This `research.md` records the 15 **plan-level** decisions only — module placement, stdlib mechanics, stable JSON serialization, contract-set bump procedure, header-band helper reuse, synthetic fixture composition, test framework, validator subcommand surface, backward-compat read path, failed-check record shape, supporting-evidence computation, `unevaluable` cause-code detection, hard-error vs. `unevaluable` boundary, the `AMENDMENTS.md` entry format, and calibration-folder exclusion implementation. This document does NOT re-litigate spec-level choices such as the any-fail aggregation rule (Q4), normalized exact match (Q5), binary text-coverage check (Q6), text-anchored row anchoring (Q7), mandatory row fields (Q8), decimal-string currency representation (Q9), the canonical money regex (Q10), or the canonical status enum (Q26). Readers of this file should consult `spec.md` for those decisions.

---

## R-022.1 — Module placement under `src/dartwing_ocr/evaluator/`

**Decision**: All new gate-logic modules — `semantic_quality.py`, `semantic_quality_normalize.py`, `semantic_quality_body_ocr.py`, `semantic_quality_anchor.py`, `semantic_quality_currency.py`, `semantic_quality_checks.py`, `semantic_quality_report.py`, `semantic_quality_metrics.py`, `stable_json.py`, and `exceptions.py` — are placed under the existing `src/dartwing_ocr/evaluator/` package. The sidecar contract validator (`semantic_table_truth.py`) and the canonical-pattern allowlist helper (`corpus_pattern.py`) are placed under the existing `src/dartwing_ocr/validator/` package. No new top-level package is introduced. No new CLI entry point is created (per Clarifications Q13 — the sidecar's presence is itself the opt-in).

**Rationale**: The constitution (Principle I) requires the harness/evaluator layer to own this gate — it must not touch `src/dartwing_ocr/preprocessing/`, `src/dartwing_ocr/extract/`, `src/dartwing_ocr/router/`, or `src/dartwing_ocr/assembler/`. Placing the gate under `evaluator/` makes that boundary immediately visible from the file tree alone and matches the constitution check outcome recorded in `plan.md`. The validator package is the established home for artifact contract enforcement; `semantic_table_truth.py` is a contract enforcer, not pipeline logic, so it belongs there alongside the existing folder and artifact validators.

**Alternatives considered**:
- A new top-level package `src/dartwing_ocr/semantic_gate/` (rejected: no constitutional or functional reason justifies a new top-level package when the existing evaluator boundary is the correct home; adds unnecessary package surface that would need its own `__init__.py` exports and documentation).
- Placing gate logic in `src/dartwing_ocr/validator/` alongside the sidecar validator (rejected: mixes truth-contract enforcement with gate computation; the validator package is concerned with schema validity, the evaluator package with producing verdicts).

---

## R-022.2 — Unicode-category detection via `unicodedata.category(ch)`

**Decision**: The FR-009 punctuation-stripping step uses `unicodedata.category(ch)[0] == "P"` to classify each code point, iterated over the NFKC-normalized, case-folded, whitespace-collapsed text. The `unicodedata` module is part of the Python standard library; the Unicode tables it ships are pinned to the CPython release — Python 3.12 ships Unicode 15.0.0 data and that version is fixed for the lifetime of the 3.12 interpreter. All gate logic therefore runs identically on any host running the same CPython 3.12 minor version without a separately-installed Unicode database package. The seven `P*` sub-categories are enumerated in FR-009 and Clarifications Q32: `Pc` (connector), `Pd` (dash), `Pe` (close), `Pf` (final quote), `Pi` (initial quote), `Po` (other punctuation), `Ps` (open). The category check `category[0] == "P"` covers all seven and is future-proof against any new `P*` sub-category added in a future Unicode version.

**Rationale**: The `unicodedata` module is the only correct stdlib tool for Unicode general-category classification; there is no equivalent in `re` (character classes in `re` do not map to Unicode categories). Using `unicodedata.category(ch)[0] == "P"` avoids importing a third-party library and keeps the module CPU-safe, dependency-additive-free, and byte-identical across environments with the same CPython 3.12 version. The check is also idiomatic — it is the pattern used by reference Unicode implementations and is recognizable to any Python developer.

**Alternatives considered**:
- A hard-coded `re` character class listing all punctuation code points (rejected: a static character class cannot be complete without enumerating every `P*` code point, which changes with each Unicode version; `unicodedata.category` is the canonical source of truth).
- A third-party `unicodedata2` or `regex` package for richer Unicode support (rejected: no new pinned dependency is permitted by the plan; Python 3.12's built-in Unicode 15.0 tables cover the entire `P*` category set without a supplement).

---

## R-022.3 — Stable JSON serialization mechanics for Q34

**Decision**: The new `stable_json.py` module exposes a single public function `dump_stable(obj, path: Path) -> None` that writes JSON with `sort_keys=True, ensure_ascii=False, indent=2`, followed by a single LF trailing newline, to the given path, using UTF-8 encoding and LF line endings throughout. Derived ratios and confidence values (e.g. `semantic_table_quality_pass_rate`, `body_confidence_mean`, `body_confidence_min`) are represented as `decimal.Decimal` internally, rounded to 6 decimal places with `ROUND_HALF_EVEN`, and emitted as **JSON numbers** (not strings) by a custom `JSONEncoder` subclass that overrides `default()` to detect `Decimal` instances and calls `float()` after rounding — the resulting `float` serializes as a JSON number via the standard encoder, preserving numeric schema types. Integer counts pass through unchanged as Python `int` values, which `json.dumps` serializes as JSON integers. The Decimal-based approach avoids the `float` precision pitfall (Python floats do not round to a fixed decimal digit count on their own) without introducing a `parse_float=Decimal` round-trip through the full document, which would convert all existing floats in `preprocess_output.json` and break the read path.

**Rationale**: Clarifications Q34 requires fixed-precision numeric floats as JSON numbers (not strings), sorted keys, UTF-8, LF line endings, and a trailing newline. These constraints together pin byte-identity of newly-written semantic outputs across re-runs (FR-014 / SC-007). The `decimal.Decimal` + custom encoder approach is the standard-library-only way to emit a float-typed JSON number with a guaranteed 6-decimal-digit representation without converting every float in the document.

**Alternatives considered**:
- `json.dumps(obj, cls=CustomEncoder, parse_float=Decimal)` round-trip (rejected: converts ALL float-typed values in the input object — including those in `preprocess_output.json` read content — to Decimal, which changes every floating-point value's serialization precision and breaks backward-compat assertions against pre-feature-generated content).
- Format derived ratios as strings (e.g. `"0.975000"`) (rejected: violates Q34's requirement that derived values be emitted as JSON numbers, not strings, to preserve numeric schema types).
- Use `round(val, 6)` without Decimal (rejected: Python `float` rounding is not guaranteed to produce exactly 6 decimal digits of representation in the JSON output because `json.dumps` formats floats via C `repr`, which may emit more or fewer significant digits).

---

## R-022.4 — Reuse feature-020's page-1 header-band Y_THRESHOLD_FRACTION = 0.25

**Decision**: `semantic_quality_body_ocr.py` imports `Y_THRESHOLD_FRACTION` from `dartwing_ocr.preprocessing.evidence_gate` rather than defining a local copy. The constant is imported under the alias `EVIDENCE_GATE_Y_THRESHOLD_FRACTION` at the call site to make the provenance explicit in the body-OCR module's source. The body-OCR selection rule is identical to feature-020's header-band filter: a line is excluded from "observed body OCR" iff it belongs to `pages[0]` and its bbox top y-coordinate (fraction of page height) is strictly less than `0.25`. Lines on `pages[1..N]` are fully included regardless of y-coordinate. The `header_band_excluded: bool` flag on `BodyOcrEvidence` is `True` iff at least one line was filtered by this rule (Clarifications Q22 / FR-007).

**Rationale**: Clarifications Q22 requires that the body-OCR selection rule be lane-robust and identical to the feature-020 header-band definition. Importing the constant directly from `preprocessing.evidence_gate` guarantees the two definitions can never silently diverge from a copy-paste drift. The import also makes the dependency relationship visible in the module — a reviewer can see exactly which prior feature's threshold is being reused. The `0.25` fraction was calibrated against the corpus header-band depth in feature-018 and is already established as a named module-level constant; redefinition would be technical debt.

**Alternatives considered**:
- Define a separate `BODY_OCR_Y_THRESHOLD_FRACTION = 0.25` constant in `semantic_quality_body_ocr.py` (rejected: creates two constants with the same value and no enforcement of equality; future updates to feature-020's threshold would silently skip the gate).
- Move the constant to a shared `dartwing_ocr.constants` module (rejected: scope creep — moving a constant from its authoritative module to a new shared module requires changes to feature-020 code; the import approach achieves reuse without moving anything).

---

## R-022.5 — Contract-set bump procedure (Q14)

**Decision**: The v1.3.0 contract set is created by copying the entire `contracts/stage1_vendor_identity/v1.2.0/` directory verbatim to `contracts/stage1_vendor_identity/v1.3.0/`, then making targeted edits to exactly four files: `evaluation_document.schema.json` (add optional `semantic_table_quality` object and `document_pass_fail.semantic_table_quality_passed`), `evaluation_run_summary.schema.json` (add top-level `semantic_table_quality_metrics` namespace and per-document semantic status entries), `folder.schema.json` (add `semantic_table_truth.json` as an optional file in the per-document folder contract), and `contract_set.json` (update `contract_set_version` to `"1.3.0"` and add `semantic_table_truth.schema.json` to the schema listing). One new file is added: `semantic_table_truth.schema.json`. The remaining seven schemas (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`, `evidence_packet`, `expected`, and `README.md`) are carried over byte-identical from v1.2.0. The v1.2.0 directory remains in place, read-accessible for backward-compat per FR-019 and Q43.

**Rationale**: The copy-then-edit procedure makes the diff from v1.2.0 to v1.3.0 easily auditable — every unchanged schema is byte-identical, and every changed schema carries only the additive delta. The `AMENDMENTS.md` entry references Clarifications Q14 and the exact four changed files. The v1.2.0 directory must remain accessible because the existing evaluator's backward-compat read path (R-022.9) must be able to load pre-feature reports without schema upgrade.

**Alternatives considered**:
- In-place schema mutation with a version field update (rejected: destroys the frozen v1.2.0 snapshot; breaks the amendment changelog model; pre-feature reports can no longer be validated against the version they were written against).
- A patch-file-based approach rather than a full directory copy (rejected: adds tooling complexity; the copy-then-edit approach is already established by v1.0.0 → v1.1.0 → v1.2.0 precedent in the `contracts/` directory).

---

## R-022.6 — Synthetic preprocess_output.json composition (Q25)

**Decision**: The US2 synthetic fixture at `tests/stage1_semantic_quality/inv_001_hard/` commits a hand-authored `preprocess_output.json` that is schema-valid against the v1.3.0 `preprocess_output.schema.json` (which is copied byte-identical from v1.2.0). The fixture reproduces the 8-row degraded-body OCR pattern documented in `docs/stage1-vendor-identity/ocr-semantic-quality-observations.md` as the `inv_024_hard_degraded_body` calibration evidence: per-line OCR detector confidence values are set to approximately `0.97` (high, consistent with the calibration finding of body confidence mean ≈ 0.97), while the body text carries the known failure patterns — colon-for-decimal currency (`$21:00` where `$21.00` is expected), missing quantity values, and mutated product descriptions. The fixture contains no `source.pdf` and is not produced by running the preprocessing pipeline — it is a static, deterministic, CPU-only test input. The matching `semantic_table_truth.json` declares 8 rows with `row_id`, `required_row_text_tokens`, `unit_price`, and `amount` fields so that at least the `malformed-currency-shape` and `missing-required-content` check categories fire.

**Rationale**: Clarifications Q25 requires the US2 fixture to be hand-authored, schema-valid, CPU-only, and free of any Paddle/GPU dependency. Using the `inv_024_hard_degraded_body` calibration observations as the source of the fixture pattern ensures the gate is validated against a realistic degraded-body failure signature rather than an arbitrary synthetic case. The fixture must not contain `source.pdf` to keep the test suite runnable on any CPU host.

**Alternatives considered**:
- Generating the fixture by running the preprocessing pipeline on a real degraded invoice (rejected: Q25 explicitly forbids a pipeline-produced fixture; doing so would introduce a Paddle/GPU dependency into the test corpus).
- Using a simpler, entirely arbitrary synthetic preprocess_output.json (rejected: the point of the synthetic fixture is to validate that the gate catches the specific failure modes documented in the calibration evidence; an arbitrary fixture would not exercise the currency-shape or missing-content checks in a realistic way).

---

## R-022.7 — pytest as the test framework

**Decision**: All gate logic tests use `pytest` as the test framework, consistent with the existing `tests/contract_tests/`, `tests/unit/`, and `tests/integration/` directories in the repository. All gate tests are CPU-only and Paddle-free — no `@pytest.mark.gpu` tag is needed for any new gate test file. The single committed fixture at `tests/stage1_semantic_quality/inv_001_hard/` is a static artifact and requires no fixture-generation infrastructure. The `tests/stage1_semantic_quality/` root is a new directory parallel to `tests/stage1_vendor_identity/`; it is recognized by `pytest` via the existing `pyproject.toml` test discovery configuration without any new `conftest.py` additions.

**Rationale**: pytest is the established framework for this repository (features 001–021 all use it). Gate tests are deterministic in-memory comparisons with no GPU, no model, and no network — they are simpler than any prior feature's test suite and do not require any new framework capability. Keeping the same framework avoids introducing a split testing surface that would require separate CI configuration.

**Alternatives considered**:
- `unittest` (rejected: the project has already standardized on pytest; mixing frameworks adds unnecessary complexity).
- A separate test runner for the synthetic corpus (rejected: the existing evaluator's `pytest`-based integration test structure is sufficient and already supports corpus-style test organization under the `tests/integration/` tree).

---

## R-022.8 — Validator subcommand surface

**Decision**: The existing `python -m dartwing_ocr.validator` CLI is extended with two targeted changes. First, the `validate folder` subcommand is updated to accept an optional `semantic_table_truth.json` sidecar alongside the mandatory `source.pdf`, `expected.json`, and `preprocess_output.json`; sidecar validation is triggered only when the file is present in the folder. Second, a new `validate semantic-truth <folder>` subcommand is added for sidecar-only validation, bypassing the full folder contract check. The `validate corpus` subcommand is updated to exclude non-matching-pattern folders from scored aggregation (per Q23 / FR-027) but continues to validate per-document artifacts in those folders. No new top-level CLI entry point is introduced, consistent with Clarifications Q13.

**Rationale**: The `validate semantic-truth` subcommand mirrors the pattern of existing targeted subcommands such as `validate artifact` and `validate folder`; it gives fixture authors a focused validation path for sidecars without requiring a full folder-contract check (which would fail on the US2 fixture that lacks `source.pdf`). The `validate corpus` exclusion change is required by SC-009 — noncanonical folders must not appear in scored evaluation output. The absence of a new top-level CLI entry point keeps the CLI surface minimal per Q13.

**Alternatives considered**:
- A new `dartwing-validate-sidecar` entry point (rejected: Q13 requires no new CLI entry point; the `validate` subcommand tree is the established extension surface).
- Requiring `source.pdf` for `validate semantic-truth` (rejected: the US2 synthetic fixture explicitly has no `source.pdf` per Q25; a sidecar-only subcommand must work without it).

---

## R-022.9 — Backward-compat read path (FR-019 / Q43)

**Decision**: `contract_versions.py` bumps `CURRENT_CONTRACT_SET_VERSION` from `"1.2.0"` to `"1.3.0"`, but the v1.2.0 schema loader function is retained and continues to be importable for backward-compat reads of pre-feature `evaluation_document.json` and `evaluation_run_summary.json` artifacts. A pre-feature `evaluation_document.json` that lacks `document_pass_fail.semantic_table_quality_passed` is interpreted by the reader as `null` (per Q43 — "the semantic gate did not run on this document"), not as a validation failure. This interpretation is enforced in the reader layer, not in the JSON Schema: the v1.3.0 `evaluation_document.schema.json` marks `semantic_table_quality_passed` as required-on-write for newly generated documents, but a separate read-tolerant validation path (the v1.2.0 schema or a permissive read schema) is used when the caller explicitly signals backward-compat read mode.

**Rationale**: FR-019 requires that pre-feature reports remain readable after the feature lands (SC-008). The cleanest way to implement this without inflating the v1.3.0 schema with complex `if/then/else` conditional validation is to maintain the two-schema model: the write schema enforces the full v1.3.0 shape, and the backward-compat read path uses the v1.2.0 schema (or a simplified permissive read-tolerant schema). Q43 pins the interpretation of absent `semantic_table_quality_passed` as `null` so reader code has a deterministic value to return without raising.

**Alternatives considered**:
- Making `semantic_table_quality_passed` optional in the v1.3.0 write schema (rejected: this would silently permit newly-generated reports to omit the field, violating FR-019's requirement that newly-written reports carry all required semantic fields when the feature is active).
- Raising a validation error for pre-feature reports that lack the new field (rejected: directly violates FR-019 / SC-008).

---

## R-022.10 — AMENDMENTS.md entry format

**Decision**: The v1.3.0 entry in `contracts/stage1_vendor_identity/AMENDMENTS.md` follows the same format as the v1.1.0 and v1.2.0 entries: a level-two heading `## v1.3.0 — <date>`, a brief one-sentence summary of what changed, a bulleted list of the four impacted schema files (with a short description of the additive change in each), the justification referencing feature 022 and Clarifications Q14, and a statement that v1.2.0 remains frozen and read-accessible. The amendment does not re-litigate design decisions; it cross-references `specs/022-ocr-semantic-quality-gate/` for rationale. The date is `2026-05-23` (the planning date for this feature).

**Rationale**: Consistency with prior entries (`v1.1.0` and `v1.2.0`) ensures that operators reading the changelog can compare entries without adapting to a different format. The justification reference to Clarifications Q14 makes the governance decision traceable: Q14 explicitly mandated the minor bump from 1.2.0 to 1.3.0 with an AMENDMENTS.md entry. The schema-file bullet list is required so a reader can confirm that the seven unchanged schemas were intentionally carried forward.

**Alternatives considered**:
- Embedding the full schema delta in the AMENDMENTS.md entry (rejected: schema diffs are better represented by comparing the v1.2.0 and v1.3.0 directories directly; prose-duplicating the diff in AMENDMENTS.md would diverge from the machine-readable source of truth).
- Using a different heading hierarchy (rejected: the existing entries use level-two headings; consistency is required for changelog tooling and human readability).

---

## R-022.11 — Failed-check record shape pinned (Q29 / FR-015)

**Decision**: Each element in the `failed_checks` flat ordered array on `semantic_table_quality` is a JSON object with the following closed field set: `category` (string, one of the four kebab-case enum values: `malformed-currency-shape`, `missing-required-content`, `row-text-coverage-gap`, `row-alignment-failure`), `row_id` (string, matching the sidecar row's `row_id`), `field` (string or null — null for `row-text-coverage-gap` and `row-alignment-failure` where no single cell applies), `expected` (string — the expected value or token), `observed` (string or null — the raw observed OCR token for currency-shape failures, a normalized substring for missing-content failures, or null when the content is entirely absent), `predicate` (string — a one-line machine-readable description of the check predicate that was applied), and `position_index` (integer — the 0-based index of this record within the `failed_checks` array). The array is ordered by sidecar row declaration order as the outer key, then by the four-category order as the inner key (per FR-015 / Clarifications Q17).

**Rationale**: Q29 establishes the two-view model (`failed_checks` as the flat source of truth, `row_reasons` as a derived per-row aggregation). Pinning the field set here ensures that the JSON Schema in `evaluation_document.schema.json` v1.3.0 can enforce the closed shape via `additionalProperties: false`. The `field: null` convention for whole-row check categories (row-text-coverage-gap, row-alignment-failure) avoids conflating row-level and cell-level failures while still maintaining a uniform record shape. The `position_index` field makes the ordering auditable from the record itself without requiring the consumer to traverse the full array.

**Alternatives considered**:
- A union type with per-category record shapes (rejected: different shapes per category would require a discriminated union in the JSON Schema, complicating validation; a uniform closed shape with nullable `field` is simpler and equally expressive).
- Omitting `position_index` (rejected: without an explicit index, a consumer re-deriving the check order from `row_id` + `category` alone would need to resolve ties using the sidecar declaration order, which is an extra indirection that `position_index` eliminates).

---

## R-022.12 — Supporting evidence computation (Q30 / Q37)

**Decision**: The five fields in `semantic_table_quality.supporting_evidence` are computed from the `BodyOcrEvidence` object returned by `semantic_quality_body_ocr.py` after the page-1 header-band exclusion rule has been applied. `body_confidence_mean` is the arithmetic mean of the per-line OCR detector confidence values across all included body-OCR lines. `body_confidence_min` is the minimum confidence across the same set. `body_line_count` is the count of included body-OCR lines. `body_token_count` is the sum of whitespace-split token counts across those lines. `header_band_excluded` is `True` iff at least one line was filtered by the `Y_THRESHOLD_FRACTION` rule on page 1. Both `body_confidence_mean` and `body_confidence_min` are rounded to 6 decimal places with `ROUND_HALF_EVEN` and emitted as fixed-precision JSON numbers via `stable_json.dump_stable` per R-022.3. When `body_line_count` is zero (no body lines), BOTH `body_confidence_mean` and `body_confidence_min` are emitted as `0.0` (matching feature-020's convention for empty band, the data-model.md §6 pinning, the `contracts/evaluator-output-contract.md` Example C reference output, and the `body_confidence_min: {"type": "number"}` schema declaration in `contracts/schema-amendments.md`). Both fields are JSON numbers throughout — neither is ever `null`. This resolves F3 from the 2026-05-23 `/speckit.analyze` report by collapsing the prior min-vs-mean asymmetry.

**Rationale**: Q30 restricts confidence to document-aggregate supporting evidence only; no per-row or per-failed-check confidence field is added. Q37 pins the closed shape. Computing confidence from only the included (post-filter) body-OCR lines ensures that the header-band's typically-high confidence values do not inflate the body mean, which would misrepresent the quality signal for the degraded-body case (where the interesting failure is in the body, not the header).

**Alternatives considered**:
- Computing confidence over all lines including the page-1 header band (rejected: the header band has high confidence on most invoices; including it would dilute the body mean and mask the degraded-body pattern the gate targets).
- Per-row confidence breakdown (rejected: Q30 explicitly restricts confidence to document-aggregate supporting evidence; adding per-row confidence fields would violate that pin).

---

## R-022.13 — `unevaluable` cause-code detection logic (Q31)

**Decision**: The gate determines the `cause` code for `unevaluable` status using a four-step detection cascade in `semantic_quality.py`, executed before any row check is attempted. Step 1: if `Path(preprocess_output_path).exists()` returns `False`, cause is `preprocess_output_missing`. Step 2: if the file exists but `json.loads()` raises `json.JSONDecodeError`, cause is `preprocess_output_invalid_json`. Step 3: if the file parses but `jsonschema.validate(content, preprocess_output_schema)` raises `jsonschema.ValidationError`, cause is `preprocess_output_schema_invalid`. Step 4: if the file parses and schema-validates but traversing the expected `pages[*].blocks[*].lines` / `pages[*].lines` structure yields zero lines OR raises an unexpected structural exception (e.g., missing key, wrong type in a field not caught by the schema), cause is `body_ocr_unreadable`. All four cause codes are members of the closed enum defined in Q31. An optional free-text `cause_detail` field may be populated with the exception message or a short diagnostic for operator use.

**Rationale**: The four-step cascade exactly covers the failure surface a human operator would diagnose: file missing, file not JSON, file fails contract, file structurally traversable but yields no useful OCR. The cascade order is correct — each step is predicated on the prior step passing (you cannot detect a JSON error in a missing file, nor a schema error in an unparseable file). Using the v1.3.0 `preprocess_output.schema.json` for step 3 ensures the gate rejects inputs that are semantically invalid, not just syntactically malformed.

**Alternatives considered**:
- A single `input_unreadable` catch-all cause (rejected: Q31 requires a closed enum with four distinct codes; a single cause code would eliminate operator diagnostics).
- Including `sidecar_missing` as an `unevaluable` cause (rejected: Q31 and FR-016 establish that absent sidecar maps to `not_applicable`, not `unevaluable`; `unevaluable` is strictly for unreadable INPUT files when a sidecar IS present).

---

## R-022.14 — Hard-error vs. `unevaluable` boundary (Q42)

**Decision**: Gate-time invariant violations — conditions that indicate an implementation bug rather than a bad input file — raise `SemanticGateInvariantError` (defined in `src/dartwing_ocr/evaluator/exceptions.py`). The exception propagates without being caught by the semantic-quality output layer, the document is excluded from `semantic_table_quality_metrics` aggregation, and no `semantic_table_quality` object is emitted for that document. The exception is not recorded as `unevaluable`. Concrete examples of conditions that raise `SemanticGateInvariantError`: the anchor function returns a span whose end index is less than its start index; the verdict aggregation function produces a status string that is not a member of the closed four-value enum; a normalization invariant breaks (i.e., `normalize(normalize(x)) != normalize(x)` for some input). The distinction from `unevaluable` is: `unevaluable` is reserved for bad INPUT (the sidecar is present but `preprocess_output.json` cannot be read); a hard error is an internal code invariant that the inputs being valid or invalid is irrelevant to.

**Rationale**: Q42 explicitly establishes the hard-error boundary to prevent gate-time bugs from being silently swallowed as `unevaluable` status. Allowing invariant violations to produce `unevaluable` would mean a latent implementation bug results in apparently-valid (though unevaluable) evaluation records, masking the defect. Raising a named exception that propagates to the top level makes the failure visible immediately and forces a fix before the run can be used as evidence.

**Alternatives considered**:
- Emitting `unevaluable` with cause `body_ocr_unreadable` for invariant violations (rejected: Q42 explicitly reserves `unevaluable` for input file failures; conflating implementation bugs with input errors would prevent operators from distinguishing a bad file from a broken gate).
- Using a generic `RuntimeError` instead of a named `SemanticGateInvariantError` (rejected: a named exception type enables targeted `except` clauses in tests and integration code; a generic `RuntimeError` would require string-matching the message to identify the failure class).

---

## R-022.15 — Calibration-folder exclusion implementation (Q39)

**Decision**: In `semantic_quality_metrics.py`, the per-document accumulation loop calls `corpus_pattern.is_scored_corpus_folder(folder_basename)` for each processed document before deciding whether to increment the aggregate counters. If `is_scored_corpus_folder` returns `False`, the document's semantic status entry `{document_id, semantic_table_quality_status, semantic_table_quality_passed}` is still appended to the per-document status list (so operators can see the gate ran), but none of the nine aggregate counter fields (`semantic_applicable_document_count`, `semantic_not_applicable_document_count`, `semantic_evaluable_document_count`, `semantic_passed_document_count`, `semantic_failed_document_count`, `semantic_unevaluable_document_count`, and the three `semantic_failed_check_counts` sub-fields) are incremented. The `semantic_table_quality_pass_rate` denominator is `semantic_evaluable_document_count` computed over scored documents only; a calibration folder's `passed` or `failed` status does not affect the pass rate. The `corpus_pattern.CANONICAL_FOLDER_PATTERN = re.compile(r"^inv_\d{3}_(easy|medium|hard)$")` constant is compiled once at module load and shared between `semantic_quality_metrics.py` and `validator/cli.py` via the `corpus_pattern.is_scored_corpus_folder` helper.

**Rationale**: Q39 requires calibration folders to appear in per-document status entries but be excluded from aggregate counts. The `corpus_pattern` module is the single authoritative implementation of the Q23 canonical-pattern allowlist; importing it in `semantic_quality_metrics.py` eliminates any risk of a duplicate regex definition drifting from the validator's pattern. The default-exclude semantics (unrecognized name → calibration) protect the scored corpus integrity without requiring explicit opt-out annotation per folder.

**Alternatives considered**:
- A separate `calibration_folders: set[str]` allowlist maintained alongside the scored corpus (rejected: requires a manual update for each new calibration sample, is error-prone, and diverges from the default-exclude principle that Q23 mandates).
- Fully excluding calibration folders from per-document status entries as well (rejected: Q39 explicitly requires calibration folders to appear in per-document entries so operators can inspect the gate output on calibration samples; only aggregate count exclusion is required).
