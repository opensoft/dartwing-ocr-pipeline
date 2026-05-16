"""US3: the packet is voter-, model-, and prompt-independent."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from dartwing_ocr.evidence_packet import assemble_from_preprocess

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "evidence_packet"
_FIXTURE_NAMES = sorted(p.name for p in _FIXTURE_DIR.iterdir() if p.suffix == ".json")
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "stage1_vendor_identity"
    / "v1.2.0"
    / "evidence_packet.schema.json"
)

_BANNED = (
    "prompt",
    "voter",
    "qwen",
    "gemma",
    "phi",
    "llama",
    "token_budget",
    "temperature",
)
_BANNED_RE = re.compile(
    r"\b(" + "|".join(re.escape(b) for b in _BANNED) + r")\b", re.IGNORECASE
)


def _walk(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield "key", key
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, str):
        yield "value", node


def _walk_schema_properties(node):  # NOSONAR S3776 — recursive schema walker — flat structure with type-dispatch branches.
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            for k in props.keys():
                yield k
            for v in props.values():
                yield from _walk_schema_properties(v)
        for k, v in node.items():
            if k == "properties":
                continue
            yield from _walk_schema_properties(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_schema_properties(item)


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_ac1_no_voter_specific_keys_in_packet(fixture_name):
    data = json.loads((_FIXTURE_DIR / fixture_name).read_text())
    packet = assemble_from_preprocess(data)
    offenders = []
    for kind, s in _walk(packet):
        if _BANNED_RE.search(s):
            offenders.append((kind, s))
    assert offenders == [], f"voter/model/prompt leakage: {offenders}"


def test_ac2_no_voter_specific_keys_in_schema():
    schema = json.loads(_SCHEMA_PATH.read_text())
    offenders = [k for k in _walk_schema_properties(schema) if _BANNED_RE.search(k)]
    assert offenders == [], f"schema properties name voter/model/prompt: {offenders}"
