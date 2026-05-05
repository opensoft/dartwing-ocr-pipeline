"""US6 Acceptance Scenarios 1-2 + 4: warm corpus with ppstructurev3@cpu.

Spec User Story 6 Acceptance Scenarios 1-2 + 4; SC-009 + SC-010;
FR-030 / FR-036 folder-contract; Research R-009; design.md CHK022 /
CHK026 / CHK036 / CHK048.

Paddle-gated: skipped when ``paddleocr`` cannot be imported. The test
uses a real corpus PDF so the assertions about init timing reflect a
genuine PPStructureV3 run.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

paddleocr = pytest.importorskip("paddleocr")  # noqa: F841

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = REPO_ROOT / "tests" / "stage1_vendor_identity"


@pytest.fixture(autouse=True)
def opt_in_live_ppstructurev3():
    """Ensure the live ppstructurev3@cpu adapter is registered for this test."""
    from ledgerlinc_ocr.pipeline import stages as stages_mod

    stages_mod.register_ppstructurev3_cpu()
    try:
        yield
    finally:
        stages_mod.reset_live_registry()


@pytest.fixture
def warm_corpus_three_documents(tmp_path: Path) -> tuple[Path, list[Path]]:
    """Stage three real-PDF folders inside tmp_path (so the test does not
    write anywhere under the tracked corpus tree).
    """
    sources = [
        CORPUS_ROOT / "inv_001_easy" / "source.pdf",
        CORPUS_ROOT / "inv_002_easy" / "source.pdf",
        CORPUS_ROOT / "inv_003_easy" / "source.pdf",
    ]
    for src in sources:
        if not src.exists():
            pytest.skip(f"missing corpus PDF: {src}")
    folders: list[Path] = []
    for i, src in enumerate(sources, start=1):
        folder = tmp_path / f"inv_{i:03d}_easy"
        folder.mkdir()
        shutil.copy(src, folder / "source.pdf")
        folders.append(folder)
    docs_file = tmp_path / "corpus.txt"
    docs_file.write_text(
        "\n".join(f.name for f in folders) + "\n",
        encoding="utf-8",
    )
    return docs_file, folders


def test_warm_corpus_ppstructurev3_cpu_init_once_sc009(
    warm_corpus_three_documents,
    capsys: pytest.CaptureFixture[str],
):
    """SC-009 + SC-010: PPStructureV3 init exactly once across N documents."""
    from ledgerlinc_ocr.pipeline.cli import main

    docs_file, folders = warm_corpus_three_documents
    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--preprocess-profile", "ppstructurev3@cpu",
        # Other stages stub-only so the test self-contains.
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    summary = json.loads(out[-1])

    # SC-009: exactly one preprocess init event.
    init_seconds = summary["profile_initialization_seconds"]
    assert "preprocess" in init_seconds
    assert len(init_seconds) == 1
    # Sanity: PPStructureV3 init is non-trivial; at least 100ms.
    assert init_seconds["preprocess"] > 0.1

    # SC-010: per-document timings present for all attempted documents.
    per_doc = summary["per_document"]
    assert len(per_doc) == 3
    for entry in per_doc:
        assert entry["status"] == "success"
        assert "preprocess" in entry["stages"]
        assert "total_seconds" in entry["stages"]["preprocess"]

    # FR-030 / FR-036 folder contract: each folder contains exactly the
    # four canonical artifacts (no unexpected extras).
    for folder in folders:
        artifact_filenames = sorted(
            p.name for p in folder.iterdir() if p.is_file()
        )
        assert "preprocess_output.json" in artifact_filenames
        assert "edge_extraction_output.json" in artifact_filenames
        assert "routing_decision.json" in artifact_filenames
        assert "final_structured_payload.json" in artifact_filenames

    # R-009: kind:"run_summary" line is the LAST stdout line.
    assert summary["kind"] == "run_summary"
    last_line = out[-1]
    assert last_line.startswith('{"kind":"run_summary"')


def test_warm_corpus_validator_folder_passes_post_run(
    warm_corpus_three_documents,
):
    """C1: folder-contract validation passes after a warm-corpus run, so
    no unexpected files appeared beyond the four canonical artifacts.
    """
    from ledgerlinc_ocr.pipeline.cli import main
    from ledgerlinc_ocr.validator.folder import validate_folder

    docs_file, folders = warm_corpus_three_documents
    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--preprocess-profile", "ppstructurev3@cpu",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    assert code == 0
    for folder in folders:
        outcome = validate_folder(folder)
        assert outcome.passed, (
            f"validator validate folder failed for {folder}: "
            f"{outcome.violations}"
        )
