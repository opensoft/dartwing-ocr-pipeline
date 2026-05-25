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
