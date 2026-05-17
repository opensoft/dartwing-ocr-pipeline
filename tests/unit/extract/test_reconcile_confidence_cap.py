"""T040 — FR-011 ungrounded-confidence cap is applied per-field post-reconciliation."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dartwing_ocr.extract.config import load_voter_config
from dartwing_ocr.extract.reconcile import reconcile

_REPO_ROOT = Path(__file__).resolve().parents[3]
_US2_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "extract" / "us2_evidence"
_US1_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "extract" / "us1_happy"


def _load(folder: Path, response_name: str):
    packet = json.loads((folder / "preprocess_output.json").read_text(encoding="utf-8"))
    parsed = json.loads((folder / response_name).read_text(encoding="utf-8"))
    config, _, _ = load_voter_config(
        name_or_path=str(folder / "voter_config.yaml"),
        base_dir=Path.cwd(),
    )
    return packet, parsed, config


def _run(packet, parsed, config):
    return reconcile(
        packet=packet,
        parsed=parsed,
        config=config,
        now=datetime(2026, 4, 21, 12, 0, 0, tzinfo=UTC),
        pipeline_version="0.0.0-test+cap",
        repair_trail=[],
    )


def test_cap_applied_to_ungrounded_scalar_fields() -> None:
    packet, parsed, config = _load(_US2_FIXTURE, "voter_response_bogus_evidence.json")
    out = _run(packet, parsed, config)
    cap = config.reconciliation.ungrounded_confidence_cap

    addr = out["vendor_candidate"]["address"]
    # city's evidence was dropped → ungrounded → confidence capped
    assert addr["city"]["evidence"] == []
    assert addr["city"]["confidence"] <= cap
    assert addr["state"]["confidence"] <= cap
    assert addr["postal_code"]["confidence"] <= cap
    assert addr["country"]["confidence"] <= cap

    assert out["vendor_candidate"]["phone"]["confidence"] <= cap
    assert out["invoice_header_fields"]["invoice_number"]["confidence"] <= cap


def test_cap_not_applied_to_grounded_scalar_fields() -> None:
    packet, parsed, config = _load(_US2_FIXTURE, "voter_response_bogus_evidence.json")
    out = _run(packet, parsed, config)
    cap = config.reconciliation.ungrounded_confidence_cap

    # street_1 kept its evidence → confidence is the model's 0.93, above cap
    st1 = out["vendor_candidate"]["address"]["street_1"]
    assert st1["evidence"] == ["p1_l2"]
    assert st1["confidence"] > cap
    assert st1["confidence"] == pytest.approx(0.93)

    # ein, website, email, invoice_date all kept their evidence
    assert out["vendor_candidate"]["tax_ids"]["ein"]["confidence"] > cap
    assert out["vendor_candidate"]["website"]["confidence"] > cap
    assert out["vendor_candidate"]["email"]["confidence"] > cap
    assert out["invoice_header_fields"]["invoice_date"]["confidence"] > cap
    assert out["invoice_header_fields"]["total_amount"]["confidence"] > cap


def test_cap_not_applied_when_any_field_grounded_for_document_type() -> None:
    packet, parsed, config = _load(_US2_FIXTURE, "voter_response_bogus_evidence.json")
    out = _run(packet, parsed, config)
    # At least one field is grounded → document_type.confidence preserved
    assert out["document_type"]["confidence"] == pytest.approx(0.9)


def test_cap_applied_to_total_amount_when_ungrounded() -> None:
    packet, parsed, config = _load(_US1_FIXTURE, "voter_response_clean.json")
    # Wipe total_amount's evidence only
    parsed = copy.deepcopy(parsed)
    parsed["invoice_header_fields"]["total_amount"]["evidence"] = []
    out = _run(packet, parsed, config)
    cap = config.reconciliation.ungrounded_confidence_cap

    total = out["invoice_header_fields"]["total_amount"]
    assert total["evidence"] == []
    assert total["confidence"] <= cap
    # Value and currency still preserved — cap is on confidence only.
    assert total["value"] == pytest.approx(1250.0)
    assert total["currency"] == "USD"


def test_cap_value_comes_from_config() -> None:
    packet, parsed, config = _load(_US1_FIXTURE, "voter_response_clean.json")
    parsed = copy.deepcopy(parsed)
    # Strip every piece of evidence so everything is ungrounded.
    def _strip(obj):
        if isinstance(obj, dict):
            if "evidence" in obj and isinstance(obj["evidence"], list):
                obj["evidence"] = []
            for v in obj.values():
                _strip(v)
        elif isinstance(obj, list):
            for v in obj:
                _strip(v)

    _strip(parsed)

    # Mutate the config cap to a non-default value to prove it flows through.
    tight = config.model_copy(
        update={
            "reconciliation": config.reconciliation.model_copy(
                update={"ungrounded_confidence_cap": 0.10}
            )
        }
    )
    out = _run(packet, parsed, tight)
    for path, field in [
        ("street_1", out["vendor_candidate"]["address"]["street_1"]),
        ("ein", out["vendor_candidate"]["tax_ids"]["ein"]),
        ("website", out["vendor_candidate"]["website"]),
        ("invoice_date", out["invoice_header_fields"]["invoice_date"]),
    ]:
        assert field["evidence"] == [], path
        assert field["confidence"] <= 0.10, f"{path} confidence {field['confidence']!r} > 0.10"

    assert out["document_type"]["confidence"] <= 0.10
