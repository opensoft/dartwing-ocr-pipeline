"""Feature 019: closed-vocabulary `preprocess_strategy_id` preset registry.

Sibling of `preprocessing/raster_profiles.py` (feature 018),
`preprocessing/region_strategies.py` (feature 018), and
`preprocessing/presets.py` (feature 017). Same shape:

- Frozen dataclass `PreprocessStrategy` (immutable per instance).
- Closed `PREPROCESS_STRATEGIES` registry keyed by `name`.
- `resolve_preprocess_strategy(name)` raises `UnknownPresetError` on
  any name not in the registry (R-019.12 / exit code 16 / I-019.1).
- **CPU-safe at module load** — no Paddle import, no preset
  registry introspection beyond the immutable strings exported by
  `identifiers.py` (FR-014 / I-019.10).

Per FR-001 / R-019.2, the registry is closed at landing to exactly four
entries: ``ppstructurev3`` (the layout-aware strategy active on `main`
at landing time of feature 018), ``ocr-only-v1`` (the OCR-only candidate
preset with token_threshold=8 per R-019.5, confidence_threshold=0.60 per
R-019.6, confidence_aggregator="mean" per R-019.6), ``cpu-default`` and
``stub-default`` (identity presets for the non-GPU profiles).

Adding a future preset (e.g., ``ocr-only-v2`` with tuned thresholds) is
a code change plus a new identifier value — not a runtime knob and not
a config-file override.

Reference: data-model.md §PreprocessStrategy; research.md R-019.2,
R-019.5, R-019.6; contracts/module-invariants.md I-019.1.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping

from ledgerlinc_ocr.preprocessing.errors import UnknownPresetError
from ledgerlinc_ocr.preprocessing.identifiers import (
    CPU_DEFAULT_PREPROCESS_STRATEGY,
    LEGACY_PREPROCESS_STRATEGY,
    OCR_ONLY_V1_PREPROCESS_STRATEGY,
    STUB_DEFAULT_PREPROCESS_STRATEGY,
)

# Numeric thresholds for the FR-005 combined two-threshold eligibility
# check on the OCR-only preset (R-019.5 / R-019.6). Tuning these is a
# code change plus (potentially) a new `preprocess_strategy_id` value
# per FR-001 — never a runtime knob.
OCR_ONLY_MIN_TOKEN_COUNT: int = 8
OCR_ONLY_MIN_CONFIDENCE_MEAN: float = 0.60


PreprocessStrategyKind = Literal["ppstructurev3", "ocr-only", "identity"]


@dataclass(frozen=True)
class PreprocessStrategy:
    """A named, closed-vocabulary preset that fixes which preprocessing
    pipeline the ``ppstructurev3@gpu`` profile runs.

    Equality is by ``name`` (frozen=True + slots-less dataclass uses
    structural equality). ``name`` equals the ``preprocess_strategy_id``
    value emitted on ``run_summary`` when this strategy is active.

    ``kind`` is the dispatch discriminator used by
    ``preprocessing/pipeline.py``:

    - ``"ppstructurev3"`` ⇒ existing layout-aware path (PPStructureV3).
    - ``"ocr-only"``       ⇒ new OCR-only path (PaddleOCR det+rec only).
    - ``"identity"``       ⇒ CPU/stub-default identity preset; no GPU
      effect. ``identity``-kind presets are emitted as the
      ``preprocess_strategy_id`` value on `run_summary` for the CPU
      lane and stub adapter but never reach the dispatcher (the warn-
      and-proceed path nulls the resolved strategy before the
      orchestrator runs).

    The ``token_threshold`` / ``confidence_threshold`` /
    ``confidence_aggregator`` fields are populated **only** for
    ``kind="ocr-only"`` strategies; they are ``None`` for
    ``ppstructurev3`` and identity strategies.
    """

    name: str
    kind: PreprocessStrategyKind
    token_threshold: int | None = None
    confidence_threshold: float | None = None
    confidence_aggregator: Literal["mean"] | None = None

    @classmethod
    def identity(cls, name: str) -> "PreprocessStrategy":
        """Build an identity-kind preset (CPU / stub defaults)."""
        return cls(name=name, kind="identity")


# Closed registry. The keys are the only valid values for
# ``--preprocess-strategy`` / ``LEDGERLINC_PREPROCESS_STRATEGY`` /
# ``run_summary.preprocess_strategy_id``. Adding a key is a feature-
# level decision per FR-001, not a runtime configuration choice.
PREPROCESS_STRATEGIES: Mapping[str, PreprocessStrategy] = MappingProxyType({
    LEGACY_PREPROCESS_STRATEGY: PreprocessStrategy(
        name=LEGACY_PREPROCESS_STRATEGY,
        kind="ppstructurev3",
    ),
    OCR_ONLY_V1_PREPROCESS_STRATEGY: PreprocessStrategy(
        name=OCR_ONLY_V1_PREPROCESS_STRATEGY,
        kind="ocr-only",
        token_threshold=OCR_ONLY_MIN_TOKEN_COUNT,
        confidence_threshold=OCR_ONLY_MIN_CONFIDENCE_MEAN,
        confidence_aggregator="mean",
    ),
    CPU_DEFAULT_PREPROCESS_STRATEGY: PreprocessStrategy.identity(
        CPU_DEFAULT_PREPROCESS_STRATEGY,
    ),
    STUB_DEFAULT_PREPROCESS_STRATEGY: PreprocessStrategy.identity(
        STUB_DEFAULT_PREPROCESS_STRATEGY,
    ),
})

USER_SELECTABLE_PREPROCESS_STRATEGIES: tuple[str, ...] = (
    LEGACY_PREPROCESS_STRATEGY,
    OCR_ONLY_V1_PREPROCESS_STRATEGY,
)


def resolve_preprocess_strategy(name: str) -> PreprocessStrategy:
    """Return the ``PreprocessStrategy`` instance for ``name``.

    Raises ``UnknownPresetError(preset_axis="preprocess_strategy", ...)``
    on any ``name`` not in ``PREPROCESS_STRATEGIES`` (R-019.12 / exit
    code 16 / I-019.1). The exception's ``valid_values`` is the tuple
    of registry keys in insertion order.
    """
    if name not in PREPROCESS_STRATEGIES:
        valid = tuple(PREPROCESS_STRATEGIES.keys())
        raise UnknownPresetError(
            f"unknown preprocess_strategy: {name!r} — "
            f"valid values are: {', '.join(valid)}",
            preset_axis="preprocess_strategy",
            preset_value=name,
            valid_values=valid,
        ) from None
    return PREPROCESS_STRATEGIES[name]


def resolve_user_preprocess_strategy(name: str) -> PreprocessStrategy:
    """Resolve a user-selectable preprocess strategy.

    Internal identity sentinels (`cpu-default`, `stub-default`) are valid
    registry members for run_summary/defaulting, but they are not accepted
    on the user-facing CLI surface.
    """
    if name not in USER_SELECTABLE_PREPROCESS_STRATEGIES:
        raise UnknownPresetError(
            f"unknown preprocess_strategy: {name!r} — "
            f"valid values are: {', '.join(USER_SELECTABLE_PREPROCESS_STRATEGIES)}",
            preset_axis="preprocess_strategy",
            preset_value=name,
            valid_values=USER_SELECTABLE_PREPROCESS_STRATEGIES,
        ) from None
    return PREPROCESS_STRATEGIES[name]


__all__ = (
    "OCR_ONLY_MIN_TOKEN_COUNT",
    "OCR_ONLY_MIN_CONFIDENCE_MEAN",
    "PreprocessStrategyKind",
    "PreprocessStrategy",
    "PREPROCESS_STRATEGIES",
    "USER_SELECTABLE_PREPROCESS_STRATEGIES",
    "resolve_preprocess_strategy",
    "resolve_user_preprocess_strategy",
)
