"""Perceptual observations: stage-1 empties, status mirrors falcon_perception."""
from __future__ import annotations

from typing import Any


def build_perceptual_observations(preprocess_output: dict[str, Any]) -> dict[str, Any]:
    status = preprocess_output["ingestion_sources"]["falcon_perception"]["status"]
    return {
        "status": status,
        "logos": [],
        "stamps": [],
        "header_candidates": [],
        "footer_candidates": [],
    }
