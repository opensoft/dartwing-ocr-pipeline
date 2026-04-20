"""Rule-derived quality signals (FR-013, research Decision 6)."""

from __future__ import annotations

from typing import Any

LOW_CONFIDENCE_THRESHOLD = 0.60
SKEW_FLAG_DEG = 2.0

SCAN_GOOD_AVG = 0.85
SCAN_GOOD_LOWCONF = 0.10
SCAN_FAIR_AVG = 0.70
SCAN_FAIR_LOWCONF = 0.25

NOISE_LOW_MAX = 0.10
NOISE_MEDIUM_MAX = 0.30


def compute_quality(
    all_lines: list[dict[str, Any]],
    max_skew_deg: float,
) -> dict[str, Any]:
    if all_lines:
        confs = [float(l["confidence"]) for l in all_lines]
        avg_conf = sum(confs) / len(confs)
        low_ratio = sum(1 for c in confs if c < LOW_CONFIDENCE_THRESHOLD) / len(confs)
    else:
        avg_conf = 0.0
        low_ratio = 1.0

    if avg_conf >= SCAN_GOOD_AVG and low_ratio <= SCAN_GOOD_LOWCONF:
        scan_quality = "good"
    elif avg_conf >= SCAN_FAIR_AVG and low_ratio <= SCAN_FAIR_LOWCONF:
        scan_quality = "fair"
    else:
        scan_quality = "poor"

    if low_ratio <= NOISE_LOW_MAX:
        noise_level = "low"
    elif low_ratio <= NOISE_MEDIUM_MAX:
        noise_level = "medium"
    else:
        noise_level = "high"

    return {
        "scan_quality": scan_quality,
        "skew_detected": bool(max_skew_deg >= SKEW_FLAG_DEG),
        "noise_level": noise_level,
    }
