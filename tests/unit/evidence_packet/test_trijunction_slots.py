"""Unit tests for ``sections.trijunction.build_ingestion_sources``."""
from __future__ import annotations

import itertools

import pytest

from dartwing_ocr.evidence_packet.sections.trijunction import build_ingestion_sources

_STATUSES = ["success", "failure", "not_implemented"]
_ENABLED = [True, False]


def _preprocess(paddle_status, paddle_enabled, falcon_ocr, falcon_perception):
    return {
        "ingestion_sources": {
            "paddleocr_vl": {"enabled": paddle_enabled, "status": paddle_status},
            "falcon_ocr": {"enabled": False, "status": falcon_ocr},
            "falcon_perception": {"enabled": False, "status": falcon_perception},
        }
    }


@pytest.mark.parametrize(
    "status,enabled", list(itertools.product(_STATUSES, _ENABLED))
)
def test_paddleocr_payload_follows_status(status, enabled):
    pre = _preprocess(status, enabled, "not_implemented", "not_implemented")
    sources = build_ingestion_sources(pre)
    slot = sources["paddleocr_vl"]
    assert slot["enabled"] == enabled
    assert slot["status"] == status
    if status == "success":
        assert slot["payload"] == {"kind": "structural"}
    else:
        assert slot["payload"] is None


@pytest.mark.parametrize("falcon_status", _STATUSES)
def test_falcon_slots_payload_always_null_in_stage1(falcon_status):
    pre = _preprocess("success", True, falcon_status, falcon_status)
    sources = build_ingestion_sources(pre)
    assert sources["falcon_ocr"]["payload"] is None
    assert sources["falcon_perception"]["payload"] is None
    assert sources["falcon_ocr"]["status"] == falcon_status
    assert sources["falcon_perception"]["status"] == falcon_status
