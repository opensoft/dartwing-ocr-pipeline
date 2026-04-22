"""T040 [US6] — FR-016 routing-internal consistency (Decision 9 enumeration)."""

from __future__ import annotations

import pytest

from ledgerlinc_ocr.assembler.errors import RoutingContradictionError
from ledgerlinc_ocr.assembler.validation import check_routing_internal_consistency


def _routing(decision: str, mrr: bool, reason: str | None) -> dict:
    return {
        "decision": decision,
        "review_status": {"manual_review_required": mrr, "review_reason": reason},
    }


@pytest.mark.parametrize("decision,mrr,reason", [
    ("edge_accept", True, None),               # mrr contradicts accept
    ("edge_accept", False, "anything"),        # reason contradicts accept
    ("edge_review_required", False, None),     # mrr contradicts review
    ("edge_review_required", True, None),      # missing reason when review
])
def test_forbidden_combinations_raise(decision: str, mrr: bool, reason: str | None):
    with pytest.raises(RoutingContradictionError):
        check_routing_internal_consistency(_routing(decision, mrr, reason))


@pytest.mark.parametrize("decision,mrr,reason", [
    ("edge_accept", False, None),
    ("edge_review_required", True, "company_name_inferred"),
    ("edge_review_required", True, "post_extraction_spam_gate_failed"),
])
def test_valid_combinations_pass(decision: str, mrr: bool, reason: str | None):
    check_routing_internal_consistency(_routing(decision, mrr, reason))
