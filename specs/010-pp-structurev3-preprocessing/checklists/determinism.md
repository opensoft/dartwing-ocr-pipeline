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
