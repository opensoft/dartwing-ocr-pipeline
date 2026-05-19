"""Feature 021 / T027 / FR-026 / R-021.11: CPU-safe promotion-decision
synchronization contract test.

The Promotion Decision is recorded in TWO places (per FR-026):

1. **Authoritative**: `specs/020-vendor-evidence-gate/quickstart.md`
   Appendix B `### Promotion Decision (YYYY-MM-DD)` subsection. This
   is the single source of truth.
2. **Mirror**: `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`
   `## Promotion Decision` section. Operator-facing; ensures a demo
   audience can see the operational posture without leaving the
   runbook.

R-021.11 requires the two media to **agree on the binary `Decision:` literal**
(`stay opt-in` or `promote to default`). This contract test extracts the
`Decision:` line from each file via regex and asserts the two literals
match exactly. Rationale-text agreement is NOT enforced (the mirror is a
summary, not a verbatim copy).

When the Promotion Decision has not yet been recorded (initial landing
state — both files contain `_(placeholder — populate ...)_` for the
Decision field), the test treats both as "unrecorded" and PASSES (the
contract is "both files agree", and they agree on the unrecorded state).

Runs under ``pytest -m 'not gpu'`` (no GPU required).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
APPENDIX_B_PATH = REPO_ROOT / "specs" / "020-vendor-evidence-gate" / "quickstart.md"
RUNBOOK_PATH = REPO_ROOT / "docs" / "stage1-vendor-identity" / "runbook-gpu-mvp-demo.md"

# Match `**Decision**: <value>` (Appendix B's bold-prefixed form) OR
# `Decision: <value>` (runbook's plain form). Both forms permitted because
# the appendix-recording contract bolds the field label but the runbook
# may emit either. Value captures everything until the next newline or
# `(` (for the "_(placeholder — ...)_" sentinel) or `_` (italic marker).
#
# Multi-agent-review MED-2 fix: regex now actually matches both forms (the
# prior pattern only matched bold form, contradicting the docstring above).
# Anchored to start-of-line / start-of-`**` to avoid matching mid-sentence
# `decision:` strings in prose (e.g., "the team's promotion decision:").
_DECISION_RE = re.compile(
    r"^(?:\*\*Decision\*\*|Decision)\s*:\s*([^\n_()]+?)(?:\s*[_(]|\s*$)",
    re.MULTILINE,
)


# Canonical-form normalization: lowercase, strip whitespace and backticks.
# Allows the two files to use different ornamentation (e.g., `stay opt-in`
# vs. **stay opt-in**) without flagging a sync failure.
def _normalize(decision_text: str) -> str:
    text = decision_text.strip().lower()
    text = text.replace("`", "").replace("*", "")
    return text


# The closed set of allowed decision values (FR-026). The "unrecorded"
# state is also valid — both files agree on "no decision yet".
_VALID_DECISIONS = {"stay opt-in", "promote to default"}
_UNRECORDED_MARKERS = {
    "placeholder",
    "tbd",
    "todo",
    "(placeholder",
    "_(placeholder",
    "not yet recorded",
}


def _extract_decision(path: Path) -> str | None:
    """Extract the Decision literal from a markdown file.

    Returns the normalized literal (e.g., "stay opt-in") on a recorded
    decision; returns None for the unrecorded / placeholder state.
    Raises AssertionError if no Decision field is found at all.
    """
    text = path.read_text(encoding="utf-8")
    matches = _DECISION_RE.findall(text)
    if not matches:
        raise AssertionError(
            f"{path}: no `**Decision**: <value>` field found. "
            f"Expected at least one Decision line per FR-026 / R-021.11."
        )
    # If multiple Decision lines exist (e.g., past history + current
    # entry), the CURRENT entry is the last one in document order.
    raw = matches[-1]
    normalized = _normalize(raw)
    # An empty capture means the regex matched `**Decision**: ` followed
    # immediately by a terminator like `_(` or `*(` — i.e., a placeholder
    # / italic-bracketed unrecorded marker on the same line. Treat as None.
    if not normalized:
        return None
    # Treat explicit placeholder / unrecorded markers as None.
    for marker in _UNRECORDED_MARKERS:
        if marker in normalized:
            return None
    return normalized


def test_appendix_b_exists() -> None:
    """Sanity: the Appendix B source file is present."""
    assert APPENDIX_B_PATH.is_file(), (
        f"feature-020 quickstart.md Appendix B file missing at {APPENDIX_B_PATH}; "
        f"this feature 021 contract test requires it to be present."
    )


def test_runbook_exists() -> None:
    """Sanity: the GPU MVP demo runbook is present (created by T023)."""
    assert RUNBOOK_PATH.is_file(), (
        f"feature-021 runbook missing at {RUNBOOK_PATH}; "
        f"T023 (runbook authoring) must land before T027 can verify sync."
    )


def test_promotion_decision_appendix_b_and_runbook_agree() -> None:
    """R-021.11: Appendix B (authoritative) and runbook (mirror) MUST
    agree on the binary Decision literal."""
    appendix_b_decision = _extract_decision(APPENDIX_B_PATH)
    runbook_decision = _extract_decision(RUNBOOK_PATH)

    assert appendix_b_decision == runbook_decision, (
        f"Promotion Decision sync violation (R-021.11):\n"
        f"  Appendix B: {appendix_b_decision!r}\n"
        f"  Runbook:    {runbook_decision!r}\n"
        f"The two files MUST agree on the binary Decision literal. "
        f"Update one or the other to match — the Appendix B subsection is "
        f"the authoritative source; the runbook section is the mirror."
    )

    # When a non-None decision is recorded, it MUST be one of the FR-026
    # binary literals.
    if appendix_b_decision is not None:
        assert appendix_b_decision in _VALID_DECISIONS, (
            f"Decision literal not in FR-026 allowed set "
            f"{_VALID_DECISIONS!r}; got {appendix_b_decision!r}. "
            f"Allowed binary values are 'stay opt-in' or 'promote to default'."
        )
