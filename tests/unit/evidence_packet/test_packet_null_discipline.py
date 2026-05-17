"""FR-014: null discipline — lists are typed, documented-nullable keys only."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dartwing_ocr.evidence_packet import assemble_from_preprocess

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "evidence_packet"
_FIXTURE_NAMES = sorted(p.name for p in _FIXTURE_DIR.iterdir() if p.suffix == ".json")

# Keys documented as nullable in data-model.md.
_NULLABLE_KEYS = {
    "payload",                 # ingestion_source.payload
    "company_name",            # candidate_vendor_signals.company_name
    "confidence_mean",         # block.confidence_mean
}


def _walk(node, path=()):
    if isinstance(node, dict):
        for k, v in node.items():
            yield path + (k,), v
            yield from _walk(v, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, path + (i,))


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_null_values_only_on_documented_nullable_keys(fixture_name):
    data = json.loads((_FIXTURE_DIR / fixture_name).read_text())
    packet = assemble_from_preprocess(data)
    for path, value in _walk(packet):
        if value is None:
            # Final element of path is the key (int if list index; but null can only
            # appear at a string key in our schema).
            key = path[-1]
            assert isinstance(key, str), f"unexpected null at list index path {path}"
            assert key in _NULLABLE_KEYS, f"null at non-nullable path {path}"


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_list_typed_fields_are_never_null(fixture_name):
    data = json.loads((_FIXTURE_DIR / fixture_name).read_text())
    packet = assemble_from_preprocess(data)

    # Top-level list-typed fields
    assert isinstance(packet["pages"], list)
    assert isinstance(packet["reading_order"], list)
    assert isinstance(packet["tables"], list)

    signals = packet["candidate_vendor_signals"]
    assert isinstance(signals["addresses"], list)
    for category in ("emails", "websites", "phones", "tax_ids"):
        assert isinstance(signals[category], list)

    perceptual = packet["perceptual_observations"]
    for category in ("logos", "stamps", "header_candidates", "footer_candidates"):
        assert isinstance(perceptual[category], list)
