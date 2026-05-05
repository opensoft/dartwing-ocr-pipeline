"""012 evaluator harness integration over the top-level pipeline CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).parents[1] / "evaluator_tests" / "fixtures"

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


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ledgerlinc_ocr.evaluator", *argv],
        capture_output=True,
        text=True,
    )


def _stage_doc(root: Path, folder_name: str, document_id: str) -> Path:
    folder = root / folder_name
    shutil.copytree(FIXTURES / "all_match", folder)
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    for name in (
        "final_structured_payload.json",
        "evaluation_document.json",
    ):
        (folder / name).unlink(missing_ok=True)
    expected_path = folder / "expected.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    expected["document_id"] = document_id
    expected["difficulty"] = folder_name.rsplit("_", 1)[-1]
    expected_path.write_text(json.dumps(expected, indent=2), encoding="utf-8")
    return folder


def test_evaluator_corpus_run_pipeline_uses_warm_stub_path(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    docs = (
        _stage_doc(root, "inv_001_easy", "inv_001"),
        _stage_doc(root, "inv_002_medium", "inv_002"),
    )

    result = _run(
        [
            "evaluate",
            "corpus",
            str(root),
            "--run-pipeline",
            "--pipeline-overwrite",
            "--refresh",
        ]
    )

    assert result.returncode == 0, result.stderr
    assert "pipeline preparation: total=2 succeeded=2 failed=0" in result.stderr
    assert (root / "evaluation_run_summary.json").is_file()
    summary = json.loads(
        (root / "evaluation_run_summary.json").read_text(encoding="utf-8")
    )
    assert summary["document_count"] == 2
    for folder in docs:
        assert (folder / "evaluation_document.json").is_file()
        assert (folder / "final_structured_payload.json").is_file()
