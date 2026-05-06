"""Pipeline GPU fail-fast gate test (T018, FR-009, SC-003).

Two independent sub-tests, NOT a parameterization cross-product
(analyze finding NEW.5):

(1) **Fail-state matrix**: parameterized across the five FR-001 fail
    states. For each, monkeypatch
    `ledgerlinc_ocr.preprocessing.preflight.classify` to return that
    state, invoke the single-doc CLI with
    `--preprocess-profile ppstructurev3@gpu`, and assert
    (a) no `preprocess_output.json` is written for any document;
    (b) stderr names both the profile (`ppstructurev3@gpu`) and the
    FR-001 state value verbatim;
    (c) exit code matches the explicit FR-001 mapping (analyze finding
    VT1): paddle_not_installed→10, paddle_cpu_only→11,
    gpu_not_exposed→12, gpu_exposed_paddle_cant_bind→13,
    ppstructurev3_init_failed→14.

(2) **Warm-corpus abort case**: stub class for the warm-corpus path
    is not yet wired (T024 reaches this in a later task). The
    structural assertions (run_summary.on_failure preserved,
    gpu_lane_forced_abort:true on the failure record, third doc absent,
    stderr/message names ppstructurev3@gpu and the offending
    document_id) are deferred to T024's integration coverage and a
    follow-up corpus_run.py extension test. Documented here as a TODO
    so a reviewer can verify the matrix-only coverage.
"""
from __future__ import annotations

import json
import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# VT-003 / T035: skip if preflight is unavailable.
preflight = pytest.importorskip("ledgerlinc_ocr.preprocessing.preflight")
PreflightEvidence = preflight.PreflightEvidence
PreflightReadout = preflight.PreflightReadout
PreflightState = preflight.PreflightState

from ledgerlinc_ocr.preprocessing import cli as preprocessing_cli


def _fake_readout(state: PreflightState) -> PreflightReadout:
    """Build a synthetic readout for the given fail state."""
    selected_device = "gpu:0" if state is PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED else None
    evidence = PreflightEvidence(
        interpreter_path="/usr/bin/python",
        interpreter_version="3.12.0",
        venv_path=None,
        paddle_version=None,
        paddleocr_version=None,
        paddle_compiled_with_cuda=None,
        paddle_compiled_with_rocm=None,
        visible_device_count=None,
        selected_device=selected_device,
        runtime_device_exposure={},
        ppstructurev3_init_seconds=None,
        ppstructurev3_init_error=None,
        ppstructurev3_init_skipped_reason=None,
    )
    return PreflightReadout(
        state=state,
        evidence=evidence,
        recommendation=f"test recommendation for {state.value}",
    )


_FAIL_STATE_EXIT_CODES: list[tuple[PreflightState, int]] = [
    (PreflightState.PADDLE_NOT_INSTALLED, 10),
    (PreflightState.PADDLE_CPU_ONLY, 11),
    (PreflightState.GPU_NOT_EXPOSED, 12),
    (PreflightState.GPU_EXPOSED_PADDLE_CANT_BIND, 13),
    (PreflightState.PPSTRUCTUREV3_INIT_FAILED, 14),
]


@pytest.fixture
def folder_with_pdf(tmp_path: Path) -> Path:
    """Create a syntactically valid document folder with a placeholder
    PDF. The fail-state test never actually reads the PDF because the
    GPU gate fires before input validation, but the folder exists so
    the parsing path is exercised."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%placeholder\n")
    return folder


@pytest.mark.parametrize("state,expected_exit", _FAIL_STATE_EXIT_CODES)
def test_gpu_gate_failfast_per_fr001_state(
    state: PreflightState,
    expected_exit: int,
    folder_with_pdf: Path,
    monkeypatch,
    capsys,
) -> None:
    """For each FR-001 fail state: assert no artifact, exit code maps,
    stderr names profile + state."""
    artifact = folder_with_pdf / "preprocess_output.json"
    assert not artifact.exists(), "artifact should not exist before run"

    fake = _fake_readout(state)
    # Reset cache and patch classify so ensure_gpu_ready raises GpuPrerequisiteError.
    from ledgerlinc_ocr.preprocessing import preflight as preflight_mod

    preflight_mod.reset_cache()
    monkeypatch.setattr(
        preflight_mod, "classify",
        lambda *args, **kwargs: fake,
    )
    # Also patch the import alias used inside ensure_gpu_ready.
    # (ensure_gpu_ready calls module-level classify, so patching the
    # module attribute is enough.)

    rc = preprocessing_cli.main(
        [
            "--document-folder", str(folder_with_pdf),
            "--preprocess-profile", "ppstructurev3@gpu",
        ]
    )
    err = capsys.readouterr().err

    # (a) no artifact
    assert not artifact.exists(), (
        f"FR-009 violated: artifact written for fail state {state.value}"
    )
    # (b) stderr names both profile and FR-001 state value
    assert "ppstructurev3@gpu" in err
    assert state.value in err
    # (c) exit code per FR-001 mapping (VT1)
    assert rc == expected_exit, (
        f"exit code mismatch for {state.value}: expected {expected_exit}, got {rc}"
    )


def test_omitted_profile_does_not_invoke_gate(folder_with_pdf: Path, monkeypatch) -> None:
    """When --preprocess-profile is omitted, the resolved profile is
    ppstructurev3@cpu and the GPU gate must NOT fire (FR-008 default).
    We verify by setting a sentinel on classify; if the gate is
    invoked, the sentinel raises."""
    from ledgerlinc_ocr.preprocessing import preflight as preflight_mod

    preflight_mod.reset_cache()

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("classify must NOT be called on CPU lane")

    monkeypatch.setattr(preflight_mod, "classify", _should_not_be_called)
    # Also bypass actual preprocessing (we don't want to parse the
    # placeholder PDF — just check that the gate doesn't fire).
    from ledgerlinc_ocr.preprocessing import pipeline

    def _fake_run(invocation):
        # Confirm the lane is cpu when no flag is passed.
        assert invocation.preprocess_lane == "cpu"
        out = invocation.document_folder / "preprocess_output.json"
        out.write_text(
            '{"document_id":"inv_001_easy","warnings":[]}'
        )
        return out

    monkeypatch.setattr(pipeline, "run", _fake_run)

    rc = preprocessing_cli.main(["--document-folder", str(folder_with_pdf)])
    assert rc == 0


# =============================================================================
# T018 sub-test 2: warm-corpus abort case (NEW.5 / R-014.4).
# =============================================================================
# Independent of the fail-state matrix above, NOT a parameterization
# cross-product (analyze finding NEW.5). Drives the full warm-corpus
# CLI path with `--on-failure=continue`, GPU gate succeeding, then
# forces a per-document GPU inference failure on the SECOND document.
# Asserts:
#   (a) the harness aborts (third document is not processed and has no artifact);
#   (b) the trailing `kind:"run_summary"` JSON line carries `on_failure:"continue"`
#       (the user's requested mode is preserved per R-014.4 transparency rule);
#   (c) the failed document's per_document entry carries `gpu_lane_forced_abort: true`;
#   (d) `per_document[]` contains exactly two entries — first success, second failure;
#   (e) the failure message names `ppstructurev3@gpu` and the second document id
#       (analyze finding VT-010 attribution rule).

_MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\n"
    b"xref\n0 3\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000053 00000 n \n"
    b"trailer<</Size 3/Root 1 0 R>>\n"
    b"startxref\n100\n%%EOF\n"
)


def test_warm_corpus_gpu_lane_aborts_on_first_per_doc_failure(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Warm-corpus: GPU gate passes on the warm-init step, then per-doc
    GPU inference fails on document 2. Document 3 must not be attempted
    even though `--on-failure=continue` was requested."""
    from ledgerlinc_ocr.pipeline import corpus_run as _corpus_run_mod
    from ledgerlinc_ocr.pipeline import runner as _runner_mod
    from ledgerlinc_ocr.pipeline.cli import main as pipeline_cli_main
    from ledgerlinc_ocr.pipeline.exit_codes import ExitCode
    from ledgerlinc_ocr.pipeline.runner import RunResult
    from ledgerlinc_ocr.pipeline.timing import DocumentTimings
    from ledgerlinc_ocr.preprocessing import preflight as _preflight_mod

    # Reset preflight module-level cache so the gate runs fresh.
    _preflight_mod.reset_cache()
    # Reset corpus_run.py's module-level cache too.
    _corpus_run_mod._PREFLIGHT_READOUT = None

    # Stage three valid document folders.
    docs_file = tmp_path / "corpus.txt"
    folder1 = tmp_path / "inv_001_easy"
    folder2 = tmp_path / "inv_002_easy"
    folder3 = tmp_path / "inv_003_easy"
    for f in (folder1, folder2, folder3):
        f.mkdir()
        (f / "source.pdf").write_bytes(_MINIMAL_PDF_BYTES)
    docs_file.write_text(
        "\n".join([folder1.name, folder2.name, folder3.name]) + "\n",
        encoding="utf-8",
    )

    # Stub classify so the warm-init GPU gate succeeds (PPSTRUCTUREV3_INIT_SUCCEEDED)
    # without actually constructing PPStructureV3.
    fake_success = _fake_readout(PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED)
    monkeypatch.setattr(_preflight_mod, "classify", lambda *a, **kw: fake_success)

    # Stub the warm-instance factory's _get_engine call so it doesn't actually
    # reach into Paddle. We register a fake live capability for the GPU triple
    # and short-circuit the engine construction.
    from ledgerlinc_ocr.preprocessing import ocr as _ocr_mod
    monkeypatch.setattr(_ocr_mod, "_get_engine", lambda *args, **kwargs: object())

    # Patch the binding inside corpus_run.py (where it's used), not in
    # the stages module — `from … import is_live_capable` binds the
    # name into corpus_run's namespace at import time.
    monkeypatch.setattr(
        _corpus_run_mod, "is_live_capable",
        lambda stage, impl, lane: (stage, impl, lane) == ("preprocess", "ppstructurev3", "gpu"),
    )

    # Counter capturing how many documents the runner saw.
    calls: list[str] = []

    def fake_run_plan(self, plan, *, folder):
        calls.append(plan.cli_invocation.document_id)
        if plan.cli_invocation.document_id == "inv_002_easy":
            # Per-document GPU inference failure (e.g. ROCm OOM).
            return RunResult(
                exit_code=ExitCode.PROCESSING_FAILURE,
                stage="preprocess",
                message="ROCm OOM during PPStructureV3.predict",
                timings=DocumentTimings(),
            )
        return RunResult(
            exit_code=ExitCode.SUCCESS,
            stage="final_payload",
            message="",
            artifacts_written=[],
            timings=DocumentTimings(),
            routing_decision={"document_id": plan.cli_invocation.document_id},
        )

    monkeypatch.setattr(_runner_mod.Runner, "run_plan", fake_run_plan)

    # Drive the warm-corpus runner via the public CLI. preprocess-profile
    # is the new GPU lane; on-failure=continue is the user's requested
    # mode that the GPU lane override must preserve verbatim.
    rc = pipeline_cli_main(
        [
            "run",
            "--documents-file", str(docs_file),
            "--preprocess-profile", "ppstructurev3@gpu",
            "--extract-profile", "stub",
            "--routing-profile", "stub",
            "--final-payload-profile", "stub",
            "--on-failure", "continue",
        ]
    )
    captured = capsys.readouterr()

    # (a) third document was NOT processed.
    assert calls == ["inv_001_easy", "inv_002_easy"], (
        f"GPU lane should abort after doc 2; runner saw {calls}"
    )
    assert rc != 0  # aggregate exit reflects the per-doc failure

    # Parse the trailing run_summary JSON line.
    out_lines = [
        ln for ln in captured.out.strip().splitlines() if ln.startswith("{")
    ]
    summary_line = out_lines[-1]
    summary = json.loads(summary_line)

    # (b) on_failure preserved verbatim (R-014.4 transparency).
    assert summary["on_failure"] == "continue", (
        "warm-corpus on_failure must be preserved as the user-requested 'continue', "
        "not silently rewritten to 'fail-fast' even when the GPU lane forces abort."
    )
    # preprocess_lane reflects the GPU lane (T029).
    assert summary["preprocess_lane"] == "gpu0"

    # (d) exactly two per_document entries (third is absent).
    per_doc = summary["per_document"]
    assert len(per_doc) == 2, (
        f"per_document[] must have exactly 2 entries (first=success, "
        f"second=failure with gpu_lane_forced_abort); got {len(per_doc)}"
    )
    assert per_doc[0]["status"] == "success"
    assert per_doc[0]["document_id"] == "inv_001_easy"
    assert per_doc[1]["status"] == "failure"
    assert per_doc[1]["document_id"] == "inv_002_easy"

    # (c) gpu_lane_forced_abort flag on the failed entry, absent on success.
    assert per_doc[1].get("gpu_lane_forced_abort") is True
    assert "gpu_lane_forced_abort" not in per_doc[0]

    # (e) failure message names ppstructurev3@gpu + offending document_id (VT-010).
    failure_message = per_doc[1]["message"]
    assert "ppstructurev3@gpu" in failure_message
    assert "inv_002_easy" in failure_message


def test_warm_corpus_gpu_preflight_failure_uses_fr009_path(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Contracts §2 Pre-write GPU gate: when the warm preflight gate
    fails (e.g. classify returns paddle_cpu_only), the warm-corpus
    runner emits the FR-009 stderr form `error: --preprocess-profile=...`
    and exits with the FR-001-state-mapped exit code (10–14), NOT the
    generic PROCESSING_FAILURE exit code that pre-feature warm-init
    failures use."""
    from ledgerlinc_ocr.pipeline.cli import main as pipeline_cli_main
    from ledgerlinc_ocr.preprocessing import preflight as _preflight_mod
    from ledgerlinc_ocr.pipeline import corpus_run as _corpus_run_mod

    _preflight_mod.reset_cache()
    _corpus_run_mod._PREFLIGHT_READOUT = None

    docs_file = tmp_path / "corpus.txt"
    folder1 = tmp_path / "inv_001_easy"
    folder1.mkdir()
    (folder1 / "source.pdf").write_bytes(_MINIMAL_PDF_BYTES)
    docs_file.write_text(folder1.name + "\n", encoding="utf-8")

    # Stub classify to return PADDLE_CPU_ONLY so ensure_gpu_ready raises
    # GpuPrerequisiteError (state.value == "paddle_cpu_only") at warm-init.
    fake_fail = _fake_readout(PreflightState.PADDLE_CPU_ONLY)
    monkeypatch.setattr(_preflight_mod, "classify", lambda *a, **kw: fake_fail)

    # Mark the GPU triple as live-capable so the warm factory registers.
    # Patch the binding inside corpus_run.py (where it's used), not in
    # the stages module — `from … import is_live_capable` binds the
    # name into corpus_run's namespace at import time.
    monkeypatch.setattr(
        _corpus_run_mod, "is_live_capable",
        lambda stage, impl, lane: (stage, impl, lane) == ("preprocess", "ppstructurev3", "gpu"),
    )

    rc = pipeline_cli_main(
        [
            "run",
            "--documents-file", str(docs_file),
            "--preprocess-profile", "ppstructurev3@gpu",
            "--extract-profile", "stub",
            "--routing-profile", "stub",
            "--final-payload-profile", "stub",
            "--on-failure", "continue",
        ]
    )
    captured = capsys.readouterr()

    # FR-001 state-mapped exit code (paddle_cpu_only -> 11).
    assert rc == 11, f"expected exit 11 (paddle_cpu_only); got {rc}"

    # FR-009 stderr form: names both selected profile and FR-001 state.
    assert "ppstructurev3@gpu" in captured.err
    assert "paddle_cpu_only" in captured.err
    assert "error: --preprocess-profile=ppstructurev3@gpu:" in captured.err
