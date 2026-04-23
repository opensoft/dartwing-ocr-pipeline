"""ingestion_sources block assembly (FR-003, FR-015, FR-019)."""

from __future__ import annotations

from typing import Any

PADDLEOCR_VL = "paddleocr_vl"
FALCON_OCR = "falcon_ocr"
FALCON_PERCEPTION = "falcon_perception"


def build_ingestion_sources(
    pages_total: int,
    pages_with_paddleocr_output: int,
    silent_empty_page_detected: bool = False,
) -> dict[str, dict[str, Any]]:
    """Assemble the `ingestion_sources` artifact block.

    `paddleocr_vl.status` is downgraded to `"failure"` when either:
      - all pages failed to produce any paddleocr output
        (`pages_with_paddleocr_output < 1`), OR
      - any page fired FR-003 (lines > 0 AND blocks == 0) or FR-019
        (blocks > 0 AND lines == 0 AND >=1 text-type block) — propagated
        by the caller via `silent_empty_page_detected=True`.

    Unknown-label warnings (FR-006) and suspicious-single-block warnings
    (FR-018) do NOT contribute to the downgrade signal.
    """
    if pages_total < 1:
        raise ValueError(f"pages_total must be >= 1, got {pages_total}")
    if pages_with_paddleocr_output < 0 or pages_with_paddleocr_output > pages_total:
        raise ValueError(
            f"pages_with_paddleocr_output must be in [0, {pages_total}], got {pages_with_paddleocr_output}"
        )

    all_pages_empty = pages_with_paddleocr_output < 1
    paddle_status = "failure" if (all_pages_empty or silent_empty_page_detected) else "success"

    return {
        PADDLEOCR_VL: {"enabled": True, "status": paddle_status},
        FALCON_OCR: {"enabled": False, "status": "not_implemented"},
        FALCON_PERCEPTION: {"enabled": False, "status": "not_implemented"},
    }
