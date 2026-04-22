"""Pass-gate logic — vendor identity, review routing, overall (§FR-008/009/010)."""

from __future__ import annotations

from dataclasses import dataclass

from ledgerlinc_ocr.evaluator.compare import FieldResult
from ledgerlinc_ocr.evaluator.scoring import (
    GATE_EPSILON,
    GATE_THRESHOLD,
    ResultLabel,
)


@dataclass(frozen=True, slots=True)
class DocumentPassFail:
    vendor_identity_passed: bool
    review_routing_passed: bool
    overall_passed: bool


def _results_by_name(field_results: tuple[FieldResult, ...]) -> dict[str, FieldResult]:
    return {fr.field_name: fr for fr in field_results}


def _is_match(fr: FieldResult | None) -> bool:
    return fr is not None and fr.result is ResultLabel.MATCH


def _is_match_or_partial(fr: FieldResult | None) -> bool:
    return fr is not None and fr.result in (
        ResultLabel.MATCH,
        ResultLabel.PARTIAL_MATCH,
    )


def _agrees(fr: FieldResult | None) -> bool:
    """MATCH or NOT_APPLICABLE — both mean expected and actual agree."""
    return fr is not None and fr.result in (
        ResultLabel.MATCH,
        ResultLabel.NOT_APPLICABLE,
    )


def vendor_identity_passed(field_results: tuple[FieldResult, ...]) -> bool:
    """FR-008 (Q3 clarification): `company_name.value` MATCH or acceptable
    PARTIAL_MATCH, `company_name.present` and `company_name.inferred` MATCH,
    and at least 2 of 5 secondary-identifier slots hold.

    Slot definitions:
    - **address slot** = `address.city` AND `address.state` AND `address.postal_code`
      each MATCH or acceptable PARTIAL_MATCH (`street_1`/`street_2`/`country`
      excluded from the slot)
    - **tax-ID slot** = at least one of the four `tax_ids.*` sub-fields is strict
      MATCH (tax IDs never PARTIAL_MATCH per FR-006)
    - **website / phone / email slots** = that field MATCH or acceptable
      PARTIAL_MATCH
    """
    results = _results_by_name(field_results)
    if not _is_match_or_partial(results.get("company_name.value")):
        return False
    if not _is_match(results.get("company_name.present")):
        return False
    if not _is_match(results.get("company_name.inferred")):
        return False
    slots_matched = 0
    if (
        _is_match_or_partial(results.get("address.city"))
        and _is_match_or_partial(results.get("address.state"))
        and _is_match_or_partial(results.get("address.postal_code"))
    ):
        slots_matched += 1
    if any(
        _is_match(results.get(name))
        for name in (
            "tax_ids.ein",
            "tax_ids.state_tax_id",
            "tax_ids.vat_id",
            "tax_ids.other_tax_id",
        )
    ):
        slots_matched += 1
    if _is_match_or_partial(results.get("website")):
        slots_matched += 1
    if _is_match_or_partial(results.get("phone")):
        slots_matched += 1
    if _is_match_or_partial(results.get("email")):
        slots_matched += 1
    return slots_matched >= 2


def review_routing_passed(
    field_results: tuple[FieldResult, ...], *, missing_name: bool = False
) -> bool:
    """FR-009 + FR-012: manual_review_required MATCH AND review_reason agrees.

    `review_reason` legitimately null on both sides (expected and actual null when
    no review is required) counts as agreement.

    When `missing_name=True`, FR-012 additionally requires the prediction to
    satisfy all four missing-name invariants — `company_name.present == False`,
    `company_name.inferred == True`, `manual_review_required == True`,
    `review_reason == "company_name_inferred"` — checked against the prediction
    (`actual`) side of each FieldResult, not against `match` equality alone.
    """
    results = _results_by_name(field_results)
    base = _is_match(results.get("manual_review_required")) and _agrees(
        results.get("review_reason")
    )
    if not base:
        return False
    if not missing_name:
        return True
    # FR-012 invariants — inspect the prediction (`actual`) values directly.
    present = results.get("company_name.present")
    inferred = results.get("company_name.inferred")
    mrr = results.get("manual_review_required")
    reason = results.get("review_reason")
    if present is None or present.actual is not False:
        return False
    if inferred is None or inferred.actual is not True:
        return False
    if mrr is None or mrr.actual is not True:
        return False
    if reason is None or reason.actual != "company_name_inferred":
        return False
    return True


def overall_passed(
    vendor_identity_ok: bool, review_routing_ok: bool, document_score: float
) -> bool:
    """FR-010: all three conditions must hold; FR-018 epsilon-tolerant threshold."""
    if not vendor_identity_ok or not review_routing_ok:
        return False
    return (document_score + GATE_EPSILON) >= GATE_THRESHOLD
