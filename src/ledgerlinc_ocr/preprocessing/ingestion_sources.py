"""ingestion_sources block assembly (FR-015, FR-015a, FR-016)."""

from __future__ import annotations

from typing import Any

PADDLEOCR_VL = "paddleocr_vl"
FALCON_OCR = "falcon_ocr"
FALCON_PERCEPTION = "falcon_perception"


def build_ingestion_sources(
    pages_total: int,
    pages_with_paddleocr_output: int,
) -> dict[str, dict[str, Any]]:
    if pages_total < 1:
        raise ValueError(f"pages_total must be >= 1, got {pages_total}")
    if pages_with_paddleocr_output < 0 or pages_with_paddleocr_output > pages_total:
        raise ValueError(
            f"pages_with_paddleocr_output must be in [0, {pages_total}], got {pages_with_paddleocr_output}"
        )

    paddle_status = "success" if pages_with_paddleocr_output >= 1 else "failure"

    return {
        PADDLEOCR_VL: {"enabled": True, "status": paddle_status},
        FALCON_OCR: {"enabled": False, "status": "not_implemented"},
        FALCON_PERCEPTION: {"enabled": False, "status": "not_implemented"},
    }
