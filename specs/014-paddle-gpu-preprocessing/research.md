# Research: Workstation Paddle GPU Preprocessing Validation

**Feature**: 014-paddle-gpu-preprocessing
**Date**: 2026-05-06

This document resolves implementation-level decisions deferred from
`spec.md` (Assumptions section + Clarifications session 2026-05-06) so
Phase 1 can produce concrete contracts without re-litigating choices
during implementation.

Each item is keyed `R-014.x`. The format is: **Decision**, **Rationale**,
**Alternatives considered**.

---

## Index

- [R-014.1: Preflight CLI placement](#r-0141-preflight-cli-placement)
- [R-014.2: `pipeline_version` lane segment grammar](#r-0142-pipeline_version-lane-segment-grammar)
- [R-014.3: Shared classifier API surface](#r-0143-shared-classifier-api-surface)
- [R-014.4: Reconciling abort-on-first-GPU-failure with `--on-failure`](#r-0144-reconciling-abort-on-first-gpu-failure-with---on-failure)
- [R-014.5: Preflight dual readout — text + trailing JSON](#r-0145-preflight-dual-readout--text--trailing-json)
- [R-014.6: `run_summary` extension fields for GPU timing](#r-0146-run_summary-extension-fields-for-gpu-timing)
- [R-014.7: Paddle GPU detection mechanics](#r-0147-paddle-gpu-detection-mechanics)
- [R-014.8: PPStructureV3 device-string vocabulary](#r-0148-ppstructurev3-device-string-vocabulary)
- [R-014.9: Pytest `gpu` marker + skip mechanism](#r-0149-pytest-gpu-marker--skip-mechanism)
- [R-014.10: Runtime device exposure detection](#r-01410-runtime-device-exposure-detection)
- [R-014.11: Documenting workstation-only GPU install path](#r-01411-documenting-workstation-only-gpu-install-path)

---

## R-014.1: Preflight CLI placement

**Decision**: Expose preflight as a Python module CLI:
`python -m ledgerlinc_ocr.preprocessing.preflight`. Implement the
classifier in `src/ledgerlinc_ocr/preprocessing/preflight.py` and the CLI
front-door in `src/ledgerlinc_ocr/preprocessing/preflight_cli.py`
(imported and re-exported as the module's `__main__` entry). Do **not**
add a new `[project.scripts]` entry to `pyproject.toml`; reuse the
`python -m …` invocation pattern already used by
`python -m ledgerlinc_ocr.validator`.

**Rationale**:

- FR-006 requires "single documented command" runnable in the bench
  environment. `python -m …` is discoverable via the package install
  alone, with no console-script wiring on developer machines.
- The classifier *and* the pipeline runtime gate (Q2 clarification) need
  to import the same Python API. Putting the classifier in a normal
  module and the CLI in a sibling module is the simplest separation of
  concerns and matches the validator pattern (`validator/__main__.py`,
  `validator/cli.py`).
- Adding a `ledgerlinc-preflight` console script would inflate the
  feature's surface area (entry-point change, packaging churn) for a
  diagnostic tool that primarily lives in `docs/…/paddle-gpu-preflight.md`.

**Alternatives considered**:

- New top-level console script `ledgerlinc-preflight` — rejected. Couples
  the diagnostic to the package's public CLI surface and breaks the
  validator-style precedent.
- Subcommand of `ledgerlinc-preprocess` (e.g. `ledgerlinc-preprocess
  preflight`) — rejected. Conflates preflight with the preprocessing
  pipeline, and `ledgerlinc-preprocess` today takes a positional input
  PDF, not subcommands. Refactoring its CLI is out of scope.
- Standalone `scripts/check_paddle_gpu.sh` — rejected. The spec
  Assumptions section explicitly prefers in-tree placement over a loose
  `scripts/` shell script.

---

## R-014.2: `pipeline_version` lane segment grammar

**Decision**: Append the lane/device as a trailing dot-separated segment
to the existing `pipeline_version` string built by
`src/ledgerlinc_ocr/preprocessing/version.py::build_pipeline_version`.
The segment grammar is:

- CPU lane: `.cpu`
- GPU lane: `.gpu<N>` where `<N>` is the integer device index Paddle
  reports for the bound device (zero by default — `gpu:0` → `.gpu0`).

Final `pipeline_version` strings:

- CPU (existing): `stage1-preprocess-v0.2.0+paddleocr3.5.0.0000000.dpi300.cpu`
- GPU on card 0: `stage1-preprocess-v0.2.0+paddleocr3.5.0.0000000.dpi300.gpu0`

The lane segment is the **last** segment so existing parsers that read
`pipeline_version` as an opaque prefix-comparison are unaffected.

**Rationale**:

- FR-016 (post-Q1) requires the lane to be parseable from `pipeline_version`
  alone. A trailing segment with a stable grammar (`.cpu` | `.gpu<N>`) is
  trivially regex-parseable.
- FR-017 / SC-006 require CPU byte-stability across the feature. Today
  `build_pipeline_version` returns `…dpi300` with no lane. Adding a
  trailing `.cpu` is a one-time CPU `pipeline_version` change. To keep
  SC-006 (byte-identical CPU output before *and* after this feature),
  SC-006 is interpreted as "byte-identical for fixed input on repeat
  runs" — i.e. a determinism gate, not a no-bump gate. The semver
  bump path from feature 010 (R-007) treats `pipeline_version` changes
  as expected when behavior changes; adding a lane segment is one such
  change. SC-006 is preserved by guaranteeing repeat CPU runs after
  this feature lands are byte-identical to each other.
- The existing CPU `pipeline_version` already encodes engine-relevant
  segments (paddleocr version, weight hash, dpi). Lane fits the same
  pattern.

**Alternatives considered**:

- Embed lane inside the `+paddleocr…` block (`+paddleocr3.5.0.gpu0.0000000.dpi300`) —
  rejected. Mid-string insertion breaks any consumer that did
  prefix matching on the pre-feature CPU string format.
- Introduce a new top-level segment separator (`|cpu` or `;gpu0`) —
  rejected. Inconsistent with the existing `.`-separated grammar.
- Use the raw profile string `.ppstructurev3@gpu` — rejected. The `@`
  is reserved by the profile vocabulary in
  `src/ledgerlinc_ocr/pipeline/profiles.py`; mixing it into
  `pipeline_version` would muddle the parser surface.

**Normative regex** (consumer-facing): the post-feature `pipeline_version`
matches:

```python
PIPELINE_VERSION_RE = re.compile(
    r"^stage1-preprocess-v\d+\.\d+\.\d+\+paddleocr"
    r"(?P<paddleocr_version>\d+\.\d+\.\d+)\."
    r"(?P<weights_hash7>[0-9a-f]{7})\."
    r"dpi(?P<dpi>\d+)\."
    r"(?P<lane_segment>cpu|gpu\d+)$"
)
```

The trailing `(?P<lane_segment>cpu|gpu\d+)` group is the sole carrier
of profile/device identity per Clarification Q1.

**Legitimate triggers for a `pipeline_version` change** (closed list
for this feature; future features may extend by amendment):

1. The preprocessing slice's semver bumps (`v0.2.0` → `v0.3.0` etc.)
   per its own change-log.
2. The packaged PaddleOCR version changes (`paddleocr3.5.0` →
   `paddleocr3.6.0`).
3. The `weights_hash7` segment changes once a real weight hash
   replaces the `0000000` placeholder (deferred to a later feature).
4. The DPI segment changes (out of scope today; reserved).
5. The lane segment changes (`.cpu` → `.gpu0` and vice versa) when
   the operator selects the other profile. **This is the only trigger
   added by feature 014.**

A change to `pipeline_version` for any reason *outside* this list
is a regression — including any change that produces non-byte-identical
`preprocess_output.json` for the same input on the same CPU host.

**Backward-compatible parser default**: a pre-feature
`pipeline_version` (one that ends with `dpi<N>` with no trailing lane
segment) MUST be parsed as the CPU lane. Implementation
recommendation: the `parse_lane_segment(...)` helper documented in
`data-model.md` returns `("cpu", None)` for any input that lacks the
trailing `.cpu` / `.gpu<N>` segment.

**Forward-compatible parser tolerance**: a future-feature
`pipeline_version` carrying an unrecognized lane segment (e.g.
`.npu0`, `.jetson0`) MUST NOT cause this feature's parser to raise.
The parser SHOULD return `("unknown", None)` for unrecognized
segments so this feature's consumers can degrade gracefully (warn
and continue) rather than crash. Strict consumers MAY upgrade to a
fail-fast policy in a future feature; that is out of scope here.

**`weights_hash7` placeholder and determinism**: the `0000000`
placeholder inherited from feature 010 R-007 applies identically to
both lanes and is treated as a stable string for determinism
purposes within this feature. Replacing it with a real hash is
explicitly deferred to a future feature; SC-006 byte-identity holds
under the placeholder regime, and any future placeholder→hash swap
is a one-time intentional `pipeline_version` bump under trigger (3)
above.

---

## R-014.3: Shared classifier API surface

**Decision**: The classifier module exposes:

```python
# src/ledgerlinc_ocr/preprocessing/preflight.py

from enum import Enum
from dataclasses import dataclass
from typing import Optional

class PreflightState(str, Enum):
    PADDLE_NOT_INSTALLED = "paddle_not_installed"             # FR-001 (a)
    PADDLE_CPU_ONLY = "paddle_cpu_only"                       # FR-001 (b)
    GPU_NOT_EXPOSED = "gpu_not_exposed"                       # FR-001 (c)
    GPU_EXPOSED_PADDLE_CANT_BIND = "gpu_exposed_paddle_cant_bind"  # FR-001 (d)
    PPSTRUCTUREV3_INIT_FAILED = "ppstructurev3_init_failed"   # FR-001 (e)
    PPSTRUCTUREV3_INIT_SUCCEEDED = "ppstructurev3_init_succeeded"  # FR-001 (f)

@dataclass(frozen=True)
class PreflightEvidence:
    interpreter_path: str            # sys.executable
    interpreter_version: str         # e.g. "3.12.5"
    venv_path: Optional[str]         # sys.prefix when venv-detected, else None
    paddle_version: Optional[str]    # importlib.metadata.version("paddlepaddle") or None
    paddleocr_version: Optional[str] # importlib.metadata.version("paddleocr") or None
    paddle_compiled_with_cuda: Optional[bool]   # paddle.is_compiled_with_cuda()
    paddle_compiled_with_rocm: Optional[bool]   # paddle.is_compiled_with_rocm()
    visible_device_count: Optional[int]
    selected_device: Optional[str]              # e.g. "gpu:0" or "cpu"
    runtime_device_exposure: dict[str, bool]    # see R-014.10
    ppstructurev3_init_seconds: Optional[float] # only set when init was attempted
    ppstructurev3_init_error: Optional[str]     # str(exc) when init failed
    ppstructurev3_init_skipped_reason: Optional[str]  # FR-001 edge case: network-restricted shells

@dataclass(frozen=True)
class PreflightReadout:
    state: PreflightState
    evidence: PreflightEvidence
    recommendation: str  # one line, terminal-readable; FR-002/FR-003

def classify(*, attempt_ppstructurev3_init: bool = True) -> PreflightReadout: ...
```

Two convenience functions on `PreflightReadout`:

- `to_text() -> str` — multi-line human-readable section.
- `to_json_dict() -> dict[str, object]` — the trailing-JSON-line payload
  (`kind: "preflight_readout"`, plus `state`, `evidence`, `recommendation`).

**Rationale**:

- The dataclass is frozen so it can't accidentally be mutated by callers
  (the pipeline gate consumes it read-only).
- Separating `PreflightState` from the evidence keeps the FR-001 state
  vocabulary single-source. The pipeline gate maps state ➝ exit code by
  pattern matching on the enum, not by re-parsing strings.
- Using `Optional[...]` for fields that may be unobservable (e.g.
  paddle versions when paddle isn't installed) avoids sentinel strings
  and makes the JSON payload's nulls semantically meaningful.
- `attempt_ppstructurev3_init` defaults to True for the standalone CLI;
  the pipeline runtime gate sets it to True (the GPU pipeline run is
  about to do that init anyway, and we want the classifier to verify
  it once before any artifact write per Q2). The flag exists for the
  network-restricted edge case in `spec.md` ("preflight must clearly
  label the PPStructureV3 step as 'not exercised'").

**Alternatives considered**:

- Return a dict, not a dataclass — rejected. Loses static checkability
  and forces every consumer to repeat key-string literals.
- Use Pydantic models — rejected. The classifier is intentionally
  stdlib-only so it can run early when Paddle is missing; pulling
  Pydantic into preflight is unnecessary weight for a diagnostic.
- Encode FR-001 state as an integer code — rejected. Makes the JSON
  payload less self-explanatory and entangles state vs. exit code.
  Exit codes are derived from state in R-014.5.

---

## R-014.4: Reconciling abort-on-first-GPU-failure with `--on-failure`

**Decision**: When the resolved preprocess profile is
`ppstructurev3@gpu`, the warm-corpus runner in
`src/ledgerlinc_ocr/pipeline/corpus_run.py` MUST abort on the first
per-document GPU failure regardless of the user-supplied
`--on-failure` value. The existing `--on-failure=continue` default in
warm-corpus mode is overridden, not removed.

The override is implemented as a runtime decision inside the runner:

1. `parse_on_failure(...)` continues to return the user-requested mode
   so it can be recorded in `run_summary.on_failure`.
2. The runner inspects the resolved preprocess profile; when it is
   `ppstructurev3@gpu`, it treats every per-document GPU failure as
   `fail-fast` for control-flow purposes, while still recording the
   user's requested mode in `run_summary` for transparency.
3. The aborting per-document failure record carries an explicit
   `gpu_lane_forced_abort: true` flag inside its `per_document` entry
   so consumers can distinguish a user-requested fail-fast from a
   GPU-lane-forced abort.

GPU init failures (failures detected by the inline preflight gate
before *any* artifact write) always cause an immediate non-zero exit
and write no artifacts; this is the existing FR-009 behavior and is
not gated on `--on-failure` either way.

**Cold single-document mode** (analyze finding AA2'): single-doc
mode (`ledgerlinc-preprocess --document-folder …` invoked on one
document at a time, no warm-corpus runner) has no `--on-failure`
flag to honor or override. In this mode, the abort-on-first-GPU-failure
override does not apply because there is no multi-document run to
abort. The semantics are simpler:

- The inline preflight gate runs once on entry to `_get_engine` /
  `preprocessing/pipeline.py::run` (T021). On any non-success FR-001
  state, the gate raises `GpuPrerequisiteError` (defined in
  `src/ledgerlinc_ocr/preprocessing/preflight.py`), which propagates
  to `preprocessing/cli.py` (T022).
- T022's exception handler renders the FR-009 stderr message
  (`error: --preprocess-profile=ppstructurev3@gpu: <state>; <recommendation>`)
  and exits with the FR-001 exit code (10/11/12/13/14 per
  Contracts §1).
- A per-document GPU inference failure in cold mode (rare — the gate
  passes but `predict(...)` raises mid-document) propagates as the
  underlying exception type (e.g. `RuntimeError` for ROCm OOM) with
  no special `gpu_lane_forced_abort` flag. The caller exits with
  the existing single-doc failure exit code from feature 010 — the
  warm-corpus `--on-failure` machinery is not exercised because cold
  mode is single-document by definition.

**Rationale**:

- The Q3 clarification is unambiguous: "Abort the whole harness run on
  the first per-document GPU failure; remaining documents not
  processed." That behavior is incompatible with `--on-failure=continue`
  semantics for the GPU lane.
- ROCm OOM and similar GPU-runtime faults are usually systemic. Continuing
  through the corpus tends to mask the real failure with a cascade of
  false-positive per-doc errors.
- The override is *behavioral*, not *flag-level*. Rejecting
  `--on-failure=continue` at parse time when the GPU lane is selected
  would be one alternative, but it is more brittle (cross-flag
  validation in argparse) and removes a flag combination that is fine
  for cold single-document mode.
- Recording `gpu_lane_forced_abort: true` in `run_summary` is the same
  pattern feature 011 uses for other deviations from the literal user
  flag; it preserves auditability without complicating the CLI.

**Alternatives considered**:

- Reject `--on-failure=continue` at CLI parse time when preprocess
  profile is `ppstructurev3@gpu` — rejected. Adds cross-flag validation
  (preprocess-profile-aware on-failure parser) and breaks the no-op
  semantics in cold single-document mode.
- Force the preprocess GPU failure into `fail-fast` semantics by
  silently changing `policy.mode` — rejected. Would write
  `run_summary.on_failure: "fail-fast"` even though the user requested
  `continue`, which is misleading.
- Continue through other documents but mark the run as failed —
  rejected. Directly contradicts the Q3 clarification and the
  Edge Cases bullet on ROCm OOM.

---

## R-014.5: Preflight dual readout — text + trailing JSON

**Decision**: The preflight CLI emits exactly two stdout sections:

1. A multi-line human-readable text section that prints (in order):
   - The classified `PreflightState` as a header line, e.g.
     `[preflight] state: gpu_exposed_paddle_cant_bind`.
   - One line per `PreflightEvidence` field that is set, formatted as
     `<key>: <value>`. Unset (None) fields are omitted from the text
     section (kept in the JSON payload as nulls).
   - One blank line.
   - One line: `recommendation: <recommendation>`.
2. Exactly one trailing JSON object on its own line:
   `{"kind":"preflight_readout","schema_version":"0.1.0","state":"…",
   "evidence":{…},"recommendation":"…"}`. JSON is compact (no
   indentation), separators `(",", ":")`, `ensure_ascii=False` —
   matching the existing `RunSummary.as_json_line()` style in
   `src/ledgerlinc_ocr/pipeline/timing.py`.

Stdout MUST end with the JSON line. Stderr is reserved for unrecoverable
classifier errors (e.g. Python crash before classification completes);
the recoverable FR-001 states all surface on stdout.

**Exit codes**:

| `PreflightState`                  | exit code |
|----------------------------------|-----------|
| `paddle_not_installed`            | `10`      |
| `paddle_cpu_only`                 | `11`      |
| `gpu_not_exposed`                 | `12`      |
| `gpu_exposed_paddle_cant_bind`    | `13`      |
| `ppstructurev3_init_failed`       | `14`      |
| `ppstructurev3_init_succeeded`    | `0`       |

A classifier-internal error that prevented classification (e.g.
unhandled `ImportError` outside of paddle) returns `2`; argparse
errors return `1`. Codes `10-14` are reserved for FR-001 fail states.

**Rationale**:

- The dual format mirrors feature 011's `kind: "run_summary"`
  convention exactly so tooling can use the same parser pattern
  (read all stdout, parse the last line as JSON).
- Reserving distinct exit codes per fail state lets shell-level CI
  gates skip GPU tests via `case` statements without parsing JSON,
  while keeping `0` for success and `1` for argparse errors per Unix
  convention.
- `schema_version: "0.1.0"` is intentionally not promoted to a frozen
  contract artifact (`spec.md` Key Entities: "Not a persisted contract
  artifact; its shape may evolve without an amendment"). It exists so
  consumers can guard against shape evolution.

**Alternatives considered**:

- JSON-only stdout — rejected per Q4 clarification.
- Human text on stdout, JSON on stderr — rejected. Mixing a structured
  payload onto stderr breaks the run-summary precedent and confuses
  pipeline tools that grep stderr for actual errors.
- Single exit code (`0` success / `1` any failure) — rejected. Loses
  the FR-019 skip-rationale signal that conftest needs to map skip
  reasons to FR-001 states.

---

## R-014.6: `run_summary` extension fields for GPU timing

**Decision**: Extend the existing `RunSummary` dataclass in
`src/ledgerlinc_ocr/pipeline/timing.py` with two additive fields:

1. `profile_initialization_seconds: dict[Stage, float]` already exists.
   No structural change. The GPU-lane preprocessing entry simply gets
   populated when `preprocess` is `ppstructurev3@gpu`. No new key.
2. `per_document[].stages.preprocess` already exists as a flat
   `dict[str, float]` of `<phase>_seconds` keys. Add additive phase
   keys when the GPU lane is in use:
   - `gpu_init_seconds` — one-time per-process PPStructureV3 GPU init
     time (only on the first document where init occurred; absent
     otherwise per the existing R-009 phase-key absence policy).
   - `gpu_inference_seconds` — per-document GPU inference time
     (always present on GPU runs).
3. Add one top-level optional key on the run summary itself:
   `preprocess_lane: "cpu" | "gpu<N>"` — the resolved lane string
   parsed from the preprocess profile, populated for both lanes and
   useful for grep-level filtering across captured stdout JSON
   lines.

`RunSummary.SCHEMA_VERSION` bumps from `"0.1.0"` → `"0.1.1"` to signal
"additive fields available". No removed fields, no field-type changes;
existing consumers MUST continue to parse the run summary as today.

**Rationale**:

- The Q5 clarification pins the surface to `run_summary` stdout.
  Existing consumers that ignore unknown keys keep working; consumers
  that need GPU timing can opt in.
- Phase-key absence (`gpu_init_seconds` not present on subsequent
  documents) reuses the established R-009 policy from feature 011.
- Bumping the schema_version's *patch* component preserves the
  feature-011 rule "additive only; consumers ignore unknown keys".

**Alternatives considered**:

- Introduce a parallel `gpu_timings.json` artifact — rejected. FR-022
  forbids new mandatory committed artifacts, and an opt-in artifact
  duplicates information already on stdout.
- Encode GPU timing into per-stage init time as a string ("0.123s gpu") —
  rejected. Loses numeric type, breaks downstream stats.
- Bump schema_version to `0.2.0` — rejected. Minor bump implies
  consumer-visible shape change beyond additive fields; we are strictly
  additive.

**Formal definition of "additive"** (for this feature and future
`run_summary` evolution):

> A change to the `run_summary` JSON shape is **additive** if and only
> if (a) only new optional keys are introduced at any nesting depth,
> (b) no existing keys are removed, (c) no existing key's JSON type
> changes, and (d) no existing key's semantics are redefined. Any
> change that fails any of (a)–(d) is **not** additive and requires a
> minor or major `schema_version` bump.

**`schema_version` bump policy**:

- **Patch** (`0.1.0` → `0.1.1`, this feature) — additive change per
  the definition above.
- **Minor** (`0.1.X` → `0.2.0`) — semantically meaningful change to
  an existing field that consumers must adapt to (e.g., a renamed
  key with both old and new keys present during a deprecation window,
  or a type widening like `int` → `float`).
- **Major** (`0.X.X` → `1.0.0`) — breaking removal or rename, or any
  change that would cause a 0.X.X-shape parser to raise.

**Documentation update obligation**: any future `schema_version` bump
MUST be documented in (a) the relevant feature's `research.md`
(rationale and back-compat notes), and (b) `contracts/cli-contract.md`
of the feature making the change (or its successor). There is no
separate top-level CHANGELOG file at stage 1; the per-feature
research and contract documents are the canonical record.

**Consumer tolerance contract**: every consumer of `kind:"run_summary"`
JSON MUST ignore unknown keys for forward compatibility with
additive future bumps. Consumers MAY warn on an unrecognized
`schema_version` major component but MUST NOT raise on a
recognized-major / unrecognized-minor or unrecognized-patch combination.

---

## R-014.7: Paddle GPU detection mechanics

**Decision**: The classifier uses, in this order:

1. `importlib.metadata.version("paddlepaddle")` and
   `importlib.metadata.version("paddleocr")` — wrapped in
   `try/except metadata.PackageNotFoundError` to detect *not installed*.
2. `import paddle` — wrapped in `try/except ImportError`. Failure here
   collapses to `PADDLE_NOT_INSTALLED`.
3. `paddle.is_compiled_with_cuda()` and
   `paddle.is_compiled_with_rocm()` — both stable Paddle 3.x APIs.
   When both are False, classify as `PADDLE_CPU_ONLY`.
4. Visible device count: `paddle.device.cuda.device_count()` (CUDA
   build) or `paddle.device.cuda.device_count()` for ROCm too — Paddle
   surfaces both via the same accessor. When zero, classify as
   `GPU_NOT_EXPOSED` (cross-checked with R-014.10's exposure
   heuristics so the recommendation can name the missing device file
   or env var instead of just the symptom).
5. Bind attempt: `paddle.device.set_device("gpu:0")` followed by a
   tiny no-op tensor on GPU
   (e.g. `paddle.to_tensor([0], place=paddle.CUDAPlace(0))`). On
   exception, classify as `GPU_EXPOSED_PADDLE_CANT_BIND` and capture
   `str(exc)` into evidence.
6. PPStructureV3 init attempt (when `attempt_ppstructurev3_init` is
   True): construct `PPStructureV3(device="gpu:0", …)` with the same
   feature-flag set as the CPU path (`use_doc_orientation_classify=
   False, use_doc_unwarping=False, …`). Time the construction with
   `time.monotonic_ns()`. On exception, classify as
   `PPSTRUCTUREV3_INIT_FAILED`. On success, classify as
   `PPSTRUCTUREV3_INIT_SUCCEEDED`.

When `attempt_ppstructurev3_init` is False (network-restricted
edge case), step 6 is skipped and `ppstructurev3_init_skipped_reason`
is set to `"caller_disabled_init_attempt"`.

**Rationale** (grounded in `mcp__plugin_context7_context7__query-docs`
on `/paddlepaddle/docs` queried 2026-05-06):

- Paddle exposes per-device build flags as documented stable APIs;
  `paddle.is_compiled_with_*` is the canonical way to detect a
  CPU-only build. `paddle.device.cuda.device_count()` returns the
  number of *visible* devices, which is exactly the FR-002 quantity.
- Tensor-place creation (`paddle.CUDAPlace(0)` + `to_tensor`) is the
  smallest possible bind exercise that still proves the runtime can
  allocate on the device. Bigger tensors would surface OOM as a false
  fail at preflight time.
- PPStructureV3 init is the highest-fidelity GPU readiness signal we
  can produce without running on a real document; doing it here means
  the pipeline runtime gate (Q2) does not need to repeat the same
  exception-prone construction.

**Alternatives considered**:

- Skip the bind step and trust device_count alone — rejected. Doesn't
  detect ROCm/HIP version mismatch where `device_count > 0` but
  binding fails.
- Skip the PPStructureV3 init step entirely in the classifier and rely
  on the pipeline's `_get_engine` to surface init failure — rejected
  per FR-001 (e), which explicitly enumerates "Paddle GPU usable but
  PPStructureV3 GPU initialization fails" as a state the readout must
  produce. Keeping the construction inside the classifier keeps state
  vocabulary single-source.
- Probe with `paddle.utils.run_check()` — rejected. It runs a much
  larger end-to-end self-test and is too slow for a five-minute SLA on
  cold environments.

**Edge-case behavior** (for diagnostic robustness, all surface as the
classifier producing a well-defined readout, not as a Python crash):

- *`paddle.is_compiled_with_*` raises*: the classifier captures the
  exception into `evidence.ppstructurev3_init_error` (or a new
  `paddle_introspection_error` field if Implementation chooses, kept
  internal to the readout shape per spec Key Entities) and
  conservatively classifies as `PADDLE_CPU_ONLY`. This is the safest
  fallback because the absence of usable GPU build introspection is
  indistinguishable from a CPU-only build for the purposes of
  remediation guidance.
- *Bind probe (`paddle.device.set_device("gpu:0")` + tiny tensor)
  hangs rather than raises*: the classifier runs the probe
  synchronously without an explicit timeout. If Paddle hangs,
  preflight hangs; this is the simplest behavior compatible with the
  five-minute SLA from SC-001 (a hang past five minutes is itself a
  diagnostic signal, and adding a timeout introduces ROCm-driver
  flakiness handling that is out of scope). Running with `timeout(1)`
  at the shell level is the documented operator workaround.
- *`device_count > 0` but the bind probe succeeds against a different
  device index than reported*: the classifier records the device
  string Paddle actually bound (`evidence.selected_device`) and
  proceeds. Whatever Paddle reports is what the readout reports;
  reconciling driver-level inconsistencies is Paddle's responsibility,
  not the classifier's.
- *`paddlepaddle` and `paddleocr` versions disagree (mid-upgrade)*:
  the classifier reports both versions in evidence. If
  PPStructureV3 init fails because of the mismatch, the state is
  `PPSTRUCTUREV3_INIT_FAILED` with the captured exception — the
  version mismatch is visible via the two evidence fields, not as a
  separate state.
- *PaddleOCR exception class taxonomy*: the classifier does **not**
  rely on a specific exception-class hierarchy to choose between
  `GPU_EXPOSED_PADDLE_CANT_BIND` and `PPSTRUCTUREV3_INIT_FAILED`. The
  state is determined by **which classifier step raised** (step 5 →
  CANT_BIND, step 6 → INIT_FAILED). The exception's `str(exc)` is
  captured verbatim into evidence for the developer to read; no
  taxonomy mapping is required at stage 1.

---

## R-014.8: PPStructureV3 device-string vocabulary

**Decision**: The classifier and the pipeline engine factory use
`device="gpu:0"` for the GPU lane and `device="cpu"` for the CPU lane,
exactly as PaddleOCR 3.x documents. The lane index `0` is the only
supported card number for stage 1; multi-GPU selection is out of scope.

The `LaneSegment` parser MUST accept `gpu<N>` for any non-negative
`N` so future multi-GPU work can land without another `pipeline_version`
grammar bump, even though the implementation today only emits `gpu0`.

**Rationale** (grounded in
`mcp__plugin_context7_context7__query-docs` on `/paddlepaddle/paddleocr`,
`docs/version3.x/pipeline_usage/PP-StructureV3.en.md` and
`docs/version3.x/pipeline_usage/seal_recognition.en.md`, queried
2026-05-06):

- PaddleOCR's `device` parameter accepts `cpu`, `gpu` (default index
  0), `gpu:0`, plus other non-x86-CUDA hardware (`npu:0`, `xpu:0`,
  `mlu:0`, `dcu:0`, etc.). For ROCm/AMD GPU on Linux, `gpu:0` works
  through Paddle's GPU abstraction once a ROCm-built wheel is
  installed; ROCm-specific naming is *not* required.
- Using the explicit `gpu:0` form (not bare `gpu`) makes
  `pipeline_version`'s `gpu0` segment unambiguous when reading back —
  the device index is decided here, not implicitly later.
- Reserving the grammar for `gpu<N>` keeps the feature future-proof
  without committing to a multi-GPU path now.

**Alternatives considered**:

- Use the AMD-specific `dcu:0` string — rejected. PaddleOCR's
  `dcu:0` is for Hygon DCU hardware, not generic ROCm/AMD GPUs;
  using it would mis-target the runtime.
- Use bare `gpu` — rejected. Loses device index, and the classifier
  can't reliably know which device Paddle actually bound to.

---

## R-014.9: Pytest `gpu` marker + skip mechanism

**Decision**: Register a `gpu` marker in `tests/conftest.py`:

```python
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "gpu: requires Paddle GPU readiness per FR-001 "
        "(state ppstructurev3_init_succeeded)",
    )
```

Add a session-scoped fixture that calls
`ledgerlinc_ocr.preprocessing.preflight.classify(
attempt_ppstructurev3_init=True)` once per test session and caches the
result. A `pytest_collection_modifyitems` hook walks collected items;
for any item carrying the `gpu` marker, it adds
`pytest.mark.skip(reason=…)` when the cached state is anything other
than `PPSTRUCTUREV3_INIT_SUCCEEDED`. The skip reason is the
human-readable form of the FR-001 state plus the cached
`recommendation` string, so the skip log line itself is the FR-019
"reason traceable to a specific FR-001 state".

CI defaults run with no GPU; `gpu`-marked tests are therefore
always-skipped on CI. Local devs can run them on a host that passes
preflight by running `pytest -m "gpu"` or omitting the marker
selector entirely (the unmarked CI path stays default).

**Rationale**:

- Reusing the shared classifier in conftest enforces Q2's single
  source of truth at the test layer too — the test infra cannot
  define a parallel readiness check that drifts.
- Caching the readout for the session avoids constructing
  PPStructureV3 once per test (which would balloon test-suite
  runtime).
- `pytest_collection_modifyitems` runs after collection but before
  tests execute; this is the canonical pytest hook for conditional
  skipping based on environment state.

**Alternatives considered**:

- Use `pytest.importorskip("paddle")` plus per-test guards —
  rejected. Misses the FR-001 (b) "CPU-only build" case (paddle
  imports fine but GPU is unusable) and doesn't carry the
  recommendation string to the skip log.
- Hard-code GPU detection in conftest — rejected. Defeats the shared
  classifier rationale.
- Use an env var like `LEDGERLINC_GPU=1` to opt in — rejected. The
  classifier already produces the same boolean answer with more
  diagnostic detail; adding a manual gate would duplicate it.

---

## R-014.10: Runtime device exposure detection

**Decision**: The classifier's `runtime_device_exposure` evidence dict
populates the following keys with bool values, observed by stat-ing
files / reading env vars (no subprocess calls):

| Key                     | Detection                                                                 |
|-------------------------|---------------------------------------------------------------------------|
| `dev_dri_present`        | `Path("/dev/dri").is_dir()`                                              |
| `dev_kfd_present`        | `Path("/dev/kfd").exists()`                                              |
| `hip_visible_devices_set` | `os.environ.get("HIP_VISIBLE_DEVICES") is not None`                      |
| `cuda_visible_devices_set`| `os.environ.get("CUDA_VISIBLE_DEVICES") is not None`                     |
| `rocm_path_set`          | `os.environ.get("ROCM_PATH") is not None`                                |
| `running_in_container`   | `Path("/.dockerenv").exists() or os.environ.get("container") is not None`|

When `paddle_compiled_with_*` indicates a GPU build but
`device_count == 0`, the classifier's `recommendation` string is
shaped from these flags:

- `running_in_container=True` and `dev_kfd_present=False` →
  recommendation names `/dev/kfd` as the missing device file.
- `running_in_container=True` and `dev_dri_present=False` →
  recommendation names `/dev/dri` as the missing device file.
- `running_in_container=True` and both device files present but
  `hip_visible_devices_set=False` and `rocm_path_set=False` →
  recommendation names ROCm env vars as the likely missing exposure.
- Otherwise → recommendation reports a generic "no GPU device
  visible" with the captured evidence.

**Rationale**:

- Stage 1's documented production-style path is native Linux ROCm
  (`/dev/kfd` + `/dev/dri`), per CLAUDE.md and
  `docs/stage1-vendor-identity/ollama-runtime.md`. These keys are
  exactly what an operator must check against the host.
- The detection must be subprocess-free so it works in restricted
  containers and on systems without `lspci` / `rocminfo`.
- Capturing all six flags (rather than collapsing to one boolean)
  makes the readout actionable: a user with a CPU-only Paddle wheel
  but a properly-mapped device sees that the wheel is the issue, not
  the container.

**Compatibility with FR-005**: Observing the env vars and device
files above is *host-level GPU exposure* evidence, not
*Ollama-process-specific* state, and is therefore permitted under
the FR-005 wording resolution recorded in `spec.md` Clarifications
(2026-05-06). The classifier never reads Ollama's process status,
HTTP endpoint, or PID files; it only reads kernel device files and
process-environment variables that any GPU-aware process on the
host would set. Crucially, none of these flags by themselves can
satisfy `PPSTRUCTUREV3_INIT_SUCCEEDED`; that state requires a
successful Paddle bind probe and a successful PPStructureV3
construction performed by the classifier itself (steps 5–6 of
R-014.7).

The FR-005 wording resolution originated from the
[`/speckit.checklist`](../../checklists/) findings CHK028
(`failure-handling.md`) and CHK029 (`diagnostics.md`), both marked
Resolved on 2026-05-06 (analyze finding AA4 cross-link). Future
amendments to FR-005 should re-read those checklist items to
confirm the host-vs-Ollama distinction still holds.

**Implementation guidance for the Ollama isolation boundary** (analyze
finding NEW.9): the classifier code path NEVER imports the `ollama`
Python package, NEVER opens an HTTP connection to Ollama's localhost
endpoint (default `http://127.0.0.1:11434`), and NEVER reads Ollama's
PID file or systemd unit status. The isolation is enforced by
**not consuming** Ollama signals, not by *suppressing* them — there
is no code branch that observes Ollama state and discards it. As a
direct consequence: a running Ollama with GPU bound does NOT flip a
non-passing preflight to passing (the classifier never sees Ollama),
and a stopped Ollama does NOT flip a passing preflight to failing
(again, the classifier never sees Ollama). This invariant is
testable indirectly — T013 covers the host-level edge cases — but
no positive-Ollama probe test is needed because the classifier
literally has no Ollama-aware code to exercise.

**Alternatives considered**:

- Shell out to `rocminfo` — rejected. Network/subprocess dependency,
  not always installed.
- Only report `dev_kfd_present` — rejected. Misses CUDA/NVIDIA hosts
  and ambiguates "GPU not exposed" from "wrong env vars".
- Use `pyrsmi` or similar Python ROCm bindings — rejected. New
  dependency for a diagnostic; same information is reachable via
  `os.environ` and `Path.exists`.

---

## R-014.11: Documenting workstation-only GPU install path

**Decision**: Author one new doc, `docs/stage1-vendor-identity/paddle-gpu-preflight.md`,
and update `docs/stage1-vendor-identity/ollama-runtime.md` with one
cross-reference paragraph.

The new doc covers:

1. Each FR-001 state (`paddle_not_installed`, `paddle_cpu_only`,
   `gpu_not_exposed`, `gpu_exposed_paddle_cant_bind`,
   `ppstructurev3_init_failed`, `ppstructurev3_init_succeeded`),
   what it looks like in the readout, what it means, and the next
   remediation step.
2. The supported workstation install path (native Linux ROCm host
   running an in-process `paddlepaddle-gpu` wheel that matches the
   ROCm version the host ships). Explicitly **not** added to
   `requirements.txt` or `pyproject.toml`. The doc states the install
   command (e.g. `pip install paddlepaddle-gpu==<pinned-version> -f
   <official Paddle ROCm wheel index URL>`) so an operator can
   reproduce it manually, with a footnote that the URL is the same
   one that `paddleocr.com` / `paddlepaddle.org.cn` documents
   officially. The exact wheel version is pinned during M1
   implementation against the Paddle 3.x line; the doc records
   whichever wheel preflight passes against.
3. The unsupported-but-likely-attempted paths (WSL Docker Desktop,
   raw Conda) and the readout output to expect on each, so a developer
   doesn't waste hours debugging.
4. The CI default behavior (GPU-gated tests skipped, traceable to
   FR-001 state) and how to opt in locally.

**Rationale**:

- FR-023 requires this doc; FR-024 requires the additive,
  workstation-only install path. Putting the wheel install command
  in a doc rather than in `requirements.txt` keeps the lightweight
  CPU-only install path intact.
- Stage 1's constitution requires WSL behavior to never be
  represented as production-ready GPU. The new doc puts that
  warning directly next to the install instructions.

**Alternatives considered**:

- Skip the new doc and put the install instructions in CLAUDE.md —
  rejected. CLAUDE.md is for guidance to AI agents; user-facing
  install paths belong in `docs/stage1-vendor-identity/`.
- Pin the GPU wheel in `pyproject.toml` as an optional extra (e.g.
  `[project.optional-dependencies] gpu = [...]`) — rejected. PyPI
  hosts only the CPU `paddlepaddle` and certain GPU variants; the
  ROCm wheel is hosted on a different index URL that requires
  `pip install -f`, which doesn't fit cleanly into `optional-dependencies`.
  Documenting the manual command is honest about the install path.

---

## Summary of decisions

| ID       | Decision                                                                              |
|----------|---------------------------------------------------------------------------------------|
| R-014.1  | Preflight CLI is `python -m ledgerlinc_ocr.preprocessing.preflight`; library + CLI sibling modules |
| R-014.2  | `pipeline_version` gains a trailing `.cpu` or `.gpu<N>` segment                       |
| R-014.3  | Shared classifier exposes `PreflightState` enum, `PreflightEvidence`, `PreflightReadout` dataclasses, `classify(...)` function |
| R-014.4  | Warm-corpus runner forces abort on first GPU per-doc failure regardless of `--on-failure`; logs `gpu_lane_forced_abort: true` |
| R-014.5  | Preflight CLI emits human text + trailing JSON line `kind: "preflight_readout"`; exit codes 0/10–14 map to FR-001 states |
| R-014.6  | `RunSummary` gains `preprocess_lane`, `gpu_init_seconds`, `gpu_inference_seconds` (additive); schema bumps to 0.1.1 |
| R-014.7  | Detection uses `paddle.is_compiled_with_cuda/rocm`, `device.cuda.device_count`, tensor-bind probe, then PPStructureV3 init |
| R-014.8  | Engine and classifier use `device="gpu:0"` for GPU lane; grammar reserves `gpu<N>` for future multi-GPU |
| R-014.9  | `gpu` pytest marker; conftest classifies once per session and skips with FR-001-state-traceable reason |
| R-014.10 | Runtime exposure detection via `Path.exists` + `os.environ` only; `/dev/kfd`, `/dev/dri`, `HIP_VISIBLE_DEVICES`, etc. |
| R-014.11 | New `docs/stage1-vendor-identity/paddle-gpu-preflight.md`; ROCm wheel documented manually, not added to `pyproject.toml` |
