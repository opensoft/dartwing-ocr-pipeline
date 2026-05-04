"""US5 Acceptance Scenario 4: cloud-workstation does not use cloud
credentials; pytest-socket asserts no egress.

Spec FR-021; design.md CHK043.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


MINIMAL_PDF_BYTES = (
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


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    f = tmp_path / "inv_001_easy"
    f.mkdir()
    (f / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    return f


@pytest.fixture
def disable_socket():
    import pytest_socket
    pytest_socket.disable_socket()
    try:
        yield
    finally:
        pytest_socket.enable_socket()


def test_cloud_creds_in_env_do_not_change_behavior(
    folder: Path,
    monkeypatch: pytest.MonkeyPatch,
    disable_socket,
    capsys: pytest.CaptureFixture[str],
):
    """Setting cloud-provider env vars must not change the failure path."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA0000FAKE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")

    from ledgerlinc_ocr.pipeline.cli import main

    code = main([
        "run",
        "--document-folder", str(folder),
        "--stack-preset", "cloud-workstation",
        "--overwrite",
    ])
    assert code == 10
    rec = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert "ensemble@workstation" in rec["message"]
    assert "FR-034 step 4" in rec["message"]
