"""Unit test for FR-016: schema is ready for Falcon without any amendment (T070).

Today `falcon_ocr` / `falcon_perception` come back `enabled=false,
status="not_implemented"`. The spec requires that when (and if) we wire
Falcon in, flipping their status records from `not_implemented` to a
live `enabled=true, status="success"` must NOT require editing the
frozen v1.0.0 schema. This test monkeypatches
`ingestion_sources.build_ingestion_sources` so Falcon looks live,
assembles the artifact, and confirms the validator still passes.
"""

from __future__ import annotations

from dartwing_ocr.preprocessing import artifact as artifact_mod
from dartwing_ocr.preprocessing import ingestion_sources as isrc_mod


def _base_page(page_number: int = 1) -> dict:
    return {
        "page_number": page_number,
        "width": 1275,
        "height": 1650,
        "rotation_detected": 0,
        "blocks": [
            {
                "block_id": f"p{page_number}_b1",
                "block_type": "text",
                "bbox": [10, 10, 100, 30],
                "reading_order": 1,
                "text": "ACME CORP",
                "confidence": 0.98,
            }
        ],
        "raw_ocr_lines": [
            {
                "line_id": f"p{page_number}_l1",
                "bbox": [10, 10, 100, 30],
                "text": "ACME CORP",
                "confidence": 0.98,
            }
        ],
    }


def test_live_falcon_ingestion_sources_still_schema_valid():
    live_ingestion = {
        "paddleocr_vl": {"enabled": True, "status": "success"},
        "falcon_ocr": {"enabled": True, "status": "success"},
        "falcon_perception": {"enabled": True, "status": "success"},
    }

    artifact = artifact_mod.assemble(
        contract_set_version="1.0.0",
        pipeline_version="stage1-preprocess-0.1.0+paddleocr2.8.0.deadbee.dpi300",
        document_id="inv_001",
        source_file="source.pdf",
        pages=[_base_page(1)],
        tables=[],
        quality={
            "scan_quality": "good",
            "skew_detected": False,
            "noise_level": "low",
        },
        ingestion_sources=live_ingestion,
        warnings=[],
    )

    # Must validate without any schema change — FR-016.
    artifact_mod.validate(artifact)

    assert artifact["ingestion_sources"]["falcon_ocr"]["enabled"] is True
    assert artifact["ingestion_sources"]["falcon_ocr"]["status"] == "success"
    assert artifact["ingestion_sources"]["falcon_perception"]["enabled"] is True


def test_build_ingestion_sources_only_exposes_three_pinned_keys():
    """The builder itself must not accidentally add or drop source keys
    (FR-015 pins exactly three)."""
    result = isrc_mod.build_ingestion_sources(pages_total=2, pages_with_paddleocr_output=2)
    assert set(result.keys()) == {"paddleocr_vl", "falcon_ocr", "falcon_perception"}
    for key, record in result.items():
        assert set(record.keys()) == {"enabled", "status"}
