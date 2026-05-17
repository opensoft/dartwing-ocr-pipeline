"""Trijunction ingestion_sources slot block."""
from __future__ import annotations

from typing import Any


def _slot(
    source_name: str,
    source_input: dict[str, Any],
) -> dict[str, Any]:
    enabled = bool(source_input["enabled"])
    status = source_input["status"]
    if source_name == "paddleocr_vl" and status == "success":
        payload: dict[str, Any] | None = {"kind": "structural"}
    else:
        payload = None
    return {"enabled": enabled, "status": status, "payload": payload}


def build_ingestion_sources(preprocess_output: dict[str, Any]) -> dict[str, Any]:
    sources = preprocess_output["ingestion_sources"]
    return {
        "paddleocr_vl": _slot("paddleocr_vl", sources["paddleocr_vl"]),
        "falcon_ocr": _slot("falcon_ocr", sources["falcon_ocr"]),
        "falcon_perception": _slot("falcon_perception", sources["falcon_perception"]),
    }
