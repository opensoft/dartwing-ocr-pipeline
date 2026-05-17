"""T013 [US1] — happy-path acceptance scenarios AS-1..AS-6."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dartwing_ocr.assembler import Invocation, run

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
    """SC-004: byte-identical output across runs on identical inputs, except
    for `processed_at`.

    FIX 6 / T5: strengthened from dict-compare to byte-diff. The original
    `json.loads(...) == json.loads(...)` check silently accepted drift in
    key order, whitespace, trailing newline, and UTF-8 normalization — any
    of which would violate SC-004. We now redact the one legitimately-varying
    line and compare the raw bytes.
    """
    folder = _stage(tmp_path, "happy_grounded")

    # Inject a fixed clock on the first run, advanced clock on the second.
    t1 = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 4, 22, 12, 0, 1, tzinfo=timezone.utc)

    out_path = run(Invocation(document_folder=folder, now_utc=lambda: t1))
    first_bytes = out_path.read_bytes()

    run(Invocation(document_folder=folder, now_utc=lambda: t2))
    second_bytes = out_path.read_bytes()

    # The dict-level assertions remain valuable — they catch per-field
    # regressions that a naive byte-diff would also catch but would report
    # less helpfully.
    first_payload = json.loads(first_bytes.decode("utf-8"))
    second_payload = json.loads(second_bytes.decode("utf-8"))
    assert first_payload["processed_at"] == "2026-04-22T12:00:00Z"
    assert second_payload["processed_at"] == "2026-04-22T12:00:01Z"
    first_dict_no_ts = {k: v for k, v in first_payload.items() if k != "processed_at"}
    second_dict_no_ts = {k: v for k, v in second_payload.items() if k != "processed_at"}
    assert first_dict_no_ts == second_dict_no_ts

    # Byte-level determinism: redact only the `processed_at` line, then
    # assert the remaining bytes are identical. Catches key-order drift,
    # indent drift, whitespace drift, and trailing-newline drift that the
    # dict compare cannot see.
    redact_re = re.compile(rb'"processed_at": "[^"]+"')
    first_redacted = redact_re.sub(b'"processed_at": "REDACTED"', first_bytes)
    second_redacted = redact_re.sub(b'"processed_at": "REDACTED"', second_bytes)
    assert first_redacted == second_redacted, (
        "byte-level drift detected between two runs after redacting processed_at"
    )
