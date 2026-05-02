"""FR-016 hard-fail: PPStructureV3 init failure → non-zero exit, no artifact,
structured JSON error on stderr.

Tests both subcases from research R-008: weight-download (carries missing_weight
+ weight_hoster_url fields) and generic runtime exception (omits them).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ledgerlinc_ocr.preprocessing import cli, ocr
from ledgerlinc_ocr.preprocessing.errors import (
    EXIT_INTERNAL_ERROR,
    EngineInitError,
)


@pytest.fixture
def staged_folder(tmp_path: Path, us1_source_pdf: Path) -> Path:
    folder = tmp_path / "inv_001"
    folder.mkdir()
    shutil.copy(us1_source_pdf, folder / "source.pdf")
    return folder


def _raise_weight_download_failure():
    raise EngineInitError(
        message="Unable to fetch model file: PP-DocBlockLayout_infer.tar from https://paddle-model-ecology.bj.bcebos.com/paddlex/official_models/PP-DocBlockLayout_infer.tar",
        cause_class="FileNotFoundError",
        cause_module="paddlex.utils.download",
        missing_weight="PP-DocBlockLayout_infer.tar",
        weight_hoster_url="https://paddle-model-ecology.bj.bcebos.com/paddlex/official_models/PP-DocBlockLayout_infer.tar",
    )


def _raise_generic_init_failure():
    raise EngineInitError(
        message="oneDNN PIR converter failed: ConvertPirAttribute2RuntimeAttribute",
        cause_class="RuntimeError",
        cause_module="paddle.base",
        missing_weight=None,
        weight_hoster_url=None,
    )


def _capture_stderr(capsys) -> dict:
    """Read the single-line JSON envelope the CLI wrote to stderr."""
    captured = capsys.readouterr()
    lines = [ln for ln in captured.err.splitlines() if ln.strip()]
    assert len(lines) == 1, f"expected a single stderr JSON line, got: {captured.err!r}"
    return json.loads(lines[0])


def test_weight_download_failure_hard_fails_with_weight_fields(
    monkeypatch, capsys, staged_folder: Path,
):
    monkeypatch.setattr(ocr, "_get_engine", _raise_weight_download_failure)
    rc = cli.main([
        "--document-folder", str(staged_folder),
    ])
    assert rc == EXIT_INTERNAL_ERROR
    envelope = _capture_stderr(capsys)

    assert envelope["status"] == "error"
    assert envelope["kind"] == "engine_init_failed"
    assert envelope["cause_class"] == "FileNotFoundError"
    assert envelope["cause_module"] == "paddlex.utils.download"
    assert envelope["missing_weight"] == "PP-DocBlockLayout_infer.tar"
    assert envelope["weight_hoster_url"].startswith("https://paddle-model-ecology.bj.bcebos.com/")

    # FR-016: no preprocess_output.json is written — not even a failure stub.
    assert not (staged_folder / "preprocess_output.json").exists()


def test_generic_init_failure_hard_fails_without_weight_fields(
    monkeypatch, capsys, staged_folder: Path,
):
    monkeypatch.setattr(ocr, "_get_engine", _raise_generic_init_failure)
    rc = cli.main([
        "--document-folder", str(staged_folder),
    ])
    assert rc == EXIT_INTERNAL_ERROR
    envelope = _capture_stderr(capsys)

    assert envelope["status"] == "error"
    assert envelope["kind"] == "engine_init_failed"
    assert envelope["cause_class"] == "RuntimeError"
    assert envelope["cause_module"] == "paddle.base"
    # When the cause is not weight-related, the weight fields are OMITTED (not null).
    assert "missing_weight" not in envelope
    assert "weight_hoster_url" not in envelope

    assert not (staged_folder / "preprocess_output.json").exists()


def test_engine_init_error_propagates_from_pipeline(monkeypatch, staged_folder: Path):
    """Unit-level check: pipeline.run lets EngineInitError propagate instead of catching."""
    from ledgerlinc_ocr.preprocessing import pipeline

    monkeypatch.setattr(ocr, "_get_engine", _raise_generic_init_failure)
    with pytest.raises(EngineInitError):
        pipeline.run(pipeline.Invocation(document_folder=staged_folder))

    # FR-016: no artifact written on init failure.
    assert not (staged_folder / "preprocess_output.json").exists()
