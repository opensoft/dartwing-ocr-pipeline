"""T013 [US1] — happy-path acceptance scenarios AS-1..AS-6."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ledgerlinc_ocr.assembler import Invocation, run

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "assembler"

ISO_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _stage(tmp_path: Path, name: str) -> Path:
    dst = tmp_path / name
    shutil.copytree(FIXTURE_ROOT / name, dst)
    return dst


@pytest.fixture
def happy_folder(tmp_path: Path) -> Path:
    return _stage(tmp_path, "happy_grounded")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_as1_as6_required_keys_and_constants(happy_folder: Path):
    out_path = run(Invocation(document_folder=happy_folder))
    payload = _load(out_path)

    # AS-1: every required top-level key present
    for key in (
        "contract_set_version", "pipeline_version", "document_id", "processed_at",
        "document_type", "vendor_candidate", "review_status", "quality_summary", "trace",
    ):
        assert key in payload

    # AS-2: contract_set_version == "1.0.0"
    assert payload["contract_set_version"] == "1.0.0"

    # AS-3: processed_at ISO-8601 UTC, Z suffix
    assert ISO_Z_RE.match(payload["processed_at"])

    # AS-4: pipeline_version is assembler's, not copied from inputs
    assert payload["pipeline_version"] == "009-final-payload@0.1.0"

    # AS-5: document_type pinned to "invoice"
    assert payload["document_type"] == "invoice"

    # AS-6: document_id matches both inputs
    ext = _load(happy_folder / "edge_extraction_output.json")
    rt = _load(happy_folder / "routing_decision.json")
    assert payload["document_id"] == ext["document_id"] == rt["document_id"]


def test_two_runs_differ_only_by_processed_at(tmp_path: Path):
    folder = _stage(tmp_path, "happy_grounded")

    # Inject a fixed clock on the first run, advanced clock on the second.
    t1 = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 4, 22, 12, 0, 1, tzinfo=timezone.utc)

    out_path = run(Invocation(document_folder=folder, now_utc=lambda: t1))
    first = out_path.read_text(encoding="utf-8")

    run(Invocation(document_folder=folder, now_utc=lambda: t2))
    second = out_path.read_text(encoding="utf-8")

    # They differ only by the `processed_at` line.
    first_payload = json.loads(first)
    second_payload = json.loads(second)
    assert first_payload["processed_at"] == "2026-04-22T12:00:00Z"
    assert second_payload["processed_at"] == "2026-04-22T12:00:01Z"
    del first_payload["processed_at"]
    del second_payload["processed_at"]
    assert first_payload == second_payload
