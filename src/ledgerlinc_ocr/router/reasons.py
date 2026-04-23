"""Canonical reason strings and the FR-015 priority-ordering helper.

All strings defined here are **part of ``policy_version``**. Adding, removing,
or renaming any of them MUST bump ``version.POLICY_VERSION`` per FR-005 /
SC-010.

Three classes of reasons are emitted by the router:

1. **Forcing** — drive ``review_status.review_reason`` when a rule fires.
   Priority order (highest wins) per FR-015:
   1. missing-name      (``"company_name_inferred"``)
   2. spam-gate         (``"post_extraction_spam_gate_failed"``)
   3. secondary floor   (``"secondary_identifiers_insufficient"``)
   4. upstream failure  (``"upstream_extraction_failed"``)

2. **Affirmative** — appear only in ``reasons`` on ``edge_accept`` decisions,
   naming the conditions met (FR-016). Research Decision 9 pins the spellings.

3. **Informational** — appear only in ``reasons``, never supply
   ``review_reason``. Research Decision 10 pins the spellings.

The ``reasons`` array is emitted in forcing (priority 1→4) order, then
affirmatives, then informationals, so byte-identity holds across reruns.
"""
from __future__ import annotations

# -- Forcing reasons (priority 1→4) -----------------------------------------
REASON_COMPANY_NAME_INFERRED: str = "company_name_inferred"
REASON_SPAM_GATE: str = "post_extraction_spam_gate_failed"
REASON_SECONDARY_FLOOR: str = "secondary_identifiers_insufficient"
REASON_UPSTREAM_FAILURE: str = "upstream_extraction_failed"

FORCING_PRIORITY: tuple[str, ...] = (
    REASON_COMPANY_NAME_INFERRED,
    REASON_SPAM_GATE,
    REASON_SECONDARY_FLOOR,
    REASON_UPSTREAM_FAILURE,
)
"""Tuple pinning the priority order; index 0 is highest priority."""

# -- Affirmative reasons (edge_accept traceability) -------------------------
AFFIRMATIVE_NAME_EXPLICIT: str = "company_name_explicit"
AFFIRMATIVE_SPAM_GATE_PASSED: str = "spam_gate_passed"
AFFIRMATIVE_SECONDARY_FLOOR_MET: str = "secondary_identifier_floor_met"
AFFIRMATIVE_UPSTREAM_OK: str = "upstream_extraction_ok"

AFFIRMATIVE_ORDER: tuple[str, ...] = (
    AFFIRMATIVE_NAME_EXPLICIT,
    AFFIRMATIVE_SPAM_GATE_PASSED,
    AFFIRMATIVE_SECONDARY_FLOOR_MET,
    AFFIRMATIVE_UPSTREAM_OK,
)
"""Deterministic emission order for affirmative reasons on ``edge_accept``."""

# -- Informational reasons (always in reasons, never review_reason) ---------
INFORMATIONAL_UPSTREAM_PARTIAL: str = "upstream_status_partial"
INFORMATIONAL_CONTRACT_VIOLATION_PRESENT_INFERRED_BOTH_TRUE: str = (
    "contract_violation_detected"
)
INFORMATIONAL_CONTRACT_VIOLATION_PRESENT_INFERRED_BOTH_FALSE: str = (
    "contract_violation_detected"
)
# Both forbidden combos share one canonical informational string per the
# CLI contract. The two module-level aliases keep call sites self-documenting
# about WHICH invariant was violated without splitting the policy vocabulary.

INFORMATIONAL_ORDER: tuple[str, ...] = (
    "upstream_status_partial",
    "contract_violation_detected",
)
"""Deterministic emission order for informational reasons."""


def sort_reasons(reasons: list[str]) -> list[str]:
    """Return ``reasons`` reordered to the pinned FR-015 emission order.

    Forcing reasons first (priority 1→4), then affirmatives, then
    informationals. Unknown strings preserve their relative order AFTER all
    pinned classes — this lets a caller append a future informational string
    without the ordering silently shifting pinned entries around.
    """
    forcing_rank = {s: i for i, s in enumerate(FORCING_PRIORITY)}
    affirmative_rank = {s: i for i, s in enumerate(AFFIRMATIVE_ORDER)}
    informational_rank = {s: i for i, s in enumerate(INFORMATIONAL_ORDER)}

    def bucket(s: str) -> tuple[int, int, int]:
        if s in forcing_rank:
            return (0, forcing_rank[s], 0)
        if s in affirmative_rank:
            return (1, affirmative_rank[s], 0)
        if s in informational_rank:
            return (2, informational_rank[s], 0)
        return (3, 0, reasons.index(s))

    return sorted(reasons, key=bucket)
