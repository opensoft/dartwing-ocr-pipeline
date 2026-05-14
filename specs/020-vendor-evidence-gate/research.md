# Phase 0 Research: Deterministic Vendor-Identity Signals And Early Accept Gate

This document records the decisions made in Phase 0 of `/speckit.plan` for feature 020. Each `R-020.x` entry follows the Decision / Rationale / Alternatives format. References to FR-### / SC-### / Clarifications point at `spec.md`. The four `/speckit.clarify` resolutions are the load-bearing inputs to this phase.

---

## R-020.1 — CLI flag name and env-var fallback for the skip-fallback opt-in

**Decision**: A single boolean opt-in flag `--evidence-gate-skip-fallback` (off by default) on both `python -m ledgerlinc_ocr.preprocessing` and `python -m ledgerlinc_ocr.pipeline`, with env-var fallback `LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK`. Precedence: CLI wins when both are set; empty-string env = unset. Truthy values: `"1"`, `"true"`, `"yes"`, `"on"` (case-insensitive). Falsy values: `"0"`, `"false"`, `"no"`, `"off"`, `""`, unset. Any other value rejects with the same error path the existing `_PRESET_ENV_VAR` helpers use.

**Rationale**: Mirrors feature 016 `--gpu-warmup` / feature 017 `--module-set` / `--det-rec-variant` / feature 018 `--raster-profile` / `--region-strategy` / feature 019 `--preprocess-strategy` exactly. The CLI-wins-with-empty-string-env precedence keeps composition predictable when operators script the pipeline. Boolean opt-in (rather than a value-bearing preset axis) is correct here because the registry has size one at landing — there is no `--evidence-gate <id>` selection to make. The flag has exactly two states: opt-in active or not.

**Alternatives considered**:
- A value-bearing `--evidence-gate <id>` axis (rejected: the closed vocabulary at landing has one entry, so the flag would have only `v1` as a valid value and no selection power).
- Env-var-only activation (rejected: breaks the CLI-first pattern features 014–019 established; operators wouldn't be able to override the env per invocation).
- Defaulting the opt-in to on (rejected: violates FR-012 / SC-008 — promotion of a non-default behavior requires the FR-016 quality gate to pass first, which is a follow-up activity outside this feature's landing).

---

## R-020.2 — `evidence_gate_id` closed vocabulary at landing

**Decision**: One entry — `"v1"`. The codebase exposes a closed registry `EVIDENCE_GATES = {"v1": EvidenceGate(...)}` in `preprocessing/evidence_gate.py`. Future presets (`"v2"`, `"v3"`, ...) are added by code change with their own decision-table bodies and would land their own `--evidence-gate <id>` flag at that time. The active `evidence_gate_id` at landing time is the constant `EVIDENCE_GATE_ID_DEFAULT = EVIDENCE_GATE_ID_V1 = "v1"` exposed from `preprocessing/identifiers.py`.

**Rationale**: FR-005 requires the gate-rule body to be versioned and selectable via an `evidence_gate_id` preset. At landing time we ship exactly one preset; there is no selection mechanism to define yet. This matches feature 017's pattern of shipping `module_set_id ∈ {"original", "minimal-text-only"}` with a default that didn't change until promotion (R-017.3 / R-017.5). The registry shape is future-extensible (additive code change to add a new preset, additive `--evidence-gate <id>` flag added when there's a real selection to make).

**Alternatives considered**:
- Ship two presets at landing — a `"strict-v1"` and a `"lenient-v1"` (rejected: scope creep — Q4 already pins the page-1 header band, Q3 pins the run_summary surface; a second preset would require its own quality-gate evaluation per FR-016 with no additional value at landing).
- No `evidence_gate_id` field on `run_summary` at all (rejected: FR-010 requires the field as a regression signal; absence is itself a regression).
- Use a numeric version (`1`, `2`, ...) instead of `"v1"` (rejected: FR-010 requires a human-readable string, not an opaque numeric hash; `"v1"` matches the spec's wording exactly).

---

## R-020.3 — The five FR-001 signals

**Decision**: At landing the signal set comprises exactly five signals over the page-1 header band (R-020.5 coordinate scope):

| # | Signal | Type | Definition |
|---|---|---|---|
| 1 | `vendor_name_candidate_count` | `int` | Count of tokens in the page-1 header band that match the vendor-name-candidate heuristic: (a) at least two characters long AND (b) starts with an uppercase letter OR is title-case OR is all-caps AND (c) is not a pure number AND (d) is not in the small stop-word set `{"INVOICE", "BILL", "TAX", "DATE", "PAGE", "NUMBER", "TOTAL", "AMOUNT", "DUE", "PAYMENT", "FROM", "TO"}` (case-insensitive). Token boundaries are whitespace-separated within the recognized text strings emitted on each block/box. |
| 2 | `header_band_token_density` | `int` | Total count of non-whitespace tokens in the page-1 header band, where tokenization is whitespace-based on the recognized text strings emitted on each block/box. |
| 3 | `ocr_detection_confidence_mean` | `float` (range `[0.0, 1.0]`, `0.0` when the band is empty) | Arithmetic mean of `confidence` values across all detection boxes whose y-coordinate falls in the page-1 header band. |
| 4 | `business_suffix_present` | `bool` | `True` if any token in the page-1 header band matches the business-suffix regex (R-020.4) after case-folding. |
| 5 | `tax_id_shaped_present` | `bool` | `True` if any token in the page-1 header band matches the EIN regex OR the VAT regex (R-020.4). |

All five values are computed by `EvidenceGate.evaluate(preprocess_output_dict, *, y_threshold_fraction=0.25)` in a single deterministic pass over the file's `pages[0]` content. Tokenization is whitespace-based with NFKC Unicode normalization applied to the recognized text before tokenizing (consistent across platforms and locales). Empty band ⇒ `vendor_name_candidate_count=0`, `header_band_token_density=0`, `ocr_detection_confidence_mean=0.0`, `business_suffix_present=False`, `tax_id_shaped_present=False`.

**Rationale**: This is the minimal set required by FR-001's floor plus the two clarify-pinned presence signals (Clarifications Q2). The three numeric signals give content-density and confidence inputs; the two boolean signals give high-precision structural-evidence inputs. The vendor-name-candidate heuristic is deliberately conservative (uppercase / title-case + stop-word exclusion) to avoid false positives on noise tokens. The confidence-mean is the same aggregation feature 019 uses for its FR-005 trigger (R-019.6), which keeps the math consistent across the two surfaces (one operator-facing gate decision, one preprocessing-time fallback trigger).

**Alternatives considered**:
- Aggregate non-whitespace character count instead of token count (rejected: density-by-tokens is more interpretable for operators reading run_summary).
- Median confidence instead of mean (rejected: feature 019 uses mean for its FR-005 trigger; consistency reduces operator confusion).
- Adding telephone-shaped, email-shaped, postal-address-shaped tokens (rejected at Clarifications Q2: format-sensitive, deferred to a follow-on feature).

---

## R-020.4 — Regex patterns for FR-001 signals

**Decision**: Three module-level regex constants in `preprocessing/evidence_gate.py`, compiled once at module load:

```python
BUSINESS_SUFFIX_RE = re.compile(
    r"(?i)\b(LLC|Inc|Incorporated|Ltd|Limited|GmbH|S\.A\.|S\.A\.S\.|Corp|Corporation|Co\.)\b"
)
TAX_ID_EIN_RE = re.compile(r"\b\d{2}-\d{7}\b")
TAX_ID_VAT_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{2,12}\b")
```

`business_suffix_present` matches against `BUSINESS_SUFFIX_RE`. `tax_id_shaped_present` matches against `TAX_ID_EIN_RE` OR `TAX_ID_VAT_RE`. Matching is whole-token only (the `\b` boundary handles this); the `\.` escapes prevent dot-class wildcards. Patterns are case-insensitive only for the business-suffix list (legitimately variant cased in invoices — `inc.` / `Inc.` / `INC.`); tax-id patterns are case-sensitive because EIN is numeric and VAT is conventionally uppercase.

**Rationale**: These patterns are deterministic, locally-evaluable, and capture the most common vendor-identity tokens without requiring NLP. The `S.A.` and `S.A.S.` patterns intentionally include French/Spanish entity types since the corpus may contain non-US invoices. VAT patterns are conservative — they match the EU canonical shape (`[A-Z]{2}` country prefix + alphanumeric body); they will produce some false positives on order numbers, but that's acceptable for a presence signal feeding a residual `borderline` decision.

**Alternatives considered**:
- `(?i)` on the tax-id patterns (rejected: EIN is numeric, no case variation possible; VAT inflates false positives without case anchoring).
- Use word-boundary lookarounds instead of `\b` (rejected: adds regex complexity without precision gain).
- Add UK-specific NI numbers / SSN-shaped patterns (rejected: PII risk and not needed for vendor-identity; SSN-shaped patterns would actually FAIL the test corpus per the PII screening checklist in `labeling-guide.md`).

---

## R-020.5 — Page-1 header-band coordinate filter

**Decision**: A token is "in the page-1 header band" iff:
- it belongs to `pages[0]` (zero-indexed page 1), AND
- its bbox top y-coordinate (after normalization to fraction-of-page-height) is strictly less than `Y_THRESHOLD_FRACTION = 0.25` of `pages[0].height_pt`.

The y-fraction comparison is `bbox_top_y / page_height < 0.25`. The default threshold `0.25` is a module-level constant `Y_THRESHOLD_FRACTION = 0.25`; the value is plan-time pinned but kept as a named constant so a future preset (`v2`) can adjust it via a new `EvidenceGate` entry. The coordinate origin convention follows `preprocess_output.json` schema: top-left origin, y increases downward, units `pt` (PDF points).

Multi-page documents: tokens on `pages[1..N]` are NOT considered by any of the five signals. If a document has only one page, the band is the top quarter of that page. If `pages[0]` is empty (zero blocks/boxes), the band is empty and all five signals reach their negative level (per R-020.3).

**Rationale**: Clarifications Q4 selected page-1 header band only. The top-25% fraction is the most common header-band depth in invoices on the corpus subset (per feature 018's header-first-v1 calibration); using a fraction rather than an absolute point value makes the filter dimension-invariant across different page sizes (US Letter, A4, Legal). The strict-less-than comparison places the band boundary cleanly: tokens exactly at the boundary belong to the page body, not the header.

**Alternatives considered**:
- Use feature 018's exact `header-first-v1` crop coordinates instead of a fixed fraction (rejected: the gate must work even when feature 018's `region_strategy_id` is `full-page` — the band must be a property of the gate's evaluation, not of the preprocessing strategy).
- Use absolute y-coordinate threshold in points (e.g., `top 200pt`) (rejected: not dimension-invariant; would mis-band A4 vs. Legal pages).
- Make `Y_THRESHOLD_FRACTION` operator-configurable via env var (rejected: violates FR-005's "future iterations of the rule add new preset values, not runtime parameter knobs").

---

## R-020.6 — V1 decision table

**Decision**: The v1 gate-rule body is an explicit boolean expression over the five signals:

```python
def v1_decide(signals: FiveSignalSet) -> Literal["sufficient", "borderline", "insufficient"]:
    has_name = signals.vendor_name_candidate_count >= 1
    has_density = signals.header_band_token_density >= 8
    has_confidence = signals.ocr_detection_confidence_mean >= 0.70
    has_suffix = signals.business_suffix_present
    has_tax_id = signals.tax_id_shaped_present

    if has_name and has_density and has_confidence and (has_suffix or has_tax_id):
        return "sufficient"
    if (not has_name) and (not has_density) and (not has_confidence) and (not has_suffix) and (not has_tax_id):
        return "insufficient"
    return "borderline"
```

Equivalently, the decision table:

| `has_name` | `has_density` | `has_confidence` | `has_suffix OR has_tax_id` | Decision |
|---|---|---|---|---|
| T | T | T | T | `sufficient` |
| F | F | F | F (i.e., both suffix and tax-id false) | `insufficient` |
| any other combination | | | | `borderline` |

Thresholds pinned at landing: `DENSITY_THRESHOLD = 8` tokens, `CONFIDENCE_THRESHOLD = 0.70`. Comparisons are inclusive on the high side (`>=`) so the boundary token-count of exactly 8 and the boundary confidence of exactly `0.70` both qualify as positive.

**Rationale**: The conjunction-on-`sufficient` rule is precision-first — it requires both a real candidate name AND density AND confidence AND a structural-evidence presence signal. This matches the spec's conservative-miss philosophy (Clarifications Q4 narrative). The all-negative-on-`insufficient` rule is symmetric — it only fires when every signal at its negative level — so `borderline` becomes the residual catch-all and naturally absorbs documents with partial evidence. The `8`-token density threshold is the empirical median over the feature 017/018/019 benchmark subset's header-band token counts (it's a generous floor that still excludes near-blank pages). The `0.70` confidence threshold is the same level feature 019's R-019.6 fallback trigger uses, so the gate's `has_confidence` signal aligns with the existing pipeline's confidence-aggregation surface.

**Alternatives considered**:
- Weighted-score gate (e.g., score = `2*has_name + has_density + has_confidence + 0.5*has_suffix + 0.5*has_tax_id`; thresholds on score) (rejected: harder to re-derive from recorded signals; less explainable on `run_summary`; the explicit-table form is what the spec assumption block called out and what `borderline` as residual requires).
- Strict 5/5 conjunction for `sufficient` (require both `has_suffix` AND `has_tax_id`) (rejected: too strict — many legitimate vendor blocks have a suffix OR a tax-id, not both).
- Lower `DENSITY_THRESHOLD = 4` (rejected: would trip `sufficient` on title-only blocks; calibration during benchmark may revise upward per R-020.14).
- Lower `CONFIDENCE_THRESHOLD = 0.60` (matching feature 019's FR-005) (rejected: feature 019's threshold is for fallback-triggering, where lower confidence means re-run; the gate's threshold is for sufficiency-claiming, where higher confidence is required).

---

## R-020.7 — Gate evaluation order: when, where, and how many times per document

**Decision**: For every document, the gate is evaluated on the document's FINAL `preprocess_output.json` and that evaluation is the one recorded on `run_summary`. Additionally, when shape (b) skip-fallback is engaged (opt-in active AND `preprocess_strategy_id = "ocr-only-v1"` AND feature 019 FR-005 trigger fires), the gate is evaluated ONCE MORE on the OCR-only **candidate** output PRIOR to the fallback decision; that candidate-output evaluation is used only to decide suppression vs. fallback and is not recorded directly on `run_summary`.

Per-document evaluation count:
- Non-OCR-only run (preprocess_strategy = `ppstructurev3` or any non-OCR strategy): gate evaluates **once** (on the final `preprocess_output.json`).
- OCR-only run with skip-fallback opt-in INACTIVE: gate evaluates **once** (on the final `preprocess_output.json`, which is OCR-only when FR-005 doesn't trigger and PPStructureV3 when it does — feature 019 logic is unchanged).
- OCR-only run with skip-fallback opt-in ACTIVE and FR-005 trigger does NOT fire on candidate: gate evaluates **once** (on the OCR-only candidate, which becomes the final output).
- OCR-only run with skip-fallback opt-in ACTIVE and FR-005 trigger fires, gate on candidate is `sufficient`: gate evaluates **once** on the OCR-only candidate, the candidate is kept as final, the same evaluation is the recorded decision. `evidence_gate_suppressed_fallback_count` increments by 1.
- OCR-only run with skip-fallback opt-in ACTIVE and FR-005 trigger fires, gate on candidate is `borderline` or `insufficient`: gate evaluates **twice** — once on the candidate (for the suppression decision, which fails), then once on the post-fallback PPStructureV3 final output (for the recorded decision). `ocr_only_fallback_count` increments by 1 per feature 019; `evidence_gate_suppressed_fallback_count` does NOT increment.

**Rationale**: An operator re-deriving the recorded decision from `preprocess_output.json` + the documented v1 table on disk gets the right answer only if the recorded evaluation is over the final file. The two-evaluation case (when suppression doesn't fire on a falling-back doc) is an acceptable overhead because the gate is cheap (pure Python regex + numeric work on the page-1 header band) and at most one extra evaluation per fallback-triggered document. R-020.8 derives the suppression predicate.

**Alternatives considered**:
- Always record the gate decision over the OCR-only candidate (rejected: when fallback fires, the candidate is discarded — recording a decision against a discarded file is unauditable from disk).
- Evaluate gate on every document twice (once on candidate, once on final) regardless of fallback (rejected: doubles the gate work for the common no-fallback case).
- Skip the candidate-output gate evaluation and decide suppression on a simpler proxy (rejected: drifts from spec language "gate decision `sufficient` on an OCR-only run"; would also weaken the predicate's auditability).

---

## R-020.8 — Skip-fallback suppression predicate

**Decision**: The suppression predicate (executed in `preprocessing/pipeline.py` after the OCR-only candidate output is produced):

```python
def should_suppress_fallback(*,
    preprocess_strategy_id: str,
    fr_005_trigger_would_fire: bool,
    opt_in_active: bool,
    candidate_gate_decision: Literal["sufficient", "borderline", "insufficient"],
) -> bool:
    return (
        preprocess_strategy_id == "ocr-only-v1"
        and fr_005_trigger_would_fire
        and opt_in_active
        and candidate_gate_decision == "sufficient"
    )
```

All four conjuncts must be true. The function is pure — its inputs come from preprocessing-pass state (the active strategy id, the FR-005 trigger output for this document, the resolved opt-in boolean, the candidate-gate decision). No model in the loop. `evidence_gate_suppressed_fallback_count` increments by exactly `1` per document whenever this predicate returns `True`.

**Rationale**: FR-009 requires that only `sufficient` MAY trip the optional behavior. The four-conjunct predicate makes this explicit and re-derivable from preprocessing-pass inputs alone (R-020.7). Returning a `bool` rather than a more complex disposition keeps the integration with feature 019's existing fallback logic surgical (a single early-exit in the if-then-else that decides whether to discard the OCR-only output).

**Alternatives considered**:
- Have the gate module decide suppression directly (rejected: violates the separation between gate-rule body and pipeline orchestration; the gate produces a decision, the pipeline acts on it).
- Allow `borderline` to suppress fallback under a separate opt-in (rejected: FR-009 forbids it; would also create a non-monotonic gate where `borderline` is treated as stronger than `borderline` in other contexts).
- Increment `evidence_gate_suppressed_fallback_count` for every `sufficient` document, not just suppression events (rejected: spec definition of the counter is "OCR-only-fast-lane documents whose FR-005 fallback was suppressed"; a `sufficient` document whose FR-005 trigger didn't fire is not a suppression event).

---

## R-020.9 — `RunSummary.SCHEMA_VERSION` patch bump 0.1.6 → 0.1.7

**Decision**: Bump `SCHEMA_VERSION = "0.1.6"` → `"0.1.7"` in `pipeline/timing.py`. This is a patch-level bump for four additive top-level fields. The bump is codebase-level only and lives next to the existing `RunSummary` dataclass; no JSON Schema file is touched.

**Rationale**: Continues the established additive-only pattern from features 014/015/016/017/018/019. Patch bump (third segment) signals that the change is purely additive — existing consumers reading the previous fields by name continue to work; only new consumers need to read the new fields. The four canonical stage 1 artifact schemas, `contract_set_version`, and `pipeline_version` are unchanged (Constitution II / FR-020 / SC-010).

**Alternatives considered**:
- Minor bump 0.1.6 → 0.2.0 (rejected: minor bumps signal a breaking shape change; this is purely additive).
- Document the bump in `docs/stage1-vendor-identity/schemas.md` (rejected: `run_summary` is not a stage 1 output contract; QG#2 explicitly does not apply per Constitution II discussion in `plan.md`).
- Add `RUN_SUMMARY_FEATURES = {..., "evidence-gate"}` constant alongside the bump (rejected: not needed; the bump itself is the signal, and the four new fields are self-describing).

---

## R-020.10 — Run-summary additive field shapes

**Decision**: Four new top-level fields on the existing `kind: "run_summary"` stdout line, emitted in this deterministic order after feature 019's two fields:

```json
{
    "kind": "run_summary",
    "schema_version": "0.1.7",
    ...,
    "preprocess_strategy_id": "...",       // feature 019, unchanged
    "ocr_only_fallback_count": 0,           // feature 019, unchanged
    "evidence_gate_id": "v1",
    "evidence_gate_state_counts": {
        "sufficient": 0,
        "borderline": 0,
        "insufficient": 0
    },
    "evidence_gate_documents": [
        {
            "document_id": "inv_001_easy",
            "decision": "sufficient",
            "signals": {
                "vendor_name_candidate_count": 3,
                "header_band_token_density": 14,
                "ocr_detection_confidence_mean": 0.84,
                "business_suffix_present": true,
                "tax_id_shaped_present": false
            }
        }
    ],
    "evidence_gate_suppressed_fallback_count": 0
}
```

Defaults when no documents reached the gate (e.g., a stub-adapter run with no preprocessing): `evidence_gate_id = "v1"`, `evidence_gate_state_counts = {"sufficient": 0, "borderline": 0, "insufficient": 0}`, `evidence_gate_documents = []`, `evidence_gate_suppressed_fallback_count = 0`. Always emitted regardless of profile (FR-008 always-emit pattern). `evidence_gate_state_counts` is emitted as an object even when all three counters are zero, NOT as a sparse object.

**Rationale**: Clarifications Q3 pinned shape (a) — single `run_summary` line carrying aggregate counters AND per-document table. The `signals` nested object inside each `evidence_gate_documents` element keeps signal-recording self-contained per document, which is what SC-012 requires for "documented signals + v1 table re-derive recorded decision". The deterministic ordering (counters before per-doc table before suppression counter) makes diffing two run_summary lines straightforward.

**Alternatives considered**:
- Flatten the signals into the per-doc record (e.g., `"signals_vendor_name_candidate_count": 3`) (rejected: harder to grep/jq for the full signal set on one document; the nested object is cleaner).
- Use `null` instead of `0` / `[]` defaults (rejected: contradicts the FR-008 always-emit-with-default pattern features 018/019 established).
- Emit `evidence_gate_state_counts` as a sparse object (only present states) (rejected: forces consumers to handle missing keys; default-zero is the established pattern from feature 018's `region_strategy_fallback_count` and feature 019's `ocr_only_fallback_count`).

---

## R-020.11 — `document_id` semantics in `evidence_gate_documents`

**Decision**: `document_id` is the per-document folder name relative to the corpus root, as used by feature 007's evaluator and feature 019's `ocr_only_fallback_count` tracking. Examples: `"inv_001_easy"`, `"inv_002_easy"`, `"inv_006_layout_table"`. The string is sourced from `corpus_run.py`'s existing per-document iteration and matches `evaluation_run_summary.json`'s per-document identifier so the FR-016 quality-gate evaluation can join on it without translation. Single-doc runs (via `runner.py`) emit a single-element `evidence_gate_documents` array with the `document_id` derived from the input folder's basename.

**Rationale**: Reusing the existing per-document identifier keeps the gate's per-doc surface joinable with the evaluator's per-doc surface (FR-016 / SC-008 needs both metrics on the same `document_id`). Avoiding a new identifier eliminates a translation layer that would otherwise need to live in the evaluator-facing path.

**Alternatives considered**:
- Use the source PDF's filename without extension (rejected: identical to the folder name in practice but introduces ambiguity when the corpus structure ever diverges).
- Use a UUID per document per run (rejected: not stable across reruns, violates SC-001's "byte-identical signal values" requirement when the same document is processed twice).

---

## R-020.12 — CPU/stub warn-and-proceed for `--evidence-gate-skip-fallback`

**Decision**: When `--evidence-gate-skip-fallback` (or its env-var fallback) resolves to `True` AND the active profile is NOT `ppstructurev3@gpu` (i.e., CPU profile, stub adapter, or any future non-GPU profile), `preprocessing/cli.py` and `pipeline/cli.py` emit ONE stderr warning line and proceed with the run unchanged. The warning line is produced by `evidence_gate_skip_fallback_warn_message(active_profile)` and contains the literal grep-able marker `--evidence-gate-skip-fallback ignored:`. Exit code is unchanged from the no-flag run. The four `run_summary` evidence-gate fields are still emitted (the gate itself runs on CPU per FR-014).

The warn fires only when the opt-in is GPU-relevant but the profile isn't GPU. It does NOT fire when:
- The opt-in is unset (the default state — no warn needed).
- The active profile is `ppstructurev3@gpu` but `preprocess_strategy_id` is not `ocr-only-v1` (the suppression has no candidate to act on, but this is a GPU run so the flag wasn't ignored — it's just a no-op for this document set).
- The active profile is `ppstructurev3@gpu` and `preprocess_strategy_id` is `ocr-only-v1` but no document triggers FR-005 (the suppression has no fallback to suppress; not a warn condition).

**Rationale**: This is the exact warn-and-proceed pattern features 016 / 017 / 018 / 019 established (R-019.1 / R-019.4). Silent ignore would be a footgun (operators wouldn't know their flag was ineffective on a CPU profile); rejecting the flag would break the orthogonal-CLI-composition pattern. Restricting the warn to true non-GPU profiles avoids spurious warns on legitimate GPU runs that happen to have no documents tripping FR-005.

**Alternatives considered**:
- Reject the flag with a non-zero exit on CPU (rejected: breaks orthogonal CLI composition; users scripting CLI invocations across profiles can't pass the flag uniformly).
- Silently ignore (rejected: makes regressions undetectable; the spec's FR-013 mandates a warn).
- Always warn even on GPU runs where the suppression doesn't fire (rejected: spurious noise on legitimate GPU runs).

---

## R-020.13 — Benchmark subset for FR-015

**Decision**: The FR-015 benchmark exercises the same fixed 5-doc subset features 017 / 018 / 019 used (per R-017.11 / R-018.13 / R-019.13): `inv_001_easy`, `inv_002_easy`, plus the three originally chosen by R-017.11 (whichever they are at landing time — `tasks.md` is normative if the inventory changes between landing dates). The benchmark records, per document and per configuration:
- Per-document `evidence_gate_documents` records (decision + the five signal values).
- `evidence_gate_state_counts` distribution across the 5 docs.
- `evidence_gate_suppressed_fallback_count` (≥ 1 expected on at least one document with the opt-in active and a `sufficient` decision).
- Per-document and per-corpus latency-or-quality delta vs. the legacy default (no opt-in active).

**Rationale**: Reusing the same 5-doc subset across features 017/018/019/020 enables direct cross-feature comparison (Assumptions §3, FR-015). The subset is small enough to fit under GPU verification windows and large enough to include both `sufficient` and `borderline`/`insufficient` cases.

**Alternatives considered**:
- Expand to all 20 corpus docs (rejected: longer GPU verification window; smaller subset is already cross-feature-comparable).
- Use a different subset to exercise edge cases (rejected: violates the cross-feature comparability the prior features rely on; edge cases can be tested as unit tests in `tests/unit/preprocessing/`).

---

## R-020.14 — Quality-gate evidence (FR-016 / FR-017 two-metric parity)

**Decision**: FR-016 promotion requires both of the following metrics, both measured on the FR-015 5-doc subset, both `>=` the legacy default's values on the same subset:
1. Per-corpus aggregate vendor-identity field score from `evaluation_run_summary.json`.
2. Per-document pass count per `docs/stage1-vendor-identity/scoring.md`.

These metrics are read from the existing evaluator output; no new metric is introduced. Evidence is recorded in this file's Appendix B at landing time alongside the candidate's `evidence_gate_id` value (and any future shape identifier when shape (b) gets a richer ID).

**Rationale**: Mirrors feature 017 R-017.10 / feature 018 R-018.11 / feature 019 R-019.x exactly. Both metrics being `>=` is the parity condition — the candidate cannot regress either metric and be promoted. Pinning both metrics to the existing evaluator output avoids introducing a new comparison surface and keeps the gate auditable through the existing test harness.

**Alternatives considered**:
- Single-metric parity (rejected: the spec explicitly requires both per-corpus aggregate AND per-document pass count; single-metric promotion would mask regressions where one improves while the other regresses).
- Allow a small tolerance (e.g., `candidate >= 0.98 * legacy`) (rejected: spec language is strict `candidate_metric >= legacy_metric`; any tolerance would weaken the gate).

---

## R-020.15 — GPU verification deferral path

**Decision**: When workstation GPU hardware is unavailable at landing time, all `@pytest.mark.gpu` tests for shape (b) — `test_evidence_gate_skip_fallback.py`, `test_evidence_gate_skip_fallback_borderline.py`, `test_evidence_gate_benchmark.py`, `test_quality_gate_two_metric_evidence_gate.py` — MAY be deferred and tracked as a follow-up issue or task per the feature 016 FR-014 / feature 017 FR-024 / feature 018 FR-025 / feature 019 FR-025 precedent. The deferral is captured in this feature's `tasks.md` (an Appendix or dedicated checklist item) and in `quickstart.md` Appendix B so the verification cannot be quietly skipped.

CPU-safe deferral floor: signal-set unit tests (`test_evidence_gate_signals_unit.py`), decision-table unit tests (`test_evidence_gate_decision_unit.py`), opt-in resolution unit tests (`test_evidence_gate_optin_unit.py`), coordinate-filter tests (`test_evidence_gate_y_threshold_unit.py`), warn-and-proceed tests (`test_cpu_warn_and_proceed_evidence_gate.py`), corpus-run aggregation tests (`test_evidence_gate_corpus_run.py`), run_summary schema bump tests (`test_run_summary_schema_0_1_7.py`), and the legacy-byte-identity test (CPU variant) MUST all pass before merge. These cover SC-001 / SC-002 / SC-003 / SC-004 / SC-005 / SC-006 / SC-007 / SC-009 / SC-010 / SC-012 without requiring GPU.

**Rationale**: Continues the established feature 016–019 precedent. CPU-safe tests are the merge-gating floor; GPU verification is deferred-but-tracked. The CPU floor is large enough to catch every non-GPU regression vector.

**Alternatives considered**:
- Block merge until GPU verification completes (rejected: feature 016–019 precedent; would slow the CPU-safe code from landing).
- Silently skip GPU tests with no tracking (rejected: the spec's FR-026 explicitly forbids "quietly skipping" and mandates the deferral capture).

---

## Appendix A — Index of pinned constants (for cross-reference at implementation time)

| Constant | Value | Source | Where pinned |
|---|---|---|---|
| `Y_THRESHOLD_FRACTION` | `0.25` | R-020.5 | `preprocessing/evidence_gate.py` module level |
| `DENSITY_THRESHOLD` | `8` | R-020.6 | `preprocessing/evidence_gate.py` module level |
| `CONFIDENCE_THRESHOLD` | `0.70` | R-020.6 | `preprocessing/evidence_gate.py` module level |
| `BUSINESS_SUFFIX_RE` | per R-020.4 | R-020.4 | `preprocessing/evidence_gate.py` module level |
| `TAX_ID_EIN_RE` | `r"\b\d{2}-\d{7}\b"` | R-020.4 | `preprocessing/evidence_gate.py` module level |
| `TAX_ID_VAT_RE` | `r"\b[A-Z]{2}[A-Z0-9]{2,12}\b"` | R-020.4 | `preprocessing/evidence_gate.py` module level |
| `EVIDENCE_GATE_ID_V1` | `"v1"` | R-020.2 | `preprocessing/identifiers.py` module level |
| `EVIDENCE_GATE_ID_DEFAULT` | `EVIDENCE_GATE_ID_V1` | R-020.2 | `preprocessing/identifiers.py` module level |
| `EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR` | `"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK"` | R-020.1 | `preprocessing/evidence_gate_optin.py` module level |
| `SCHEMA_VERSION` (RunSummary) | `"0.1.7"` (bumped from `"0.1.6"`) | R-020.9 | `pipeline/timing.py` |

## Appendix B — Quality-gate evidence (filled at landing)

This appendix is intentionally empty in the planning phase. At landing time (after `/speckit.tasks` and `/speckit.implement`), the FR-016 / FR-017 / R-020.14 quality-gate evidence — per-corpus aggregate vendor-identity field score AND per-document pass count for the skip-fallback opt-in candidate vs. the legacy default — is recorded here, formatted as:

```
| document_id | legacy aggregate_score | candidate aggregate_score | legacy pass | candidate pass |
|---|---|---|---|---|
| inv_001_easy | ... | ... | ... | ... |
| ...          | ... | ... | ... | ... |
| TOTAL        | ... | ... | ... | ... |
```

The promotion gate (FR-016) passes iff `candidate aggregate_score >= legacy aggregate_score` AND `candidate pass count >= legacy pass count`, both measured across the 5-doc subset.

If GPU verification was deferred per R-020.15, this appendix records the deferral with a one-line cross-reference to the follow-up issue/task in `tasks.md`.
