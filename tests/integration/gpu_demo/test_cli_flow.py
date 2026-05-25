"""US1 happy-path tests (T023).

Uses the stub PipelineComposer + bypass_schema_validation fixtures to
exercise the orchestrator's full success path without booting the real
feature 003/005/008/009 pipeline. The workstation-only smoke test (T073,
``@pytest.mark.gpu``) exercises the real pipeline path.
"""

from __future__ import annotations

import io
import json
import shutil
from contextlib import redirect_stdout
from pathlib import Path

import pytest


def _invoke_main(argv: list[str]) -> tuple[int, str]:
    """Run the demo CLI via ``cli.main`` and capture stdout JSON."""
    from dartwing_ocr.gpu_demo.cli import main

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


@pytest.fixture
def per_doc_folder(tmp_path: Path) -> Path:
    """Per-test per-document folder with a real source.pdf for the happy path."""
    src = (
        Path(__file__).parent / "fixtures" / "ok" / "source.pdf"
    ).resolve()
    folder = tmp_path / "inv_test"
    folder.mkdir()
    # The orchestrator only requires source.pdf to exist — we symlink to avoid
    # copying the canonical fixture's bytes.
    (folder / "source.pdf").symlink_to(src)
    return folder


def test_happy_path(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    bypass_schema_validation,
    patch_orchestrator_composer,
    per_doc_folder: Path,
) -> None:
    """Bare command against the canonical fixture exits 0 with the full report.

    Asserts the US1 acceptance criteria (FR-009, FR-019, FR-020, FR-025):
    - exit 0 (ExitCode.SUCCESS)
    - four canonical artifacts present on disk
    - ``runtime_outcome == "success"``
    - ``quality_status`` non-null (placeholder "review_required" per T060 TODO)
    - all 8 readiness checks ``"pass"``
    - ``schema_version == "0.1.0"``
    - ``phase_timings`` populated with 4 non-null floats
    """
    patch_orchestrator_composer(stub_pipeline_composer())
    code, stdout = _invoke_main(
        [
            "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
            "--document-folder", str(per_doc_folder),
        ]
    )
    from dartwing_ocr.gpu_demo.exit_codes import ExitCode

    assert code == ExitCode.SUCCESS, (
        f"expected SUCCESS (0), got {code}; stdout={stdout!r}"
    )
    assert stdout.count("\n") == 1, "stdout MUST be one JSON line"

    parsed = json.loads(stdout)

    # All four canonical artifacts written to disk.
    for basename in (
        "preprocess_output.json",
        "edge_extraction_output.json",
        "routing_decision.json",
        "final_structured_payload.json",
    ):
        artifact_path = per_doc_folder / basename
        assert artifact_path.exists(), f"{basename} not written"

    # Report-level assertions per US1 acceptance.
    assert parsed["schema_version"] == "0.1.0"
    assert parsed["runtime_outcome"] == "success"
    assert parsed["quality_status"] is not None  # T060 will tighten to the real value
    assert parsed["quality_status_source"] == "gate"
    assert parsed["stalled_phase"] is None
    assert parsed["failure_kind"] is None

    # All 8 readiness checks must be "pass".
    statuses = {c["name"]: c["status"] for c in parsed["readiness"]["checks"]}
    for check_name in (
        "interpreter/venv", "paddle-rocm-preflight", "ollama-reachability",
        "ollama-version", "ollama-model-gpu-placement", "ollama-context-length",
        "artifact-schema-validation", "pipeline-runtime-timeout",
    ):
        assert statuses[check_name] == "pass", (
            f"{check_name} should pass on happy path: {statuses}"
        )
    assert parsed["readiness"]["overall_passed"] is True

    # phase_timings populated for all 4 keys.
    pt = parsed["phase_timings"]
    assert set(pt.keys()) == {"preprocess", "extraction", "routing", "final_payload"}
    for key, val in pt.items():
        assert val is not None, f"phase_timings.{key} should be non-null on success"
        assert isinstance(val, (int, float))

    # artifact_paths is a 4-element list.
    assert parsed["artifact_paths"] is not None
    assert len(parsed["artifact_paths"]) == 4

    # total_runtime_seconds non-null.
    assert parsed["total_runtime_seconds"] is not None


def test_happy_path_failed_at_phase(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    bypass_schema_validation,
    patch_orchestrator_composer,
    per_doc_folder: Path,
) -> None:
    """Stub composer raising at 'extraction' produces runtime_outcome: failed_at_extraction."""
    patch_orchestrator_composer(stub_pipeline_composer(fail_phase="extraction"))
    code, stdout = _invoke_main(
        [
            "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
            "--document-folder", str(per_doc_folder),
        ]
    )
    from dartwing_ocr.gpu_demo.exit_codes import ExitCode

    assert code == ExitCode.PIPELINE_RUNTIME_ERROR

    parsed = json.loads(stdout)
    assert parsed["runtime_outcome"] == "failed_at_extraction"
    assert parsed["failure_kind"] == "pipeline-runtime-error"
    # Quality must be null when runtime_outcome != success (invariant 5).
    assert parsed["quality_status"] is None
    assert parsed["quality_status_source"] is None
    # phase_timings.preprocess populated (it ran), .extraction populated (it tried then failed).
    assert parsed["phase_timings"]["preprocess"] is not None
    assert parsed["phase_timings"]["extraction"] is not None
    # routing/final_payload never reached.
    assert parsed["phase_timings"]["routing"] is None
    assert parsed["phase_timings"]["final_payload"] is None
