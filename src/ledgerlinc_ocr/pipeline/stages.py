"""Default stub stage callables.

Each stub writes a minimal schema-valid artifact for its stage. Real model
inference is a downstream feature; the CLI contract only cares that the four
artifacts exist in the right place with the right shape.

Stage signatures
----------------
Every stage callable takes `(invocation: CLIInvocation, artifacts_so_far: dict)`
and returns a dict matching its v1.0.0 artifact schema. The runner writes the
returned dict to disk under the reserved filename and advances.

Schema-invalidity toggle
------------------------
The runner passes through injected stage callables verbatim, so tests can swap
in a stub that writes an intentionally invalid artifact to exercise
SCHEMA_VALIDATION_FAILURE.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ledgerlinc_ocr.pipeline.runner import CLIInvocation


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_preprocess(
    invocation: "CLIInvocation", artifacts_so_far: dict[str, Any]
) -> dict[str, Any]:
    return {
        "contract_set_version": invocation.contract_set_version,
        "pipeline_version": invocation.pipeline_version,
        "document_id": invocation.document_id,
        "source_type": "pdf",
        "source_file": "source.pdf",
        "page_count": 1,
        "pages": [
            {
                "page_number": 1,
                "width": 850,
                "height": 1100,
                "rotation_detected": 0,
                "blocks": [
                    {
                        "block_id": "p1_b1",
                        "block_type": "text",
                        "bbox": [0, 0, 100, 20],
                        "reading_order": 1,
                        "text": "stub block",
                        "confidence": 0.9,
                    }
                ],
                "raw_ocr_lines": [
                    {
                        "line_id": "p1_l1",
                        "bbox": [0, 0, 100, 20],
                        "text": "stub block",
                        "confidence": 0.9,
                    }
                ],
            }
        ],
        "document_text": "stub block",
        "tables": [],
        "quality": {
            "scan_quality": "good",
            "skew_detected": False,
            "noise_level": "low",
        },
        "ingestion_sources": {
            "paddleocr_vl": {"enabled": False, "status": "not_implemented"},
            "falcon_ocr": {"enabled": False, "status": "not_implemented"},
            "falcon_perception": {"enabled": False, "status": "not_implemented"},
        },
        "warnings": [],
    }


def _empty_value_confidence_evidence() -> dict[str, Any]:
    return {"value": None, "confidence": 0.0, "evidence": []}


def _empty_value_confidence() -> dict[str, Any]:
    return {"value": None, "confidence": 0.0}


def default_extraction(
    invocation: "CLIInvocation", artifacts_so_far: dict[str, Any]
) -> dict[str, Any]:
    company_name = {
        "value": "Stub Vendor Co.",
        "present": True,
        "inferred": False,
        "confidence": 0.9,
        "evidence": ["p1_b1"],
    }
    return {
        "contract_set_version": invocation.contract_set_version,
        "pipeline_version": invocation.pipeline_version,
        "document_id": invocation.document_id,
        "processed_at": _now_iso(),
        "model_runtime": {
            "provider": "stub",
            "model_name": "stub-extractor",
            "model_version": "0.0.0",
            "runtime": "stub",
        },
        "vote_metadata": {
            "voter_id": "stub-voter-1",
            "voter_role": "primary_extractor",
            "consensus_mode": "single_voter_baseline",
        },
        "document_type": {"value": "invoice", "confidence": 0.9},
        "vendor_candidate": {
            "company_name": company_name,
            "address": {
                k: _empty_value_confidence_evidence()
                for k in ("street_1", "street_2", "city", "state", "postal_code", "country")
            },
            "tax_ids": {
                k: _empty_value_confidence_evidence()
                for k in ("ein", "state_tax_id", "vat_id", "other_tax_id")
            },
            "website": _empty_value_confidence_evidence(),
            "phone": _empty_value_confidence_evidence(),
            "email": _empty_value_confidence_evidence(),
        },
        "invoice_header_fields": {
            "invoice_number": _empty_value_confidence_evidence(),
            "invoice_date": _empty_value_confidence_evidence(),
            "total_amount": {
                "value": None,
                "currency": None,
                "confidence": 0.0,
                "evidence": [],
            },
        },
        "extraction_notes": [],
        "warnings": [],
        "status": "success",
    }


def default_routing(
    invocation: "CLIInvocation", artifacts_so_far: dict[str, Any]
) -> dict[str, Any]:
    extraction = artifacts_so_far["edge_extraction_output.json"]
    company_name = extraction["vendor_candidate"]["company_name"]

    present = bool(company_name.get("present"))
    inferred = bool(company_name.get("inferred"))

    if not present and inferred:
        decision = "edge_review_required"
        manual_review_required = True
        review_reason: str | None = "company_name_inferred"
        reasons = ["company_name_inferred"]
    else:
        decision = "edge_accept"
        manual_review_required = False
        review_reason = None
        reasons = []

    return {
        "contract_set_version": invocation.contract_set_version,
        "pipeline_version": invocation.pipeline_version,
        "policy_version": invocation.policy_version,
        "document_id": invocation.document_id,
        "processed_at": _now_iso(),
        "status": "success",
        "decision": decision,
        "consensus_summary": {
            "mode": "single_voter_baseline",
            "agreement_level": "not_applicable",
        },
        "scores": {
            "company_name_score": float(company_name.get("confidence", 0.0)),
            "address_score": 0.0,
            "tax_id_score": 0.0,
            "contact_score": 0.0,
            "overall_vendor_identity_score": float(
                company_name.get("confidence", 0.0)
            ),
        },
        "checks": {
            "company_name_present": present,
            "company_name_inferred": inferred,
            "address_has_minimum_components": False,
            "at_least_one_tax_id_present": False,
            "website_or_email_present": False,
            "post_extraction_spam_gate_passed": True,
        },
        "review_status": {
            "manual_review_required": manual_review_required,
            "review_reason": review_reason,
        },
        "reasons": reasons,
    }


def default_final_payload(
    invocation: "CLIInvocation", artifacts_so_far: dict[str, Any]
) -> dict[str, Any]:
    extraction = artifacts_so_far["edge_extraction_output.json"]
    routing = artifacts_so_far["routing_decision.json"]
    vc = extraction["vendor_candidate"]

    def strip_evidence(field: dict[str, Any]) -> dict[str, Any]:
        return {"value": field["value"], "confidence": field["confidence"]}

    flat_company = {
        "value": vc["company_name"]["value"],
        "present": vc["company_name"]["present"],
        "inferred": vc["company_name"]["inferred"],
        "confidence": vc["company_name"]["confidence"],
    }

    return {
        "contract_set_version": invocation.contract_set_version,
        "pipeline_version": invocation.pipeline_version,
        "document_id": invocation.document_id,
        "processed_at": _now_iso(),
        "document_type": "invoice",
        "vendor_candidate": {
            "company_name": flat_company,
            "address": {k: strip_evidence(v) for k, v in vc["address"].items()},
            "tax_ids": {k: strip_evidence(v) for k, v in vc["tax_ids"].items()},
            "website": strip_evidence(vc["website"]),
            "phone": strip_evidence(vc["phone"]),
            "email": strip_evidence(vc["email"]),
        },
        "review_status": {
            "manual_review_required": routing["review_status"][
                "manual_review_required"
            ],
            "review_reason": routing["review_status"]["review_reason"],
        },
        "quality_summary": {
            "overall_vendor_confidence": routing["scores"][
                "overall_vendor_identity_score"
            ],
            "explicit_name_found": flat_company["present"] and not flat_company["inferred"],
            "consensus_level": "single_voter_baseline",
            "secondary_identifiers_found": [],
        },
        "trace": {
            "source_file": "source.pdf",
            "preprocess_output_file": "preprocess_output.json",
            "edge_extraction_output_file": "edge_extraction_output.json",
            "routing_decision_file": "routing_decision.json",
        },
    }
