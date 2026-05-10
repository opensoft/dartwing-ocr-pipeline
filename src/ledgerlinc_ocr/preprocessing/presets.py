"""Feature 017: closed-vocabulary preset registries for `ppstructurev3@gpu`.

Houses two named-preset axes:

- `ModuleSetPreset` (`MODULE_SET_PRESETS`): selects which PPStructureV3
  sub-modules are enabled at engine construction. Closed vocabulary at
  landing: `legacy`, `reduced-v1`, `cpu-default`, `stub-default`.
- `DetRecVariant` (`DET_REC_VARIANTS`): selects the PaddleOCR detection +
  recognition model pair. Closed vocabulary at landing: `legacy`,
  `ppocrv5-mobile`, `ppocrv4-mobile`, `cpu-default`, `stub-default`.

Module is **CPU-safe at module-load** — no `import paddleocr` / `import
paddle` at module level (FR-014 / contracts/module-invariants.md I-3). The
audit callable's lazy imports live inside its body so a host without
Paddle GPU can `import ledgerlinc_ocr.preprocessing.presets` cleanly.

Public API:

- `ModuleSetPreset` — frozen dataclass; carries `name`, `use_kwargs`, `audit_callable`
- `DetRecVariant` — frozen dataclass; carries `name`, `det_model_name`, `rec_model_name`
- `MODULE_SET_PRESETS` — closed-vocabulary registry for module-set names
- `DET_REC_VARIANTS` — closed-vocabulary registry for det/rec variant names
- `resolve_module_set(name: str) -> ModuleSetPreset` — dict-lookup; raises
  `UnknownPresetError(preset_axis="module_set", ...)` on miss
- `resolve_det_rec_variant(name: str) -> DetRecVariant` — same; raises
  `UnknownPresetError(preset_axis="det_rec_variant", ...)`

Decision sources:

- spec.md §FR-002, FR-005, FR-006, FR-008, FR-013, FR-014; /speckit.clarify Q4
- research.md R-017.2 (module_set vocabulary), R-017.3 (reduced-v1 membership),
  R-017.4 (det_rec_variant vocabulary + Appendix A), R-017.5 (CPU/stub
  identifier values), R-017.6 (preset → constructor kwargs), R-017.7 (audit
  callable), R-017.9 (UnknownPresetError shape)
- data-model.md §ModuleSetPreset, §DetRecVariant, §UnknownPresetError,
  §AUDIT_SUB_MODULE_VOCABULARY
- contracts/module-invariants.md I-1 through I-13
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping

from ledgerlinc_ocr.preprocessing.errors import UnknownPresetError
from ledgerlinc_ocr.preprocessing.identifiers import AUDIT_SUB_MODULE_VOCABULARY


# ---------------------------------------------------------------------------
# Module-set preset axis (FR-002 / R-017.2 / R-017.3 / R-017.6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModuleSetPreset:
    """A named, closed-vocabulary PPStructureV3 module-set preset.

    Carries the constructor kwargs (`use_kwargs`) that get splatted into
    `PPStructureV3(**preset.use_kwargs, ...)` at preflight engine
    construction (FR-002 / R-017.6 / contracts/module-invariants.md I-7
    step 3), plus an `audit_callable` that is invoked once per process
    after engine adoption to populate `run_summary.ppstructure_modules_invoked`
    (FR-001 / R-017.7 / contracts/module-invariants.md I-5 / I-6).

    CPU/stub identity presets carry `use_kwargs={}` (no kwargs splatted —
    CPU singleton in `preprocessing/ocr.py` retains its hard-coded
    defaults; FR-014 / I-2). Their `audit_callable` returns `[]` without
    touching the engine.
    """

    name: str
    use_kwargs: Mapping[str, bool]
    audit_callable: Callable[[Any], list[str]]


# Frozen module-level mapping (R-017.6) for the legacy GPU constructor kwargs.
# Mirrors the literal kwargs that lived in `preflight.py:447` and
# `ocr.py:259` before this feature. `reduced-v1` adds `use_table_recognition=False`
# per R-017.3.
_LEGACY_GPU_USE_KWARGS: Mapping[str, bool] = MappingProxyType(
    {
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
        "use_formula_recognition": False,
        "use_seal_recognition": False,
        "use_chart_recognition": False,
    }
)

_REDUCED_V1_USE_KWARGS: Mapping[str, bool] = MappingProxyType(
    {
        **dict(_LEGACY_GPU_USE_KWARGS),
        # R-017.3: the only sub-module reduced-v1 disables beyond the legacy
        # GPU defaults. Confirmed at landing time by the FR-001 audit
        # narrative in `research.md` Appendix B.
        "use_table_recognition": False,
    }
)

# Identity presets for CPU singleton and stub adapter — no kwargs splatted
# (FR-014 / I-2). The CPU singleton in `preprocessing/ocr.py` retains its
# existing hard-coded module-disable kwargs unchanged.
_IDENTITY_USE_KWARGS: Mapping[str, bool] = MappingProxyType({})


# ---------------------------------------------------------------------------
# Audit callables (R-017.7 / I-5 / I-6)
# ---------------------------------------------------------------------------


def _inspect_predict_result(predict_results: Any) -> list[str]:
    """Inspect a PPStructureV3.predict result list and return the sorted
    subset of `AUDIT_SUB_MODULE_VOCABULARY` whose sub-modules ran.

    PaddleOCR's `PPStructureV3.predict(...)` returns a list of result
    objects (per page). Each result object exposes either a dict-like
    interface or attribute access; common keys/attrs that signal a
    given sub-module ran:

    - layout detection: any of `layout_det_res`, `layout_det_results`,
      `layout_parsing_res`, `boxes`
    - table recognition: any of `table_res`, `table_results`,
      `table_recognition_res`, `html`
    - text detection (ocr_det): any of `dt_polys`, `rec_polys`,
      `ocr_det_res`, `text_det_res`
    - text recognition (ocr_rec): any of `rec_texts`, `ocr_rec_res`,
      `text_rec_res`

    Per R-017.7's "silently drop unknown" policy + Plan §I-6: any string
    outside `AUDIT_SUB_MODULE_VOCABULARY` is dropped. Returns a
    deterministic lex-sorted list.
    """
    found: set[str] = set()
    if not predict_results:
        return []
    iterable = predict_results if isinstance(predict_results, (list, tuple)) else [predict_results]
    for res in iterable:
        keys = _extract_result_keys(res)
        if any(k in keys for k in (
            "layout_det_res", "layout_det_results", "layout_parsing_res", "boxes"
        )):
            found.add("layout_detection")
        if any(k in keys for k in (
            "table_res", "table_results", "table_recognition_res", "html"
        )):
            found.add("table_recognition")
        if any(k in keys for k in (
            "dt_polys", "rec_polys", "ocr_det_res", "text_det_res",
        )):
            found.add("ocr_det")
        if any(k in keys for k in (
            "rec_texts", "ocr_rec_res", "text_rec_res",
        )):
            found.add("ocr_rec")
    return sorted(found & set(AUDIT_SUB_MODULE_VOCABULARY))


def _extract_result_keys(res: Any) -> set[str]:
    """Pull the set of keys/attrs from a PaddleOCR result object.

    PPStructureV3 predict results vary in shape across PaddleOCR patch
    releases — some return plain dicts, some custom objects with
    attribute access. We probe both, silently drop unknowns, and treat
    presence of a known signature key as evidence the sub-module ran.
    """
    keys: set[str] = set()
    if isinstance(res, dict):
        keys.update(str(k) for k in res.keys())
    else:
        # Object-style results: collect public attribute names only
        for attr in dir(res):
            if not attr.startswith("_"):
                keys.add(attr)
    return keys


def _audit_identity_no_op(engine: Any) -> list[str]:
    """CPU/stub identity-preset audit: returns `[]` immediately without
    invoking `engine.predict`. CPU-safe (no fixture load, no Paddle import).

    Per R-017.7 / Plan §I-6: identity presets always return an empty list,
    explicitly signalling "audit not run on this lane" — distinct from
    "audit ran but found no sub-modules" (which would be an empty list
    too, but coming from a real predict invocation).
    """
    return []


def _audit_gpu_via_predict(engine: Any) -> list[str]:
    """Live-path audit for GPU module-set presets: invokes
    `engine.predict(np_img)` once on the canonical fixture (page 1 of
    `inv_001_easy/source.pdf`, reused from feature 016 R-016.2 per R-017.7),
    then inspects the returned result list for `AUDIT_SUB_MODULE_VOCABULARY`
    signatures.

    Lazy imports keep the CPU lane import-safe (FR-014 / I-3): the fixture
    loader pulls in `pypdfium2` + `PIL.Image` only when actually invoked.

    Per R-017.7 + Plan §I-4: invoked exactly once per process between
    engine adoption and the per-document loop. Failures (fixture load /
    predict) raise `WarmupError` (cause class `AuditError`) so they
    surface on the same exit-15 fail-fast path as feature 016's warmup.
    """
    from ledgerlinc_ocr.preprocessing.errors import WarmupError

    try:
        np_img = _load_audit_fixture()
    except WarmupError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise WarmupError(
            f"audit failed: {type(exc).__name__}: {exc}",
            cause_class="AuditError",
            cause_module=type(exc).__module__ or "",
        ) from exc
    try:
        results = engine.predict(np_img)
    except Exception as exc:  # noqa: BLE001
        raise WarmupError(
            f"audit failed: {type(exc).__name__}: {exc}",
            cause_class="AuditError",
            cause_module=type(exc).__module__ or "",
        ) from exc
    return _inspect_predict_result(results)


def _load_audit_fixture() -> Any:
    """Lazy-load page 1 of `inv_001_easy/source.pdf` rasterized at the
    profile's DPI (mirrors feature 016 R-016.2 fixture choice).

    Lazy imports `pypdfium2` and `PIL.Image` so this module remains
    import-safe on hosts without Paddle/ROCm. The fixture path resolution
    walks parents from this module to find the repo's `tests/`
    directory (same logic as `preprocessing/warmup.py`'s
    `_resolve_default_fixture`).
    """
    # Lazy imports only on GPU/audit path
    import numpy as np
    import pypdfium2 as pdfium
    from pathlib import Path

    from ledgerlinc_ocr.preprocessing.version import DPI

    here = Path(__file__).resolve()
    fixture_path: Path | None = None
    for ancestor in here.parents:
        candidate = (
            ancestor / "tests" / "stage1_vendor_identity" / "inv_001_easy" / "source.pdf"
        )
        if candidate.is_file():
            fixture_path = candidate
            break
    if fixture_path is None:
        from ledgerlinc_ocr.preprocessing.errors import WarmupError

        raise WarmupError(
            "audit fixture not found: tests/stage1_vendor_identity/inv_001_easy/source.pdf",
            cause_class="AuditError",
            cause_module="ledgerlinc_ocr.preprocessing.presets",
        )

    pdf = pdfium.PdfDocument(str(fixture_path))
    try:
        page = pdf[0]
        try:
            scale = DPI / 72.0
            bitmap = page.render(scale=scale)
            pil_img = bitmap.to_pil()
            return np.asarray(pil_img)
        finally:
            page.close()
    finally:
        pdf.close()


# ---------------------------------------------------------------------------
# Module-set preset registry (R-017.2)
# ---------------------------------------------------------------------------


MODULE_SET_PRESETS: Mapping[str, ModuleSetPreset] = MappingProxyType(
    {
        "legacy": ModuleSetPreset(
            name="legacy",
            use_kwargs=_LEGACY_GPU_USE_KWARGS,
            audit_callable=_audit_gpu_via_predict,
        ),
        "reduced-v1": ModuleSetPreset(
            name="reduced-v1",
            use_kwargs=_REDUCED_V1_USE_KWARGS,
            audit_callable=_audit_gpu_via_predict,
        ),
        "cpu-default": ModuleSetPreset(
            name="cpu-default",
            use_kwargs=_IDENTITY_USE_KWARGS,
            audit_callable=_audit_identity_no_op,
        ),
        "stub-default": ModuleSetPreset(
            name="stub-default",
            use_kwargs=_IDENTITY_USE_KWARGS,
            audit_callable=_audit_identity_no_op,
        ),
    }
)


def resolve_module_set(name: str) -> ModuleSetPreset:
    """Resolve a `module_set_id` string to its `ModuleSetPreset`.

    Pure dict lookup, no side effects (R-017.6). Raises
    `UnknownPresetError(preset_axis="module_set", ...)` on miss with
    deterministic-ordered `valid_values` (registry-declaration order
    per R-017.9 / data-model.md §UnknownPresetError).

    Case-sensitive (R-017.9 alternatives: identifiers are lowercase by
    codebase convention; mixed-case input fails fast rather than coercing
    silently — feature 017 research.md "Env-var literal-value handling").
    """
    if name not in MODULE_SET_PRESETS:
        raise UnknownPresetError(
            f"unknown module_set: {name!r}",
            preset_axis="module_set",
            preset_value=name,
            valid_values=tuple(MODULE_SET_PRESETS.keys()),
        )
    return MODULE_SET_PRESETS[name]


# ---------------------------------------------------------------------------
# Det/rec variant axis (FR-005 / FR-006 / R-017.4 / R-017.6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DetRecVariant:
    """A named, closed-vocabulary PaddleOCR detection + recognition model
    pair for the `ppstructurev3@gpu` lane.

    `det_model_name` and `rec_model_name` are passed through to
    `PPStructureV3(text_detection_model_name=..., text_recognition_model_name=...)`
    when non-`None`. `legacy` / `cpu-default` / `stub-default` carry
    `None` for both — meaning "use PaddleOCR's default model selection
    for `lang='en'`" (R-017.4 Appendix A).

    Per R-017.4: only PaddleOCR-officially-supported model pair names
    are valid. Custom-trained weights are explicitly out of scope.
    """

    name: str
    det_model_name: str | None
    rec_model_name: str | None


DET_REC_VARIANTS: Mapping[str, DetRecVariant] = MappingProxyType(
    {
        "legacy": DetRecVariant(
            name="legacy",
            det_model_name=None,  # PaddleOCR picks PP-OCRv5 server default for lang="en"
            rec_model_name=None,
        ),
        "ppocrv5-mobile": DetRecVariant(
            name="ppocrv5-mobile",
            det_model_name="PP-OCRv5_mobile_det",
            rec_model_name="PP-OCRv5_mobile_rec",
        ),
        "ppocrv4-mobile": DetRecVariant(
            name="ppocrv4-mobile",
            det_model_name="PP-OCRv4_mobile_det",
            rec_model_name="PP-OCRv4_mobile_rec",
        ),
        "cpu-default": DetRecVariant(
            name="cpu-default",
            det_model_name=None,
            rec_model_name=None,
        ),
        "stub-default": DetRecVariant(
            name="stub-default",
            det_model_name=None,
            rec_model_name=None,
        ),
    }
)


def resolve_det_rec_variant(name: str) -> DetRecVariant:
    """Resolve a `det_rec_variant_id` string to its `DetRecVariant`.

    Pure dict lookup, no side effects (R-017.6). Raises
    `UnknownPresetError(preset_axis="det_rec_variant", ...)` on miss with
    deterministic-ordered `valid_values`.

    Case-sensitive — see `resolve_module_set` docstring.
    """
    if name not in DET_REC_VARIANTS:
        raise UnknownPresetError(
            f"unknown det_rec_variant: {name!r}",
            preset_axis="det_rec_variant",
            preset_value=name,
            valid_values=tuple(DET_REC_VARIANTS.keys()),
        )
    return DET_REC_VARIANTS[name]


__all__ = (
    "ModuleSetPreset",
    "DetRecVariant",
    "MODULE_SET_PRESETS",
    "DET_REC_VARIANTS",
    "resolve_module_set",
    "resolve_det_rec_variant",
)
