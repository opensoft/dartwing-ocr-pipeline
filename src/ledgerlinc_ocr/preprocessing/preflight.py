"""Paddle GPU preflight classifier (feature 014).

Single source of truth for the FR-001 state vocabulary used by the
standalone `python -m ledgerlinc_ocr.preprocessing.preflight` CLI
(T014/T015), the runtime GPU gate in
`preprocessing/pipeline.py` (T021), the warm-corpus runner gate in
`pipeline/runner.py` (T023), and the pytest `gpu` marker hook in
`tests/conftest.py` (T009).

Implements:
- `PreflightState` enum (T002, six FR-001 states)
- `PreflightEvidence` frozen dataclass (T003, FR-002 evidence fields)
- `PreflightReadout` frozen dataclass + `to_text()` / `to_json_dict()` (T004, R-014.5 dual format)
- `classify()` function (T005, R-014.7 step ordering + R-014.10 device exposure)
- `GpuPrerequisiteError` exception (NEW.1: defined here per data-model §GpuPrerequisiteError)

The module is stdlib-only at import time (paddle/paddleocr are imported
lazily inside `classify()`), so a non-paddle environment can still
`from ledgerlinc_ocr.preprocessing.preflight import PreflightState`
without crashing — that is the contract the conftest's defensive
import path (T009 / RR15) relies on.

When run as `python -m ledgerlinc_ocr.preprocessing.preflight`, the
`__main__` block at the bottom dispatches to `preflight_cli.main`
(T015).
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from importlib import metadata
from pathlib import Path
from typing import Optional


SCHEMA_VERSION = "0.1.0"


class PreflightState(str, Enum):
    """Six FR-001 preflight states. Member names and string values are
    normative — used verbatim in JSON, error messages, exit codes, and
    pytest skip reasons. See spec FR-001 (a)–(f).
    """

    PADDLE_NOT_INSTALLED = "paddle_not_installed"            # FR-001 (a)
    PADDLE_CPU_ONLY = "paddle_cpu_only"                      # FR-001 (b)
    GPU_NOT_EXPOSED = "gpu_not_exposed"                      # FR-001 (c)
    GPU_EXPOSED_PADDLE_CANT_BIND = "gpu_exposed_paddle_cant_bind"  # FR-001 (d)
    PPSTRUCTUREV3_INIT_FAILED = "ppstructurev3_init_failed"  # FR-001 (e)
    PPSTRUCTUREV3_INIT_SUCCEEDED = "ppstructurev3_init_succeeded"  # FR-001 (f)


_EXIT_CODE_BY_STATE: dict[PreflightState, int] = {
    PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED: 0,
    PreflightState.PADDLE_NOT_INSTALLED: 10,
    PreflightState.PADDLE_CPU_ONLY: 11,
    PreflightState.GPU_NOT_EXPOSED: 12,
    PreflightState.GPU_EXPOSED_PADDLE_CANT_BIND: 13,
    PreflightState.PPSTRUCTUREV3_INIT_FAILED: 14,
}


def exit_code_for_state(state: PreflightState) -> int:
    """Map FR-001 state to CLI exit code per Contracts §1.Exit codes."""
    return _EXIT_CODE_BY_STATE[state]


@dataclass(frozen=True)
class PreflightEvidence:
    """FR-002 evidence fields. Operational expansion in
    data-model.md §PreflightEvidence."""

    interpreter_path: str
    interpreter_version: str
    venv_path: Optional[str]
    paddle_version: Optional[str]
    paddleocr_version: Optional[str]
    paddle_compiled_with_cuda: Optional[bool]
    paddle_compiled_with_rocm: Optional[bool]
    visible_device_count: Optional[int]
    selected_device: Optional[str]
    runtime_device_exposure: dict[str, bool] = field(default_factory=dict)
    ppstructurev3_init_seconds: Optional[float] = None
    ppstructurev3_init_error: Optional[str] = None
    ppstructurev3_init_skipped_reason: Optional[str] = None
    # Feature 015 (R-015.2): per-step timings for FR-013 phase emission.
    # Both fields are six-decimal-rounded `time.monotonic_ns()` deltas in
    # seconds, or None when the corresponding step did not execute (early
    # exit on a fail state). Fed into `phase_timings.paddle_import` and
    # `phase_timings.gpu_bind_probe` on the first successful per_document
    # entry's run_summary record.
    paddle_import_seconds: Optional[float] = None
    gpu_bind_probe_seconds: Optional[float] = None


@dataclass(frozen=True)
class PreflightReadout:
    """Result of one classify() call. Carries the FR-001 state, the
    FR-002 evidence, and a one-line FR-003 recommendation."""

    state: PreflightState
    evidence: PreflightEvidence
    recommendation: str

    def to_json_dict(self) -> dict[str, object]:
        """Serialize to the `kind:"preflight_readout"` JSON shape per
        Contracts §1.Stdout shape."""
        evidence_dict: dict[str, object] = {
            "interpreter_path": self.evidence.interpreter_path,
            "interpreter_version": self.evidence.interpreter_version,
            "venv_path": self.evidence.venv_path,
            "paddle_version": self.evidence.paddle_version,
            "paddleocr_version": self.evidence.paddleocr_version,
            "paddle_compiled_with_cuda": self.evidence.paddle_compiled_with_cuda,
            "paddle_compiled_with_rocm": self.evidence.paddle_compiled_with_rocm,
            "visible_device_count": self.evidence.visible_device_count,
            "selected_device": self.evidence.selected_device,
            "runtime_device_exposure": dict(self.evidence.runtime_device_exposure),
            "paddle_import_seconds": self.evidence.paddle_import_seconds,
            "gpu_bind_probe_seconds": self.evidence.gpu_bind_probe_seconds,
            "ppstructurev3_init_seconds": self.evidence.ppstructurev3_init_seconds,
            "ppstructurev3_init_error": self.evidence.ppstructurev3_init_error,
            "ppstructurev3_init_skipped_reason": self.evidence.ppstructurev3_init_skipped_reason,
        }
        return {
            "kind": "preflight_readout",
            "schema_version": SCHEMA_VERSION,
            "state": self.state.value,
            "evidence": evidence_dict,
            "recommendation": self.recommendation,
        }

    def to_text(self) -> str:
        """Serialize to the human-readable text section per
        Contracts §1.Stdout shape. Lines whose underlying field is
        None are omitted (the JSON payload still carries them as null)."""
        lines: list[str] = [f"[preflight] state: {self.state.value}"]
        ev = self.evidence
        ordered_fields: list[tuple[str, object]] = [
            ("interpreter_path", ev.interpreter_path),
            ("interpreter_version", ev.interpreter_version),
            ("venv_path", ev.venv_path),
            ("paddle_version", ev.paddle_version),
            ("paddleocr_version", ev.paddleocr_version),
            ("paddle_compiled_with_cuda", ev.paddle_compiled_with_cuda),
            ("paddle_compiled_with_rocm", ev.paddle_compiled_with_rocm),
            ("visible_device_count", ev.visible_device_count),
            ("selected_device", ev.selected_device),
        ]
        for key, value in ordered_fields:
            if value is None:
                continue
            lines.append(f"{key}: {value}")
        for key in (
            "dev_dri_present",
            "dev_kfd_present",
            "hip_visible_devices_set",
            "cuda_visible_devices_set",
            "rocm_path_set",
            "running_in_container",
        ):
            if key in ev.runtime_device_exposure:
                lines.append(
                    f"runtime_device_exposure.{key}: {str(ev.runtime_device_exposure[key]).lower()}"
                )
        for key, value in (
            ("paddle_import_seconds", ev.paddle_import_seconds),
            ("gpu_bind_probe_seconds", ev.gpu_bind_probe_seconds),
            ("ppstructurev3_init_seconds", ev.ppstructurev3_init_seconds),
            ("ppstructurev3_init_error", ev.ppstructurev3_init_error),
            ("ppstructurev3_init_skipped_reason", ev.ppstructurev3_init_skipped_reason),
        ):
            if value is not None:
                lines.append(f"{key}: {value}")
        lines.append("")
        lines.append(f"recommendation: {self.recommendation}")
        return "\n".join(lines)


class GpuPrerequisiteError(Exception):
    """Raised by preprocessing/pipeline.py (T021) when the inline GPU
    gate detects a non-success FR-001 state. Caught by
    preprocessing/cli.py (T022) and rendered as the FR-009 stderr
    message. Defined here in preflight.py per data-model
    §GpuPrerequisiteError (analyze finding AA1' / NEW.1) so the
    classifier types and the gate exception import from the same
    module.
    """

    def __init__(self, state: PreflightState, recommendation: str) -> None:
        super().__init__(f"{state.value}: {recommendation}")
        self.state = state
        self.recommendation = recommendation


def _detect_runtime_device_exposure() -> dict[str, bool]:
    """Per Research R-014.10. No subprocess calls; only Path.exists +
    os.environ. Six boolean keys."""
    return {
        "dev_dri_present": Path("/dev/dri").is_dir(),
        "dev_kfd_present": Path("/dev/kfd").exists(),
        "hip_visible_devices_set": os.environ.get("HIP_VISIBLE_DEVICES") is not None,
        "cuda_visible_devices_set": os.environ.get("CUDA_VISIBLE_DEVICES") is not None,
        "rocm_path_set": os.environ.get("ROCM_PATH") is not None,
        "running_in_container": (
            Path("/.dockerenv").exists() or os.environ.get("container") is not None
        ),
    }


def _interpreter_evidence() -> tuple[str, str, Optional[str]]:
    """Capture (interpreter_path, interpreter_version, venv_path)."""
    interpreter_path = sys.executable
    interpreter_version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    venv_path: Optional[str] = (
        sys.prefix if sys.prefix != sys.base_prefix else None
    )
    return interpreter_path, interpreter_version, venv_path


def _package_version(name: str) -> Optional[str]:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _paddle_distribution_version() -> Optional[str]:
    """Return the installed Paddle distribution version.

    CPU wheels use ``paddlepaddle``. CUDA wheels commonly use
    ``paddlepaddle-gpu``. Paddle's ROCm/DCU source build names the wheel
    ``paddlepaddle-dcu``. All three expose ``import paddle``.
    """
    for name in ("paddlepaddle", "paddlepaddle-gpu", "paddlepaddle-dcu"):
        version = _package_version(name)
        if version is not None:
            return version
    return None


def _recommendation_for(state: PreflightState, evidence: PreflightEvidence) -> str:
    """FR-003 three-part rule: (a) specific remediation action,
    (b) reference to docs/stage1-vendor-identity/paddle-gpu-preflight.md,
    (c) one-line plain language."""
    doc_ref = "docs/stage1-vendor-identity/paddle-gpu-preflight.md"
    if state == PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED:
        device = evidence.selected_device or "gpu:0"
        if evidence.ppstructurev3_init_skipped_reason is not None:
            return (
                f"Earlier preflight steps passed on {device}; PPStructureV3 init "
                f"was not exercised (--no-init). Re-run without --no-init to "
                f"confirm the GPU lane is ready. See {doc_ref}."
            )
        return (
            f"GPU lane is ready on {device}. You can now run "
            f"--preprocess-profile=ppstructurev3@gpu. See {doc_ref}."
        )
    if state == PreflightState.PADDLE_NOT_INSTALLED:
        return (
            f"Install paddle and paddleocr in this environment "
            f"(`pip install -e \".[dev]\"` from the repo root). See {doc_ref}."
        )
    if state == PreflightState.PADDLE_CPU_ONLY:
        return (
            f"Install or build a ROCm-enabled Paddle wheel (workstation-only, "
            f"additive to requirements.txt). See {doc_ref} for the supported "
            f"native-Linux ROCm source-build install path."
        )
    if state == PreflightState.GPU_NOT_EXPOSED:
        exposure = evidence.runtime_device_exposure
        if exposure.get("running_in_container") and not exposure.get("dev_kfd_present"):
            return (
                f"GPU device file /dev/kfd is not mapped into this container; "
                f"expose it or run on the host. See {doc_ref}."
            )
        if exposure.get("running_in_container") and not exposure.get("dev_dri_present"):
            return (
                f"GPU device file /dev/dri is not mapped into this container; "
                f"expose it or run on the host. See {doc_ref}."
            )
        return (
            f"No GPU device visible to this runtime. Check container device "
            f"exposure or run on a GPU host. See {doc_ref}."
        )
    if state == PreflightState.GPU_EXPOSED_PADDLE_CANT_BIND:
        return (
            f"Paddle GPU build does not match this host's ROCm/CUDA driver; "
            f"reinstall or rebuild the matching wheel. See {doc_ref} for the "
            f"supported ROCm build-driver combination."
        )
    if state == PreflightState.PPSTRUCTUREV3_INIT_FAILED:
        return (
            f"PPStructureV3 cannot initialize on the GPU device; check the "
            f"captured error and Paddle/PaddleOCR version compatibility. See {doc_ref}."
        )
    # unreachable
    return f"Unknown state {state}. See {doc_ref}."


def classify(
    *,
    attempt_ppstructurev3_init: bool = True,
    module_set: "ModuleSetPreset | None" = None,
    det_rec_variant: "DetRecVariant | None" = None,
) -> PreflightReadout:
    """Run the FR-001 classifier per Research R-014.7 step ordering.

    Parameters
    ----------
    attempt_ppstructurev3_init:
        When True (default), step 6 attempts to construct
        `PPStructureV3(device="gpu:0", ...)`. When False (set by the
        `--no-init` CLI flag for network-restricted shells), step 6
        is skipped — but steps 1–5 still execute and may briefly
        touch the network during `import paddle` weight verification.
        Fully offline operation requires the operator to use
        PaddleX's `PADDLE_PDX_MODEL_SOURCE` env var or `model_dir`
        parameter per `docs/stage1-vendor-identity/paddle-gpu-preflight.md`
        (NOT `PADDLE_DOWNLOAD=0` — that knob is not part of official
        PaddleX/PaddleOCR documentation).

    module_set:
        Feature 017 (T008 / R-017.6): when non-`None`, the preset's
        `use_kwargs` Mapping is splatted into the `PPStructureV3(...)`
        constructor in step 6 (replacing the literal legacy `use_*=False`
        kwargs). When `None` (default — backward-compat), the literal
        legacy GPU defaults are used so callers without preset awareness
        (e.g., the `preflight_cli.py` smoke test) preserve existing
        behavior.

    det_rec_variant:
        Feature 017 (T019 / R-017.6 / R-017.4): when non-`None` and
        the variant carries non-`None` model names, those names are
        passed to `PPStructureV3(text_detection_model_name=...,
        text_recognition_model_name=...)` in step 6. When `None`
        (default), or when the variant carries `None` model names
        (e.g., `legacy`), PaddleOCR's default model selection for
        `lang="en"` is used unchanged.
    """
    # Lazy reference to avoid circular type import at module-load
    from ledgerlinc_ocr.preprocessing.presets import (  # noqa: F401
        DetRecVariant,
        ModuleSetPreset,
    )
    interpreter_path, interpreter_version, venv_path = _interpreter_evidence()
    runtime_device_exposure = _detect_runtime_device_exposure()

    paddle_version = _paddle_distribution_version()
    paddleocr_version = _package_version("paddleocr")

    base_evidence = dict(
        interpreter_path=interpreter_path,
        interpreter_version=interpreter_version,
        venv_path=venv_path,
        paddle_version=paddle_version,
        paddleocr_version=paddleocr_version,
        paddle_compiled_with_cuda=None,
        paddle_compiled_with_rocm=None,
        visible_device_count=None,
        selected_device=None,
        runtime_device_exposure=runtime_device_exposure,
    )

    # Step 1+2: install + import paddle
    if paddle_version is None or paddleocr_version is None:
        evidence = PreflightEvidence(**base_evidence)
        return _make_readout(PreflightState.PADDLE_NOT_INSTALLED, evidence)

    # Feature 015 (R-015.2 / T006): time the `import paddle` call so the
    # first-doc run_summary can report `phase_timings.paddle_import.seconds`.
    paddle_import_start_ns = time.monotonic_ns()
    try:
        import paddle  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001 - any import-time failure → not installed
        evidence = PreflightEvidence(**base_evidence)
        return _make_readout(PreflightState.PADDLE_NOT_INSTALLED, evidence)
    paddle_import_seconds = round(
        (time.monotonic_ns() - paddle_import_start_ns) / 1e9, 6
    )
    base_evidence.update(paddle_import_seconds=paddle_import_seconds)

    # Step 3: build flags. Per R-014.7, an unexpected raise here is
    # treated as conservative PADDLE_CPU_ONLY (do not pretend GPU is
    # ready when introspection is broken).
    try:
        compiled_with_cuda = bool(paddle.is_compiled_with_cuda())
        compiled_with_rocm = bool(paddle.is_compiled_with_rocm())
    except Exception:  # noqa: BLE001
        evidence = PreflightEvidence(
            **{**base_evidence,
               "paddle_compiled_with_cuda": False,
               "paddle_compiled_with_rocm": False}
        )
        return _make_readout(PreflightState.PADDLE_CPU_ONLY, evidence)

    base_evidence.update(
        paddle_compiled_with_cuda=compiled_with_cuda,
        paddle_compiled_with_rocm=compiled_with_rocm,
    )

    if not (compiled_with_cuda or compiled_with_rocm):
        evidence = PreflightEvidence(**base_evidence)
        return _make_readout(PreflightState.PADDLE_CPU_ONLY, evidence)

    # Step 4: visible device count
    try:
        device_count = int(paddle.device.cuda.device_count())
    except Exception:  # noqa: BLE001
        device_count = 0
    base_evidence.update(visible_device_count=device_count)

    if device_count == 0:
        evidence = PreflightEvidence(**base_evidence)
        return _make_readout(PreflightState.GPU_NOT_EXPOSED, evidence)

    # Step 5: bind probe (synchronous; no timeout per R-014.7).
    # Feature 015 (R-015.2 / T006): time the bind+probe so the first-doc
    # run_summary can report `phase_timings.gpu_bind_probe.seconds`.
    gpu_bind_probe_start_ns = time.monotonic_ns()
    try:
        paddle.device.set_device("gpu:0")
        _probe = paddle.to_tensor([0])  # noqa: F841 - probe only
        del _probe
        gpu_bind_probe_seconds = round(
            (time.monotonic_ns() - gpu_bind_probe_start_ns) / 1e9, 6
        )
        base_evidence.update(
            selected_device="gpu:0",
            gpu_bind_probe_seconds=gpu_bind_probe_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        evidence = PreflightEvidence(
            **{**base_evidence,
               "ppstructurev3_init_error": _truncate(str(exc), 1000)}
        )
        return _make_readout(PreflightState.GPU_EXPOSED_PADDLE_CANT_BIND, evidence)

    # Step 6: PPStructureV3 init (skipped when caller opts out).
    if not attempt_ppstructurev3_init:
        evidence = PreflightEvidence(
            **{**base_evidence,
               "ppstructurev3_init_skipped_reason": "caller_disabled_init_attempt"}
        )
        # The earlier-step state is success-of-bind; the readout
        # still reports succeeded-up-to-bind via PPSTRUCTUREV3_INIT_SUCCEEDED's
        # contract semantics? No — we cannot claim init succeeded when we did
        # not attempt it. Report PPSTRUCTUREV3_INIT_SUCCEEDED only when init
        # actually ran. When skipped, we report the conservative state for the
        # last step that did run, which is "GPU exposed and Paddle bound to it"
        # but that is not one of the six FR-001 states. The contract: --no-init
        # surfaces as PPSTRUCTUREV3_INIT_FAILED is wrong (init wasn't tried).
        # Per spec Edge Cases bullet 7 + data-model: when --no-init is set, we
        # report the state of the last successful step. The skipped_reason
        # field signals to the operator that step 6 was not exercised. We
        # report PPSTRUCTUREV3_INIT_SUCCEEDED here ONLY IF earlier steps proved
        # the GPU is bindable; the convention is a "tentative success" with
        # the skipped_reason field acting as the qualifier. Tests T011/T013
        # assert this exact behavior.
        return _make_readout(PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED, evidence)

    start_ns = time.monotonic_ns()
    try:
        from paddleocr import PPStructureV3  # type: ignore[import-not-found]

        # Feature 015 (R-015.1 / CF5 / T008): construct PPStructureV3 and
        # persist it into the runtime singleton instead of `del`-ing it.
        # The runtime path (`ocr._get_engine`) will return this same
        # instance on its first call rather than constructing a second.
        #
        # Feature 017 (T008 / R-017.6 / contracts/module-invariants.md I-7
        # step 3): the legacy literal `use_*=False` kwargs are now sourced
        # from a `ModuleSetPreset.use_kwargs` Mapping when one is provided.
        # When `module_set is None`, the literal legacy defaults are used
        # so backward-compat callers (preflight_cli, internal tests) keep
        # working unchanged. Same pattern for `det_rec_variant` (T019):
        # `text_detection_model_name` / `text_recognition_model_name`
        # kwargs are added only when the variant carries non-None values
        # (R-017.4 Appendix A).
        if module_set is not None:
            _use_kwargs: dict[str, bool] = dict(module_set.use_kwargs)
        else:
            _use_kwargs = {
                "use_doc_orientation_classify": False,
                "use_doc_unwarping": False,
                "use_textline_orientation": False,
                "use_formula_recognition": False,
                "use_seal_recognition": False,
                "use_chart_recognition": False,
            }
        _det_rec_kwargs: dict[str, str] = {}
        if det_rec_variant is not None:
            if det_rec_variant.det_model_name is not None:
                _det_rec_kwargs["text_detection_model_name"] = det_rec_variant.det_model_name
            if det_rec_variant.rec_model_name is not None:
                _det_rec_kwargs["text_recognition_model_name"] = det_rec_variant.rec_model_name
        engine = PPStructureV3(
            **_use_kwargs,
            **_det_rec_kwargs,
            cpu_threads=1,
            enable_mkldnn=False,
            device="gpu:0",
            lang="en",
        )
        from ledgerlinc_ocr.preprocessing import ocr as _ocr_mod

        _ocr_mod._adopt_engine(engine, "gpu:0")
        elapsed = round((time.monotonic_ns() - start_ns) / 1e9, 6)
        evidence = PreflightEvidence(
            **{**base_evidence, "ppstructurev3_init_seconds": elapsed}
        )
        global _LAST_PRESET_KEY
        _LAST_PRESET_KEY = _normalize_preset_key(module_set, det_rec_variant)
        return _make_readout(PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED, evidence)
    except Exception as exc:  # noqa: BLE001
        evidence = PreflightEvidence(
            **{**base_evidence,
               "ppstructurev3_init_error": _truncate(str(exc), 1000)}
        )
        return _make_readout(PreflightState.PPSTRUCTUREV3_INIT_FAILED, evidence)


def _make_readout(state: PreflightState, evidence: PreflightEvidence) -> PreflightReadout:
    global _LAST_READOUT
    readout = PreflightReadout(
        state=state,
        evidence=evidence,
        recommendation=_recommendation_for(state, evidence),
    )
    # Cache for the process-level Q2 invariant. Only the most recent
    # classify result is retained; tests can clear via reset_cache().
    _LAST_READOUT = readout
    return readout


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


# Process-level cache (Q2: one classify per process). Set on every
# successful classify() call; consumed by both
# `preprocessing/pipeline.py` (T021 single-doc gate) and
# `pipeline/corpus_run.py` (T023 warm-corpus gate; T029 timing read).
_LAST_READOUT: Optional[PreflightReadout] = None
_LAST_PRESET_KEY: Optional[tuple[str, str]] = None


def _normalize_preset_key(
    module_set: "ModuleSetPreset | None",
    det_rec_variant: "DetRecVariant | None",
) -> tuple[str, str]:
    """Map a (module_set, det_rec_variant) pair to its cache-key form.

    ``None`` maps to ``"legacy"`` for both axes — both produce the same
    engine (literal legacy ``use_kwargs``, PaddleOCR-default det/rec
    model names), so they must compare equal in the mismatch guard.
    """
    return (
        module_set.name if module_set is not None else "legacy",
        det_rec_variant.name if det_rec_variant is not None else "legacy",
    )


def get_last_readout() -> Optional[PreflightReadout]:
    """Return the most recent classify() result for this process, or
    None if classify has not been called yet."""
    return _LAST_READOUT


def reset_cache() -> None:
    """Test-only: clear the process-level cache. Production code MUST
    NOT call this."""
    global _LAST_READOUT, _LAST_PRESET_KEY
    _LAST_READOUT = None
    _LAST_PRESET_KEY = None


def ensure_gpu_ready(
    *,
    module_set: "ModuleSetPreset | None" = None,
    det_rec_variant: "DetRecVariant | None" = None,
) -> PreflightReadout:
    """Inline GPU gate (T021 + T023). Returns the cached readout when a
    prior call succeeded; otherwise calls classify() and either caches
    the success result or raises GpuPrerequisiteError on a non-success
    state. This is the function the runtime gate consults.

    Raises GpuPrerequisiteError on any FR-001 fail state — the caller
    (preprocessing/cli.py T022 or pipeline/corpus_run.py T024) catches
    it and renders the FR-009 stderr message.

    Feature 017 (T010 followon / FR-002 / FR-005 / FR-006): preset kwargs
    are threaded into ``classify()`` on the first call so the GPU engine
    constructor receives the resolved ``use_kwargs`` splat (R-017.6) and
    the det/rec model-name overrides (R-017.4 Appendix A). The engine is
    constructed exactly once per process (feature 015 FR-001), so the
    presets used on that first call are pinned for the lifetime of the
    process. A subsequent call asking for different presets is a caller
    bug — raise ``RuntimeError`` rather than silently returning a
    readout that does not reflect the requested presets.
    """
    global _LAST_READOUT, _LAST_PRESET_KEY
    requested_key = _normalize_preset_key(module_set, det_rec_variant)
    # The cache is only valid when a prior call actually constructed and
    # adopted the engine. ``classify(attempt_ppstructurev3_init=False)``
    # (used by ``preflight_cli`` for read-only GPU probes) sets
    # ``_LAST_READOUT.state`` to SUCCEEDED without building an engine —
    # short-circuiting on that readout here would skip engine
    # construction entirely. ``_LAST_PRESET_KEY`` is set only at the
    # engine-construction success site, so it doubles as the "engine
    # actually adopted" signal.
    if (
        _LAST_READOUT is not None
        and _LAST_READOUT.state is PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED
        and _LAST_PRESET_KEY is not None
    ):
        if _LAST_PRESET_KEY != requested_key:
            raise RuntimeError(
                f"ensure_gpu_ready called with presets {requested_key!r} "
                f"after the GPU engine was already initialized with "
                f"{_LAST_PRESET_KEY!r}. Preset selection is process-wide "
                f"and resolved once at CLI parse time."
            )
        return _LAST_READOUT
    readout = classify(
        attempt_ppstructurev3_init=True,
        module_set=module_set,
        det_rec_variant=det_rec_variant,
    )
    if readout.state is not PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED:
        raise GpuPrerequisiteError(readout.state, readout.recommendation)
    return readout


__all__ = [
    "GpuPrerequisiteError",
    "PreflightEvidence",
    "PreflightReadout",
    "PreflightState",
    "SCHEMA_VERSION",
    "classify",
    "ensure_gpu_ready",
    "exit_code_for_state",
    "get_last_readout",
    "reset_cache",
]


# T015: make `python -m ledgerlinc_ocr.preprocessing.preflight` runnable
# by dispatching to preflight_cli.main. Do NOT modify __main__.py — that
# file dispatches `python -m ledgerlinc_ocr.preprocessing` (no submodule)
# to the existing single-doc preprocessing CLI; modifying it would break
# the existing `ledgerlinc-preprocess` invocation surface.
if __name__ == "__main__":  # pragma: no cover - exercised by T011/T035
    from ledgerlinc_ocr.preprocessing.preflight_cli import main as _cli_main

    raise SystemExit(_cli_main())
