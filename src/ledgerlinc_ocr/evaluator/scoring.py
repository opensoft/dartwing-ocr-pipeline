"""Scoring constants, ComparisonSummary, and document-score helpers (§FR-007/§FR-011)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ResultLabel(str, Enum):
    MATCH = "match"
    PARTIAL_MATCH = "partial_match"
    MISMATCH = "mismatch"
    MISSING_PREDICTION = "missing_prediction"
    UNEXPECTED_PREDICTION = "unexpected_prediction"
    NOT_APPLICABLE = "not_applicable"


RESULT_VALUES: dict[ResultLabel, float] = {
    ResultLabel.MATCH: 1.0,
    ResultLabel.PARTIAL_MATCH: 0.5,
    ResultLabel.MISMATCH: 0.0,
    ResultLabel.MISSING_PREDICTION: 0.0,
    ResultLabel.UNEXPECTED_PREDICTION: 0.0,
}

SCORED_FIELDS: tuple[str, ...] = (
    "company_name.value",
    "company_name.present",
    "company_name.inferred",
    "address.street_1",
    "address.street_2",
    "address.city",
    "address.state",
    "address.postal_code",
    "address.country",
    "tax_ids.ein",
    "tax_ids.state_tax_id",
    "tax_ids.vat_id",
    "tax_ids.other_tax_id",
    "website",
    "phone",
    "email",
    "manual_review_required",
    "review_reason",
)

FIELD_WEIGHTS: dict[str, int] = {
    "company_name.value": 20,
    "company_name.present": 8,
    "company_name.inferred": 8,
    "address.street_1": 8,
    "address.street_2": 1,
    "address.city": 4,
    "address.state": 3,
    "address.postal_code": 3,
    "address.country": 1,
    "tax_ids.ein": 8,
    "tax_ids.state_tax_id": 3,
    "tax_ids.vat_id": 3,
    "tax_ids.other_tax_id": 2,
    "website": 6,
    "phone": 4,
    "email": 6,
    "manual_review_required": 8,
    "review_reason": 4,
}

CONTRACT_SET_VERSION: str = "1.0.0"
GATE_THRESHOLD: float = 0.85
# Edge case "Weighted document_score = 0.849999…" in spec.md: compare with
# inclusive `>=` + small epsilon so float rounding can't falsely fail a doc
# whose weighted math lands a few ulps below 0.85.
GATE_EPSILON: float = 1e-9

assert set(FIELD_WEIGHTS) == set(SCORED_FIELDS), (
    "FIELD_WEIGHTS keys must match SCORED_FIELDS"
)
assert sum(FIELD_WEIGHTS.values()) == 100, (
    f"FIELD_WEIGHTS must sum to 100 (got {sum(FIELD_WEIGHTS.values())})"
)
assert len(SCORED_FIELDS) == 18, (
    f"SCORED_FIELDS must have exactly 18 entries (got {len(SCORED_FIELDS)})"
)


@dataclass(frozen=True, slots=True)
class ComparisonSummary:
    """Mirrors comparison_summary in evaluation_document.schema.json (Q1 clarification: no partial_match_count)."""

    applicable_field_count: int
    matched_field_count: int
    mismatched_field_count: int
    missing_prediction_count: int
    unexpected_prediction_count: int
    field_accuracy: float

    def __post_init__(self) -> None:
        applicable = self.applicable_field_count
        tallied = (
            self.matched_field_count
            + self.mismatched_field_count
            + self.missing_prediction_count
            + self.unexpected_prediction_count
        )
        if tallied > applicable:
            raise ValueError(
                f"ComparisonSummary counts exceed applicable_field_count: "
                f"{tallied} > {applicable}"
            )
        partial_count = applicable - tallied
        if applicable > 0:
            expected_accuracy = round(
                (self.matched_field_count + 0.5 * partial_count) / applicable, 6
            )
        else:
            expected_accuracy = 0.0
        if round(self.field_accuracy, 6) != expected_accuracy:
            raise ValueError(
                f"field_accuracy={self.field_accuracy} does not match derived "
                f"value {expected_accuracy} "
                f"(matched={self.matched_field_count}, partial={partial_count}, "
                f"applicable={applicable})"
            )


def build_comparison_summary(field_results: "tuple[FieldResult, ...]") -> ComparisonSummary:  # noqa: F821
    """Build a ComparisonSummary from per-field results per FR-011."""
    from ledgerlinc_ocr.evaluator.compare import FieldResult  # noqa: F401

    applicable = 0
    matched = 0
    mismatched = 0
    missing_pred = 0
    unexpected_pred = 0
    partial = 0
    for fr in field_results:
        if fr.result is ResultLabel.NOT_APPLICABLE:
            continue
        applicable += 1
        if fr.result is ResultLabel.MATCH:
            matched += 1
        elif fr.result is ResultLabel.MISMATCH:
            mismatched += 1
        elif fr.result is ResultLabel.MISSING_PREDICTION:
            missing_pred += 1
        elif fr.result is ResultLabel.UNEXPECTED_PREDICTION:
            unexpected_pred += 1
        elif fr.result is ResultLabel.PARTIAL_MATCH:
            partial += 1
    if applicable > 0:
        accuracy = round((matched + 0.5 * partial) / applicable, 6)
    else:
        accuracy = 0.0
    return ComparisonSummary(
        applicable_field_count=applicable,
        matched_field_count=matched,
        mismatched_field_count=mismatched,
        missing_prediction_count=missing_pred,
        unexpected_prediction_count=unexpected_pred,
        field_accuracy=accuracy,
    )


def compute_document_score(field_results: "tuple[FieldResult, ...]") -> float:  # noqa: F821
    """Weighted document score per FR-007. NOT_APPLICABLE excluded from both numerator and denominator."""
    numerator = 0.0
    denominator = 0
    for fr in field_results:
        if fr.result is ResultLabel.NOT_APPLICABLE:
            continue
        weight = FIELD_WEIGHTS[fr.field_name]
        numerator += RESULT_VALUES[fr.result] * weight
        denominator += weight
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)
