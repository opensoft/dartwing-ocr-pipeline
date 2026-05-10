"""Page-scoped identifier minting (FR-008, FR-009, FR-009a, research Decision 5).

Feature 017 (T005 / R-017.5 / R-017.7 / data-model.md): adds module-level
constants for the closed-vocabulary `run_summary` identifiers
(`module_set_id`, `det_rec_variant_id`) on the CPU lane and stub adapter,
plus the `AUDIT_SUB_MODULE_VOCABULARY` tuple — the closed set of strings
allowed in `run_summary.ppstructure_modules_invoked` at landing.
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
