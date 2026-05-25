"""Phase 7 T066–T069: eager-delete invariants (FR-017, SC-010)."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from dartwing_ocr.gpu_demo.exit_codes import ExitCode
from dartwing_ocr.gpu_demo.folder_canonicalize import (
    EagerDeleteError,
    canonicalize_document_folder,
    safe_eager_delete,
)


def _invoke_main(argv: list[str]) -> tuple[int, str]:
    from dartwing_ocr.gpu_demo.cli import main

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


def test_idempotent_on_missing_files(tmp_path: Path) -> None:
    """T068: eager-delete succeeds when none of the four canonical artifacts exist."""
    folder = tmp_path / "empty"
    folder.mkdir()
    canonical = canonicalize_document_folder(folder)
    safe_eager_delete(canonical, ("preprocess_output.json", "edge_extraction_output.json",
                                  "routing_decision.json", "final_structured_payload.json"))
    # No assertion needed — should not raise.


def test_partial_delete_failure_aborts_exit_2(
    tmp_path: Path,
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    monkeypatch,
) -> None:
    """T067: PermissionError on any of the four → exit 2 before any pipeline phase."""
    folder = tmp_path / "inv_test"
    folder.mkdir()
    src = (Path(__file__).parent / "fixtures" / "ok" / "source.pdf").resolve()
    (folder / "source.pdf").symlink_to(src)
    # Pre-populate one canonical artifact so the eager-delete has something to try.
    (folder / "preprocess_output.json").write_text("{}")
    (folder / "edge_extraction_output.json").write_text("{}")

    # Force unlink to raise on the second artifact.
    real_unlink = Path.unlink
    call_count = {"count": 0}

    def _flaky_unlink(self, *args, **kwargs):
        call_count["count"] += 1
        if call_count["count"] == 2:
            raise PermissionError("forced permission denied")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _flaky_unlink)

    code, stdout = _invoke_main([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(folder),
    ])
    assert code == ExitCode.INVALID_INPUT == 2
    parsed = json.loads(stdout)
    assert parsed["failure_kind"] == "invalid-input"
    assert parsed["runtime_outcome"] is None


def test_preserves_non_canonical_files(
    tmp_path: Path,
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    bypass_schema_validation,
    patch_orchestrator_composer,
) -> None:
    """T069 + SC-010: source.pdf, expected.json, notes.md, etc. preserved across a run."""
    folder = tmp_path / "inv_test"
    folder.mkdir()
    src = (Path(__file__).parent / "fixtures" / "ok" / "source.pdf").resolve()
    (folder / "source.pdf").symlink_to(src)

    # Pre-populate non-canonical operator files.
    (folder / "expected.json").write_text('{"vendor_name": "test"}')
    (folder / "notes.md").write_text("# notes\n")
    (folder / "semantic_table_truth.json").write_text('{"document_id": "inv_test", "rows": []}')
    (folder / "evaluation_document.json").write_text('{"kind": "evaluation_document", "stub": true}')
    (folder / "page_001.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")

    patch_orchestrator_composer(stub_pipeline_composer())
    code, _ = _invoke_main([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(folder),
    ])
    assert code == ExitCode.SUCCESS

    # All non-canonical files MUST still exist.
    for filename in ("source.pdf", "expected.json", "notes.md",
                     "semantic_table_truth.json", "evaluation_document.json",
                     "page_001.png"):
        assert (folder / filename).exists(), f"{filename} should be preserved"


def test_symlink_escape_aborts_exit_2(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
) -> None:
    """T066: symlink-escape fixture causes exit 2 before any phase runs."""
    fixture = Path(__file__).parent / "fixtures" / "symlink_escape"
    code, stdout = _invoke_main([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(fixture),
    ])
    assert code == ExitCode.INVALID_INPUT == 2
    parsed = json.loads(stdout)
    assert parsed["failure_kind"] == "invalid-input"
    assert parsed["runtime_outcome"] is None
