"""Cross-input invariant checks (data-model.md §Cross-input invariant table, US6).

Checks run in order; the first failure wins and raises a specific
`InputRejectedError` subclass.
"""

from __future__ import annotations

from pathlib import Path

from ledgerlinc_ocr.assembler.errors import (
    ContractDriftError,
    DocumentIdMismatchError,
    InputMissingError,
    RoutingContradictionError,
)
from ledgerlinc_ocr.assembler.io import load_json, validate_input

EXTRACTOR_FILENAME = "edge_extraction_output.json"
ROUTING_FILENAME = "routing_decision.json"
CONTRACT_SET_VERSION = "1.0.0"


def check_inputs_exist(folder: Path) -> tuple[Path, Path]:
    extractor_path = folder / EXTRACTOR_FILENAME
    routing_path = folder / ROUTING_FILENAME
    missing = []
    if not extractor_path.is_file():
        missing.append(EXTRACTOR_FILENAME)
    if not routing_path.is_file():
        missing.append(ROUTING_FILENAME)
    if missing:
        raise InputMissingError(
            f"missing input file(s): {', '.join(missing)}"
        )
    return extractor_path, routing_path


def check_inputs_readable(folder: Path) -> tuple[dict, dict]:
    extractor_path, routing_path = check_inputs_exist(folder)
    extractor = load_json(extractor_path, input_name="edge_extraction_output")
    routing = load_json(routing_path, input_name="routing_decision")
    return extractor, routing


def check_schemas_valid(extractor: dict, routing: dict) -> None:
    validate_input(extractor, "edge_extraction_output", input_name="edge_extraction_output")
    validate_input(routing, "routing_decision", input_name="routing_decision")


def check_contract_versions(extractor: dict, routing: dict) -> None:
    ext_v = extractor.get("contract_set_version")
    rt_v = routing.get("contract_set_version")
    if ext_v != CONTRACT_SET_VERSION or rt_v != CONTRACT_SET_VERSION:
        raise ContractDriftError(
            f"contract_set_version must be {CONTRACT_SET_VERSION!r}; "
            f"got extractor={ext_v!r}, routing={rt_v!r}"
        )


def check_document_ids_match(extractor: dict, routing: dict) -> str:
    ext_id = extractor.get("document_id")
    rt_id = routing.get("document_id")
    if ext_id != rt_id:
        raise DocumentIdMismatchError(
            f"document_id mismatch: extractor={ext_id!r}, routing={rt_id!r}"
        )
    return ext_id


def check_routing_internal_consistency(routing: dict) -> None:
    """FR-016 / research Decision 9 — four forbidden combinations."""
    decision = routing["decision"]
    review = routing["review_status"]
    mrr = review["manual_review_required"]
    reason = review["review_reason"]

    if decision == "edge_accept" and mrr is True:
        raise RoutingContradictionError(
            "routing contradiction: decision=edge_accept but review_status.manual_review_required=true"
        )
    if decision == "edge_accept" and reason is not None:
        raise RoutingContradictionError(
            f"routing contradiction: decision=edge_accept but review_status.review_reason={reason!r}"
        )
    if decision == "edge_review_required" and mrr is False:
        raise RoutingContradictionError(
            "routing contradiction: decision=edge_review_required but review_status.manual_review_required=false"
        )
    if decision == "edge_review_required" and reason is None:
        raise RoutingContradictionError(
            "routing contradiction: decision=edge_review_required but review_status.review_reason=null"
        )
