"""Unit tests for ``serialization.write_packet_atomic``."""
from __future__ import annotations

import json

from dartwing_ocr.evidence_packet.serialization import write_packet_atomic


def test_two_writes_of_equal_dicts_produce_identical_bytes(tmp_path):
    packet = {"contract_set_version": "1.1.0", "z": [3, 2, 1], "a": {"b": "c"}}
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_packet_atomic(packet, first)
    write_packet_atomic(dict(packet), second)
    assert first.read_bytes() == second.read_bytes()


def test_no_trailing_newline(tmp_path):
    out = tmp_path / "packet.json"
    write_packet_atomic({"k": "v"}, out)
    raw = out.read_bytes()
    assert not raw.endswith(b"\n")


def test_indent_and_insertion_order_preserved(tmp_path):
    packet = {"z_first": 1, "a_second": 2, "nested": {"second": 2, "first": 1}}
    out = tmp_path / "packet.json"
    write_packet_atomic(packet, out)
    text = out.read_text(encoding="utf-8")

    # A two-space indent token confirms json.dump was called with indent=2.
    assert "\n  " in text
    assert text.index("z_first") < text.index("a_second")
    nested = text[text.index("nested") :]
    assert nested.index("second") < nested.index("first")


def test_unicode_preserved_without_escape(tmp_path):
    out = tmp_path / "packet.json"
    write_packet_atomic({"note": "café"}, out)
    text = out.read_text(encoding="utf-8")
    assert "café" in text
    assert "\\u" not in text
    assert json.loads(text) == {"note": "café"}
