"""T092 / analysis C4 — full-pipeline-minus-model guardrail (SC-007).

End-to-end wall-clock on the US1 happy fixture with the stub voter. No network,
canned response, straight through `packet_load → prompt render → parse →
reconcile → atomic write`. Must complete in under 2 seconds on the
`pipeline-dev` devcontainer (CPU-only, Python 3.12).
"""

from __future__ import annotations

import time
from pathlib import Path

from dartwing_ocr.extract.cli import main as extract_main


def test_full_pipeline_minus_model_under_2s(us1_happy_folder: Path) -> None:
    started = time.monotonic()
    rc = extract_main(
        ["--folder", str(us1_happy_folder), "--voter", "stub",
         "--voter-config", str(us1_happy_folder / "voter_config.yaml")]
    )
    elapsed = time.monotonic() - started

    assert rc == 0
    assert elapsed < 2.0, f"full stub pipeline too slow: {elapsed:.2f}s (SC-007 budget: 2.0s)"
