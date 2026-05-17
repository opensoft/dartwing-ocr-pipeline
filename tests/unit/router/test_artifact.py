"""T016: Unit tests for ``artifact.assemble_and_write``."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from dartwing_ocr.router.artifact import assemble_and_write
from dartwing_ocr.router.errors import ContractAssertionError, MissingInputError


def _valid_artifact(document_id="inv_001_easy"):
    return {
        "contract_set_version": "1.0.0",
        "pipeline_version": "stage1-routing-v0.1.0",
        "policy_version": "stage1-routing-policy-v1.0.0",
        "document_id": document_id,
        "processed_at": "2026-04-21T12:00:00Z",
        "status": "success",
        "decision": "edge_accept",
        "consensus_summary": {
            "mode": "single_voter_baseline",
            "agreement_level": "not_applicable",
        },
        "scores": {
            "company_name_score": 1.0,
            "address_score": 1.0,
            "tax_id_score": 0.25,
            "contact_score": 2 / 3,
            "overall_vendor_identity_score": 0.72916666,
        },
        "checks": {
            "company_name_present": True,
            "company_name_inferred": False,
            "address_has_minimum_components": True,
            "at_least_one_tax_id_present": True,
            "website_or_email_present": True,
            "post_extraction_spam_gate_passed": True,
        },
        "review_status": {
            "manual_review_required": False,
            "review_reason": None,
        },
        "reasons": ["company_name_explicit"],
    }


def test_successful_write_creates_routing_decision(tmp_path: Path):
    path = assemble_and_write(tmp_path, _valid_artifact())
    assert path == tmp_path / "routing_decision.json"
    assert path.exists()


def test_written_file_trailing_newline_and_indent(tmp_path: Path):
    path = assemble_and_write(tmp_path, _valid_artifact())
    raw = path.read_bytes()
    assert raw.endswith(b"\n")
    assert b"\n  " in raw, "expected indent=2 formatting"


def test_written_file_is_schema_valid(tmp_path: Path):
    from dartwing_ocr.validator import validate_artifact

    path = assemble_and_write(tmp_path, _valid_artifact())
    outcome = validate_artifact(path, "routing_decision", version="1.0.0")
    assert outcome.passed, outcome.violations


def test_schema_invalid_artifact_does_not_write(tmp_path: Path):
    bad = _valid_artifact()
    del bad["policy_version"]
    with pytest.raises(ContractAssertionError):
        assemble_and_write(tmp_path, bad)
    assert not (tmp_path / "routing_decision.json").exists()
    # And no temp file remains
    leftovers = [p for p in tmp_path.iterdir() if p.name != "routing_decision.json"]
    assert leftovers == [], f"unexpected leftovers: {leftovers}"


def test_overwrite_replaces_existing_artifact(tmp_path: Path):
    assemble_and_write(tmp_path, _valid_artifact(document_id="inv_001_easy"))
    # Run again with different doc_id — the output should fully replace
    assemble_and_write(tmp_path, _valid_artifact(document_id="inv_002_easy"))
    written = json.loads((tmp_path / "routing_decision.json").read_text())
    assert written["document_id"] == "inv_002_easy"


def test_no_partial_temp_file_on_success(tmp_path: Path):
    assemble_and_write(tmp_path, _valid_artifact())
    leftovers = [
        p for p in tmp_path.iterdir() if p.name.startswith(".routing_decision.")
    ]
    assert leftovers == []


def test_ghost_folder_raises_typed_missing_input_error(tmp_path: Path):
    """FR-022 gate: library callers that bypass the CLI pre-check must get a
    typed ``MissingInputError`` (CLI exit 2) — not a bare ``FileNotFoundError``
    that the CLI surface would misclassify as an unexpected exception (exit 1).
    """
    ghost = tmp_path / "does_not_exist"
    with pytest.raises(MissingInputError) as exc_info:
        assemble_and_write(ghost, _valid_artifact())
    # Confirm the typed error carries the human_message attribute the CLI
    # relies on for its one-line stderr diagnostic.
    assert "does not exist" in exc_info.value.human_message


def test_ghost_folder_raises_before_any_filesystem_write(
    tmp_path: Path, monkeypatch
):
    """Pre-write gate must fire before we attempt any filesystem write.

    The prior assertion (``tmp_path`` empty after the raise) was tautological:
    ``tempfile.mkstemp(dir=ghost)`` would fail on a missing folder anyway, so
    the assertion passed even if the gate wasn't doing any work. Spy on
    ``tempfile.mkstemp`` and ``os.open`` directly — those are the only calls
    that could create filesystem state before the schema validator runs.
    """
    ghost = tmp_path / "does_not_exist"

    mkstemp_calls: list[tuple] = []
    original_mkstemp = tempfile.mkstemp

    def spy_mkstemp(*args, **kwargs):
        mkstemp_calls.append((args, kwargs))
        return original_mkstemp(*args, **kwargs)

    monkeypatch.setattr(tempfile, "mkstemp", spy_mkstemp)

    with pytest.raises(MissingInputError):
        assemble_and_write(ghost, _valid_artifact())

    assert mkstemp_calls == [], (
        "MissingInputError must fire before tempfile.mkstemp — otherwise a "
        "wrong-path caller could create tempfiles in an unintended location "
        "before the folder gate rejects them."
    )
    assert not ghost.exists(), "pre-write gate must not mkdir the target"
