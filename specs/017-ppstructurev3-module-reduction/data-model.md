# Data Model: PPStructureV3 Module And Model Reduction

**Feature**: 017-ppstructurev3-module-reduction
**Date**: 2026-05-09

This feature is preset-and-observability heavy: it adds two closed-vocabulary preset registries, three additive top-level run_summary fields, one new exception, and one new exit code. There are no new persisted artifacts. The entities below describe the stable in-process and on-the-wire surfaces this feature introduces or extends.

## Entity: ModuleSetPreset

A named, closed-vocabulary preset that resolves to a frozen mapping of `PPStructureV3(...)` constructor kwargs plus an audit callable. Lives in `src/dartwing_ocr/preprocessing/presets.py`. Entries in the registry are immutable across the process lifetime.

```python
@dataclass(frozen=True)
class ModuleSetPreset:
    name: str                                      # closed vocabulary value (R-017.2)
    use_kwargs: Mapping[str, bool]                 # constructor kwargs to splat at PPStructureV3(...)
    audit_callable: Callable[[Any], list[str]]     # wraps engine; returns sub-module list (R-017.7)
```

| Field | Type | Source | Notes |
|---|---|---|---|
| name | `str` | one of `{"legacy", "reduced-v1", "cpu-default", "stub-default"}` | Closed vocabulary at landing time. Adding a new entry is a code change. |
| use_kwargs | `Mapping[str, bool]` (frozen via `MappingProxyType`) | hard-coded per preset (R-017.6) | Splatted into `PPStructureV3(**preset.use_kwargs, ...)` in `preflight.py`. CPU/stub identity presets carry `use_kwargs = {}`. |
| audit_callable | `Callable[[engine: Any], list[str]]` | hard-coded per preset (R-017.7) | Returns a deterministic sorted list of strings drawn from `AUDIT_SUB_MODULE_VOCABULARY`. CPU/stub presets return `[]`. Failures inside raise `WarmupError` cause class `AuditError`. |

**Registry invariants**:

- `MODULE_SET_PRESETS["legacy"].use_kwargs` is exactly the GPU-lane legacy kwargs from `preprocessing/preflight.py:447` (`{use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False, use_formula_recognition=False, use_seal_recognition=False, use_chart_recognition=False}`). Adding `use_table_recognition=False` to this set defines `reduced-v1`.
- `MODULE_SET_PRESETS["cpu-default"].use_kwargs == {}` and `MODULE_SET_PRESETS["stub-default"].use_kwargs == {}`. The CPU singleton constructor in `preprocessing/ocr.py:259` is NOT preset-driven — it retains its hard-coded kwargs. Identity presets exist for the run_summary identifier surface, not to mutate the CPU constructor (FR-014 / R-017.6).
- The registry is exhaustive at landing — registry keys equal the closed `module_set_id` vocabulary 1:1.

## Entity: DetRecVariant

A named, closed-vocabulary preset that resolves to optional `text_detection_model_name` / `text_recognition_model_name` kwargs for `PPStructureV3(...)`. Same shape as `ModuleSetPreset` but for the det/rec axis, without an audit callable (det/rec variant choice is reflected in inference timing, not in `ppstructure_modules_invoked` content — the same four sub-modules execute regardless of which det/rec model is loaded, just the actual neural net weights inside `ocr_det` and `ocr_rec` differ).

```python
@dataclass(frozen=True)
class DetRecVariant:
    name: str                          # closed vocabulary value (R-017.4)
    det_model_name: str | None         # PaddleOCR text_detection_model_name kwarg (None = PaddleOCR default)
    rec_model_name: str | None         # PaddleOCR text_recognition_model_name kwarg (None = PaddleOCR default)
```

| Field | Type | Source | Notes |
|---|---|---|---|
| name | `str` | one of `{"legacy", "ppocrv5-mobile", "ppocrv4-mobile", "cpu-default", "stub-default"}` | Closed vocabulary at landing. |
| det_model_name | `str | None` | hard-coded per variant (R-017.4 Appendix A) | `None` for `legacy`, `cpu-default`, `stub-default` (PaddleOCR picks server default for `lang="en"`). |
| rec_model_name | `str | None` | hard-coded per variant (R-017.4 Appendix A) | `None` for `legacy`, `cpu-default`, `stub-default`. |

**Registry invariants**:

- `DET_REC_VARIANTS["legacy"].det_model_name is None` and `.rec_model_name is None` — explicit None means "PaddleOCR's default, do not override".
- `DET_REC_VARIANTS["ppocrv5-mobile"]` and `["ppocrv4-mobile"]` carry the model names from R-017.4 Appendix A.
- `DET_REC_VARIANTS["cpu-default"]` and `["stub-default"]` are identity presets (None / None), used only for the run_summary identifier surface.

## Entity: PresetResolution

Internal value object, never serialized. Carries the resolved presets from CLI parse to the engine constructor and to `RunSummary` build.

```python
@dataclass(frozen=True)
class PresetResolution:
    module_set: ModuleSetPreset
    det_rec_variant: DetRecVariant
```

**Validation rules**:
- Both fields are non-None — preset resolution always returns a value or raises `UnknownPresetError` (R-017.9). There is no "missing" state.
- The resolution is computed once at CLI parse time and read at (a) preflight engine construction to pull `module_set.use_kwargs` + `det_rec_variant.{det,rec}_model_name`, (b) post-engine-adoption to invoke `module_set.audit_callable(engine)` once, (c) run_summary build time to write the `module_set_id` / `det_rec_variant_id` strings.

## Entity: UnknownPresetError

New exception class in `src/dartwing_ocr/preprocessing/errors.py`. Mirrors the `EngineInitError` / `WarmupError` shape used by features 014 / 016.

```python
class UnknownPresetError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        preset_axis: Literal["module_set", "det_rec_variant"],
        preset_value: str,
        valid_values: tuple[str, ...],
    ) -> None:
        super().__init__(message)
        self.preset_axis = preset_axis
        self.preset_value = preset_value
        self.valid_values = valid_values
```

**Cause-class taxonomy**:

| Routed via `preset_axis` | When raised |
|---|---|
| `module_set` | `resolve_module_set(name)` called with a `name` not in `MODULE_SET_PRESETS` |
| `det_rec_variant` | `resolve_det_rec_variant(name)` called with a `name` not in `DET_REC_VARIANTS` |

The `valid_values` tuple is the corresponding registry's `keys()` materialized into a deterministic-ordered tuple. The CLI boundary catches `UnknownPresetError`, prints `error: unknown <preset_axis>: <preset_value!r> — valid values are: <comma-separated valid_values>` to stderr, and exits with code 16 (R-017.9 / R-017.12).

**Stability stance**: `preset_axis` is a closed two-element string literal type at the type level. Adding a third axis is a feature-level decision, not an implementation choice. `valid_values` is informational (shape contract) — its content evolves as the registries grow, but its tuple type is stable.

## Entity: `RunSummary` additive top-level fields (`module_set_id`, `det_rec_variant_id`, `ppstructure_modules_invoked`)

The three new top-level fields added to the existing `kind: "run_summary"` stdout shape (feature 011 / 014 / 015 / 016 lineage). All three are emitted on every run regardless of profile or opt-in state (FR-008 / FR-010).

**Shape**:

```jsonc
{
  // ... existing 0.1.3 fields including phase_timings.warmup ...
  "preprocess_lane": "cpu" | "gpu0" | ...,             // feature 014 T027 — last existing top-level field
  "module_set_id": <string>,                           // ← NEW: one of the closed vocabulary values (R-017.2)
  "det_rec_variant_id": <string>,                      // ← NEW: one of the closed vocabulary values (R-017.4)
  "ppstructure_modules_invoked": [<string>, ...]       // ← NEW: subset of AUDIT_SUB_MODULE_VOCABULARY (R-017.7)
}
```

**Types**:

| Field | JSON type | Python type | Default |
|---|---|---|---|
| `module_set_id` | string | `str` | `"cpu-default"` (CPU lane) / `"stub-default"` (stub) / `"legacy"` (GPU lane no-flag) |
| `det_rec_variant_id` | string | `str` | `"cpu-default"` (CPU lane) / `"stub-default"` (stub) / `"legacy"` (GPU lane no-flag) |
| `ppstructure_modules_invoked` | array of strings | `list[str]` | `[]` (CPU lane and stub adapter); subset of `AUDIT_SUB_MODULE_VOCABULARY` on GPU |

**Presence rules** (FR-008 / FR-010):

| Condition | All three fields present? | Field values |
|---|---|---|
| `ppstructurev3@cpu` no-flag run | YES | `module_set_id="cpu-default"`, `det_rec_variant_id="cpu-default"`, `ppstructure_modules_invoked=[]` |
| `ppstructurev3@cpu` with `--module-set=reduced-v1` (warn-and-proceed) | YES | identical to no-flag CPU run (warn-and-proceed nullifies the flag) |
| stub adapter | YES | `module_set_id="stub-default"`, `det_rec_variant_id="stub-default"`, `ppstructure_modules_invoked=[]` |
| `ppstructurev3@gpu` no-flag run | YES | `module_set_id="legacy"`, `det_rec_variant_id="legacy"`, `ppstructure_modules_invoked` = audit result for legacy (typically `["layout_detection", "ocr_det", "ocr_rec", "table_recognition"]`) |
| `ppstructurev3@gpu` with `--module-set=reduced-v1` | YES | `module_set_id="reduced-v1"`, `det_rec_variant_id="legacy"`, `ppstructure_modules_invoked` = audit result for reduced-v1 (typically `["layout_detection", "ocr_det", "ocr_rec"]`) |
| `ppstructurev3@gpu` with `--det-rec-variant=ppocrv5-mobile` | YES | `module_set_id="legacy"`, `det_rec_variant_id="ppocrv5-mobile"`, `ppstructure_modules_invoked` = audit result for legacy |
| Unknown preset (e.g., `--module-set=reduced-v99`) | N/A | run exits with code 16 BEFORE any run_summary is emitted (R-017.9 / R-017.12) |
| GPU bind failure / preflight failure / warmup failure | N/A | run exits non-zero before run_summary emission (existing feature 014 / 016 fail-fast paths preserved) |

**Excluded from**: `phase_timings.*`, `per_document[*]`, `profile_initialization_seconds` — the three new fields are exclusively top-level on the `run_summary` line, not nested. This matches feature 014 T027's `preprocess_lane` placement.

**Stability stance**: the three field names (`module_set_id`, `det_rec_variant_id`, `ppstructure_modules_invoked`), their types (string, string, list-of-strings), and their emission position (between `preprocess_lane` and the run_summary's terminating brace) are part of the public 0.1.4 contract. Tests, monitoring, and downstream consumers MAY assert all three are always present on every run of the new binary regardless of profile.

## Entity: `RunSummary.SCHEMA_VERSION` (codebase-level bump)

Codebase-level transition driven by this feature: `"0.1.3"` → `"0.1.4"`. Set in `src/dartwing_ocr/pipeline/timing.py:86` (the single source of truth). Every run of the new binary emits `schema_version: "0.1.4"` regardless of preset selection (R-017.8 / FR-008 / FR-010).

The 0.1.4 schema is a strict superset of 0.1.3: it adds three top-level optional-but-always-emitted fields. Existing 0.1.3 fields (`schema_version`, `kind`, `stack_preset`, `resolved_profiles`, `execution_slice`, `on_failure`, `documents_total`, `documents_succeeded`, `documents_failed`, `profile_initialization_seconds`, `per_document`, `preprocess_lane`, plus per-document `phase_timings.{paddle_import, gpu_bind_probe, engine_init, warmup, rasterization, per_page_inference, artifact_write, total}`) MUST NOT be renamed, removed, or have their type changed (FR-009 / FR-019).

## Entity: `AUDIT_SUB_MODULE_VOCABULARY` (closed string set)

Module-level constant in `src/dartwing_ocr/preprocessing/identifiers.py`. The exhaustive set of strings allowed in `RunSummary.ppstructure_modules_invoked` at landing time:

```python
AUDIT_SUB_MODULE_VOCABULARY: tuple[str, ...] = (
    "layout_detection",
    "table_recognition",
    "ocr_det",
    "ocr_rec",
)
```

**Invariants**:

- The audit-callable implementation in `preprocessing/presets.py` (R-017.7) MUST drop any sub-module name not in this tuple before populating the list. New PaddleOCR sub-modules in a future release are silently dropped, NOT emitted as unknown strings — a regression test asserts that `ppstructure_modules_invoked` is always a subset of `AUDIT_SUB_MODULE_VOCABULARY`.
- The list emitted on the run_summary is sorted lexicographically for determinism — sorted output makes diff-by-line trivial across runs.
- Adding a new sub-module to this vocabulary is a future-feature decision (matches the registry-extension stance in R-017.2 / R-017.4).

## Entity: CPU/stub identifier constants

Module-level constants in `src/dartwing_ocr/preprocessing/identifiers.py`:

```python
CPU_DEFAULT_MODULE_SET: str = "cpu-default"
CPU_DEFAULT_DET_REC_VARIANT: str = "cpu-default"
STUB_DEFAULT_MODULE_SET: str = "stub-default"
STUB_DEFAULT_DET_REC_VARIANT: str = "stub-default"
```

**Invariants**:

- These four string constants form a closed set used by run_summary build code on non-GPU lanes (R-017.5).
- They MUST match the corresponding entries in `MODULE_SET_PRESETS` and `DET_REC_VARIANTS` registries 1:1 — a missing match is a code defect.

## Entity: `ExitCode.UNKNOWN_PRESET` (new exit code 16)

New entry in `src/dartwing_ocr/pipeline/exit_codes.py`. Immediately after feature 016's `WARMUP_FAILED = 15`.

```python
class ExitCode(IntEnum):
    SUCCESS = 0
    GENERIC_FAILURE = 1
    PADDLE_NOT_INSTALLED = 10              # feature 014
    PADDLE_CPU_ONLY = 11                   # feature 014
    GPU_NOT_EXPOSED = 12                   # feature 014
    GPU_EXPOSED_PADDLE_CANT_BIND = 13      # feature 014
    PPSTRUCTUREV3_INIT_FAILED = 14         # feature 014
    WARMUP_FAILED = 15                     # feature 016
    UNKNOWN_PRESET = 16                    # ← NEW: this feature, R-017.9 / R-017.12
```

**Stability stance**: exit code 16 is the public contract for "the operator selected an unknown `module_set_id` or `det_rec_variant_id` value". Operators and CI scripts MAY key off it directly. Adding a 17th code is a future-feature decision.
