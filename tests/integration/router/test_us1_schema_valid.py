"""T017 / US1 AC#1 + AC#2: CLI emits a schema-valid routing_decision.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

ISO_UTC_Z_SECOND = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_cli_exits_zero_and_writes_schema_valid_artifact(
    green_fixture: Path, run_cli
):
    result = run_cli(green_fixture)
    assert result.returncode == 0, result.stderr
    artifact_path = green_fixture / "routing_decision.json"
    assert artifact_path.exists()

    from ledgerlinc_ocr.validator import validate_artifact

    outcome = validate_artifact(
        artifact_path, "routing_decision", version="1.0.0"
    )
    assert outcome.passed, outcome.violations


def test_cli_artifact_field_shape(green_fixture: Path, run_cli, read_artifact):
    run_cli(green_fixture)
    artifact = read_artifact(green_fixture)
    assert artifact["contract_set_version"] == "1.0.0"
    assert artifact["document_id"] == "inv_001_easy"
    assert artifact["pipeline_version"]
    assert artifact["policy_version"]
    assert ISO_UTC_Z_SECOND.match(artifact["processed_at"])


def test_cli_stdout_is_single_json_line(green_fixture: Path, run_cli):
    result = run_cli(green_fixture)
    assert result.returncode == 0
    lines = [l for l in result.stdout.splitlines() if l]
    assert len(lines) == 1
    envelope = json.loads(lines[0])
    assert envelope["status"] == "ok"
    assert envelope["document_id"] == "inv_001_easy"
    assert envelope["decision"] == "edge_accept"


REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = (
    REPO_ROOT
    / "contracts"
    / "stage1_vendor_identity"
    / "v1.0.0"
    / "routing_decision.schema.json"
)


def test_checks_and_scores_key_order_matches_schema(
    green_fixture: Path, run_cli
):
    """T067 / Finding C2 (FR-002 key-order).

    FR-002 forbids implementation-dependent key ordering: ``checks`` and
    ``scores`` MUST emit their keys in the exact order declared by the
    schema's ``required`` arrays so byte-identity across reruns is
    well-defined. ``json.loads(..., object_pairs_hook=list)`` preserves
    insertion order so we can assert against the serialized bytes.
    """
    run_cli(green_fixture)
    raw = (green_fixture / "routing_decision.json").read_text()

    # Pinned literal expected order — if the schema and the code drift
    # together (e.g., both reorder to alphabetical), the derived-from-schema
    # assertion below would still pass. This literal is the reviewer-visible
    # source of truth; changing it requires a POLICY_VERSION bump per FR-005.
    LITERAL_TOP_LEVEL_ORDER = [
        "contract_set_version",
        "pipeline_version",
        "policy_version",
        "document_id",
        "processed_at",
        "status",
        "decision",
        "consensus_summary",
        "scores",
        "checks",
        "review_status",
        "reasons",
    ]
    LITERAL_CHECKS_ORDER = [
        "company_name_present",
        "company_name_inferred",
        "address_has_minimum_components",
        "at_least_one_tax_id_present",
        "website_or_email_present",
        "post_extraction_spam_gate_passed",
    ]
    LITERAL_SCORES_ORDER = [
        "company_name_score",
        "address_score",
        "tax_id_score",
        "contact_score",
        "overall_vendor_identity_score",
    ]

    schema = json.loads(SCHEMA_PATH.read_text())
    expected_top_level_order = schema["required"]
    expected_checks_order = schema["properties"]["checks"]["required"]
    expected_scores_order = schema["properties"]["scores"]["required"]

    # object_pairs_hook=list preserves insertion order as list[tuple] at
    # every nesting level, so we can compare emitted key order directly
    # against the schema's required arrays.
    top_level_pairs = json.loads(raw, object_pairs_hook=list)
    top_level = dict(top_level_pairs)
    top_level_keys = [k for k, _ in top_level_pairs]
    checks_keys = [k for k, _ in top_level["checks"]]
    scores_keys = [k for k, _ in top_level["scores"]]

    assert top_level_keys == LITERAL_TOP_LEVEL_ORDER, (
        f"top-level key order drifted from pinned literal: got {top_level_keys}"
    )
    assert checks_keys == LITERAL_CHECKS_ORDER, (
        f"checks key order drifted from pinned literal: got {checks_keys}"
    )
    assert scores_keys == LITERAL_SCORES_ORDER, (
        f"scores key order drifted from pinned literal: got {scores_keys}"
    )
    # And the schema itself must also stay aligned with the literal pin.
    assert expected_top_level_order == LITERAL_TOP_LEVEL_ORDER, (
        "routing_decision.schema.json top-level required drifted from literal"
    )
    assert expected_checks_order == LITERAL_CHECKS_ORDER, (
        "routing_decision.schema.json checks.required drifted from literal"
    )
    assert expected_scores_order == LITERAL_SCORES_ORDER, (
        "routing_decision.schema.json scores.required drifted from literal"
    )
