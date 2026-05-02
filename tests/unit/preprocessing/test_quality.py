from ledgerlinc_ocr.preprocessing.quality import compute_quality


def test_compute_quality_ignores_missing_confidence_values():
    quality = compute_quality(
        [
            {"confidence": None},
            {"confidence": 0.9},
            {"confidence": 0.8},
        ],
        max_skew_deg=0.0,
    )

    assert quality == {
        "scan_quality": "good",
        "skew_detected": False,
        "noise_level": "low",
    }


def test_compute_quality_treats_all_missing_confidence_as_poor_high_noise():
    quality = compute_quality(
        [
            {"confidence": None},
            {"confidence": None},
        ],
        max_skew_deg=0.0,
    )

    assert quality == {
        "scan_quality": "poor",
        "skew_detected": False,
        "noise_level": "high",
    }
