"""Field comparison — FieldResult dataclass + comparators per spec §FR-004."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ledgerlinc_ocr.evaluator.normalize import classify_value
from ledgerlinc_ocr.evaluator.scoring import ResultLabel, SCORED_FIELDS

_BOOLEAN_FIELDS: frozenset[str] = frozenset(
    {"company_name.present", "company_name.inferred", "manual_review_required"}
)
_TAX_ID_FIELDS: frozenset[str] = frozenset(
    {
        "tax_ids.ein",
        "tax_ids.state_tax_id",
        "tax_ids.vat_id",
        "tax_ids.other_tax_id",
    }
)
# FR-006: PARTIAL_MATCH is permitted only on company_name.value, address.street_1,
# address.street_2, address.postal_code, and phone. All other SCORED_FIELDS must
# reject PARTIAL_MATCH. These are the non-boolean / non-tax-id / non-review_reason
# fields that additionally require exact match.
_EXACT_ONLY_FIELDS: frozenset[str] = frozenset(
    {"address.city", "address.state", "address.country", "website", "email"}
)
_NO_PARTIAL_FIELDS: frozenset[str] = (
    _BOOLEAN_FIELDS | _TAX_ID_FIELDS | _EXACT_ONLY_FIELDS | frozenset({"review_reason"})
)


@dataclass(frozen=True, slots=True)
class FieldResult:
    field_name: str
    expected: Any
    actual: Any
    result: ResultLabel

    def __post_init__(self) -> None:
        if self.field_name not in SCORED_FIELDS:
            raise ValueError(f"field_name {self.field_name!r} is not in SCORED_FIELDS")
        if not isinstance(self.result, ResultLabel):
            raise TypeError(f"result must be a ResultLabel, got {type(self.result)!r}")
        if self.expected is None and self.actual is None:
            if self.result is not ResultLabel.NOT_APPLICABLE:
                raise ValueError(
                    f"{self.field_name}: both sides null requires NOT_APPLICABLE, got {self.result!r}"
                )
            return
        if self.expected is not None and self.actual is None:
            if self.result is not ResultLabel.MISSING_PREDICTION:
                raise ValueError(
                    f"{self.field_name}: expected non-null, actual null requires "
                    f"MISSING_PREDICTION, got {self.result!r}"
                )
            return
        if self.expected is None and self.actual is not None:
            if self.result is not ResultLabel.UNEXPECTED_PREDICTION:
                raise ValueError(
                    f"{self.field_name}: expected null, actual non-null requires "
                    f"UNEXPECTED_PREDICTION, got {self.result!r}"
                )
            return
        if (
            self.result is ResultLabel.PARTIAL_MATCH
            and self.field_name in _NO_PARTIAL_FIELDS
        ):
            raise ValueError(
                f"{self.field_name}: PARTIAL_MATCH not permitted on this field per FR-006"
            )


def extract_field(payload: dict[str, Any] | None, dotted_name: str) -> Any:
    """Walk a dotted path into `payload`, returning None if any segment is absent/None."""
    if payload is None:
        return None
    current: Any = payload
    for part in dotted_name.split("."):
        if not isinstance(current, dict):
            return None
        if part not in current:
            return None
        current = current[part]
    return current


def build_expected_view(expected: dict[str, Any]) -> dict[str, Any]:
    """Flatten expected.json into a SCORED_FIELDS-compatible nested view."""
    v = expected["expected_vendor_candidate"]
    r = expected["expected_review"]
    return {
        "company_name": {
            "value": v["company_name"]["value"],
            "present": v["company_name"]["present"],
            "inferred": v["company_name"]["inferred"],
        },
        "address": {
            "street_1": v["address"]["street_1"],
            "street_2": v["address"]["street_2"],
            "city": v["address"]["city"],
            "state": v["address"]["state"],
            "postal_code": v["address"]["postal_code"],
            "country": v["address"]["country"],
        },
        "tax_ids": {
            "ein": v["tax_ids"]["ein"],
            "state_tax_id": v["tax_ids"]["state_tax_id"],
            "vat_id": v["tax_ids"]["vat_id"],
            "other_tax_id": v["tax_ids"]["other_tax_id"],
        },
        "website": v["website"],
        "phone": v["phone"],
        "email": v["email"],
        "manual_review_required": r["manual_review_required"],
        "review_reason": r["review_reason"],
    }


def build_actual_view(payload: dict[str, Any]) -> dict[str, Any]:
    """Flatten final_structured_payload.json into the same SCORED_FIELDS view.

    Unwraps `{value, confidence}` wrappers on address, tax_ids, website, phone, email.
    """
    vc = payload["vendor_candidate"]
    rs = payload["review_status"]
    cn = vc["company_name"]
    return {
        "company_name": {
            "value": cn["value"],
            "present": cn["present"],
            "inferred": cn["inferred"],
        },
        "address": {
            "street_1": vc["address"]["street_1"]["value"],
            "street_2": vc["address"]["street_2"]["value"],
            "city": vc["address"]["city"]["value"],
            "state": vc["address"]["state"]["value"],
            "postal_code": vc["address"]["postal_code"]["value"],
            "country": vc["address"]["country"]["value"],
        },
        "tax_ids": {
            "ein": vc["tax_ids"]["ein"]["value"],
            "state_tax_id": vc["tax_ids"]["state_tax_id"]["value"],
            "vat_id": vc["tax_ids"]["vat_id"]["value"],
            "other_tax_id": vc["tax_ids"]["other_tax_id"]["value"],
        },
        "website": vc["website"]["value"],
        "phone": vc["phone"]["value"],
        "email": vc["email"]["value"],
        "manual_review_required": rs["manual_review_required"],
        "review_reason": rs["review_reason"],
    }


def compare_field(
    field_name: str,
    expected: Any,
    actual: Any,
    *,
    normalized_equal: Callable[[str, Any, Any], bool] | None = None,
) -> FieldResult:
    """Baseline comparator per FR-004, extended by US3's partial-match rubric.

    Null-handling returns NOT_APPLICABLE / MISSING_PREDICTION / UNEXPECTED_PREDICTION.
    For both-non-null, delegates to `normalize.classify_value`, which returns one
    of MATCH / PARTIAL_MATCH / MISMATCH. The legacy `normalized_equal` kwarg is
    accepted for back-compat but ignored — full rubric lives in `normalize.py`.
    """
    _ = normalized_equal  # retained for back-compat; unused.
    if expected is None and actual is None:
        return FieldResult(
            field_name=field_name,
            expected=None,
            actual=None,
            result=ResultLabel.NOT_APPLICABLE,
        )
    if expected is not None and actual is None:
        return FieldResult(
            field_name=field_name,
            expected=expected,
            actual=None,
            result=ResultLabel.MISSING_PREDICTION,
        )
    if expected is None and actual is not None:
        return FieldResult(
            field_name=field_name,
            expected=None,
            actual=actual,
            result=ResultLabel.UNEXPECTED_PREDICTION,
        )
    label = classify_value(field_name, expected, actual)
    return FieldResult(
        field_name=field_name,
        expected=expected,
        actual=actual,
        result=label,
    )
