"""FR-012: no timestamps, no UUIDs anywhere in an assembled packet."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from dartwing_ocr.evidence_packet import assemble_from_preprocess

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "evidence_packet"
_FIXTURE_NAMES = sorted(p.name for p in _FIXTURE_DIR.iterdir() if p.suffix == ".json")

_ISO8601_DATE_TIME = r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
_ISO8601_FRACTIONAL = r"(?:\.\d+)?"
_ISO8601_TIMEZONE = r"(?:Z|[+-]\d{2}:?\d{2})?"
_ISO8601_RE = re.compile(
    _ISO8601_DATE_TIME + _ISO8601_FRACTIONAL + _ISO8601_TIMEZONE + r"\b"
)
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def _walk_strings(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from _walk_strings(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_strings(item)
    elif isinstance(node, str):
        yield node


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_no_timestamps(fixture_name):
    data = json.loads((_FIXTURE_DIR / fixture_name).read_text())
    packet = assemble_from_preprocess(data)
    offenders = [s for s in _walk_strings(packet) if _ISO8601_RE.search(s)]
    assert offenders == [], f"ISO-8601 timestamp leaked: {offenders}"


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_no_uuids(fixture_name):
    data = json.loads((_FIXTURE_DIR / fixture_name).read_text())
    packet = assemble_from_preprocess(data)
    offenders = [s for s in _walk_strings(packet) if _UUID_RE.search(s)]
    assert offenders == [], f"UUID leaked: {offenders}"
