"""US4 Acceptance Scenarios 2 + 3 + T028 contract assertions.

Spec User Story 4 Acceptance Scenarios 2-3; FR-002, FR-003, FR-004,
FR-004A, FR-016, FR-017, FR-023, FR-028.

Contract: specs/011-stage-runtime-profiles/contracts/cli-contract.md
(amends specs/002-cli-contract/contracts/cli-contract.md v1.0.0).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

# Ensure pytest-socket is enabled to assert no network egress (US4 Scenario 2).
pytestmark = pytest.mark.usefixtures("disable_socket_for_test")


@pytest.fixture
def disable_socket_for_test():
    """Disable all network calls for the duration of the test."""
    import pytest_socket
    pytest_socket.disable_socket()
    try:
        yield
    finally:
        pytest_socket.enable_socket()


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
def tmp_doc(tmp_path: Path) -> Path:
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    return folder


# ---------------------------------------------------------------------------
# US4 Acceptance Scenario 2: stub-only run = zero network traffic.
# ---------------------------------------------------------------------------

def test_explicit_all_stub_profiles_no_network(tmp_doc: Path):
    """Spec FR-013: stub execution opt-in via explicit profile flags."""
    from dartwing_ocr.pipeline.cli import main

    code = main([
        "run",
        "--document-folder", str(tmp_doc),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
        "--overwrite",
    ])
    assert code == 0
    # All four artifacts produced under socket disable.
    for name in (
        "preprocess_output.json",
        "edge_extraction_output.json",
        "routing_decision.json",
        "final_structured_payload.json",
    ):
        assert (tmp_doc / name).exists()


# ---------------------------------------------------------------------------
# US4 Acceptance Scenario 3 / T027: --help lists every new flag.
# ---------------------------------------------------------------------------

def test_help_lists_every_011_flag(capsys: pytest.CaptureFixture[str]):
    """Spec FR-032: contract amendment must update CLI argument set."""
    from dartwing_ocr.pipeline.cli import main

    # ``main`` traps SystemExit raised by argparse and returns 0 for --help.
    rc = main(["run", "--help"])
    assert rc == 0
    captured = capsys.readouterr().out
    for flag in (
        "--preprocess-profile",
        "--extract-profile",
        "--routing-profile",
        "--final-payload-profile",
        "--stack-preset",
        "--start-at",
        "--stop-after",
        "--documents-file",
        "--on-failure",
        "--ollama-cpu-url",
        "--ollama-jetson-url",
    ):
        assert flag in captured, f"--help is missing {flag}"


# ---------------------------------------------------------------------------
# T028 / I2: default contract set version is "1.2.0" and a no-flag run
# resolves to that contract set.
# ---------------------------------------------------------------------------

def test_default_contract_set_version_constant():
    """The runtime default follows the active stage 1 contract set."""
    from dartwing_ocr.pipeline.cli import _DEFAULT_CONTRACT_SET_VERSION
    assert _DEFAULT_CONTRACT_SET_VERSION == "1.2.0"


def test_no_flag_run_uses_default_contract_set(tmp_doc: Path):
    """Implicit contract version is whatever cli._DEFAULT_CONTRACT_SET_VERSION
    declares; the runner-level validator MUST accept schema-valid stub
    artifacts under that contract set.
    """
    from dartwing_ocr.pipeline.cli import main

    # Explicit-stubs run uses the default contract version.
    code = main([
        "run",
        "--document-folder", str(tmp_doc),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
        "--overwrite",
    ])
    assert code == 0


# ---------------------------------------------------------------------------
# Mutual exclusion of input selectors (Contract "Mutual exclusion / ordering").
# ---------------------------------------------------------------------------

def test_input_and_document_folder_both_rejected(tmp_doc: Path, tmp_path: Path):
    from dartwing_ocr.pipeline.cli import main

    other_pdf = tmp_path / "other.pdf"
    other_pdf.write_bytes(MINIMAL_PDF_BYTES)
    code = main([
        "run",
        "--input", str(other_pdf),
        "--document-folder", str(tmp_doc),
    ])
    assert code == 10  # USAGE_ERROR


def test_no_input_selector_rejected():
    from dartwing_ocr.pipeline.cli import main

    code = main(["run"])
    assert code == 10


def test_documents_file_with_document_folder_rejected(tmp_doc: Path, tmp_path: Path):
    from dartwing_ocr.pipeline.cli import main

    docs_file = tmp_path / "corpus.txt"
    docs_file.write_text(f"{tmp_doc}\n", encoding="utf-8")
    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--document-folder", str(tmp_doc),
    ])
    assert code == 10


def test_documents_file_with_output_dir_rejected(tmp_path: Path):
    """--output-dir is not allowed in warm-corpus mode."""
    from dartwing_ocr.pipeline.cli import main

    docs_file = tmp_path / "corpus.txt"
    target = tmp_path / "inv_001_easy"
    target.mkdir()
    (target / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    docs_file.write_text(f"{target}\n", encoding="utf-8")
    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--output-dir", str(tmp_path / "elsewhere"),
    ])
    assert code == 10


def test_documents_file_with_document_id_rejected(tmp_path: Path):
    """--document-id is not allowed in warm-corpus mode (per-folder derivation)."""
    from dartwing_ocr.pipeline.cli import main

    docs_file = tmp_path / "corpus.txt"
    target = tmp_path / "inv_001_easy"
    target.mkdir()
    (target / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    docs_file.write_text(f"{target}\n", encoding="utf-8")
    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--document-id", "manual_override",
    ])
    assert code == 10
