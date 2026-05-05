"""Unit tests for execution slice + prerequisite + overwrite scoping.

Covers Spec FR-009 / FR-010 / FR-011; Research R-004 / R-005 / R-006.
Design checklist CHK013 / CHK014.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlinc_ocr.pipeline.profiles import STAGES
from ledgerlinc_ocr.pipeline.slice_control import (
    ARTIFACT_FILENAME_BY_STAGE,
    ExecutionSlice,
    SliceError,
    check_prerequisites,
    existing_outputs_in_slice,
    parse_slice,
    unusable_outputs_in_slice,
)


# ---------------------------------------------------------------------------
# parse_slice
# ---------------------------------------------------------------------------

def test_parse_slice_default_bounds_full_pipeline():
    s = parse_slice(start_at=None, stop_after=None)
    assert s.start_at == "preprocess"
    assert s.stop_after == "final_payload"
    assert s.stages_in_slice == STAGES


@pytest.mark.parametrize(
    "start,stop",
    [
        ("preprocess", "preprocess"),
        ("extract", "extract"),
        ("routing", "routing"),
        ("final_payload", "final_payload"),
        ("preprocess", "extract"),
        ("preprocess", "routing"),
        ("extract", "final_payload"),
        ("routing", "final_payload"),
    ],
)
def test_parse_slice_every_contiguous_combination(start, stop):
    s = parse_slice(start_at=start, stop_after=stop)
    assert s.start_at == start
    assert s.stop_after == stop


def test_parse_slice_rejects_start_after_stop():
    with pytest.raises(SliceError, match="must not be later than"):
        parse_slice(start_at="extract", stop_after="preprocess")
    with pytest.raises(SliceError):
        parse_slice(start_at="final_payload", stop_after="routing")


@pytest.mark.parametrize("bad", ["bogus", "", "preprocess,extract"])
def test_parse_slice_rejects_unknown_stage_name(bad):
    with pytest.raises(SliceError):
        parse_slice(start_at=bad, stop_after="final_payload")
    with pytest.raises(SliceError):
        parse_slice(start_at="preprocess", stop_after=bad)


# ---------------------------------------------------------------------------
# Prerequisite tabulation per start stage
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "start,expected_prereqs",
    [
        ("preprocess", ()),
        ("extract", ("preprocess_output.json",)),
        (
            "routing",
            ("preprocess_output.json", "edge_extraction_output.json"),
        ),
        (
            "final_payload",
            (
                "preprocess_output.json",
                "edge_extraction_output.json",
                "routing_decision.json",
            ),
        ),
    ],
)
def test_prerequisite_artifact_table_matches_contract(
    start, expected_prereqs
):
    s = parse_slice(start_at=start, stop_after="final_payload")
    assert s.prerequisite_artifacts == expected_prereqs


@pytest.mark.parametrize(
    "stop,expected_outputs",
    [
        ("preprocess", ("preprocess_output.json",)),
        (
            "extract",
            ("preprocess_output.json", "edge_extraction_output.json"),
        ),
        (
            "routing",
            (
                "preprocess_output.json",
                "edge_extraction_output.json",
                "routing_decision.json",
            ),
        ),
        (
            "final_payload",
            (
                "preprocess_output.json",
                "edge_extraction_output.json",
                "routing_decision.json",
                "final_structured_payload.json",
            ),
        ),
    ],
)
def test_output_artifacts_match_slice(stop, expected_outputs):
    s = parse_slice(start_at="preprocess", stop_after=stop)
    assert s.output_artifacts == expected_outputs


# ---------------------------------------------------------------------------
# Overwrite scoping (R-006)
# ---------------------------------------------------------------------------

def test_existing_outputs_in_slice_only_reports_slice_outputs(tmp_path: Path):
    # Stage all four artifact filenames on disk.
    for name in ARTIFACT_FILENAME_BY_STAGE.values():
        (tmp_path / name).write_text("{}", encoding="utf-8")

    # Slice = preprocess only -> only that one is "in use".
    s = parse_slice(start_at="preprocess", stop_after="preprocess")
    assert existing_outputs_in_slice(tmp_path, s) == ["preprocess_output.json"]

    # Slice = routing..final_payload -> only those two count, even though
    # earlier artifacts are present (they're prerequisites, not outputs).
    s = parse_slice(start_at="routing", stop_after="final_payload")
    assert existing_outputs_in_slice(tmp_path, s) == [
        "routing_decision.json",
        "final_structured_payload.json",
    ]


def test_existing_outputs_returns_empty_when_nothing_present(tmp_path: Path):
    s = parse_slice(start_at="preprocess", stop_after="final_payload")
    assert existing_outputs_in_slice(tmp_path, s) == []


def test_directory_output_path_is_unusable_not_existing_output(tmp_path: Path):
    (tmp_path / "preprocess_output.json").mkdir()
    s = parse_slice(start_at="preprocess", stop_after="preprocess")

    assert existing_outputs_in_slice(tmp_path, s) == []
    assert unusable_outputs_in_slice(tmp_path, s) == ["preprocess_output.json"]


# ---------------------------------------------------------------------------
# check_prerequisites (R-005)
# ---------------------------------------------------------------------------

def test_check_prerequisites_skipped_when_slice_starts_at_preprocess(tmp_path: Path):
    s = parse_slice(start_at="preprocess", stop_after="preprocess")
    # No prerequisite artifact required, so the result is OK regardless of
    # whether anything exists on disk.
    result = check_prerequisites(folder=tmp_path, slice_=s, contract_set_version="1.2.0")
    assert result.ok is True


def test_check_prerequisites_reports_missing_artifact(tmp_path: Path):
    s = parse_slice(start_at="extract", stop_after="extract")
    result = check_prerequisites(folder=tmp_path, slice_=s, contract_set_version="1.2.0")
    assert result.ok is False
    assert result.missing_artifact == "preprocess_output.json"
    assert result.invalid_artifact is None


def test_check_prerequisites_reports_invalid_artifact(tmp_path: Path):
    # Place a malformed JSON file that exists but fails schema validation.
    (tmp_path / "preprocess_output.json").write_text(
        json.dumps({"this": "is not a valid preprocess_output"}),
        encoding="utf-8",
    )
    s = parse_slice(start_at="extract", stop_after="extract")
    result = check_prerequisites(folder=tmp_path, slice_=s, contract_set_version="1.2.0")
    assert result.ok is False
    assert result.invalid_artifact == "preprocess_output.json"
    assert result.invalid_reason


# ---------------------------------------------------------------------------
# Internal stage tuple invariants
# ---------------------------------------------------------------------------

def test_stages_tuple_canonical_order():
    """Spec FR-004 / FR-009: order is preprocess -> extract -> routing -> final_payload."""
    assert STAGES == ("preprocess", "extract", "routing", "final_payload")


def test_artifact_filename_by_stage_round_trip():
    assert ARTIFACT_FILENAME_BY_STAGE == {
        "preprocess": "preprocess_output.json",
        "extract": "edge_extraction_output.json",
        "routing": "routing_decision.json",
        "final_payload": "final_structured_payload.json",
    }
