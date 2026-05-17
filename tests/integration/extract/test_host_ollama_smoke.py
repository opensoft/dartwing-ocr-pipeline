"""T077 — Host-Ollama smoke test. Auto-skipped when Ollama is unreachable.

The smoke test targets `voters/configs/gemma-edge.yaml` on the real host Ollama
endpoint (see `docs/stage1-vendor-identity/ollama-runtime.md`). It asserts that
the extractor wires through end-to-end, produces a schema-valid artifact, and
lands in `status in {success, partial}`. It does NOT make claims about specific
field values — those belong in the evaluation harness, not the pipeline suite.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import httpx
import pytest

from dartwing_ocr.extract.cli import main as extract_main
from dartwing_ocr.validator import ArtifactName, validate_artifact

_REPO_ROOT = Path(__file__).resolve().parents[3]
_US1 = _REPO_ROOT / "tests" / "fixtures" / "extract" / "us1_happy"
_GEMMA_CONFIG = (
    _REPO_ROOT / "src" / "dartwing_ocr" / "extract" / "voters" / "configs" / "gemma-edge.yaml"
)


def _ollama_reachable() -> bool:
    base = os.environ.get("OLLAMA_BASE_URL", "")
    if not base:
        return False
    try:
        with httpx.Client(timeout=httpx.Timeout(2.0)) as client:
            r = client.get(f"{base.rstrip('/')}/api/tags")
        return r.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.skipif(not _ollama_reachable(), reason="host Ollama not reachable")
def test_gemma_edge_smoke(tmp_path: Path) -> None:
    folder = tmp_path / "gemma_edge_smoke"
    shutil.copytree(_US1, folder)
    # Remove the stub config that ships in the fixture — this run uses the
    # packaged `gemma-edge.yaml` directly.
    (folder / "voter_config.yaml").unlink(missing_ok=True)

    rc = extract_main(
        ["--folder", str(folder), "--voter", "gemma-edge",
         "--voter-config", str(_GEMMA_CONFIG)]
    )
    assert rc == 0

    artifact_path = folder / "edge_extraction_output.json"
    assert artifact_path.is_file()
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["status"] in {"success", "partial"}

    outcome = validate_artifact(artifact_path, ArtifactName.EDGE_EXTRACTION_OUTPUT)
    assert outcome.passed, (
        f"gemma-edge smoke artifact failed schema: "
        f"{[(v.field_path, v.violation_code) for v in outcome.violations]}"
    )
