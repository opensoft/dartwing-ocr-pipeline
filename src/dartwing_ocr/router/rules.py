"""Deterministic routing rules.

Each rule is a pure function over the parsed input dict plus the already-
computed ``checks`` block. ``apply_rules`` composes them in a fixed order and
returns a ``RuleResult`` describing which rules fired, the priority-ordered
``reasons`` array, and the derived ``decision`` / ``review_status``.

US1 scope: only the green-path / no-forcing case and the affirmative-reason
emission. Forcing rules (missing-name, spam-gate, secondary-floor,
upstream-failure) and the contract-violation path land in US2–US5 via
additions in this same file. New rules MUST bump ``version.POLICY_VERSION``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from dartwing_ocr.router import reasons as R
from dartwing_ocr.router.checks import phone_is_grounded
from dartwing_ocr.router.errors import ContractAssertionError


@dataclass(frozen=True)
class RuleResult:
    decision: str  # "edge_accept" | "edge_review_required"
    status: str    # "success" | "partial" | "failure"
    review_reason: str | None
    manual_review_required: bool
    reasons: list[str] = field(default_factory=list)


def _has_contract_violation(input_dict: dict) -> bool:
    cn = input_dict.get("vendor_candidate", {}).get("company_name", {})
    present = bool(cn.get("present", False))
    inferred = bool(cn.get("inferred", False))
    return (present and inferred) or (not present and not inferred)


def _fires_missing_name(input_dict: dict) -> bool:
    cn = input_dict.get("vendor_candidate", {}).get("company_name", {})
    return bool(cn.get("inferred", False)) or not bool(cn.get("present", False))


def _fires_spam_gate(checks: dict) -> bool:
    return checks.get("post_extraction_spam_gate_passed") is False


def _floor_slot_count(checks: dict, input_dict: dict) -> int:
    return (
        int(checks.get("address_has_minimum_components", False))
        + int(checks.get("at_least_one_tax_id_present", False))
        + int(checks.get("website_or_email_present", False))
        + int(phone_is_grounded(input_dict))
    )


def _fires_secondary_floor(checks: dict, input_dict: dict) -> bool:
    return _floor_slot_count(checks, input_dict) < 2


def _fires_upstream_failure(input_dict: dict) -> bool:
    return input_dict.get("status") == "failure"


def _map_input_status_to_output(input_status: str) -> str:
    if input_status == "success":
        return "success"
    if input_status == "partial":
        return "partial"
    # "failure" inputs: per research Decision 11, map to "partial" so the
    # artifact is still a schema-valid narrative of what the router decided.
    return "partial"


def apply_rules(checks: dict, scores: dict, input_dict: dict) -> RuleResult:
    """Compute the decision, status, review_status, and ordered reasons."""
    input_status = input_dict.get("status", "success")

    # Research Decision 11 + FR-020: on ``input_status == "failure"``, the
    # upstream extractor's structural booleans (present/inferred/evidence)
    # are not trustworthy — the spec is explicit that **no other rules are
    # evaluated**. Emit a defensive review-required with
    # ``upstream_extraction_failed`` as the SOLE forcing reason. Without
    # this short-circuit, a failure input whose extractor emitted null
    # values would trip spam-gate (priority 2) and that reason would
    # preempt upstream-failure (priority 4) in ``review_reason``, directly
    # violating FR-020's mandate that review_reason == "upstream_extraction_failed"
    # on failure inputs.
    if input_status == "failure":
        return RuleResult(
            decision="edge_review_required",
            status="partial",
            review_reason=R.REASON_UPSTREAM_FAILURE,
            manual_review_required=True,
            reasons=[R.REASON_UPSTREAM_FAILURE],
        )

    output_status = _map_input_status_to_output(input_status)
    forcing: list[str] = []

    missing_name = _fires_missing_name(input_dict)
    if missing_name:
        forcing.append(R.REASON_COMPANY_NAME_INFERRED)

    spam = _fires_spam_gate(checks)
    if spam:
        forcing.append(R.REASON_SPAM_GATE)

    floor_deficit = _fires_secondary_floor(checks, input_dict)
    if floor_deficit:
        forcing.append(R.REASON_SECONDARY_FLOOR)

    upstream_fail = _fires_upstream_failure(input_dict)
    if upstream_fail:
        forcing.append(R.REASON_UPSTREAM_FAILURE)

    contract_violation = _has_contract_violation(input_dict)
    if contract_violation:
        # Force partial status and review on any extractor-contract violation.
        output_status = "partial"

    reasons: list[str] = list(forcing)

    # Contract violations (both FR-024 forbidden combos: present==inferred)
    # always trip the missing-name rule above — `_has_contract_violation`
    # and `_fires_missing_name` overlap completely. If a future rule
    # reorder ever decouples them, FR-007 forbids emitting
    # decision="edge_review_required" with review_reason=None, so refuse
    # rather than silently produce a schema-contradictory artifact.
    # Raised as ContractAssertionError so the CLI maps it to exit 3
    # ("internal error — code and frozen contract have drifted"), matching
    # the class the schema-validator path uses in ``artifact.py``.
    if contract_violation and not forcing:
        raise ContractAssertionError(
            "invariant broken: contract violation without any forcing rule "
            "would produce decision='edge_review_required' with "
            "review_reason=None, violating FR-007"
        )

    if forcing:
        review_reason = forcing[0]
        decision = "edge_review_required"
        manual_review_required = True
    else:
        review_reason = None
        decision = "edge_accept"
        manual_review_required = False
        # Affirmative reasons, in the pinned emission order.
        if not missing_name:
            reasons.append(R.AFFIRMATIVE_NAME_EXPLICIT)
        if not spam:
            reasons.append(R.AFFIRMATIVE_SPAM_GATE_PASSED)
        if not floor_deficit:
            reasons.append(R.AFFIRMATIVE_SECONDARY_FLOOR_MET)
        if not upstream_fail:
            reasons.append(R.AFFIRMATIVE_UPSTREAM_OK)

    if input_status == "partial":
        reasons.append(R.INFORMATIONAL_UPSTREAM_PARTIAL)

    if contract_violation:
        reasons.append(R.INFORMATIONAL_CONTRACT_VIOLATION_PRESENT_INFERRED_BOTH_TRUE)

    # Re-sort to canonical FR-015 emission order to guard against any future
    # rule additions violating the priority contract.
    reasons = R.sort_reasons(reasons)

    return RuleResult(
        decision=decision,
        status=output_status,
        review_reason=review_reason,
        manual_review_required=manual_review_required,
        reasons=reasons,
    )
