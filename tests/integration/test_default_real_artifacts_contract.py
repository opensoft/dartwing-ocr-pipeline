"""US1 Acceptance Scenario 2: artifact filenames + schemas unchanged
under default real-profile run. SC-002.

Gated on Ollama + Paddle availability.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

paddleocr = pytest.importorskip("paddleocr")  # noqa: F841


REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = REPO_ROOT / "tests" / "stage1_vendor_identity"


def _ollama_reachable() -> bool:
    import httpx
    url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        r = httpx.get(f"{url}/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


@pytest.fixture
def opt_in_all_live_adapters():
    from dartwing_ocr.pipeline import stages as stages_mod
    stages_mod.register_ppstructurev3_cpu()
    stages_mod.register_ollama_gpu()
    stages_mod.register_routing_rules_cpu()
    stages_mod.register_final_payload_assembler_cpu()
    try:
        yield
    finally:
        stages_mod.reset_live_registry()


@pytest.mark.skipif(not _ollama_reachable(), reason="Ollama not reachable")
def test_default_real_run_artifacts_pass_validator(tmp_path: Path, opt_in_all_live_adapters):
    """SC-002: each artifact validates against the installed contract set."""
    from dartwing_ocr.pipeline.cli import main
    from dartwing_ocr.validator.folder import validate_folder

    src = CORPUS_ROOT / "inv_001_easy" / "source.pdf"
    if not src.exists():
        pytest.skip(f"missing corpus PDF: {src}")
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    shutil.copy(src, folder / "source.pdf")

    code = main([
        "run",
        "--document-folder", str(folder),
        "--overwrite",
    ])
    assert code == 0
    outcome = validate_folder(folder)
    assert outcome.passed, outcome.violations
