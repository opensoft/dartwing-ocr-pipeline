# Determinism Checklist: PPStructureV3 Preprocessing Migration

**Purpose**: Release-gate validation that the spec pins every axis the regenerated
corpus relies on to be byte-stable — threading, oneDNN, seeds, output ordering,
warning ordering, identifier minting, numeric precision, environment scope, and
reproducibility method — with enough clarity for the author to build and the
reviewer to gate against. Every item tests the requirements themselves, not the
implementation.
**Created**: 2026-04-22
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Author + Reviewer (PR)

## Determinism Scope & Axes

- [X] CHK001 Is "byte-identical" scoped explicitly to `preprocess_output.json` only, or does it implicitly cover debug side-artifacts (e.g., `page_*.png` under `--write-page-images`)? [Clarity, Spec §FR-004]
- [X] CHK002 Does FR-004 enumerate every persisted axis whose ordering AND value must be deterministic, or does it rely on a sample list ("including ...")? [Completeness, Spec §FR-004]
- [X] CHK003 Is the `tables[*]` array's determinism (both ordering and cell content) explicitly included or excluded from FR-004's guarantee? [Gap, Spec §FR-004]
- [X] CHK004 Are subsidiary artifact blocks (`quality`, `ingestion_sources`, `pipeline_version`) named as part of the determinism contract, or left implicit by virtue of passing the frozen v1.0.0 schema? [Gap, Spec §FR-004 §FR-008]
- [X] CHK005 Is the distinction between "byte-identical" (FR-004) and "byte-stable" (FR-020) deliberate or an inconsistency in terminology? [Consistency, Spec §FR-004 §FR-020]

## Threading & CPU Model

- [X] CHK006 Are threading constraints (`cpu_threads=1`, no multi-process) stated as determinism requirements, or left as implementation choices? [Clarity, Spec §FR-005]
- [X] CHK007 Is the rationale for single-threaded CPU execution tied explicitly to determinism (as opposed to cost or GPU avoidance) so future optimizers don't mistake it for a performance-only lever? [Consistency, Spec §FR-005]

## oneDNN / MKL-DNN / Paddle Runtime Flags

- [X] CHK008 Is the `enable_mkldnn=False` workaround stated in the normative spec, or only in research notes (FR-012) and the PRD? [Clarity, Spec §FR-005 §FR-012]
- [X] CHK009 Does the spec make clear whether `enable_mkldnn=False` is needed for determinism (scratch-buffer stability) in addition to bug-avoidance (PIR attribute converter)? [Ambiguity, Spec §FR-012 §Edge Cases]
- [X] CHK010 Is the set of PaddleOCR modules that must remain disabled (doc-orientation classify, dewarping, textline-orientation, formula, seal, chart) specified as a determinism requirement, or only as a scope constraint? [Consistency, Spec §FR-005]

## Random Seeds & Stateful Kernels

- [X] CHK011 Is "deterministic seeding" specified with a concrete seed value (e.g., `0`) or just the principle? [Clarity, Spec §FR-005]
- [X] CHK012 Are the stateful sources that must be seeded enumerated (paddle, numpy, Python `random`, any upstream C-level RNG in paddlex)? [Gap, Spec §FR-005]
- [X] CHK013 Is seeding required to happen before first engine construction (not after), and is this ordering stated? [Gap, Spec §FR-005]

## Output Ordering Rules

- [X] CHK014 Is the exact sort key for `blocks[*]` within a page specified (e.g., `(bbox.y0, bbox.x0, det_idx)`), or left to implementation? [Gap, Spec §FR-004 §US1 AC#3]
- [X] CHK015 Is the exact sort key for `raw_ocr_lines[*]` within a page specified, or conflated with block ordering? [Gap, Spec §FR-004]
- [X] CHK016 Is `reading_order` assignment (1..N from sorted order, dense, no gaps) stated as a rule rather than implied by the identifier scheme? [Clarity, Spec §FR-004 §US1 AC#3]
- [X] CHK017 Is the iteration order of `pages[*]` (page-number ascending) specified, or assumed from the `page_number` field? [Gap, Spec §FR-004]
- [X] CHK018 Does the spec address the fact that V3's layout/OCR output is NOT guaranteed list-order-stable upstream, so a post-sort is required? [Assumption, Gap, Spec §FR-004]

## Warning Array Ordering (FR-020)

- [X] CHK019 Is FR-020's two-level ordering rule (page-ascending outer, vocabulary-lexical inner) specified with enough precision to be mechanically sortable from a single-pass parser? [Clarity, Spec §FR-020]
- [X] CHK020 Is the sort position of aggregate warnings (e.g., `"ingestion_sources.paddleocr_vl: failure (all pages failed)"`) specified relative to page-scoped FR-020 warnings? [Gap, Spec §FR-020]
- [X] CHK021 Is the sort position of free-form runtime-error warnings (e.g., `"page N: OCR failed: <ExceptionClass>: <message>"`, `"page N: layout extraction failed: ..."`, rasterization-failed messages) specified relative to the FR-020 bracketed vocabulary? [Ambiguity, Spec §FR-020]
- [X] CHK022 Does FR-020 define the tie-break when multiple warnings share the same `(page, category_token)` pair, e.g., two `[unknown_layout_label]` warnings on one page? [Gap, Spec §FR-020]

## Identifier Minting

- [X] CHK023 Is the rule "identifiers (`p{page}_b{n}`, `p{page}_l{n}`) are assigned AFTER the post-sort, so `_b1` is always the first block in reading order" stated, rather than left as an implementation choice? [Clarity, Spec §FR-004 §US1 AC#3]

## Bbox & Numeric Stability

- [X] CHK024 Are bbox integer-rounding rules specified (floor/ceil direction, clipping to page bounds) so two runs produce identical integer bboxes when upstream floats drift by epsilon? [Gap, Spec §FR-004]
- [X] CHK025 Are `confidence` value precision rules specified (native float vs. rounded to N dp) so JSON serialization is byte-identical across runs? [Gap, Spec §FR-004]
- [X] CHK026 Is Unicode / encoding normalization specified for `text` and `document_text` fields (NFC vs. NFD) so OCR output with non-ASCII glyphs doesn't differ across runs? [Gap, Spec §FR-004]

## `pipeline_version` Determinism

- [X] CHK027 Is `pipeline_version`'s stability across runs with the same deps explicitly required (same deps → same string), not just "different when engine versions differ"? [Clarity, Spec §FR-008]
- [X] CHK028 Is the `<sha7>` weight-hash segment's deliberate placeholder value (`0000000` rather than a real hash) specified as a known compromise, so reviewers aren't surprised? [Ambiguity, Spec §FR-008]

## Rerun & Reproducibility Testing

- [X] CHK029 Is SC-003's verification method specified as sha256 over the serialized JSON file (vs. a JSON-canonical-form hash or field-by-field compare)? [Clarity, Spec §SC-003]
- [X] CHK030 Is the number of reruns required to satisfy SC-003 specified (twice, or an open-ended N > 2)? [Gap, Spec §SC-003]

## Cross-Environment Scope

- [X] CHK031 Does FR-004 clarify that "same code and dependency versions" holds determinism WITHIN one (OS, glibc, CPU ISA, Python version, dep-set) tuple and NOT across different environments? [Ambiguity, Spec §FR-004]
- [X] CHK032 Is cross-version determinism (different paddleocr versions producing different output) explicitly out of scope, referencing FR-008's `pipeline_version` change as the canonical signal? [Consistency, Spec §FR-004 §FR-008]

## Dependency Pinning & Model Weights

- [X] CHK033 Are dependency pins stated as a determinism dependency (lockfile exact-pin with version string in `requirements.txt`), not merely a project-declaration range in `pyproject.toml`? [Clarity, Spec §FR-009]
- [X] CHK034 Is the assumption stated that cached model weight files are byte-identical across hosters and across re-downloads (so a cache eviction doesn't silently alter output)? [Assumption, Gap, Spec §FR-015]

## Determinism Under Failure & Edge Cases

- [X] CHK035 Is determinism required under partial per-page failures (e.g., rasterization failure on page 2, success on 1 and 3) — i.e., must two runs produce identical warning ordering AND identical block/line arrays for the succeeded pages? [Coverage, Spec §FR-004 §Edge Cases]
- [X] CHK036 Is determinism required across process restarts (fresh engine init vs. warmed engine reused within one process), or only within one process? [Gap, Spec §FR-004]
- [X] CHK037 Is determinism under the concurrent-runs case specified, or safely deferred via the single-writer out-of-scope note? [Consistency, Spec §Edge Cases]

## Resolution notes (2026-04-23)

All 37 items closed after the `/speckit.analyze` remediation pass that landed the 12-finding fix set (commit `9125af3`). Most items are directly pinned in the spec; the remainder are pinned in adjacent feature artifacts that the reviewer sees alongside the spec. Soft resolutions that reviewers should be aware of:

- **CHK007** (single-threaded rationale): the link "byte-identical output → `cpu_threads=1`" is a chain between FR-004 and FR-005, not an explicit "for determinism" clause.
- **CHK012** (stateful RNG sources): FR-005 names only `paddle.seed(0)`; numpy / Python `random` are not in the inference path and need no seed.
- **CHK014–CHK017** (exact sort keys + page iteration): pinned in `plan.md` "Deferred plan-level decisions" and research §R-005, not in the spec itself.
- **CHK025** (confidence float precision): relies on Python's default repr-stable float serialization. Same-deps → same-floats → same-JSON bytes.
- **CHK028** (`<sha7>` placeholder): flagged "tolerated compromise" in research §R-007; spec uses placeholder shape.
- **CHK031** (cross-env scope): "same code and dependency versions" is treated as "same environment" by implication; cross-host (glibc/CPU ISA) determinism isn't a stated goal.
- **CHK032** (cross-version determinism): implicitly out-of-scope via FR-008's rule that different engine versions produce different `pipeline_version` strings.
- **CHK034** (cached-weight byte-identity): accepted assumption; paddlex's MD5-verified downloads back it. Drift would surface as SC-003 failure.
- **CHK035–CHK036** (determinism under partial failures + across process restarts): follow from FR-004's universal byte-identical guarantee; not called out separately.

No residuals at any severity level.

---

## Session 2026-04-23 Append — Post-Clarify Round 2+3 (CHK038–CHK055)

**Purpose**: Validate determinism-requirement quality after the seven clarifications that landed on 2026-04-22 Q16–Q19 (schema-first confidence handling, PP-OCRv5 default threshold, `tables[]` projection, debug PNG opt-in) and 2026-04-23 Q23–Q25 (FR-010 broad halt, FR-021 strict-current-shape, zero-overlap out-of-scope). Each item tests whether the determinism contract holds under the new rules — NOT whether the implementation does it right.

### Confidence Handling (FR-004 / R-013)

- [ ] CHK038 Is FR-004's confidence rule enumerated as a determinism axis alongside the existing bbox / text / ordering axes, or only as a value-sourcing rule? [Completeness, Spec §FR-004]
- [ ] CHK039 Is the retirement of the V2-era `max(0.0, min(1.0, float(...)))` clamp explicit in the requirement text, with invalid values becoming `null` instead of fabricated in-range values? [Clarity, Spec §FR-004]
- [ ] CHK040 Is the out-of-range confidence case (engine emits `1.2` or `-0.1`) specified to persist as `null` — no NaN substitution, no clamping, no drop — so two reruns produce identical null placement? [Coverage, Spec §FR-004]
- [ ] CHK041 Is the `confidence: null` persistence rule deterministic across reruns — same-engine, same-input → same null placement with no flip to `0.0`? [Consistency, Spec §FR-004]

### FR-022 PNG-Outside-FR-004 Scope

- [ ] CHK042 Does FR-004's byte-identical guarantee explicitly exclude `page_*.png` output per FR-022, or is the exclusion only implied by the "applies to `preprocess_output.json`" phrasing? [Clarity, Spec §FR-004 §FR-022]
- [ ] CHK043 Does the spec require determinism of `preprocess_output.json` to hold regardless of whether `--write-page-images` was passed — i.e., JSON byte-identity does NOT depend on the PNG-flag state? [Coverage, Spec §FR-022 §FR-004]

### FR-007 Engine-Default Threshold Stability

- [ ] CHK044 Is the PP-OCRv5 engine-default recognition threshold (FR-007) stated to be stable across runs on a given dep-pin — i.e., introspection produces the same value each time? [Assumption, Spec §FR-007]
- [ ] CHK045 Is the R-012 "probe-derived default" recording specified as a one-time commit-reviewer note, or a per-run verification that would introduce a CI-time read-back axis? [Clarity, Spec §FR-007, research §R-012]

### FR-021 Strict-Current-Shape `tables[]`

- [ ] CHK046 Does the spec require `tables[]` determinism to hold under the FR-021 strict-current-shape projection — i.e., schema widening via future AMENDMENTS does NOT silently change ordering or content of emitted fields? [Coverage, Spec §FR-021 §FR-004]
- [ ] CHK047 Is the iteration order of `table_res_list[*]` → `tables[*]` entries specified (e.g., block-order-within-page), or left to V3's upstream list-order behavior? [Gap, Spec §FR-021]
- [ ] CHK048 Is the discarded-content boundary (raw HTML, per-cell metadata, per-cell scores) enumerated with enough precision that two implementers would project identically? [Clarity, Spec §FR-021]
- [ ] CHK049 Is the determinism impact of a future AMENDMENTS widening the `tables[]` schema documented — does preprocessing's strict-current-shape rule guarantee byte-identical output until the code opts in? [Coverage, Spec §FR-021 §FR-004]

### Cross-Version / Cross-Regeneration Scope

- [ ] CHK050 Is "byte-identical" determinism scoped explicitly to one `pipeline_version` string (`v0.2.0+paddleocr3.5.0.*`), with cross-version diff expected and signaled by the FR-008 bump — or is the scope ambiguous? [Clarity, Spec §FR-004 §FR-008]
- [ ] CHK051 Is the interaction between a future R-012 engine-default threshold change (post-paddleocr-bump) and the FR-010 corpus regeneration sweep specified — does a moved default automatically trigger a new regeneration commit, or require a manual decision? [Coverage, Spec §FR-007 §FR-010] 
- [ ] CHK052 Are determinism axes for lockfile pinning stated as exact versions (`paddleocr==3.5.0`, `paddlex[ocr]==3.5.1`, `paddlepaddle==3.3.1`) — single exact pins, not ranges — in the requirement text, or only in plan.md Technical Context? [Traceability, Spec §FR-009]

### Zero-Overlap Edge Case (Session 2026-04-23 Q25)

- [ ] CHK053 Is determinism required under the zero-overlap edge case (lines > 0, blocks > 0, no bbox overlap) — i.e., does the "empty-text-per-block" path produce byte-identical output across runs? [Coverage, Spec §Edge Cases §FR-004]
- [ ] CHK054 Does the spec address whether the zero-overlap case's unwritten-text blocks (`block.text == ""`) affect `document_text` determinism — is the join-behavior stable? [Gap, Spec §Edge Cases §FR-004]

### Session-Resolution Traceability

- [ ] CHK055 Is the SC-003 sha256 verification method reiterated against the updated FR-004 (confidence float-or-null handling + PNG-out-of-scope) language, or only against the original FR-004? [Traceability, Spec §SC-003 §FR-004]
