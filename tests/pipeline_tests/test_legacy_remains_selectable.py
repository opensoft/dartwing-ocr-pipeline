"""Feature 017 (T036a / US6 / FR-017 / Analysis I4): CPU-safe
legacy-stays-selectable test.

Per FR-017: promotion of a new GPU default MUST NOT remove the legacy
configuration as a selectable option. This test asserts that
`resolve_module_set('legacy')` returns the legacy preset and
`resolve_det_rec_variant('legacy')` returns the legacy variant on a
CPU-only host, BOTH before and after a hypothetical T037 promotion
(parametrized via monkeypatch).

Covers Analysis I4 — added during the /speckit.analyze remediation
round to give FR-017 an explicit positive assertion.
"""
from __future__ import annotations

from typing import Any

import pytest

from dartwing_ocr.preprocessing.presets import (
    DET_REC_VARIANTS,
    MODULE_SET_PRESETS,
    DetRecVariant,
    ModuleSetPreset,
    resolve_det_rec_variant,
    resolve_module_set,
)


# ---------------------------------------------------------------------------
# FR-017: legacy stays selectable BEFORE any promotion (the landing-time
# default state — registry includes "legacy" with PaddleOCR-default models)
# ---------------------------------------------------------------------------


def test_legacy_module_set_resolvable_before_promotion() -> None:
    """At landing (no promotion has occurred): `resolve_module_set('legacy')`
    returns the legacy preset; `MODULE_SET_PRESETS['legacy']` exists."""
    assert "legacy" in MODULE_SET_PRESETS
    preset = resolve_module_set("legacy")
    assert isinstance(preset, ModuleSetPreset)
    assert preset.name == "legacy"


def test_legacy_det_rec_variant_resolvable_before_promotion() -> None:
    """At landing: `resolve_det_rec_variant('legacy')` returns the
    legacy variant; `DET_REC_VARIANTS['legacy']` exists."""
    assert "legacy" in DET_REC_VARIANTS
    variant = resolve_det_rec_variant("legacy")
    assert isinstance(variant, DetRecVariant)
    assert variant.name == "legacy"


# ---------------------------------------------------------------------------
# FR-017: legacy stays selectable AFTER a hypothetical promotion (a future
# T037 might update defaults; legacy must remain in the registry as an
# explicitly-selectable alternative)
# ---------------------------------------------------------------------------


def test_legacy_remains_selectable_after_hypothetical_module_set_promotion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulate a future T037 that promotes `reduced-v1` to be the
    de-facto GPU default (e.g., changes which preset gets resolved when
    no flag is set). The `legacy` preset MUST remain in the registry
    and explicitly resolvable per FR-017.

    Note: T037 may add a NEW preset (`reduced-v2`) but it MUST NOT
    remove `legacy`. This test asserts the latter."""
    # Hypothetical: future T037 adds a `reduced-v2` preset alongside
    # legacy + reduced-v1 + cpu-default + stub-default. Legacy stays.
    fake_extra_preset = ModuleSetPreset(
        name="reduced-v2",
        use_kwargs={"use_doc_orientation_classify": False, "use_table_recognition": False},
        audit_callable=lambda _engine: [],
    )
    extended_registry = dict(MODULE_SET_PRESETS)
    extended_registry["reduced-v2"] = fake_extra_preset
    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.presets.MODULE_SET_PRESETS",
        extended_registry,
    )
    # Re-import resolve_module_set against the patched registry
    from dartwing_ocr.preprocessing import presets as presets_mod

    # legacy is still selectable
    assert "legacy" in presets_mod.MODULE_SET_PRESETS
    legacy_after = presets_mod.resolve_module_set("legacy")
    assert legacy_after.name == "legacy"


def test_legacy_remains_selectable_after_hypothetical_det_rec_promotion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same FR-017 contract on the det/rec axis. A hypothetical
    promotion of `ppocrv5-mobile` to be the de-facto default MUST NOT
    remove `legacy` from the registry."""
    fake_extra_variant = DetRecVariant(
        name="ppocrv6-mobile",  # hypothetical future variant
        det_model_name="PP-OCRv6_mobile_det",
        rec_model_name="PP-OCRv6_mobile_rec",
    )
    extended_registry = dict(DET_REC_VARIANTS)
    extended_registry["ppocrv6-mobile"] = fake_extra_variant
    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.presets.DET_REC_VARIANTS",
        extended_registry,
    )
    from dartwing_ocr.preprocessing import presets as presets_mod

    assert "legacy" in presets_mod.DET_REC_VARIANTS
    legacy_variant = presets_mod.resolve_det_rec_variant("legacy")
    assert legacy_variant.name == "legacy"


# ---------------------------------------------------------------------------
# FR-017: invoking `--module-set=legacy --det-rec-variant=legacy`
# explicitly continues to produce a `module_set_id="legacy"` /
# `det_rec_variant_id="legacy"` run_summary line in both scenarios.
# (CPU-safe: we test the resolution-to-RunSummary-field flow, not the
# actual GPU engine construction.)
# ---------------------------------------------------------------------------


def test_explicit_legacy_selection_emits_legacy_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run with `module_set='legacy'` and `det_rec_variant='legacy'`
    on the GPU lane (simulated via direct preset resolution) yields
    identifier strings `'legacy'` / `'legacy'` regardless of registry
    extension state. Asserts the resolution-to-name flow that feeds
    `RunSummary.module_set_id` / `det_rec_variant_id`."""
    # Test in pristine registry state
    ms = resolve_module_set("legacy")
    drv = resolve_det_rec_variant("legacy")
    assert ms.name == "legacy"
    assert drv.name == "legacy"

    # And test in extended-registry state (post-promotion)
    extended_module = dict(MODULE_SET_PRESETS)
    extended_module["reduced-v2"] = ModuleSetPreset(
        name="reduced-v2",
        use_kwargs={},
        audit_callable=lambda _engine: [],
    )
    extended_det_rec = dict(DET_REC_VARIANTS)
    extended_det_rec["ppocrv6-mobile"] = DetRecVariant(
        name="ppocrv6-mobile",
        det_model_name="PP-OCRv6_mobile_det",
        rec_model_name="PP-OCRv6_mobile_rec",
    )
    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.presets.MODULE_SET_PRESETS",
        extended_module,
    )
    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.presets.DET_REC_VARIANTS",
        extended_det_rec,
    )
    from dartwing_ocr.preprocessing import presets as presets_mod

    ms_post = presets_mod.resolve_module_set("legacy")
    drv_post = presets_mod.resolve_det_rec_variant("legacy")
    assert ms_post.name == "legacy"
    assert drv_post.name == "legacy"
