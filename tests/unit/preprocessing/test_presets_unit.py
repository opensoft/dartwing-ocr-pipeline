"""Feature 017 (T012 / T022): CPU-safe unit tests for the preset registries.

Asserts the closed-vocabulary contract from R-017.2 / R-017.4, the
identity-preset use_kwargs invariant from Plan §I-2, the
UnknownPresetError fail-fast contract from R-017.9 / Plan §I-10, and the
import-safe-without-Paddle invariant from FR-014 / Plan §I-3.

All tests CPU-safe: no Paddle import, no GPU dependency.
"""
from __future__ import annotations

import pytest

from ledgerlinc_ocr.preprocessing.errors import UnknownPresetError
from ledgerlinc_ocr.preprocessing.presets import (
    DET_REC_VARIANTS,
    MODULE_SET_PRESETS,
    DetRecVariant,
    ModuleSetPreset,
    resolve_det_rec_variant,
    resolve_module_set,
)


# ---------------------------------------------------------------------------
# T012 / Plan §I-1: registry keys are exhaustive at landing
# ---------------------------------------------------------------------------


def test_module_set_registry_keys_are_exhaustive() -> None:
    """`MODULE_SET_PRESETS` keys are the closed vocabulary at landing
    (R-017.2 / Plan §I-1). Any future addition is a code change."""
    assert set(MODULE_SET_PRESETS.keys()) == {
        "legacy",
        "reduced-v1",
        "cpu-default",
        "stub-default",
    }


def test_det_rec_variant_registry_keys_are_exhaustive() -> None:
    """`DET_REC_VARIANTS` keys are the closed vocabulary at landing
    (R-017.4 / Plan §I-1)."""
    assert set(DET_REC_VARIANTS.keys()) == {
        "legacy",
        "ppocrv5-mobile",
        "ppocrv4-mobile",
        "cpu-default",
        "stub-default",
    }


# ---------------------------------------------------------------------------
# T012 / Plan §I-2: identity presets carry empty use_kwargs
# ---------------------------------------------------------------------------


def test_cpu_default_preset_use_kwargs_is_empty() -> None:
    """`cpu-default`'s `use_kwargs` is `{}` so the CPU singleton
    constructor in `preprocessing/ocr.py` retains its hard-coded
    defaults (FR-014 / Plan §I-2 / R-017.6)."""
    assert dict(MODULE_SET_PRESETS["cpu-default"].use_kwargs) == {}


def test_stub_default_preset_use_kwargs_is_empty() -> None:
    """`stub-default`'s `use_kwargs` is `{}` — same identity-preset
    rationale as `cpu-default` (Plan §I-2)."""
    assert dict(MODULE_SET_PRESETS["stub-default"].use_kwargs) == {}


def test_cpu_default_det_rec_variant_uses_paddleocr_defaults() -> None:
    """`cpu-default` (and `stub-default`) carry `det_model_name=None`
    and `rec_model_name=None` — meaning PaddleOCR picks its own
    server defaults for `lang='en'` (R-017.4 Appendix A)."""
    cpu = DET_REC_VARIANTS["cpu-default"]
    stub = DET_REC_VARIANTS["stub-default"]
    legacy = DET_REC_VARIANTS["legacy"]
    assert cpu.det_model_name is None and cpu.rec_model_name is None
    assert stub.det_model_name is None and stub.rec_model_name is None
    # `legacy` also defers to PaddleOCR's defaults — R-017.4 Appendix A.
    assert legacy.det_model_name is None and legacy.rec_model_name is None


# ---------------------------------------------------------------------------
# T012 / R-017.3: reduced-v1 differs from legacy by exactly one disable
# ---------------------------------------------------------------------------


def test_reduced_v1_disables_use_table_recognition_only() -> None:
    """Per R-017.3: `reduced-v1` adds exactly `use_table_recognition=False`
    to the legacy GPU defaults; no other kwarg differs."""
    legacy_kwargs = dict(MODULE_SET_PRESETS["legacy"].use_kwargs)
    reduced_kwargs = dict(MODULE_SET_PRESETS["reduced-v1"].use_kwargs)
    diff_added = set(reduced_kwargs.keys()) - set(legacy_kwargs.keys())
    diff_removed = set(legacy_kwargs.keys()) - set(reduced_kwargs.keys())
    assert diff_added == {"use_table_recognition"}, f"unexpected new keys: {diff_added}"
    assert diff_removed == set(), f"reduced-v1 must not remove keys: {diff_removed}"
    assert reduced_kwargs["use_table_recognition"] is False
    # All other kwargs unchanged
    for k, v in legacy_kwargs.items():
        assert reduced_kwargs[k] == v


def test_legacy_use_kwargs_disables_six_modules() -> None:
    """Per R-017.2 + the legacy GPU constructor on `main` at feature 016
    landing: legacy disables exactly six modules."""
    legacy_kwargs = dict(MODULE_SET_PRESETS["legacy"].use_kwargs)
    assert legacy_kwargs == {
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
        "use_formula_recognition": False,
        "use_seal_recognition": False,
        "use_chart_recognition": False,
    }


# ---------------------------------------------------------------------------
# T012 / Plan §I-10: resolve_* raises UnknownPresetError on miss
# ---------------------------------------------------------------------------


def test_resolve_module_set_returns_correct_preset() -> None:
    """`resolve_module_set('legacy')` returns the legacy preset object
    (identity dict lookup, no copying)."""
    assert resolve_module_set("legacy") is MODULE_SET_PRESETS["legacy"]
    assert resolve_module_set("reduced-v1") is MODULE_SET_PRESETS["reduced-v1"]


def test_resolve_module_set_raises_on_unknown_value() -> None:
    """`resolve_module_set('reduced-v99')` raises `UnknownPresetError`
    with `preset_axis='module_set'` and `valid_values` containing all
    four registry keys in deterministic insertion order (Plan §I-10 /
    R-017.9 / data-model.md §UnknownPresetError)."""
    with pytest.raises(UnknownPresetError) as exc_info:
        resolve_module_set("reduced-v99")
    exc = exc_info.value
    assert exc.preset_axis == "module_set"
    assert exc.preset_value == "reduced-v99"
    assert exc.valid_values == ("legacy", "reduced-v1", "cpu-default", "stub-default")
    assert exc.exit_code == 16


def test_resolve_det_rec_variant_raises_on_unknown_value() -> None:
    """Same UnknownPresetError contract for the det/rec axis."""
    with pytest.raises(UnknownPresetError) as exc_info:
        resolve_det_rec_variant("ppocrv9_imaginary")
    exc = exc_info.value
    assert exc.preset_axis == "det_rec_variant"
    assert exc.preset_value == "ppocrv9_imaginary"
    assert exc.valid_values == (
        "legacy",
        "ppocrv5-mobile",
        "ppocrv4-mobile",
        "cpu-default",
        "stub-default",
    )
    assert exc.exit_code == 16


def test_resolve_module_set_is_case_sensitive() -> None:
    """Per R-017.9 alternatives + research.md "Env-var literal-value
    handling": case-sensitive lookup. `Reduced-V1` (mixed case) does
    NOT silently coerce to `reduced-v1`."""
    with pytest.raises(UnknownPresetError):
        resolve_module_set("Reduced-V1")


def test_resolve_det_rec_variant_is_case_sensitive() -> None:
    with pytest.raises(UnknownPresetError):
        resolve_det_rec_variant("Legacy")


# ---------------------------------------------------------------------------
# T012 / Plan §I-3: registry import does not require Paddle
# ---------------------------------------------------------------------------


def test_presets_module_top_level_imports_dont_load_paddle() -> None:
    """The presets module is intended to be import-safe on a host without
    Paddle (FR-014 / Plan §I-3). The audit callable's lazy imports live
    inside the function body so module-level `import` does not trigger
    paddle/paddleocr imports.

    We verify by checking the module's top-level imports directly via
    AST parsing rather than `sys.modules` inspection (which would only
    catch transitive imports that already happened in this test session).
    """
    import ast
    from pathlib import Path

    from ledgerlinc_ocr.preprocessing import presets as presets_mod

    src = Path(presets_mod.__file__).read_text()
    tree = ast.parse(src)
    top_level_imports: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level_imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top_level_imports.add(node.module)
    forbidden = {"paddle", "paddleocr", "paddlex", "PIL", "pypdfium2"}
    leaked = forbidden & top_level_imports
    assert not leaked, (
        f"presets.py top-level imports must not include Paddle/PIL/pypdfium2; "
        f"leaked: {leaked}"
    )


def test_resolve_module_set_does_not_invoke_audit_callable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolving a preset must NOT trigger the audit callable. Audit
    runs only at the audit call site (`run_module_audit`), not during
    registry lookup. Verified by replacing one preset with a spy and
    asserting the spy is not called by `resolve_module_set`."""
    import ledgerlinc_ocr.preprocessing.presets as presets_mod

    spy_calls: list[object] = []

    def _spy(engine: object) -> list[str]:
        spy_calls.append(engine)
        return []

    spy_preset = ModuleSetPreset(
        name="legacy",
        use_kwargs=presets_mod.MODULE_SET_PRESETS["legacy"].use_kwargs,
        audit_callable=_spy,
    )
    spied_registry = dict(presets_mod.MODULE_SET_PRESETS)
    spied_registry["legacy"] = spy_preset
    monkeypatch.setattr(presets_mod, "MODULE_SET_PRESETS", spied_registry)

    resolved = presets_mod.resolve_module_set("legacy")
    assert resolved is spy_preset
    assert spy_calls == [], "resolve_module_set must not invoke audit_callable"


def test_resolve_returns_dataclass_instances() -> None:
    """`resolve_module_set` returns a `ModuleSetPreset` instance;
    `resolve_det_rec_variant` returns a `DetRecVariant` instance."""
    assert isinstance(resolve_module_set("cpu-default"), ModuleSetPreset)
    assert isinstance(resolve_det_rec_variant("legacy"), DetRecVariant)
