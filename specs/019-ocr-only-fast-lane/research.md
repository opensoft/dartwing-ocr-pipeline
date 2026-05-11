# Research: OCR-Only Fast Lane For Vendor Identity

**Feature**: 019-ocr-only-fast-lane
**Date**: 2026-05-11
**Status**: Phase 0 — design decisions and rationale. Implementation details live in `plan.md` and `data-model.md`.

This document records the design decisions made at `/speckit.plan` time. The two `/speckit.clarify` resolutions from Session 2026-05-11 (FR-005 disposition and the combined two-threshold trigger) are captured in `spec.md`'s Clarifications section and are NOT re-litigated here — research decisions below build on those resolutions.

## R-019.1 — Activation surface (CLI flag + env-var fallback)

- **Decision**: `--preprocess-strategy <id>` on both `python -m ledgerlinc_ocr.preprocessing` and `python -m ledgerlinc_ocr.pipeline` with env-var fallback `LEDGERLINC_PREPROCESS_STRATEGY`. CLI wins when both are set; env-var literal value handled verbatim (no `.strip()`, no case normalization); empty-string env-value counts as unset.
- **Rationale**: Mirrors feature 014's `--preprocess-profile`, feature 016's `--gpu-warmup`, feature 017's `--module-set` / `--det-rec-variant`, and feature 018's `--raster-profile` / `--region-strategy` precedent exactly. The CLI / env-var resolution module (`preprocess_strategy_optin.py`) is a 1:1 sibling of `region_strategy_optin.py` so single-source-of-truth for precedence is preserved and reviewers can grep-compare the four opt-in modules for asymmetry.
- **Alternatives considered**:
  - A YAML config file declaring the strategy — rejected because all prior preset axes use the CLI-flag-with-env-var pattern and asymmetry would surprise operators.
  - A positional argument on the preprocess CLI — rejected because the existing surface is fully optional flags and a positional would break backward compatibility.

## R-019.2 — Closed vocabulary for `preprocess_strategy_id`

- **Decision**: Four values at landing:
  - `ppstructurev3` — invokes the existing PPStructureV3 layout-aware pipeline (the strategy active on `main` at landing time of feature 018; the GPU-lane default until FR-016 promotion).
  - `ocr-only-v1` — invokes PaddleOCR text-detection + text-recognition only; blocks reassembled by deterministic Y-axis line clustering (R-019.8).
  - `cpu-default` — emitted by `ppstructurev3@cpu` runs (any value of `--preprocess-strategy`; flag warn-and-proceed-ignored).
  - `stub-default` — emitted by stub-adapter runs (any value of `--preprocess-strategy`).
- **Rationale**: Mirrors feature 017 / 018 vocabulary shape exactly — two GPU-visible names + two identity defaults. The `v1` suffix on the OCR-only preset reserves room for `ocr-only-v2` (with tuned thresholds or a different aggregator) as a future feature without renaming this one.
- **Alternatives considered**:
  - Three values (no `cpu-default` and `stub-default`) — rejected because absence-as-regression-signal (FR-010) requires a stable non-null value on every run kind.
  - More OCR-only presets at landing (`ocr-only-fast`, `ocr-only-careful`, etc.) — rejected because the spec asks for **at least one** OCR-only preset, and shipping one well-tuned preset is lower-risk than three.

## R-019.3 — CPU and stub default identifier values

- **Decision**: `CPU_DEFAULT_PREPROCESS_STRATEGY = "cpu-default"` and `STUB_DEFAULT_PREPROCESS_STRATEGY = "stub-default"`. Distinct strings — never the same value on the two profiles.
- **Rationale**: Mirrors feature 017 / 018's identifier-string contract exactly (`cpu-default` vs. `stub-default`). Distinct strings preserve absence-as-regression-signal discrimination (FR-010): a stub-only test that suddenly emits `cpu-default` is a real regression rather than silently passing.
- **Alternatives considered**:
  - Re-using `ppstructurev3` as the CPU default — rejected because the CPU profile does not actually exercise the preset axis (it runs feature 018's CPU path with no strategy selection), so labeling it `ppstructurev3` would conflate "this profile selected the ppstructurev3 strategy" with "this profile is the CPU default".

## R-019.4 — GPU-lane default when no flag is set

- **Decision**: `LEGACY_PREPROCESS_STRATEGY = "ppstructurev3"`. A `ppstructurev3@gpu` run with no `--preprocess-strategy` flag set emits `preprocess_strategy_id = "ppstructurev3"` on `run_summary`.
- **Rationale**: This feature does not flip the GPU default. FR-016's quality gate decides promotion; until and unless the gate passes, the legacy `ppstructurev3` default holds (US6). Naming the no-flag GPU-lane value `ppstructurev3` (not `legacy`) matches the strategy name itself and makes the closed vocabulary smaller (three distinct GPU-visible labels would be ambiguous; one is unambiguous).
- **Alternatives considered**:
  - Naming the GPU-lane no-flag default `legacy` (mirroring feature 018's `raster_profile_id = "legacy"`) — rejected because feature 018's `legacy` is a *DPI* label, not a strategy name; here the natural label is the strategy itself. Also, after a future hypothetical promotion to `ocr-only-v1`, the operator would still be able to select `--preprocess-strategy=ppstructurev3` to get the legacy strategy back (FR-018), and naming that value `ppstructurev3` directly is clearer than naming it `legacy`.

## R-019.5 — Token-count threshold (combined-trigger arm 1)

- **Decision**: `OCR_ONLY_MIN_TOKEN_COUNT = 8` (integer). The non-whitespace token count is computed by splitting each detected line's recognized text on Unicode whitespace categories (Python's default `str.split()` honors Unicode whitespace) and counting non-empty pieces, then summing across all detected lines in the document's targeted region(s).
- **Rationale**: A typical invoice header (vendor name + address line + city/state/ZIP) yields at least 6–10 non-whitespace tokens; 8 sits at the conservative edge of "below this is genuinely too thin for vendor identity." The threshold is documented in `preprocess_strategies.py` and recorded in `research.md` here; tuning is a code change plus (potentially) a new `preprocess_strategy_id` value per FR-001. The benchmark run at landing (`tasks.md` ID T0xx) will validate this on the fixed 5-doc subset; if benchmarking shows 8 is too aggressive or too conservative, the value is adjusted before merge.
- **Alternatives considered**:
  - Character count (e.g., 32 characters) — rejected because token count is more naturally aligned with "vendor-identity evidence is too sparse" (1 character = 1 token in CJK but ~5 characters = 1 token in Latin scripts; tokens normalize that).
  - Tunable via an env var or CLI knob — rejected because FR-001 forbids free-form runtime overrides on the preset axis (tuning ⇒ new preset value).
  - A more elaborate stop-list-aware tokenizer — rejected because determinism + simplicity matter more than English-specific heuristics; Unicode whitespace splitting is locale-stable.

## R-019.6 — Detector-confidence aggregate (combined-trigger arm 2)

- **Decision**: Aggregation function is the **arithmetic mean** of PaddleOCR text-detector per-box confidence scores across all detected boxes in the document's targeted region(s). Threshold `OCR_ONLY_MIN_CONFIDENCE_MEAN = 0.60` (float, range [0.0, 1.0]). Sufficiency holds when `mean_confidence >= 0.60`. The mean is computed over per-box detector confidence (not per-line, not per-character), so a document with a few high-confidence boxes and many low-confidence boxes can still trip the trigger if its mean drops below 0.60.
- **Rationale**: Mean is the simplest deterministic aggregation function. Weighted-by-area was considered but rejected because it adds a tuning surface (which area metric: bounding-box area or detected text length proxy?) and the marginal accuracy gain is unclear. Median was considered but rejected because it discards detector-confidence variance information that the mean preserves. The 0.60 threshold sits at the low edge of "OCR det confidence is generally trustworthy" — PaddleOCR detector confidences above 0.6 reliably correspond to detectable text regions, while values below 0.6 are increasingly noisy. The benchmark validates this; if too aggressive, lower to 0.5; if too conservative, raise to 0.65.
- **Alternatives considered**:
  - Per-box confidence required to be `>= threshold` (worst-case, not mean) — rejected because a single low-confidence box on a noisy edge region would trigger fallback even on otherwise-clean documents.
  - Recognizer confidence (text-rec) instead of detector confidence — rejected because recognizer confidence depends on text content (recognizable English words score higher than receipt-style abbreviations), which would bias the rule against legitimate invoice text.

## R-019.7 — Zero-detection edge case

- **Decision**: When the OCR-only pass detects **zero** boxes on the targeted region, the eligibility check returns **INSUFFICIENT** unconditionally (the document falls back to `ppstructurev3`). The arithmetic-mean aggregation in R-019.6 is undefined on an empty input set; the check short-circuits to INSUFFICIENT before computing the mean.
- **Rationale**: Zero detections is the strongest possible "thin evidence" signal; falling back is uncontroversial. Making the rule explicit prevents an implementation bug where `numpy.mean([])` returns `nan` and the mean ≥ threshold comparison evaluates `nan >= 0.6` → `False` → INSUFFICIENT *anyway* — but only by accident. The explicit short-circuit is clearer to read and easier to test.
- **Alternatives considered**:
  - Letting the mean computation produce `nan` and relying on the comparison to fall back — rejected because relying on `nan` semantics is brittle and obscure.

## R-019.8 — Deterministic block reassembly from OCR-only lines

- **Decision**: After PaddleOCR returns the list of detected lines (each with `bbox`, `text`, `confidence`), reassemble them into the `preprocess_output.json` `blocks[]` shape as follows:
  1. Compute each line's vertical center `cy = (bbox.y_min + bbox.y_max) / 2` and median line height `H` over all lines on the page.
  2. Sort lines by `cy` ascending.
  3. Group lines into blocks greedily: two consecutive lines belong to the same block if their `cy` distance is `<= 1.5 * H`; otherwise start a new block. (The `1.5 * H` proximity threshold is a deterministic, page-local heuristic; it does NOT depend on PDF metadata, fonts, or any model output.)
  4. Within each block, sort lines by `cy` ascending; the block's `bbox` is the per-axis min/max envelope of its lines; the block's `text` is the lines' `text` joined with `"\n"`; the block's `block_type` is `"text"` (R-019.8 OCR-only output is always typed `"text"` since layout classification is not run); the block's per-block ordering rules in the existing schema hold (one block per cluster, deterministic order by `cy`).
- **Rationale**: Y-axis line clustering is the canonical pattern for grouping OCR lines into reading-order blocks when layout output is unavailable. The `1.5 * H` proximity threshold is robust to common font sizes and line spacing on invoice headers. The output preserves `block_type ∈ {"text", "title", "table", "figure", "header", "footer"}` from the existing schema (OCR-only always emits `"text"`); downstream stages (evidence packet, extractor, router) already accept blocks of type `"text"` and do not require layout-derived block types for vendor-identity extraction.
- **Alternatives considered**:
  - X-axis clustering (column detection) — rejected as out of scope for a vendor-identity-only slice; the header band on page 1 is single-column for the vast majority of invoices.
  - DBSCAN or similar density-based clustering — rejected because non-deterministic with respect to processing order if the library version changes; the greedy Y-axis rule is trivially reproducible.
  - Emitting one block per line (no clustering) — rejected because downstream evidence-packet block consolidation expects multi-line blocks for address/identity grouping.

## R-019.9 — Tokenization rule for R-019.5

- **Decision**: For the FR-005 token-count arm, tokens are computed by Python's `str.split()` on each line's recognized text (which honors Unicode whitespace categories: space, tab, newline, NBSP, ideographic space, etc.) and summing non-empty results across all lines in the targeted region. Empty strings, whitespace-only strings, and zero-character strings count as 0 tokens.
- **Rationale**: `str.split()` without arguments is locale-stable across Python versions and platforms; it splits on any whitespace and discards empty pieces. This is deterministic and easy to test.
- **Alternatives considered**:
  - Word-boundary regex (`\w+`) — rejected because it would treat punctuation-separated tokens differently across locales and depends on Python's Unicode category tables.
  - Character count instead of token count — addressed in R-019.5 (token count chosen for locale stability).

## R-019.10 — Engine construction and fallback orchestration

- **Decision**: Two singleton engines coexist in the same process under independent single-construction guarantees:
  - `preprocessing/ocr.py:_ENGINE` — the existing PPStructureV3 singleton (feature 015 FR-001).
  - `preprocessing/ocr_only.py:_OCR_ENGINE` — the new PaddleOCR (det+rec only) singleton, constructed lazily on first predict.
- For a `preprocess_strategy_id = ocr-only-v1` run that produces no fallbacks, **only** `_OCR_ENGINE` is constructed; `_ENGINE` (PPStructureV3) remains `None` for the entire process. For an `ocr-only-v1` run that produces ≥1 fallback, **both** engines are constructed during that run (PaddleOCR for all OCR-only attempts; PPStructureV3 for the fallback documents). Each engine still satisfies "exactly once per process" individually. For a `ppstructurev3` run, **only** `_ENGINE` is constructed; `_OCR_ENGINE` remains `None`. Both engines bind to the same `gpu:0` device when GPU is selected, satisfying the single-device-per-process guard (feature 015 FR-006) per-engine.
- Fallback orchestration: when the FR-005 eligibility check returns INSUFFICIENT for a document, the orchestrator (a) discards the partial OCR-only output for that document; (b) ensures PPStructureV3 is constructed (`_get_engine(device, ...)` on first fallback in the run); (c) re-runs the fallback document under the `ppstructurev3` strategy on the same engine; (d) accumulates the fallback document's rasterization + inference time into the same per-document `phase_timings.rasterization` and `phase_timings.per_page_inference` surfaces; (e) increments `run_summary.ocr_only_fallback_count` by 1.
- **Rationale**: Bypassing PPStructureV3 entirely on the OCR-only path is the only way to satisfy FR-002 ("MUST invoke PaddleOCR text detection and text recognition only. It MUST NOT invoke PPStructureV3's layout-detection, table-recognition, formula-recognition, or seal-recognition modules"). PaddleOCR exposes a pure-OCR API (`paddleocr.PaddleOCR`) that does det+rec without layout. The dual-singleton pattern preserves feature 015 FR-001's "exactly once per process *when invoked*" semantics for both engines; the spec FR-022 explicitly accommodates this with: *"When `preprocess_strategy_id = ocr-only-v1`, the PPStructureV3 engine MAY remain unconstructed for the run — the 015 FR-001 'exactly once per process' guarantee applies *to* PPStructureV3 *when* it is invoked, not as a requirement to invoke it."*
- **Alternatives considered**:
  - Invoking PPStructureV3 with all sub-modules disabled (`use_table_recognition=False`, `use_formula_recognition=False`, `use_seal_recognition=False`, `use_doc_orientation_classify=False`, `use_doc_unwarping=False`, `use_textline_orientation=False`) — rejected because PPStructureV3 still runs layout detection internally even with all toggles off; this would violate FR-002 ("MUST NOT invoke ... layout-detection ... modules").
  - Forking PPStructureV3 source — rejected as out of scope and unmaintainable.

## R-019.11 — Orthogonality with feature 018's region-strategy axis

- **Decision**: The OCR-only path uses `region_strategy.page_targeting(pdf_doc, page_index)` exactly as the PPStructureV3 path does today. When `region_strategy_id = header-first-v1` is active:
  - The OCR-only pass rasterizes only the page-1 header band, runs PaddleOCR det+rec on that crop, and emits a schema-valid `preprocess_output.json` with header-band blocks on page 1 and empty records on pages 2..N per feature 018 Q2.
  - If the OCR-only eligibility check (R-019.5 / R-019.6) trips, the fallback to `ppstructurev3` **preserves the active `region_strategy_id`** — `ppstructurev3` runs on the same header band on page 1, emitting header-band blocks. Feature 018's region-strategy-side fallback (region-first → full-page when the targeted region yields no `blocks[].text`) is INDEPENDENT and may still fire on the fallen-back document, in which case both `ocr_only_fallback_count` and `region_strategy_fallback_count` increment by 1 for that document.
- **Rationale**: FR-026 establishes the orthogonality contract. Preserving `region_strategy_id` on fallback is the simpler invariant: each axis owns its own disposition; fallback on one axis does not silently change another axis. The compound fallback (OCR-only → ppstructurev3 → full-page) is rare in practice but well-defined, and the two `*_fallback_count` fields together let operators distinguish each axis's contribution.
- **Alternatives considered**:
  - On OCR-only fallback, always switch `region_strategy_id` to `full-page` for the `ppstructurev3` retry — rejected because it would break the orthogonality invariant from FR-026 and surprise operators who set `header-first-v1` deliberately.

## R-019.12 — `UnknownPresetError` widening and exit code

- **Decision**: Extend `UnknownPresetError.preset_axis: Literal[…]` additively from the 4 values added by features 017/018 (`"module_set"`, `"det_rec_variant"`, `"raster_profile"`, `"region_strategy"`) to 5 values by adding `"preprocess_strategy"`. No new exception class. Reuse exit code `UNKNOWN_PRESET = 16` from feature 017's `pipeline/exit_codes.py`. The stderr message format `error: unknown <preset_axis>: <preset_value!r> — valid values are: <comma-separated valid_values>` is applied identically across all 5 axes.
- **Rationale**: Additive widening of the literal type is the minimal-change pattern feature 018 established. No CLI catch site needs modification — the existing uniform routing in `preprocessing/cli.py` and `pipeline/cli.py` catches `UnknownPresetError` once and exits with `error.exit_code`.
- **Alternatives considered**:
  - New exception class `UnknownPreprocessStrategyError` — rejected because the existing class is precisely shaped for this kind of "you passed me a bad value on a closed axis" error; a sibling class would duplicate code with no semantic gain.
  - New exit code — rejected because the meaning ("unknown preset value on a closed-vocabulary axis") is identical across all axes.

## R-019.13 — Fixed corpus subset for the FR-015 benchmark

- **Decision**: Same fixed 5-document subset features 017 and 018 used (R-017.11; R-018.13): `inv_001_easy`, `inv_002_easy`, plus the three additional documents established by R-017.11. The subset is referenced by per-doc folder ID in `quickstart.md` Appendix A at landing time.
- **Rationale**: Re-using the established subset makes feature 017 ↔ feature 018 ↔ feature 019 benchmarks directly comparable. The subset is intentionally small (5 docs) to keep manual reproduction practical.
- **Alternatives considered**:
  - The full 20-document corpus — rejected for benchmark turnaround time; the 5-doc subset is the established convention.
  - A different 5-doc subset chosen for OCR-only-relevant difficulty — rejected because it would break feature 017/018 comparability.

## R-019.14 — `RunSummary.SCHEMA_VERSION` bump

- **Decision**: Patch bump from `0.1.5` (set by feature 018) to **`0.1.6`** (set by this feature). The bump is codebase-level in `pipeline/timing.py`; the `kind: "run_summary"` JSON object's top-level `schema_version` field reflects it on every run regardless of profile or preset selection. The four canonical stage 1 artifact schemas (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`) and `contract_set_version` are unchanged.
- **Rationale**: Mirrors the established additive pattern (feature 014 0.1.0 → 0.1.1, 015 0.1.1 → 0.1.2, 016 0.1.2 → 0.1.3, 017 0.1.3 → 0.1.4, 018 0.1.4 → 0.1.5, this feature 0.1.5 → 0.1.6). Two additive fields qualify for a patch bump per the SemVer-style convention applied to this schema since feature 014. No existing field is renamed, removed, or retyped.
- **Alternatives considered**:
  - Minor bump (`0.1.5` → `0.2.0`) — rejected because the change is purely additive; a minor bump would imply a non-additive change and devalue the patch-bump signal.
  - No bump (silent addition) — rejected because the `SCHEMA_VERSION` field is the operator-visible signal that two additive fields are now expected.

## R-019.15 — `phase_timings.per_page_inference` semantics on OCR-only and on fallback

- **Decision**: The existing `phase_timings.per_page_inference` key continues to mean "time spent in inference for this page" — its definition is unchanged. On the OCR-only path the value reflects PaddleOCR det+rec time only (no PPStructureV3 layout time, no table/formula/seal modules). On a fallback document, the value reflects **combined wall-clock cost**: OCR-only attempt time (det+rec on the targeted region) + PPStructureV3 fallback time (layout-aware inference on the same region or full page per R-019.11). The same accumulation pattern applies to `phase_timings.rasterization` (R-018.10 precedent for combined cost on feature 018's region-first fallback).
- **Rationale**: Keeping the existing key's definition unchanged is required by FR-022 and the Edge Cases entry on `phase_timings` shape. Combined-cost accounting on fallback documents is the only way to satisfy SC-001 / SC-003's "measurable difference" requirement without introducing a new key — and adding a new key would violate FR-022 / Edge Cases.
- **Alternatives considered**:
  - Reporting only the successful pass's time (OCR-only's time for non-fallback documents; only PPStructureV3's time for fallback documents, ignoring the OCR-only attempt cost) — rejected because it understates the true wall-clock cost of fallbacks and would mislead the benchmark.
  - Adding a separate `phase_timings.ocr_only_attempt` key — rejected because FR-022 / Edge Cases forbids changing the `phase_timings` shape.

## R-019.16 — `--gpu-warmup` engine binding under `preprocess_strategy_id`

- **Decision** (resolved at `/speckit.clarify` Session 2026-05-11 Q3): The `--gpu-warmup` pass binds **only the engine implied by the selected `preprocess_strategy_id`**:
  - `preprocess_strategy_id = "ppstructurev3"` (or default / unset on the GPU lane) ⇒ warmup binds `_ENGINE` (PPStructureV3). Existing feature 016 behavior — unchanged.
  - `preprocess_strategy_id = "ocr-only-v1"` ⇒ warmup binds `_OCR_ENGINE` (PaddleOCR det+rec only). PPStructureV3 (`_ENGINE`) remains `None` after warmup.
  - `preprocess_strategy_id ∈ {"cpu-default", "stub-default"}` ⇒ warmup is profile-defined (CPU/stub paths don't exercise the OCR-only engine; the warn-and-proceed path nulls the strategy flag before warmup).
- **Warmup credit is not transferred across engines.** If a document later trips the FR-005 trigger on an `ocr-only-v1` warmup run and falls back to `ppstructurev3`, the PPStructureV3 cold-start (construction + first-predict) cost is included in that document's `phase_timings.per_page_inference` and `phase_timings.rasterization` per R-019.15's combined-cost rule. This is the honest measurement — the run paid for the engine it actually used at warmup, and the fallback document pays for the engine it triggered post-warmup.
- **`phase_timings.warmup` value semantics**: measures the single warmed engine's warmup cost only (PaddleOCR warmup time on `ocr-only-v1`; PPStructureV3 warmup time on `ppstructurev3`). On `ocr-only-v1`, `phase_timings.warmup` is NOT the sum of "would-have-been" PPStructureV3 warmup + actual PaddleOCR warmup; the unconstructed engine contributes zero to the warmup line.
- **Rationale**: Matches FR-022's explicit exception that PPStructureV3 MAY remain unconstructed under `ocr-only-v1`. Smallest cost — an `ocr-only-v1` run with zero fallbacks doesn't pay for a PPStructureV3 warmup it never uses. Mirrors the "exactly once *when invoked*" semantics across both engines. Operators who want pre-warmed PPStructureV3 for the fallback case can run a `ppstructurev3` warmup explicitly (different invocation); the OCR-only path is unambiguous about which engine it warmed.
- **Alternatives considered**:
  - Warm both engines on `ocr-only-v1` — rejected because it doubles warmup cost on the most common case (an OCR-only run with zero fallbacks). Also violates the "warmup follows the strategy" mental model.
  - Make `--gpu-warmup` a no-op on `ocr-only-v1` — rejected because it would regress feature 016's warmup benefits on the OCR-only path itself (the OCR-only engine would always cold-start on the first document).
  - Lazy hybrid (warm OCR-only eagerly, warm PPStructureV3 just-in-time on first fallback) — rejected because it muddles `phase_timings.warmup` semantics (one engine's warmup is in `warmup`; the other's is folded into `per_page_inference`) and creates an inconsistent accounting story.

## Appendix A — Benchmark numbers (filled at landing time)

The FR-015 benchmark cells are: `ppstructurev3` baseline AND `ocr-only-v1` candidate, both on the fixed 5-doc subset (R-019.13). Per-document `phase_timings.rasterization`, `phase_timings.per_page_inference`, `phase_timings.total`, and per-doc evaluator metrics will be recorded here. (Verification deferred per FR-025 if workstation GPU is unavailable at merge; deferral captured in `tasks.md` and `quickstart.md` Appendix B.)

## Appendix B — Quality-gate evidence (filled at landing time)

The FR-016 promotion gate is computed from existing evaluator outputs:
1. Per-corpus aggregate vendor-identity field score from `evaluation_run_summary.json`.
2. Per-document pass count per `docs/stage1-vendor-identity/scoring.md`.

Both metrics are recorded here for the `ocr-only-v1` candidate alongside the `ppstructurev3` baseline on the same fixed 5-doc subset. The gate passes only if `candidate >= baseline` on BOTH metrics. (Verification deferred per FR-025 if workstation GPU is unavailable at merge.)
