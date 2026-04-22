"""T085 — reconcile() performance guardrail (< 500 ms on a 10-page synthetic packet)."""

from __future__ import annotations

import copy
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from ledgerlinc_ocr.extract.config import load_voter_config
from ledgerlinc_ocr.extract.reconcile import reconcile

_REPO_ROOT = Path(__file__).resolve().parents[3]
_US1 = _REPO_ROOT / "tests" / "fixtures" / "extract" / "us1_happy"


def _synthetic_10_page_packet(base: dict) -> dict:
    """Expand the US1 packet to 10 pages by stamping page_n offsets onto the one real page."""

    base_page = copy.deepcopy(base["pages"][0])
    pages = []
    for n in range(1, 11):
        page = copy.deepcopy(base_page)
        page["page_number"] = n
        for b in page["blocks"]:
            b["block_id"] = b["block_id"].replace("p1_", f"p{n}_")
        for l in page["raw_ocr_lines"]:
            l["line_id"] = l["line_id"].replace("p1_", f"p{n}_")
        pages.append(page)
    packet = copy.deepcopy(base)
    packet["pages"] = pages
    packet["page_count"] = 10
    return packet


def test_reconcile_under_500ms_on_10_page_packet() -> None:
    packet = _synthetic_10_page_packet(
        json.loads((_US1 / "preprocess_output.json").read_text(encoding="utf-8"))
    )
    parsed = json.loads((_US1 / "voter_response_clean.json").read_text(encoding="utf-8"))
    config, _, _ = load_voter_config(
        name_or_path=str(_US1 / "voter_config.yaml"), base_dir=Path.cwd()
    )

    started = time.monotonic()
    reconcile(
        packet=packet,
        parsed=parsed,
        config=config,
        now=datetime(2026, 4, 21, 12, 0, 0, tzinfo=UTC),
        pipeline_version="0.0.0-test+perf",
        repair_trail=[],
    )
    elapsed_ms = (time.monotonic() - started) * 1000.0
    assert elapsed_ms < 500.0, f"reconcile too slow: {elapsed_ms:.1f} ms"
