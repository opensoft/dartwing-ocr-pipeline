"""US3 T046 + T047: runtime outcome enum coverage.

T046: timeout → ``runtime_outcome: "timeout"`` + ``stalled_phase`` matches the phase
       executing when the SIGALRM fired.
T047: parameterized over the four ``failed_at_<phase>`` values; injects a sub-module
       exception per phase, asserts the matching runtime_outcome value and exit 4.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from dartwing_ocr.gpu_demo.exit_codes import ExitCode


def _invoke_main(argv: list[str]) -> tuple[int, str]:
    from dartwing_ocr.gpu_demo.cli import main

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


@pytest.fixture
def per_doc(tmp_path: Path) -> Path:
    src = (Path(__file__).parent / "fixtures" / "ok" / "source.pdf").resolve()
    folder = tmp_path / "inv_test"
    folder.mkdir()
    (folder / "source.pdf").symlink_to(src)
    return folder


@pytest.mark.parametrize(
    "timeout_phase",
    ["preprocess", "extraction", "routing", "final_payload"],
)
def test_timeout_sets_stalled_phase(
    timeout_phase: str,
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    timeout_trigger_composer,
    bypass_schema_validation,
    patch_orchestrator_composer,
    per_doc: Path,
) -> None:
    """T046 + FR-008 + FR-020: SIGALRM during phase X → runtime_outcome=timeout, stalled_phase=X.

    Regression guard against the latent orchestrator bug where ``except Exception``
    in ``_run_phase`` swallowed ``TimeoutError`` and mis-mapped it to
    ``failed_at_<phase>`` + exit 4 instead of ``timeout`` + exit 3. The fix
    adds ``except TimeoutError: raise`` ahead of the generic handler.
    """
    patch_orchestrator_composer(timeout_trigger_composer(timeout_phase=timeout_phase))
    code, stdout = _invoke_main([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(per_doc),
    ])
    assert code == ExitCode.PIPELINE_RUNTIME_TIMEOUT == 3, (
        f"timeout in {timeout_phase} should exit 3; got {code}"
    )

    parsed = json.loads(stdout)
    assert parsed["runtime_outcome"] == "timeout"
    assert parsed["stalled_phase"] == timeout_phase
    assert parsed["failure_kind"] == "pipeline-runtime-timeout"
    # Quality null on every non-success outcome (invariant 5).
    assert parsed["quality_status"] is None
    assert parsed["quality_status_source"] is None


@pytest.mark.parametrize(
    "fail_phase, expected_outcome",
    [
        ("preprocess", "failed_at_preprocess"),
        ("extraction", "failed_at_extraction"),
        ("routing", "failed_at_routing"),
        ("final_payload", "failed_at_final_payload"),
    ],
)
def test_failed_at_phase(
    fail_phase,
    expected_outcome,
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    bypass_schema_validation,
    patch_orchestrator_composer,
    per_doc: Path,
) -> None:
    patch_orchestrator_composer(stub_pipeline_composer(fail_phase=fail_phase))
    code, stdout = _invoke_main([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(per_doc),
    ])
    assert code == ExitCode.PIPELINE_RUNTIME_ERROR == 4

    parsed = json.loads(stdout)
    assert parsed["runtime_outcome"] == expected_outcome
    assert parsed["failure_kind"] == "pipeline-runtime-error"
    # Quality is null whenever runtime_outcome != "success" (invariant 5).
    assert parsed["quality_status"] is None
    # The failing phase has a non-null timing; later phases are null.
    pt = parsed["phase_timings"]
    assert pt[fail_phase] is not None
    phases_order = ["preprocess", "extraction", "routing", "final_payload"]
    fail_idx = phases_order.index(fail_phase)
    for later in phases_order[fail_idx + 1:]:
        assert pt[later] is None, f"{later} should be null when {fail_phase} failed"
