"""Unit tests for null / empty discipline in ``candidate_vendor_signals``."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlinc_ocr.evidence_packet import assemble_from_preprocess

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "evidence_packet"
_FIXTURE_NAMES = sorted(p.name for p in _FIXTURE_DIR.iterdir() if p.suffix == ".json")


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_company_name_null_and_addresses_empty(fixture_name):
    data = json.loads((_FIXTURE_DIR / fixture_name).read_text())
    packet = assemble_from_preprocess(data)
    signals = packet["candidate_vendor_signals"]
    assert signals["company_name"] is None
    assert signals["addresses"] == []


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_every_hint_has_unverified_provenance(fixture_name):
    data = json.loads((_FIXTURE_DIR / fixture_name).read_text())
    packet = assemble_from_preprocess(data)
    signals = packet["candidate_vendor_signals"]
    for category in ("emails", "websites", "phones", "tax_ids"):
        for hit in signals[category]:
            assert hit["provenance"] == "unverified"
