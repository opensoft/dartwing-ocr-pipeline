"""T039 — exercise reconcile.py step 3 (evidence reconciliation) in isolation.

Feeds a known packet + a parsed response with the four evidence classes:
(a) valid IDs that resolve, (b) pattern-malformed IDs, (c) pattern-valid IDs
that don't resolve against this packet's index, (d) duplicated valid IDs.
Asserts final evidence arrays contain only resolved IDs, first-seen order,
deduplicated; at least one warning per dropped ID names the field + ID.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ledgerlinc_ocr.extract.config import load_voter_config
from ledgerlinc_ocr.extract.reconcile import reconcile

_REPO_ROOT = Path(__file__).resolve().parents[3]
_US2_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "extract" / "us2_evidence"


def _reconciled():
    packet = json.loads((_US2_FIXTURE / "preprocess_output.json").read_text(encoding="utf-8"))
    parsed = json.loads((_US2_FIXTURE / "voter_response_bogus_evidence.json").read_text(encoding="utf-8"))
    config, _, _ = load_voter_config(
        name_or_path=str(_US2_FIXTURE / "voter_config.yaml"),
        base_dir=Path.cwd(),
    )
    return reconcile(
        packet=packet,
        parsed=parsed,
        config=config,
        now=datetime(2026, 4, 21, 12, 0, 0, tzinfo=UTC),
        pipeline_version="0.0.0-test+us2",
        repair_trail=[],
    )


def test_valid_ids_survive_and_deduplicate_first_seen() -> None:
    out = _reconciled()
    cn = out["vendor_candidate"]["company_name"]
    # Input had ["p1_b1", "p1_b1", "p1_l1"]; dedup keeps first-seen order.
    assert cn["evidence"] == ["p1_b1", "p1_l1"]


def test_malformed_ids_are_dropped_with_warning() -> None:
    out = _reconciled()
    addr = out["vendor_candidate"]["address"]
    # p1_x5 (malformed — x not b/l) dropped
    assert addr["postal_code"]["evidence"] == []
    # b0 (malformed — no page prefix) dropped
    assert addr["country"]["evidence"] == []
    # page1_line9 (malformed) dropped
    assert out["vendor_candidate"]["phone"]["evidence"] == []

    warnings_blob = "\n".join(out["warnings"])
    assert "postal_code" in warnings_blob and "p1_x5" in warnings_blob
    assert "country" in warnings_blob and "b0" in warnings_blob
    assert "phone" in warnings_blob and "page1_line9" in warnings_blob


def test_unresolved_ids_are_dropped_with_warning() -> None:
    out = _reconciled()
    addr = out["vendor_candidate"]["address"]
    # Pattern-valid but not in evidence_index → dropped
    assert addr["city"]["evidence"] == []
    assert addr["state"]["evidence"] == []
    assert out["invoice_header_fields"]["invoice_number"]["evidence"] == []

    warnings_blob = "\n".join(out["warnings"])
    assert "city" in warnings_blob and "p1_l99" in warnings_blob
    assert "state" in warnings_blob and "p2_b1" in warnings_blob
    assert "invoice_number" in warnings_blob and "p1_b99" in warnings_blob


def test_valid_grounded_fields_remain_intact() -> None:
    out = _reconciled()
    addr = out["vendor_candidate"]["address"]
    assert addr["street_1"]["evidence"] == ["p1_l2"]
    assert out["vendor_candidate"]["tax_ids"]["ein"]["evidence"] == ["p1_b3", "p1_l5"]
    assert out["vendor_candidate"]["website"]["evidence"] == ["p1_l11"]
    assert out["vendor_candidate"]["email"]["evidence"] == ["p1_l10"]
    assert out["invoice_header_fields"]["invoice_date"]["evidence"] == ["p1_l7"]
    assert out["invoice_header_fields"]["total_amount"]["evidence"] == ["p1_l8"]


def test_evidence_dropped_sets_partial_status() -> None:
    out = _reconciled()
    # Soft-failure (evidence_dropped) with some grounded evidence → "partial"
    assert out["status"] == "partial"
