"""US1 report-shape tests (T024).

Asserts the 17 top-level keys are present with the success-outcome values
from ``contracts/demo-report-schema.md``'s outcome matrix.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest


EXPECTED_TOP_LEVEL_KEYS = {
    "kind",
    "schema_version",
    "pipeline_version",
    "run_id",
    "interpreter_path",
    "voter_config_path",
    "expected_extraction_model",
    "document_folder",
    "bounded_timeout_seconds",
    "readiness",
    "runtime_outcome",
    "stalled_phase",
    "failure_kind",
    "failing_check_name",
    "phase_timings",
    "total_runtime_seconds",
    "artifact_paths",
    "quality_status",
    "quality_status_source",
    "cpu_fallback_detection",
    "diagnostic",
}


def _invoke_main(argv: list[str]) -> tuple[int, str]:
    from dartwing_ocr.gpu_demo.cli import main

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


@pytest.fixture
def per_doc_folder(tmp_path: Path) -> Path:
    src = (Path(__file__).parent / "fixtures" / "ok" / "source.pdf").resolve()
    folder = tmp_path / "inv_test"
    folder.mkdir()
    (folder / "source.pdf").symlink_to(src)
    return folder


def test_success_outcome(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    bypass_schema_validation,
    patch_orchestrator_composer,
    per_doc_folder: Path,
) -> None:
    """Success outcome: every top-level key present, values match the matrix."""
    patch_orchestrator_composer(stub_pipeline_composer())
    _, stdout = _invoke_main(
        [
            "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
            "--document-folder", str(per_doc_folder),
        ]
    )
    parsed = json.loads(stdout)

    # 21 top-level keys exactly (17 in FR-019 + kind + cpu_fallback_detection + diagnostic + …).
    assert set(parsed.keys()) == EXPECTED_TOP_LEVEL_KEYS, (
        f"missing keys: {EXPECTED_TOP_LEVEL_KEYS - set(parsed.keys())}; "
        f"extra keys: {set(parsed.keys()) - EXPECTED_TOP_LEVEL_KEYS}"
    )

    # Per-cell value assertions from contracts/demo-report-schema.md outcome matrix.
    assert parsed["kind"] == "demo_run_report"
    assert parsed["schema_version"] == "0.1.0"
    assert isinstance(parsed["pipeline_version"], str)
    assert isinstance(parsed["run_id"], str) and len(parsed["run_id"]) == 36
    assert isinstance(parsed["interpreter_path"], str)
    assert isinstance(parsed["voter_config_path"], str)
    assert isinstance(parsed["expected_extraction_model"], str)
    assert isinstance(parsed["document_folder"], str)
    assert parsed["bounded_timeout_seconds"] == 600
    assert parsed["runtime_outcome"] == "success"
    assert parsed["stalled_phase"] is None
    assert parsed["failure_kind"] in (None, "post-run-interrogation-unreachable")
    assert parsed["failing_check_name"] is None
    assert parsed["quality_status"] in ("pass", "weak", "review_required")
    assert parsed["quality_status_source"] in ("gate", "evaluator")
    assert parsed["diagnostic"] is None

    # readiness shape: 8 checks, overall_passed True.
    assert len(parsed["readiness"]["checks"]) == 8
    assert parsed["readiness"]["overall_passed"] is True
    assert isinstance(parsed["readiness"]["elapsed_seconds"], (int, float))

    # phase_timings: 4 keys, all non-null floats.
    assert set(parsed["phase_timings"].keys()) == {
        "preprocess", "extraction", "routing", "final_payload"
    }
    for key, val in parsed["phase_timings"].items():
        assert val is not None and isinstance(val, (int, float)), (
            f"phase_timings.{key} should be a non-null float on success"
        )

    # artifact_paths: 4-element list of strings.
    assert isinstance(parsed["artifact_paths"], list)
    assert len(parsed["artifact_paths"]) == 4
    for p in parsed["artifact_paths"]:
        assert isinstance(p, str)

    # cpu_fallback_detection: always present, always shaped.
    cpu = parsed["cpu_fallback_detection"]
    assert set(cpu.keys()) >= {"ollama_post_run", "paddle_post_run"}
    assert cpu["ollama_post_run"] in ("consistent", "fell_back", "unreachable", "skipped")
    assert cpu["paddle_post_run"] in ("consistent", "fell_back", "unreachable", "skipped")
