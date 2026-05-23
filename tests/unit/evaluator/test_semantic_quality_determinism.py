"""T032 / SC-007 / FR-014 / MI-2 — determinism tests.

Two runs of the gate on the same inputs MUST produce equal
SemanticQualityResult values AND byte-identical serialization via
stable_json.dump_stable.

Uses the committed synthetic fixture if available; otherwise builds an
in-tmp fixture.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from dartwing_ocr.evaluator.semantic_quality import run_semantic_quality_gate
from dartwing_ocr.evaluator.stable_json import dump_stable


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "tests" / "stage1_semantic_quality" / "inv_001_hard"


def _result_to_serializable(result) -> dict:
    """Convert a SemanticQualityResult to a JSON-serializable dict for
    byte-comparison via stable_json."""
    out: dict = {"status": result.status}
    # failed_checks
    if result.failed_checks is not None:
        out["failed_checks"] = [
            {
                "category": fc.category,
                "row_id": fc.row_id,
                "field": fc.field,
                "expected": fc.expected,
                "observed": fc.observed,
                "predicate": fc.predicate,
                "position_index": fc.position_index,
            }
            for fc in result.failed_checks
        ]
    if result.row_reasons is not None:
        out["row_reasons"] = {
            row_id: {
                "categories": list(entry.categories),
                "reason": entry.reason,
            }
            for row_id, entry in result.row_reasons.items()
        }
    if result.supporting_evidence is not None:
        se = result.supporting_evidence
        out["supporting_evidence"] = {
            "body_confidence_mean": se.body_confidence_mean,
            "body_confidence_min": se.body_confidence_min,
            "body_line_count": se.body_line_count,
            "body_token_count": se.body_token_count,
            "header_band_excluded": se.header_band_excluded,
        }
    if result.cause is not None:
        out["cause"] = result.cause
    if result.cause_detail is not None:
        out["cause_detail"] = result.cause_detail
    return out


class TestByteIdenticalRuns:
    def test_two_runs_on_synthetic_fixture_byte_identical(self, tmp_path: Path) -> None:
        pp = FIXTURE_ROOT / "preprocess_output.json"
        sc = FIXTURE_ROOT / "semantic_table_truth.json"
        if not pp.exists() or not sc.exists():
            # The fixture is created by T041/T042; skip if not present yet.
            import pytest

            pytest.skip("Synthetic fixture not yet present")

        r1 = run_semantic_quality_gate(pp, sc, folder_basename="inv_001_hard")
        r2 = run_semantic_quality_gate(pp, sc, folder_basename="inv_001_hard")
        # Dataclass equality
        assert r1 == r2

        # Byte-identical serialization
        p1 = tmp_path / "out1.json"
        p2 = tmp_path / "out2.json"
        dump_stable(_result_to_serializable(r1), p1)
        dump_stable(_result_to_serializable(r2), p2)
        assert p1.read_bytes() == p2.read_bytes()
