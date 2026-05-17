"""Constitution §I: evidence-packet assembly is self-contained (no network, no models)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("pytest_socket")

from pytest_socket import disable_socket, enable_socket  # noqa: E402

from dartwing_ocr.evidence_packet import assemble_from_folder  # noqa: E402

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "evidence_packet"


@pytest.fixture
def no_network():
    disable_socket()
    try:
        yield
    finally:
        enable_socket()


def test_assembly_runs_with_sockets_disabled(tmp_path, no_network):
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    shutil.copyfile(
        _FIXTURE_DIR / "with_regex_hits.json", folder / "preprocess_output.json"
    )
    packet = assemble_from_folder(folder)
    assert packet["contract_set_version"] == "1.2.0"
    assert packet["candidate_vendor_signals"]["emails"]
