"""T005: ExitCode enum contract."""
from __future__ import annotations

import pytest

from ledgerlinc_ocr.pipeline.exit_codes import ExitCode, StructuredFailureRecord


EXPECTED = {
    "SUCCESS": 0,
    "USAGE_ERROR": 10,
    "INPUT_NOT_FOUND": 11,
    "INVALID_PDF": 12,
    "OUTPUT_IN_USE": 13,
    "OUTPUT_PATH_NOT_USABLE": 14,
    # Feature 016: GPU warmup pass failed (preprocessing/warmup.py raises
    # WarmupError) — exit 15. Slots immediately after feature 014's preflight
    # 10–14 codes per research R-016.6.
    "WARMUP_FAILED": 15,
    # Feature 017: unknown `module_set_id` or `det_rec_variant_id` value
    # selected via CLI flag or env var — exit 16. CLI parse boundary fails
    # fast before any Paddle import (R-017.9 / R-017.12).
    "UNKNOWN_PRESET": 16,
    "PROCESSING_FAILURE": 20,
    "SCHEMA_VALIDATION_FAILURE": 30,
}


@pytest.mark.parametrize("name,code", EXPECTED.items())
def test_each_member_has_exact_numeric_value(name, code):
    assert ExitCode[name].value == code


def test_closed_set_no_extras():
    assert {m.name for m in ExitCode} == set(EXPECTED)


def test_numeric_values_are_unique():
    values = [m.value for m in ExitCode]
    assert len(values) == len(set(values))


def test_structured_record_round_trips():
    import json as _json

    rec = StructuredFailureRecord.for_code(
        ExitCode.PROCESSING_FAILURE,
        stage="extraction",
        message="boom",
        artifacts_written=["/abs/preprocess_output.json"],
    )
    line = rec.as_json_line()
    assert "\n" not in line
    parsed = _json.loads(line)
    assert parsed == {
        "exit_code": 20,
        "exit_code_name": "PROCESSING_FAILURE",
        "stage": "extraction",
        "message": "boom",
        "artifacts_written": ["/abs/preprocess_output.json"],
    }
