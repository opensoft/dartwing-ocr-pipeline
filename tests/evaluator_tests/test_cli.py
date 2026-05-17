"""T083: CLI exit-code matrix (0 clean / 2 usage / 3 hard error) + --help."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

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


def _run(
    argv: list[str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "dartwing_ocr.evaluator", *argv],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def _stage_pipeline_document(tmp_path: Path) -> Path:
    folder = tmp_path / "inv_001_easy"
    shutil.copytree(FIXTURES / "all_match", folder)
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    (folder / "final_structured_payload.json").unlink()
    (folder / "evaluation_document.json").unlink()
    expected_path = folder / "expected.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    expected["document_id"] = "inv_001_easy"
    expected_path.write_text(json.dumps(expected, indent=2), encoding="utf-8")
    return folder


# ---- Help surface ---------------------------------------------------------


def test_top_level_help_exits_zero() -> None:
    result = _run(["--help"])
    assert result.returncode == 0
    assert "evaluate" in result.stdout


def test_evaluate_document_help_exits_zero() -> None:
    result = _run(["evaluate", "document", "--help"])
    assert result.returncode == 0
    assert "--json" in result.stdout
    assert "--text" in result.stdout
    assert "--run-pipeline" in result.stdout


def test_evaluate_corpus_help_exits_zero() -> None:
    result = _run(["evaluate", "corpus", "--help"])
    assert result.returncode == 0
    assert "--no-lazy" in result.stdout
    assert "--run-pipeline" in result.stdout


# ---- Exit code 0: clean completion ----------------------------------------


def test_evaluate_document_clean_exit_zero(tmp_path: Path) -> None:
    folder = tmp_path / "all_match"
    shutil.copytree(FIXTURES / "all_match", folder)
    result = _run(["evaluate", "document", str(folder)])
    assert result.returncode == 0, result.stderr
    assert (folder / "evaluation_document.json").is_file()


def test_evaluate_document_run_pipeline_clean_exit_zero(tmp_path: Path) -> None:
    folder = _stage_pipeline_document(tmp_path)

    result = _run(
        [
            "evaluate",
            "document",
            str(folder),
            "--run-pipeline",
            "--pipeline-overwrite",
        ]
    )

    assert result.returncode == 0, result.stderr
    for name in (
        "preprocess_output.json",
        "edge_extraction_output.json",
        "routing_decision.json",
        "final_structured_payload.json",
        "evaluation_document.json",
    ):
        assert (folder / name).is_file()
    final_payload = json.loads(
        (folder / "final_structured_payload.json").read_text(encoding="utf-8")
    )
    evaluation = json.loads(
        (folder / "evaluation_document.json").read_text(encoding="utf-8")
    )
    assert final_payload["document_id"] == "inv_001_easy"
    assert evaluation["document_id"] == "inv_001_easy"


def test_evaluate_corpus_clean_exit_zero(tmp_path: Path) -> None:
    root = tmp_path / "corpus_prebuilt_3"
    shutil.copytree(FIXTURES / "corpus_prebuilt_3", root)
    result = _run(["evaluate", "corpus", str(root), "--no-lazy"])
    assert result.returncode == 0, result.stderr
    assert (root / "evaluation_run_summary.json").is_file()
    assert (root / "evaluation_run_summary.md").is_file()


# ---- Exit code 2: usage errors --------------------------------------------


def test_missing_positional_exits_two() -> None:
    result = _run(["evaluate", "document"])
    assert result.returncode == 2


def test_unknown_flag_exits_two(tmp_path: Path) -> None:
    result = _run(["evaluate", "document", str(tmp_path), "--nope"])
    assert result.returncode == 2


# ---- Exit code 3: hard errors with path on stderr --------------------------


def test_missing_expected_file_exits_three(tmp_path: Path) -> None:
    folder = tmp_path / "nothing_here"
    folder.mkdir()
    result = _run(["evaluate", "document", str(folder)])
    assert result.returncode == 3
    assert "expected.json" in result.stderr


def test_contract_set_drift_exits_three(tmp_path: Path) -> None:
    folder = tmp_path / "contract_set_drift"
    shutil.copytree(FIXTURES / "hard_errors" / "contract_set_drift", folder)
    result = _run(["evaluate", "document", str(folder)])
    assert result.returncode == 3
    assert str(folder) in result.stderr or "contract_set_version" in result.stderr


def test_explicit_version_rejection_exits_three(tmp_path: Path) -> None:
    """Passing `--contract-set-version 2.0.0` against a 1.0.0 artifact must fail."""
    folder = tmp_path / "all_match"
    shutil.copytree(FIXTURES / "all_match", folder)
    result = _run(
        [
            "evaluate",
            "document",
            str(folder),
            "--contract-set-version",
            "2.0.0",
        ]
    )
    assert result.returncode == 3


def test_document_id_mismatch_exits_three(tmp_path: Path) -> None:
    folder = tmp_path / "document_id_mismatch"
    shutil.copytree(FIXTURES / "hard_errors" / "document_id_mismatch", folder)
    result = _run(["evaluate", "document", str(folder)])
    assert result.returncode == 3
    assert str(folder) in result.stderr or "document_id" in result.stderr


def test_no_lazy_missing_evaluation_exits_three(tmp_path: Path) -> None:
    """--no-lazy against a corpus where one folder lacks evaluation_document.json."""
    root = tmp_path / "corpus_prebuilt_3"
    shutil.copytree(FIXTURES / "corpus_prebuilt_3", root)
    missing = root / "inv_corpus_easy_02" / "evaluation_document.json"
    missing.unlink()
    result = _run(["evaluate", "corpus", str(root), "--no-lazy"])
    assert result.returncode == 3
    # SC-007: the offending path should appear verbatim in stderr.
    assert str(missing) in result.stderr
