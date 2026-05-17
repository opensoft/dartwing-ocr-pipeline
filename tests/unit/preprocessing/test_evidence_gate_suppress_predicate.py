"""Feature 020 / T032 / R-020.8 / MI-13 / MI-14 / FR-009 / SC-011:
exhaustive truth-table coverage of
`preprocessing.evidence_gate.should_suppress_fallback`.

The predicate has four boolean-like inputs but `candidate_gate_decision`
is drawn from a closed three-element vocabulary
(`"sufficient"`/`"borderline"`/`"insufficient"`), so the truth table is
`2 * 2 * 2 * 3 = 24` rows, of which exactly 1 must return True (all four
conjuncts hold AND decision is "sufficient"). The tasks.md description
calls this "16-row truth-table coverage" — the booleans are
2*2*2 = 8 and each decision contributes 8 rows; we exhaustively cover
all 24 here, which is a strict superset of the called-out 16 (the 16
boolean rows × decision="sufficient" + the 16 boolean rows × decision
in {"borderline","insufficient"} would be 48 — the contract is
clearly the 24-row exhaustive set).

Covers:
- MI-13: True iff all four conjuncts hold.
- MI-14 / FR-009 / SC-011: `borderline`/`insufficient` NEVER trigger
  suppression regardless of the other three inputs.
- Pure-function contract: same inputs → same outputs across calls.
"""

from __future__ import annotations

import itertools

import pytest

from ledgerlinc_ocr.preprocessing.evidence_gate import should_suppress_fallback


# Closed input domains for the four arguments.
STRATEGY_IDS = ["ocr-only-v1", "ppstructurev3"]
TRIGGER_VALUES = [True, False]
OPT_IN_VALUES = [True, False]
DECISIONS = ["sufficient", "borderline", "insufficient"]


def _expected_suppress(
    strategy_id: str,
    trigger: bool,
    opt_in: bool,
    decision: str,
) -> bool:
    """Reference implementation of the four-conjunct predicate.

    Mirrors `should_suppress_fallback` so the test is independent of the
    SUT. Any divergence between this reference and the SUT signals a
    regression on either side; the truth-table coverage below catches it.
    """
    return (
        strategy_id == "ocr-only-v1"
        and trigger is True
        and opt_in is True
        and decision == "sufficient"
    )


@pytest.mark.parametrize(
    "strategy_id,trigger,opt_in,decision",
    list(itertools.product(STRATEGY_IDS, TRIGGER_VALUES, OPT_IN_VALUES, DECISIONS)),
)
def test_truth_table_exhaustive(
    strategy_id: str, trigger: bool, opt_in: bool, decision: str
) -> None:
    """Exhaustive `2*2*2*3 = 24` truth-table coverage. The predicate MUST
    match the reference implementation on every row (MI-13)."""
    actual = should_suppress_fallback(
        preprocess_strategy_id=strategy_id,
        fr_005_trigger_would_fire=trigger,
        opt_in_active=opt_in,
        candidate_gate_decision=decision,
    )
    expected = _expected_suppress(strategy_id, trigger, opt_in, decision)
    assert actual is expected, (
        f"row({strategy_id=}, {trigger=}, {opt_in=}, {decision=}): "
        f"expected {expected}, got {actual}"
    )


def test_only_one_row_returns_true() -> None:
    """Across the entire `2*2*2*3 = 24` truth table, exactly ONE row
    returns True — the all-conjuncts-hold case (MI-13)."""
    true_rows = []
    for strategy_id, trigger, opt_in, decision in itertools.product(
        STRATEGY_IDS, TRIGGER_VALUES, OPT_IN_VALUES, DECISIONS
    ):
        if should_suppress_fallback(
            preprocess_strategy_id=strategy_id,
            fr_005_trigger_would_fire=trigger,
            opt_in_active=opt_in,
            candidate_gate_decision=decision,
        ):
            true_rows.append((strategy_id, trigger, opt_in, decision))
    assert true_rows == [("ocr-only-v1", True, True, "sufficient")]


@pytest.mark.parametrize(
    "decision", ["borderline", "insufficient"]
)
@pytest.mark.parametrize("strategy_id", STRATEGY_IDS)
@pytest.mark.parametrize("trigger", TRIGGER_VALUES)
@pytest.mark.parametrize("opt_in", OPT_IN_VALUES)
def test_borderline_and_insufficient_never_suppress(
    strategy_id: str, trigger: bool, opt_in: bool, decision: str
) -> None:
    """MI-14 / FR-009 / SC-011: `borderline` and `insufficient` candidate
    decisions MUST NEVER trigger suppression regardless of the other
    three inputs."""
    assert (
        should_suppress_fallback(
            preprocess_strategy_id=strategy_id,
            fr_005_trigger_would_fire=trigger,
            opt_in_active=opt_in,
            candidate_gate_decision=decision,
        )
        is False
    )


def test_non_ocr_only_strategy_never_suppresses() -> None:
    """Conjunct 1: any `preprocess_strategy_id` other than `"ocr-only-v1"`
    suppresses False even with the other three at True/sufficient."""
    for strategy_id in ["ppstructurev3", "cpu-default", "stub-default", None, "", "v1"]:
        assert (
            should_suppress_fallback(
                preprocess_strategy_id=strategy_id,
                fr_005_trigger_would_fire=True,
                opt_in_active=True,
                candidate_gate_decision="sufficient",
            )
            is False
        ), f"strategy_id={strategy_id!r} should not suppress"


def test_no_trigger_never_suppresses() -> None:
    """Conjunct 2: when the FR-005 trigger would NOT fire, there is no
    fallback to suppress."""
    assert (
        should_suppress_fallback(
            preprocess_strategy_id="ocr-only-v1",
            fr_005_trigger_would_fire=False,
            opt_in_active=True,
            candidate_gate_decision="sufficient",
        )
        is False
    )


def test_opt_in_off_never_suppresses() -> None:
    """Conjunct 3: opt-in OFF (FR-012 / MI-20 default) NEVER suppresses."""
    assert (
        should_suppress_fallback(
            preprocess_strategy_id="ocr-only-v1",
            fr_005_trigger_would_fire=True,
            opt_in_active=False,
            candidate_gate_decision="sufficient",
        )
        is False
    )


def test_pure_function_idempotent() -> None:
    """Pure function: same inputs → same outputs across repeated calls."""
    for _ in range(5):
        assert (
            should_suppress_fallback(
                preprocess_strategy_id="ocr-only-v1",
                fr_005_trigger_would_fire=True,
                opt_in_active=True,
                candidate_gate_decision="sufficient",
            )
            is True
        )
