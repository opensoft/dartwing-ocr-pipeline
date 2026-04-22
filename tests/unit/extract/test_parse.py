"""US5 T064 — parse.py repair pipeline coverage."""

from __future__ import annotations

import json

import pytest

from ledgerlinc_ocr.extract.errors import UnrepairableResponse
from ledgerlinc_ocr.extract.parse import parse_model_response


_CLEAN = json.dumps({"document_type": {"value": "invoice", "confidence": 0.9}})


def test_clean_json_no_repair_trail() -> None:
    parsed, repair_trail = parse_model_response(_CLEAN)
    assert parsed["document_type"]["value"] == "invoice"
    assert repair_trail == []


def test_markdown_fenced_json_repairs_with_trail_entry() -> None:
    fenced = f"```json\n{_CLEAN}\n```"
    parsed, repair_trail = parse_model_response(fenced)
    assert parsed["document_type"]["value"] == "invoice"
    assert any("fence" in step.lower() for step in repair_trail)


def test_prose_prefixed_json_repairs() -> None:
    wrapped = f"Here is the extracted JSON:\n\n{_CLEAN}\n"
    parsed, repair_trail = parse_model_response(wrapped)
    assert parsed["document_type"]["value"] == "invoice"
    assert any("prose" in step.lower() for step in repair_trail)


def test_bom_prefixed_json_repairs() -> None:
    bom = "﻿" + _CLEAN
    parsed, repair_trail = parse_model_response(bom)
    assert parsed["document_type"]["value"] == "invoice"
    assert any("bom" in step.lower() for step in repair_trail)


def test_pure_prose_raises_unrepairable() -> None:
    with pytest.raises(UnrepairableResponse):
        parse_model_response("I cannot extract this document.\n")


def test_empty_string_raises_unrepairable() -> None:
    with pytest.raises(UnrepairableResponse):
        parse_model_response("")
