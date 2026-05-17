# Data Model: Workstation Paddle GPU Preprocessing Validation

**Feature**: 014-paddle-gpu-preprocessing
**Date**: 2026-05-06

This feature introduces no new persisted artifact and no schema field
on any of the four stage 1 contracts. The data model below covers the
*in-memory* entities the implementation materializes and the
*string-format* additions that propagate into existing artifact fields.

---

## In-memory entities

### `PreflightState` (enum)

```python
class PreflightState(str, Enum):
    PADDLE_NOT_INSTALLED = "paddle_not_installed"
    PADDLE_CPU_ONLY = "paddle_cpu_only"
    GPU_NOT_EXPOSED = "gpu_not_exposed"
    GPU_EXPOSED_PADDLE_CANT_BIND = "gpu_exposed_paddle_cant_bind"
    PPSTRUCTUREV3_INIT_FAILED = "ppstructurev3_init_failed"
    PPSTRUCTUREV3_INIT_SUCCEEDED = "ppstructurev3_init_succeeded"
```

Member ordering matches FR-001 (a)–(f). The enum is the **single
source of truth** for FR-001 vocabulary; the pipeline runtime gate, the
preflight CLI, and the pytest skip-reason mapper all import this
type directly. Adding a new state is a deliberate code change in
`preprocessing/preflight.py` plus a corresponding update to the
documentation in `docs/stage1-vendor-identity/paddle-gpu-preflight.md`.

### `PreflightEvidence` (frozen dataclass)

| Field                                | Type             | Source / Provenance |
|--------------------------------------|------------------|---------------------|
| `interpreter_path`                   | `str`            | `sys.executable` |
| `interpreter_version`                | `str`            | `f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"` |
| `venv_path`                          | `Optional[str]`  | `sys.prefix` if it differs from `sys.base_prefix`, else `None` |
| `paddle_version`                     | `Optional[str]`  | `importlib.metadata.version("paddlepaddle")` or `None` if not installed |
| `paddleocr_version`                  | `Optional[str]`  | `importlib.metadata.version("paddleocr")` or `None` |
| `paddle_compiled_with_cuda`          | `Optional[bool]` | `paddle.is_compiled_with_cuda()` (None if paddle import failed) |
| `paddle_compiled_with_rocm`          | `Optional[bool]` | `paddle.is_compiled_with_rocm()` (None if paddle import failed) |
| `visible_device_count`               | `Optional[int]`  | `paddle.device.cuda.device_count()` (None on import failure) |
| `selected_device`                    | `Optional[str]`  | `"gpu:0"` after a successful `paddle.device.set_device`; `"cpu"` for CPU-only build; `None` if no attempt |
| `runtime_device_exposure`            | `dict[str,bool]` | See R-014.10 — six boolean keys |
| `ppstructurev3_init_seconds`         | `Optional[float]`| `time.monotonic_ns()` delta around `PPStructureV3(...)` construction; rounded to 6 decimals; only set when init was attempted and succeeded |
| `ppstructurev3_init_error`           | `Optional[str]`  | `str(exc)` truncated to 1000 chars when init was attempted and failed |
| `ppstructurev3_init_skipped_reason`  | `Optional[str]`  | Set to `"caller_disabled_init_attempt"` when classifier called with `attempt_ppstructurev3_init=False`; else None |

Validation rules (enforced in classifier construction, not via Pydantic):

- Exactly one of `ppstructurev3_init_seconds`, `ppstructurev3_init_error`,
  `ppstructurev3_init_skipped_reason` is non-None when paddle import
  succeeded; all three are None when paddle import failed.
- When `paddle_compiled_with_cuda` and `paddle_compiled_with_rocm` are
  both False, `state` MUST be `PADDLE_CPU_ONLY` and
  `visible_device_count` MUST be `0` or None.
- When `state == PPSTRUCTUREV3_INIT_SUCCEEDED`, `selected_device` MUST
  match `^gpu:\d+$`.

### `PreflightReadout` (frozen dataclass)

| Field             | Type                | Notes |
|-------------------|---------------------|-------|
| `state`           | `PreflightState`    | Drives exit code per R-014.5 |
| `evidence`        | `PreflightEvidence` | Captured at classify-time |
| `recommendation`  | `str`               | One sentence, terminal-readable; FR-002 / FR-003 |
| `schema_version`  | `Literal["0.1.0"]`  | Class constant, surfaced into JSON |

Methods:

- `to_text() -> str` — human-readable section per R-014.5.
- `to_json_dict() -> dict[str, object]` — JSON-serializable mapping with
  shape `{kind, schema_version, state, evidence, recommendation}`.

The dataclass is frozen so consumers (pipeline gate, conftest) cannot
mutate it. Construction goes through `classify(...)` in
`preprocessing/preflight.py`; consumers MUST NOT instantiate `PreflightReadout`
directly outside the classifier or its tests.

### `LaneSegment` (string-typed value object)

Not a class; just a documented format. Defined in
`preprocessing/version.py`:

- Grammar: `lane_segment ::= "cpu" | ("gpu" digit+)` where `digit+`
  is the device index Paddle bound to.
- Appended to `pipeline_version` as the trailing `.<lane_segment>`
  segment, *after* `dpi<N>`.
- Parsed back by a pure helper with this normative signature
  (analyze finding AA5):

  ```python
  def parse_lane_segment(pipeline_version: str) -> tuple[str, Optional[int]]: ...
  ```

  Behavior:
  - For a post-feature CPU string ending in `.cpu`: returns `("cpu", None)`.
  - For a post-feature GPU string ending in `.gpu<N>`: returns `("gpu", N)`.
  - For a **pre-feature** `pipeline_version` (no trailing lane
    segment, ends with `.dpi<N>`): returns `("cpu", None)`. This is
    the backward-compatible parser default — pre-feature artifacts
    were always produced by the CPU profile, so coercing to `cpu` is
    semantically correct.
  - For a **forward-compatible unknown segment** (e.g.
    `.npu0`, `.jetson0`, anything not matching `cpu|gpu\d+`):
    returns `("unknown", None)` and does NOT raise. Strict
    consumers in future features may upgrade to a fail-fast policy;
    today's parser MUST tolerate unrecognized segments.
  - For a malformed `pipeline_version` (e.g. empty, missing
    `dpi<N>`, missing the `+paddleocr…` block): raises a
    `ValueError` with a message naming the offending input.

**Rationale for the backward-compat default** (analyze finding NEW.11):
pre-feature artifacts were CPU-only by definition (the GPU lane did
not exist before this feature), so coercing the missing trailing
segment to `("cpu", None)` preserves their original semantics and
keeps them forward-parseable in contexts where lane identity is
needed. This is **not** a parsing bug to be "fixed" in a future
feature — it is the documented backward-compat default. Future lane
additions (e.g., a hypothetical `npu` lane) should follow the same
discipline: treat unrecognized segments as `("unknown", None)`
(forward-compat), and treat missing segments on pre-feature
artifacts as `("cpu", None)` (backward-compat). Genuinely malformed
strings — those missing `dpi<N>` or the `+paddleocr…` block — still
raise `ValueError`; only the trailing-segment slot is permissive.

### `RunSummary` (existing dataclass — additive change)

Located in `src/dartwing_ocr/pipeline/timing.py`. Three additive
field-paths land in this feature:

| Field path                                                | Type              | Presence                                  |
|-----------------------------------------------------------|-------------------|-------------------------------------------|
| `preprocess_lane`                                          | `str`             | Always present once the feature ships; values `"cpu"` or `"gpu<N>"` |
| `profile_initialization_seconds.preprocess`               | `float`           | Already exists; populated for both CPU and GPU lanes (no shape change) |
| `per_document[].stages.preprocess.gpu_init_seconds`       | `float`           | Present only on the first document in a GPU run where init occurred (R-009 phase-key absence policy) |
| `per_document[].stages.preprocess.gpu_inference_seconds`  | `float`           | Present on every per-document entry produced by the GPU lane |
| `per_document[].gpu_lane_forced_abort`                    | `bool` (always `true` when present) | Present only on the per-document failure record that triggered the R-014.4 forced abort; always `true` when present |

`SCHEMA_VERSION` bumps from `0.1.0` → `0.1.1`. Consumers of the
existing schema MUST keep working; the new fields are strictly
additive.

### `GpuPrerequisiteError` (in-memory exception type — analyze finding AA1, module location pinned per AA1')

**Defined in**: `src/dartwing_ocr/preprocessing/preflight.py`, alongside
`PreflightState`, `PreflightEvidence`, and `PreflightReadout`. Implemented
as part of T002–T005 (the same Foundational tasks that define the
classifier surface).

**Imported by**:
- `src/dartwing_ocr/preprocessing/pipeline.py` (T021) — raises
  `GpuPrerequisiteError` from the inline GPU gate when the cached
  `PreflightReadout.state` is anything other than
  `PPSTRUCTUREV3_INIT_SUCCEEDED`.
- `src/dartwing_ocr/preprocessing/cli.py` (T022) — catches
  `GpuPrerequisiteError`, renders the FR-009 stderr message, and exits
  with the FR-001 exit code from Contracts §1.
- `src/dartwing_ocr/pipeline/runner.py` and
  `src/dartwing_ocr/pipeline/corpus_run.py` (T023, T024) — also
  catch the same exception type when running the warm-corpus path.

**Shape**:

```python
class GpuPrerequisiteError(Exception):
    """Raised by preprocessing/pipeline.py when the GPU gate detects a
    non-success FR-001 state. Caught by preprocessing/cli.py (T022) and
    rendered as the FR-009 stderr message."""

    state: PreflightState   # the FR-001 fail state from the cached PreflightReadout
    recommendation: str     # the human-readable next-step recommendation
```

Not persisted, not serialized to JSON, not part of any contract
artifact. Exists purely as the transport between the preprocessing
gate (T021) and the CLI error formatter (T022). Its shape may evolve
without an amendment so long as the (state, recommendation) pair
remains accessible to the CLI rendering code path.

**Runtime model bridge** (analyze finding NEW.10): the gate's
runtime model integrates three concerns:

1. **Q2 clarification** (`spec.md` Clarifications 2026-05-06):
   single `classify(...)` invocation per process before the first
   artifact write; no cross-process cache.
2. **Research R-014.4** (cached in-process readout): the per-process
   result is stored in the module-level `_PREFLIGHT_READOUT:
   Optional[PreflightReadout] = None` variable in
   `src/dartwing_ocr/pipeline/corpus_run.py` (established by T023,
   read by T029).
3. **`GpuPrerequisiteError`** (this section): the in-memory
   transport from the gate (T021, which raises) to the CLI error
   formatter (T022, which catches). The exception's `state` and
   `recommendation` are populated from the cached `PreflightReadout`,
   so the FR-001 vocabulary remains the single source of truth all
   the way from classifier output to stderr message.

Together these three concerns implement the FR-009 fail-fast gate
without leaking Paddle/PaddleOCR exception types into the pipeline
error path.

---

## Persisted artifact field changes

Only one persisted-artifact field changes shape, and it is a free-form
string today:

### `preprocess_output.json :: pipeline_version`

| Before this feature                                      | After (CPU)                                             | After (GPU on card 0)                                    |
|---------------------------------------------------------|---------------------------------------------------------|----------------------------------------------------------|
| `stage1-preprocess-v0.2.0+paddleocr3.5.0.0000000.dpi300` | `stage1-preprocess-v0.2.0+paddleocr3.5.0.0000000.dpi300.cpu` | `stage1-preprocess-v0.2.0+paddleocr3.5.0.0000000.dpi300.gpu0` |

Schema validation: `preprocess_output.schema.json` only requires
`pipeline_version` to be `{"type": "string", "minLength": 1}`. Both
the old and new strings satisfy that constraint, so no schema
amendment is required (per FR-015 / FR-025).

CPU byte-stability (FR-017 / SC-006): repeat CPU runs after this
feature lands MUST produce the same `pipeline_version` string and
the same `preprocess_output.json` bytes. The byte-level pre-feature
vs. post-feature comparison is a change of one trailing segment;
that change is a one-time intentional bump, not a determinism
regression.

---

## Entity relationships

```text
PreflightState  ←  enum member  ←  PreflightReadout.state
                                          ↑
                                          │
                                          │ produced by
                                          │
                              classify(...)  in  preprocessing/preflight.py
                                          │
                                          │ consumed by
                                          │
                ┌─────────────────────────┼─────────────────────────┐
                │                         │                         │
                ▼                         ▼                         ▼
   preflight_cli.py             preprocessing/pipeline.py   tests/conftest.py
   (text + JSON readout)        (FR-009 inline gate)        (gpu marker skip)

LaneSegment   →   build_pipeline_version(..., lane_segment=…)
                                          │
                                          ▼
                            preprocess_output.json :: pipeline_version

RunSummary   →   timing.py emit_run_summary(...)
                                          │
                                          ▼
                              stdout last line: kind: "run_summary"
```

---

## State transitions

`PreflightState` is a classification, not a state machine — each
`classify(...)` call produces exactly one terminal state from the
six-member enum. There are no transitions between states within a
classifier run. Consecutive `classify(...)` calls are independent.

The pipeline runtime gate's behavior given each preflight state:

| Preflight state                         | Pipeline action when GPU lane requested                              |
|-----------------------------------------|----------------------------------------------------------------------|
| `PPSTRUCTUREV3_INIT_SUCCEEDED`          | Proceed to preprocessing                                             |
| `PADDLE_NOT_INSTALLED`                  | Fail-fast; exit code 10; no artifact written                         |
| `PADDLE_CPU_ONLY`                       | Fail-fast; exit code 11; no artifact written                         |
| `GPU_NOT_EXPOSED`                       | Fail-fast; exit code 12; no artifact written                         |
| `GPU_EXPOSED_PADDLE_CANT_BIND`          | Fail-fast; exit code 13; no artifact written                         |
| `PPSTRUCTUREV3_INIT_FAILED`             | Fail-fast; exit code 14; no artifact written                         |

The error message in every fail-fast case names both the selected
profile (`ppstructurev3@gpu`) and the FR-001 state name verbatim —
this is the FR-009 contract.
