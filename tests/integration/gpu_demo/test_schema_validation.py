"""US3 T048: multi-artifact schema-validation aggregation (CHK052).

When multiple artifacts fail validation, check 7's diagnostic.observed is a
list of ``{path, error}`` objects in canonical artifact order.
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


def test_multi_artifact_failure(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    patch_orchestrator_composer,
    monkeypatch,
    per_doc: Path,
) -> None:
    """Two-of-four artifact validation failures → diagnostic.observed has 2 entries in order."""
    from dartwing_ocr.gpu_demo.readiness import schema_validation as svm

    def _validator(path: Path):
        # Two of the four artifacts fail; preserve canonical order.
        if path.name in ("preprocess_output.json", "routing_decision.json"):
            return f"forced failure: {path.name}"
        return None

    monkeypatch.setattr(svm, "_validate_artifact", _validator)
    patch_orchestrator_composer(stub_pipeline_composer())

    code, stdout = _invoke_main([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(per_doc),
    ])
    assert code == ExitCode.ARTIFACT_SCHEMA_VALIDATION_FAILED == 5

    parsed = json.loads(stdout)
    schema_check = next(
        c for c in parsed["readiness"]["checks"]
        if c["name"] == "artifact-schema-validation"
    )
    assert schema_check["status"] == "fail"
    observed = schema_check["diagnostic"]["observed"]
    assert isinstance(observed, list)
    assert len(observed) == 2

    # Canonical order: preprocess_output first, routing_decision second.
    assert "preprocess_output.json" in observed[0]["path"]
    assert "routing_decision.json" in observed[1]["path"]
    for entry in observed:
        assert "path" in entry
        assert "error" in entry

    # T1 (triage): schema-validation failure rewrites runtime_outcome to
    # failed_at_final_payload and failure_kind to artifact-schema-validation-failed.
    # Asserting these explicitly is the regression-guard for the closed RuntimeOutcome
    # enum value path that previously was unverified at the CLI seam.
    assert parsed["runtime_outcome"] == "failed_at_final_payload"
    assert parsed["failure_kind"] == "artifact-schema-validation-failed"


def test_phase_failure_does_not_mask_as_schema_failure(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    bypass_schema_validation,
    patch_orchestrator_composer,
    per_doc: Path,
) -> None:
    """B2 regression guard (triage).

    When the pipeline fails mid-phase (e.g. extraction), the post-pipeline
    artifact-schema-validation check sees missing later artifacts and reports
    ``fail``. The orchestrator MUST NOT rewrite the already-set
    ``runtime_outcome="failed_at_extraction"`` to ``failed_at_final_payload``,
    and the exit code MUST remain 4 (PIPELINE_RUNTIME_ERROR), not 5.
    """
    # Composer fails AT extraction; routing + final_payload artifacts will
    # never be written. Post-pipeline check 7 would natively fail on the
    # missing files; the guard added by triage B2 must hold.
    patch_orchestrator_composer(stub_pipeline_composer(fail_phase="extraction"))

    code, stdout = _invoke_main([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(per_doc),
    ])
    # Exit must be 4 (pipeline-runtime-error), NOT 5 (schema-validation-failed).
    assert code == ExitCode.PIPELINE_RUNTIME_ERROR == 4, (
        f"phase failure must not mask as schema-validation failure; got exit {code}"
    )

    parsed = json.loads(stdout)
    assert parsed["runtime_outcome"] == "failed_at_extraction"
    assert parsed["failure_kind"] == "pipeline-runtime-error"
    # The schema-validation check itself MAY report fail (since artifacts are
    # missing), but the outcome cells above must reflect the true phase that
    # died, not the downstream artifact-absence side effect.
