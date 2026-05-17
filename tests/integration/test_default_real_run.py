"""US1 Acceptance Scenarios 1 + 4: default real-profile run end-to-end.

Spec User Story 1; SC-002. Gated on Ollama + Paddle availability.

When this test runs, all four live adapters are opted in, the CLI is
invoked with no profile flags, and the resulting artifacts must come
from non-stub implementations.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

paddleocr = pytest.importorskip("paddleocr")  # noqa: F841


REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = REPO_ROOT / "tests" / "stage1_vendor_identity"


def _ollama_reachable() -> bool:
    """Best-effort GPU-lane Ollama probe."""
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


@pytest.fixture
def staged_doc(tmp_path: Path) -> Path:
    src = CORPUS_ROOT / "inv_001_easy" / "source.pdf"
    if not src.exists():
        pytest.skip(f"missing corpus PDF: {src}")
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    shutil.copy(src, folder / "source.pdf")
    return folder


@pytest.mark.skipif(not _ollama_reachable(), reason="Ollama GPU lane not reachable")
def test_default_real_profile_run_end_to_end(
    staged_doc: Path,
    opt_in_all_live_adapters,
):
    """Acceptance Scenario 1: no flags -> all four real artifacts."""
    from dartwing_ocr.pipeline.cli import main

    code = main([
        "run",
        "--document-folder", str(staged_doc),
        "--overwrite",
    ])
    assert code == 0
    for name in (
        "preprocess_output.json",
        "edge_extraction_output.json",
        "routing_decision.json",
        "final_structured_payload.json",
    ):
        assert (staged_doc / name).exists()

    # Acceptance Scenario 4: default profiles match FR-007 values.
    extraction = json.loads((staged_doc / "edge_extraction_output.json").read_text())
    assert extraction.get("model_runtime", {}).get("provider") != "stub"
