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

R-021.11 / `appendix-recording.md §Promotion-decision synchronization
contract` requires the two media to **agree on BOTH**:

1. The binary `Decision:` literal (`stay opt-in` or `promote to default`).
2. The `Gating verdict:` reference (a back-pointer of the form
   `see §Quality-Gate Verdict YYYY-MM-DD (PASS / FAIL / BLOCKED)` per
   appendix-recording.md §Promotion Decision schema).

This contract test extracts both fields from each file via regex and
asserts the pairs match. Rationale-text agreement is NOT enforced (the
mirror is a summary, not a verbatim copy).

When the Promotion Decision has not yet been recorded (initial landing
state — both files contain `_(placeholder — populate ...)_` for the
Decision field), the test treats both as "unrecorded" and PASSES (the
contract is "both files agree", and they agree on the unrecorded state).

**Placeholder-passing is intentional at landing time.** Feature 021's
US6 / T028 records the Promotion Decision AFTER the PR merges, once
the operator has run the four-run GPU benchmark and the team has
reviewed the Appendix A + B evidence. At PR-landing time both files
are in the placeholder state by design (T021 / T026 placed the
skeletons; T022 / T028 will populate them on the workstation
post-merge). This test enforces "both files agree on the same state"
in BOTH directions — both unrecorded, or both recorded with matching
literals. It does NOT enforce "must be recorded" because requiring a
recorded decision pre-merge would be a chicken-and-egg violation of
FR-029 (promotion is an explicit team decision; the PR is the
infrastructure to enable that decision, not the decision itself).

If a future feature wants to require recorded state as a release-gate
check, it should add a SEPARATE test (e.g., `test_promotion_decision_
must_be_recorded.py`) that explicitly asserts not-None on both
extractors — and gate it behind a `RELEASE_GATE=1` env var or similar
so the landing PR is not blocked.

Runs under ``pytest -m 'not gpu'`` (no GPU required).
"""

from __future__ import annotations

import re
from pathlib import Path

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
#
# PR #43 SonarCloud maintainability hardening: alternation is explicitly
# grouped (already was) and the reluctant `+?` quantifier has been
# replaced with a greedy `+` followed by a trailing-context anchor. The
# capture's character class already excludes `_`, `(`, and `\n`, so the
# greedy form stops at exactly the same boundary the lazy form did; the
# only behavioral difference is trailing whitespace, which the
# `_normalize` helper strips downstream. The new form is simpler to
# audit and avoids the "lazy quantifier with flexible-trailing-context"
# pattern Sonar flags.
_DECISION_RE = re.compile(
    r"^(?:\*\*Decision\*\*|Decision)\s*:\s*([^\n_()]+)",
    re.MULTILINE,
)

# Match a `Gating verdict:` line (bold or plain form). The reference value
# is captured as a (date, verdict) tuple drawn from the line — a real
# recorded reference looks like
#   `see §Quality-Gate Verdict 2026-05-19 (PASS) above`
# and contains both a concrete `YYYY-MM-DD` date AND a verdict literal
# from {PASS, FAIL, BLOCKED}. Templated placeholder text (literal
# `YYYY-MM-DD`, or no concrete verdict) returns None.
#
# Multi-agent-review verification round (P2-3): the appendix-recording
# contract requires the mirror to agree on BOTH the decision literal AND
# the gating-verdict reference; the test previously only checked the
# decision. Cross-document references can legitimately use different
# wording (intra-doc anchor in Appendix B vs. inter-doc link in the
# runbook), so the test compares the extracted (date, verdict) pair
# rather than the raw line text.
_GATING_VERDICT_LINE_RE = re.compile(
    r"^(?:\*\*Gating verdict\*\*|Gating verdict)\s*:.*$",
    re.MULTILINE,
)
_RECORDED_VERDICT_REFERENCE_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}).*?\b(PASS|FAIL|BLOCKED)\b"
)
# Match any parenthetical substring; used to scope the placeholder-list
# check below to "inside parens" so trailing FR-027 prose (which contains
# the literal words FAIL and BLOCKED) does NOT poison the unrecorded
# detection. Round-4 fix per agent B's critical false-negative finding.
_PARENTHETICAL_RE = re.compile(r"\(([^)]*)\)")


# Canonical-form normalization: lowercase, strip whitespace and backticks.
# Allows the two files to use different ornamentation (e.g., `stay opt-in`
# vs. **stay opt-in**) without flagging a sync failure.
def _normalize(decision_text: str) -> str:
    text = decision_text.strip().lower()
    text = text.replace("`", "").replace("*", "")
    return text


# The closed set of allowed decision values (FR-026).
#
# Source of truth: ``specs/021-gpu-mvp-promotion/spec.md`` FR-026 (binary
# decision literal: "stay opt-in" or "promote to default") and
# ``specs/021-gpu-mvp-promotion/data-model.md`` §5 (Promotion Decision Record
# entity). If FR-026 ever broadens the vocabulary (e.g., a "demote to opt-in"
# literal is added per the §5 Demotion path subsection), update BOTH the spec
# and this set in the same commit — the LOW-8 review note flagged this as a
# documentation-coupling risk worth surfacing inline.
#
# The "unrecorded" state is also valid — both files agree on "no decision yet".
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


def _extract_gating_verdict(path: Path) -> tuple[str, str] | None:
    """Extract the (date, verdict) reference from a Gating-verdict line.

    Returns a `(YYYY-MM-DD, "PASS"/"FAIL"/"BLOCKED")` tuple on a recorded
    Promotion Decision; returns None for templated / unrecorded state
    (e.g., the line still contains the literal `YYYY-MM-DD` placeholder,
    or no concrete verdict token).

    Compared this way (extracted tuple, not raw line text) so the two
    files can legitimately differ in wording — Appendix B uses an
    intra-doc anchor reference; the runbook uses an inter-doc markdown
    link — while still being verified as pointing at the same recorded
    verdict.
    """
    text = path.read_text(encoding="utf-8")
    line_matches = _GATING_VERDICT_LINE_RE.findall(text)
    if not line_matches:
        return None
    # Round-5 fix (adversarial-regex stress test, case 18): mirror the
    # Decision extractor's `findall(...)[-1]` pattern so "current entry"
    # semantics stay symmetric across both extractors. If a file ever
    # records a history of multiple Promotion Decisions, the LAST
    # Gating-verdict line is the current one (matches the LAST
    # Decision line in `_extract_decision`). `.search()` returned the
    # FIRST match (oldest), which would silently compare today's
    # Decision against an ancestor's Gating-verdict reference.
    line = line_matches[-1]
    # Strip the literal "YYYY-MM-DD" placeholder so it can't accidentally
    # match _RECORDED_VERDICT_REFERENCE_RE.
    sanitized = line.replace("YYYY-MM-DD", "")
    # Round-4 fix per agent B's critical false-negative finding: reject
    # any line where a PARENTHETICAL substring contains all three verdict
    # tokens (the literal `(PASS / FAIL / BLOCKED)` placeholder list).
    # Scoping to "inside parens" is essential — the real placeholder
    # strings in feature-020 quickstart.md:413 and runbook-gpu-mvp-demo.md
    # both end with trailing FR-027 prose like "FR-027 — if the gating
    # verdict is FAIL or BLOCKED, ..." that contains the words FAIL and
    # BLOCKED in plain text. The previous whole-line check would falsely
    # reject a fully-recorded `(PASS)` line because its surrounding prose
    # still mentions FAIL/BLOCKED.
    for paren_content in _PARENTHETICAL_RE.findall(sanitized):
        if all(token in paren_content for token in ("PASS", "FAIL", "BLOCKED")):
            return None
    ref_match = _RECORDED_VERDICT_REFERENCE_RE.search(sanitized)
    if ref_match is None:
        return None
    return ref_match.group(1), ref_match.group(2)


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


def test_promotion_gating_verdict_reference_agrees() -> None:
    """Multi-agent review P2-3 / appendix-recording.md §Promotion-decision
    synchronization contract: Appendix B (authoritative) and runbook
    (mirror) MUST also agree on the `Gating verdict:` reference.

    The reference is encoded as a (date, verdict) tuple
    (`YYYY-MM-DD`, `PASS`/`FAIL`/`BLOCKED`). Templated placeholder text
    (literal `YYYY-MM-DD` with no concrete verdict) is treated as
    unrecorded — both files agreeing on "no reference yet" satisfies
    the contract.
    """
    appendix_b_verdict = _extract_gating_verdict(APPENDIX_B_PATH)
    runbook_verdict = _extract_gating_verdict(RUNBOOK_PATH)

    assert appendix_b_verdict == runbook_verdict, (
        f"Promotion Gating-verdict reference sync violation (P2-3):\n"
        f"  Appendix B (date, verdict): {appendix_b_verdict!r}\n"
        f"  Runbook    (date, verdict): {runbook_verdict!r}\n"
        f"The two files MUST point at the same recorded verdict per "
        f"appendix-recording.md §Promotion-decision synchronization "
        f"contract. The Appendix B subsection is authoritative; update "
        f"the runbook mirror to match."
    )


def test_gating_verdict_partial_fill_returns_none(tmp_path: Path) -> None:
    """Multi-agent review verification round (P2-3, agent 4 audit):
    if the operator dates the Gating-verdict line but leaves the verdict
    tokens as the literal `(PASS / FAIL / BLOCKED)` placeholder list,
    `_extract_gating_verdict` MUST return None (treat as unrecorded) —
    NOT extract `('YYYY-MM-DD-stripped-date', 'PASS')` as if a real
    verdict were recorded.

    Fixture mirrors the REAL placeholder text including FR-027 trailing
    prose (verified against `specs/020-vendor-evidence-gate/quickstart.md`
    Appendix B and `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`).
    """
    # Operator dated the line but kept the placeholder verdict list.
    # Trailing FR-027 prose mentions FAIL and BLOCKED — the sanitization
    # must NOT be fooled by that into thinking the placeholder list is
    # present outside the parens.
    partial_fill = (
        "# Test fixture\n\n"
        "**Decision**: _(placeholder)_\n\n"
        "**Gating verdict**: see §Quality-Gate Verdict 2026-05-19 "
        "(`PASS` / `FAIL` / `BLOCKED`) above. FR-027 — if the gating "
        "verdict is FAIL or BLOCKED, the decision MUST be `stay opt-in`; "
        "promotion is not a permitted option.\n"
    )
    fake = tmp_path / "partial.md"
    fake.write_text(partial_fill, encoding="utf-8")

    result = _extract_gating_verdict(fake)
    assert result is None, (
        f"partial-fill regression: a date+placeholder-verdict-list line "
        f"MUST extract as None (unrecorded), got {result!r}. The regex "
        f"sanitization must reject lines containing the literal "
        f"placeholder list inside parens."
    )


def test_gating_verdict_multi_entry_history_returns_current(tmp_path: Path) -> None:
    """Round-5 fix (adversarial-regex case 18): if a file accumulates a
    history of multiple `**Gating verdict**:` lines, `_extract_gating_verdict`
    MUST return the LAST entry (the current one), mirroring the
    Decision extractor's `findall(...)[-1]` semantics. Using `.search()`
    would return the FIRST match (the oldest), silently comparing
    today's Decision against an ancestor's Gating-verdict reference.
    """
    history = (
        "# Test fixture\n\n"
        "## Promotion Decision (2026-05-01)\n\n"
        "**Decision**: stay opt-in\n\n"
        "**Gating verdict**: see §Quality-Gate Verdict 2026-05-01 (FAIL) above. "
        "FR-027 — if FAIL or BLOCKED, the decision MUST be `stay opt-in`.\n\n"
        "## Promotion Decision (2026-05-19)\n\n"
        "**Decision**: promote to default\n\n"
        "**Gating verdict**: see §Quality-Gate Verdict 2026-05-19 (PASS) above. "
        "FR-027 — if FAIL or BLOCKED, the decision MUST be `stay opt-in`.\n"
    )
    fake = tmp_path / "history.md"
    fake.write_text(history, encoding="utf-8")

    result = _extract_gating_verdict(fake)
    assert result == ("2026-05-19", "PASS"), (
        f"multi-entry history regression: the LAST Gating-verdict entry "
        f"is the current one; got {result!r}. The extractor MUST use "
        f"`findall(...)[-1]` (mirroring _extract_decision), not `.search()` "
        f"which returns the oldest."
    )


def test_gating_verdict_fully_recorded_extracts_tuple(tmp_path: Path) -> None:
    """Positive case (round-4 agent B critical regression): a fully-
    recorded Gating-verdict line whose surrounding prose ALSO mentions
    FAIL and BLOCKED (via the FR-027 trailing clause) MUST still extract
    as `(date, verdict)`. The whole-line placeholder check would falsely
    reject this; the parenthetical-scoped check correctly accepts it.
    """
    # Realistic recorded form including FR-027 trailing prose — this is
    # the exact false-negative case agent B caught in round-4.
    recorded = (
        "**Gating verdict**: see §Quality-Gate Verdict 2026-05-19 (PASS) "
        "above. FR-027 — if the gating verdict is FAIL or BLOCKED, the "
        "decision MUST be `stay opt-in`; promotion is not a permitted "
        "option.\n"
    )
    fake = tmp_path / "recorded.md"
    fake.write_text(recorded, encoding="utf-8")

    result = _extract_gating_verdict(fake)
    assert result == ("2026-05-19", "PASS"), (
        f"recorded reference should extract as ('2026-05-19', 'PASS') "
        f"even when surrounding FR-027 prose mentions FAIL / BLOCKED; "
        f"got {result!r}. The placeholder-list check MUST be scoped to "
        f"inside parens, not the whole line."
    )
