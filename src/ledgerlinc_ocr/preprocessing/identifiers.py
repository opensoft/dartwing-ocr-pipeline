"""Page-scoped identifier minting (FR-008, FR-009, FR-009a, research Decision 5).

Feature 017 (T005 / R-017.5 / R-017.7 / data-model.md): adds module-level
constants for the closed-vocabulary `run_summary` identifiers
(`module_set_id`, `det_rec_variant_id`) on the CPU lane and stub adapter,
plus the `AUDIT_SUB_MODULE_VOCABULARY` tuple — the closed set of strings
allowed in `run_summary.ppstructure_modules_invoked` at landing.

Feature 018 (T005 / R-018.2 / R-018.4 / data-model.md §Identifier-string
constants): adds module-level constants for the two new closed-vocabulary
`run_summary` identifiers (`raster_profile_id`, `region_strategy_id`) on
the CPU lane, stub adapter, and GPU-lane legacy default. Default selection
flows through `preprocessing/cli.py` and `pipeline/cli.py` per
contracts/cli-contract.md §1 (CLI sets the GPU-default to LEGACY_*; CPU
profile uses CPU_DEFAULT_*; stub adapter uses STUB_DEFAULT_*).

Feature 019 (T005 / R-019.2 / R-019.3 / R-019.4 / data-model.md §Identifier-string
constants): adds module-level constants for the closed-vocabulary
`run_summary` identifier (`preprocess_strategy_id`) on the CPU lane,
stub adapter, GPU-lane legacy default, and the OCR-only candidate
preset. Same flow pattern as features 017/018.
"""

from __future__ import annotations


def block_id(page_number: int, reading_order: int) -> str:
    if page_number < 1 or reading_order < 1:
        raise ValueError(f"page_number and reading_order must be >= 1, got {page_number=}, {reading_order=}")
    return f"p{page_number}_b{reading_order}"


def line_id(page_number: int, line_index: int) -> str:
    if page_number < 1 or line_index < 1:
        raise ValueError(f"page_number and line_index must be >= 1, got {page_number=}, {line_index=}")
    return f"p{page_number}_l{line_index}"


# Feature 017 (T005 / R-017.5): CPU and stub-adapter `run_summary` identifier
# defaults. CPU lane writes `cpu-default` for both axes; stub adapter writes
# `stub-default`. Distinct strings preserve absence-as-regression-signal
# discrimination (FR-010) — a stub-only test that suddenly emits `cpu-default`
# is a real regression.
CPU_DEFAULT_MODULE_SET: str = "cpu-default"
CPU_DEFAULT_DET_REC_VARIANT: str = "cpu-default"
STUB_DEFAULT_MODULE_SET: str = "stub-default"
STUB_DEFAULT_DET_REC_VARIANT: str = "stub-default"

# Feature 017 (T005 / R-017.7 / data-model.md §"AUDIT_SUB_MODULE_VOCABULARY"):
# the closed, exhaustive set of strings allowed in
# `run_summary.ppstructure_modules_invoked` at landing. The audit callable in
# `preprocessing/presets.py` MUST drop any sub-module name not in this tuple
# before populating the list. Any new PaddleOCR sub-module name in a future
# release is silently dropped; expanding this vocabulary is a future-feature
# decision, not an implementation choice.
AUDIT_SUB_MODULE_VOCABULARY: tuple[str, ...] = (
    "layout_detection",
    "table_recognition",
    "ocr_det",
    "ocr_rec",
)

# Feature 018 (T005 / R-018.2 / R-018.4 / data-model.md §Identifier-string
# constants): closed-vocabulary `run_summary` identifier defaults for the
# two new preset axes added by feature 018. CPU lane writes `cpu-default`
# for both axes; stub adapter writes `stub-default`; GPU lane defaults to
# `legacy` (raster) / `full-page` (region) when no flag is set. Distinct
# strings preserve absence-as-regression-signal discrimination (FR-011).
LEGACY_RASTER_PROFILE: str = "legacy"
CPU_DEFAULT_RASTER_PROFILE: str = "cpu-default"
STUB_DEFAULT_RASTER_PROFILE: str = "stub-default"

LEGACY_REGION_STRATEGY: str = "full-page"
CPU_DEFAULT_REGION_STRATEGY: str = "cpu-default"
STUB_DEFAULT_REGION_STRATEGY: str = "stub-default"

# Feature 019 (T005 / R-019.2 / R-019.3 / R-019.4 / data-model.md §Identifier-string
# constants): closed-vocabulary `run_summary` identifier defaults for the
# preprocess-strategy axis added by feature 019. CPU lane writes `cpu-default`;
# stub adapter writes `stub-default`; GPU lane defaults to `ppstructurev3`
# (the layout-aware strategy on `main` at landing time of feature 018) when
# no flag is set. The OCR-only candidate preset is named `ocr-only-v1`.
# Distinct strings preserve absence-as-regression-signal discrimination
# (FR-010).
LEGACY_PREPROCESS_STRATEGY: str = "ppstructurev3"
OCR_ONLY_V1_PREPROCESS_STRATEGY: str = "ocr-only-v1"
CPU_DEFAULT_PREPROCESS_STRATEGY: str = "cpu-default"
STUB_DEFAULT_PREPROCESS_STRATEGY: str = "stub-default"

# Feature 020 (T004 / R-020.2 / data-model.md §1 / contracts/evidence-gate-rule.md
# §Closed-vocabulary preset registry): closed-vocabulary `run_summary` identifier
# for the evidence-gate axis. Only `"v1"` is a valid value at landing. Future
# presets (`"v2"`, `"v3"`, ...) land via additive code change in
# `preprocessing/evidence_gate.py` — a new `_v2_decide` function plus an
# additional branch in `evaluate_evidence_gate` / `decide_for_gate` — plus a
# new `--evidence-gate <id>` CLI flag at that time (R-020.2). Unlike features
# 017/018/019, the evidence-gate axis emits the same `"v1"` identifier on CPU,
# stub-adapter, and GPU lanes uniformly — the gate is a pure read over
# `preprocess_output.json` content and runs on every profile (FR-014 /
# data-model.md §9 "CPU/stub identity values for `evidence_gate_id`"). There
# are NO `CPU_DEFAULT_EVIDENCE_GATE` / `STUB_DEFAULT_EVIDENCE_GATE` constants
# because no CPU/stub-default discrimination is needed for this axis.
EVIDENCE_GATE_ID_V1: str = "v1"
EVIDENCE_GATE_ID_DEFAULT: str = EVIDENCE_GATE_ID_V1
