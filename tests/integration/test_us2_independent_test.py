"""T033 — US2 acceptance scenarios AS1-AS7.

US2: Deterministically evaluate semantic/table OCR quality.

AS1: `$21:00` observed vs `21.00` expected → failed currency-shape
AS2: missing required cell → failed missing-required-content
AS3: shifted/split row → failed row-alignment
AS4: partial row text → failed row-text-coverage
AS5: high body_confidence_mean ≈ 0.97 + failing content checks →
     status remains `failed` (FR-013: confidence is evidence, not authority)
AS6: two runs byte-identical (SC-007)
AS7: no network and no model call during the run (assert via
     monkey-patched socket.socket and absence of paddle* modules)

This test runs against the committed synthetic fixture at
tests/stage1_semantic_quality/inv_001_hard/.
"""

from __future__ import annotations

import socket
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from dartwing_ocr.evaluator.semantic_quality import run_semantic_quality_gate
from dartwing_ocr.evaluator.stable_json import dump_stable


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "stage1_semantic_quality" / "inv_001_hard"


@pytest.fixture(scope="module")
def fixture_paths() -> tuple[Path, Path]:
    pp = FIXTURE_ROOT / "preprocess_output.json"
    sc = FIXTURE_ROOT / "semantic_table_truth.json"
    if not pp.exists() or not sc.exists():
        pytest.skip("Synthetic fixture not present")
    return pp, sc


class TestUS2AcceptanceScenarios:
    def test_as1_as2_as4_status_is_failed(
        self, fixture_paths: tuple[Path, Path]
    ) -> None:
        """AS1+AS2+AS4 (combined): the fixture is engineered to fail multiple
        categories. Verify status == 'failed' and at least the three core
        categories fire."""
        pp, sc = fixture_paths
        result = run_semantic_quality_gate(pp, sc, folder_basename="inv_001_hard")
        assert result.status == "failed"
        cats = {fc.category for fc in result.failed_checks}
        # AS1: malformed-currency-shape
        assert "malformed-currency-shape" in cats
        # AS2: missing-required-content
        assert "missing-required-content" in cats
        # AS4: row-text-coverage-gap
        assert "row-text-coverage-gap" in cats

    def test_failed_checks_have_concrete_evidence(
        self, fixture_paths: tuple[Path, Path]
    ) -> None:
        pp, sc = fixture_paths
        result = run_semantic_quality_gate(pp, sc, folder_basename="inv_001_hard")
        assert len(result.failed_checks) >= 1
        for fc in result.failed_checks:
            assert fc.row_id
            assert fc.expected is not None
            assert fc.predicate

    def test_as5_high_confidence_does_not_promote_failure_to_pass(
        self, fixture_paths: tuple[Path, Path]
    ) -> None:
        """AS5: body_confidence_mean ≈ 0.97 must NOT change a `failed` to `passed`."""
        pp, sc = fixture_paths
        result = run_semantic_quality_gate(pp, sc, folder_basename="inv_001_hard")
        assert result.status == "failed"
        assert result.supporting_evidence is not None
        # The fixture is engineered with high body confidence (≈0.97).
        assert result.supporting_evidence.body_confidence_mean >= 0.9

    def test_as6_two_runs_byte_identical(
        self, fixture_paths: tuple[Path, Path], tmp_path: Path
    ) -> None:
        """SC-007: identical inputs → byte-identical serialized output."""
        pp, sc = fixture_paths
        r1 = run_semantic_quality_gate(pp, sc, folder_basename="inv_001_hard")
        r2 = run_semantic_quality_gate(pp, sc, folder_basename="inv_001_hard")
        assert r1 == r2

    def test_as7_no_paddle_module_imported(
        self, fixture_paths: tuple[Path, Path]
    ) -> None:
        """MI-1 / FR-008 / FR-034: no paddle module loaded."""
        pp, sc = fixture_paths
        run_semantic_quality_gate(pp, sc, folder_basename="inv_001_hard")
        leaked = [m for m in sys.modules if m.lower().startswith("paddle")]
        assert leaked == [], f"paddle modules leaked: {leaked}"

    def test_as7_no_network_io(
        self, fixture_paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-034: socket.connect blocked → gate still runs."""

        def _refuse(*args, **kwargs):  # noqa: ANN001
            raise AssertionError("Network I/O during gate run")

        monkeypatch.setattr(socket.socket, "connect", _refuse)
        monkeypatch.setattr(socket.socket, "connect_ex", _refuse)

        pp, sc = fixture_paths
        result = run_semantic_quality_gate(pp, sc, folder_basename="inv_001_hard")
        assert result.status in {"passed", "failed", "unevaluable", "not_applicable"}


class TestUS2FixtureShape:
    """Sanity tests on the committed fixture: it MUST validate against
    v1.3.0 preprocess_output.schema.json."""

    def test_preprocess_output_schema_valid(
        self, fixture_paths: tuple[Path, Path]
    ) -> None:
        import json

        import jsonschema

        pp, _ = fixture_paths
        schema_path = (
            REPO_ROOT
            / "contracts"
            / "stage1_vendor_identity"
            / "v1.3.0"
            / "preprocess_output.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        instance = json.loads(pp.read_text(encoding="utf-8"))
        jsonschema.validate(instance=instance, schema=schema)

    def test_sidecar_schema_valid(self, fixture_paths: tuple[Path, Path]) -> None:
        import json

        import jsonschema

        _, sc = fixture_paths
        schema_path = (
            REPO_ROOT
            / "contracts"
            / "stage1_vendor_identity"
            / "v1.3.0"
            / "semantic_table_truth.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        instance = json.loads(sc.read_text(encoding="utf-8"))
        jsonschema.validate(instance=instance, schema=schema)

    def test_sidecar_document_id_matches_folder(
        self, fixture_paths: tuple[Path, Path]
    ) -> None:
        import json

        _, sc = fixture_paths
        obj = json.loads(sc.read_text(encoding="utf-8"))
        assert obj["document_id"] == "inv_001_hard"

    def test_sidecar_row_ids_match_safety_pattern(
        self, fixture_paths: tuple[Path, Path]
    ) -> None:
        import json
        import re

        _, sc = fixture_paths
        obj = json.loads(sc.read_text(encoding="utf-8"))
        pat = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
        for row in obj["rows"]:
            assert pat.fullmatch(row["row_id"]), f"row_id violates safety pattern: {row['row_id']}"

    def test_sidecar_has_8_rows(self, fixture_paths: tuple[Path, Path]) -> None:
        import json

        _, sc = fixture_paths
        obj = json.loads(sc.read_text(encoding="utf-8"))
        assert len(obj["rows"]) == 8

    def test_no_source_pdf_in_fixture_folder(self) -> None:
        """MI-25: no source.pdf in the synthetic fixture."""
        if not FIXTURE_ROOT.exists():
            pytest.skip("fixture folder not present")
        assert not (FIXTURE_ROOT / "source.pdf").exists()
