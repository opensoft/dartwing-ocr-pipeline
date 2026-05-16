"""Cross-input invariant checks (data-model.md §Cross-input invariant table, US6).

Checks run in order; the first failure wins and raises a specific
`InputRejectedError` subclass.
"""

from __future__ import annotations

from pathlib import Path

from dartwing_ocr.contract_versions import (
    ContractVersionError,
    require_matching_contract_version,
    require_stage1_contract_version,
)
from dartwing_ocr.assembler.errors import (
    ContractDriftError,
    DocumentIdMismatchError,
    InputMissingError,
    InputSchemaInvalidError,
    RoutingContradictionError,
)
from dartwing_ocr.assembler.io import load_json, validate_input

EXTRACTOR_FILENAME = "edge_extraction_output.json"
ROUTING_FILENAME = "routing_decision.json"


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


def check_schemas_valid(
    extractor: dict,
    routing: dict,
    *,
    contract_set_version: str,
) -> None:
    validate_input(
        extractor,
        "edge_extraction_output",
        input_name="edge_extraction_output",
        contract_set_version=contract_set_version,
    )
    validate_input(
        routing,
        "routing_decision",
        input_name="routing_decision",
        contract_set_version=contract_set_version,
    )


def check_contract_versions(
    extractor: dict,
    routing: dict,
    *,
    contract_set_version: str | None = None,
) -> str:
    try:
        ext_v = require_stage1_contract_version(
            extractor.get("contract_set_version"),
            artifact_label="edge_extraction_output.json",
        )
        rt_v = require_stage1_contract_version(
            routing.get("contract_set_version"),
            artifact_label="routing_decision.json",
        )
        if ext_v != rt_v:
            raise ContractVersionError(
                "input contract_set_version values must match; "
                f"got extractor={ext_v!r}, routing={rt_v!r}"
            )
        return require_matching_contract_version(
            found=ext_v,
            expected=contract_set_version,
            artifact_label="assembler inputs",
        )
    except ContractVersionError as exc:
        raise ContractDriftError(str(exc)) from exc


def check_document_ids_match(extractor: dict, routing: dict) -> str:
    ext_id = extractor.get("document_id")
    rt_id = routing.get("document_id")
    if ext_id != rt_id:
        raise DocumentIdMismatchError(
            f"document_id mismatch: extractor={ext_id!r}, routing={rt_id!r}"
        )
    return ext_id


def _reason_absent(reason: object) -> bool:
    # H4: routing must explicitly spell out *why* a review is required. Empty
    # or whitespace-only strings carry no policy information and would defeat
    # downstream reason-based routing.
    if reason is None:
        return True
    if isinstance(reason, str) and not reason.strip():
        return True
    return False


def check_routing_internal_consistency(routing: dict) -> None:
    """FR-016 / research Decision 9 — forbidden `decision` × `review_status` combinations.

    Preconditions: `routing` has already been validated against
    `routing_decision.schema.json`. If this function is called out of order
    with an un-validated dict, missing required keys surface as
    ``InputSchemaInvalidError`` (exit 2, kind ``schema_invalid_input``) rather
    than leaking ``KeyError`` to the CLI's ``Exception`` arm as an
    ``unexpected`` / exit 1 failure.
    """
    try:
        decision = routing["decision"]
        review = routing["review_status"]
        mrr = review["manual_review_required"]
        reason = review["review_reason"]
    except (KeyError, TypeError) as exc:
        raise InputSchemaInvalidError(
            f"routing_decision missing required key for consistency check: {exc}"
        ) from exc

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
    if decision == "edge_review_required" and _reason_absent(reason):
        raise RoutingContradictionError(
            f"routing contradiction: decision=edge_review_required but "
            f"review_status.review_reason is absent (got {reason!r})"
        )
