"""T040 [US6] — FR-016 routing-internal consistency (Decision 9 enumeration).

FIX 5 / T4: the original parametrization had four forbidden combos. FR-016
is broader — *any* mismatch between `decision` and `review_status` must be
rejected. The full 2x2x2 (decision x mrr x reason-present) matrix has six
inconsistent cells; the expanded `FORBIDDEN_COMBINATIONS` list below covers
every one.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ledgerlinc_ocr.assembler.errors import (
    InputSchemaInvalidError,
    RoutingContradictionError,
)
from ledgerlinc_ocr.assembler.validation import check_routing_internal_consistency


def _routing(decision: str, mrr: bool, reason: str | None) -> dict:
    return {
        "decision": decision,
        "review_status": {"manual_review_required": mrr, "review_reason": reason},
    }


# Full enumeration of inconsistent cells in the (decision, mrr, reason?) cube.
FORBIDDEN_COMBINATIONS = [
    # decision=edge_accept: mrr must be False AND reason must be None.
    ("edge_accept", True, None),                 # (1) mrr contradicts accept
    ("edge_accept", False, "company_name_inferred"),   # (2) reason contradicts accept
    ("edge_accept", True, "company_name_inferred"),    # (3) both contradict accept
    # decision=edge_review_required: mrr must be True AND reason must be non-null.
    ("edge_review_required", False, None),       # (4) neither flag set
    ("edge_review_required", True, None),        # (5) missing reason when review
    ("edge_review_required", False, "company_name_inferred"),
                                                  # (6) FIX 5 — mrr=false but reason
                                                  #     set: decision says review,
                                                  #     flag says no review, reason
                                                  #     still present → contradiction
]


@pytest.mark.parametrize("decision,mrr,reason", FORBIDDEN_COMBINATIONS)
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


# --------------------------------------------------------------------------
# H4 — empty or whitespace-only `review_reason` under `edge_review_required`
# must be rejected as a contradiction. The schema permits `["string","null"]`
# with no minLength, so the code must enforce the semantic "reason present"
# invariant itself.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("empty_reason", ["", " ", "   ", "\t", "\n", " \t \n "])
def test_empty_or_whitespace_reason_under_review_required_contradicts(empty_reason):
    with pytest.raises(RoutingContradictionError) as excinfo:
        check_routing_internal_consistency(
            _routing("edge_review_required", True, empty_reason)
        )
    assert "absent" in str(excinfo.value)


# --------------------------------------------------------------------------
# H3 — calling the public invariant function out of order (i.e., without
# prior schema validation) must surface as `InputSchemaInvalidError`, not
# leak as a bare KeyError that the CLI would route to exit 1 "unexpected".
# --------------------------------------------------------------------------

@pytest.mark.parametrize("broken_routing", [
    {},  # nothing at all
    {"decision": "edge_accept"},  # missing review_status
    {"decision": "edge_accept", "review_status": {}},  # missing mrr + reason
    {"decision": "edge_accept", "review_status": {"manual_review_required": False}},
    # missing review_reason
    {"decision": "edge_accept", "review_status": None},  # review_status wrong type
    {"review_status": {"manual_review_required": False, "review_reason": None}},
    # missing decision
])
def test_missing_keys_raise_schema_invalid_not_keyerror(broken_routing):
    with pytest.raises(InputSchemaInvalidError):
        check_routing_internal_consistency(broken_routing)


# --------------------------------------------------------------------------
# FIX 5 / T4 — CLI-level hard-fail parametrized test for FR-016.
#
# Complements the unit-level `test_forbidden_combinations_raise` above: for
# each forbidden combo we mutate a real fixture's `routing_decision.json`,
# run the CLI end-to-end, and assert exit=2 + kind=routing_contradiction.
# --------------------------------------------------------------------------

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "assembler"


def _stage(tmp_path: Path, name: str) -> Path:
    dst = tmp_path / name
    shutil.copytree(FIXTURE_ROOT / name, dst)
    return dst


def _parse_stderr_json(stderr: str) -> dict:
    for line in reversed(stderr.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    pytest.fail(f"no JSON error line in stderr: {stderr!r}")


@pytest.mark.parametrize("decision,mrr,reason", FORBIDDEN_COMBINATIONS)
def test_routing_contradiction_cli_hard_fail(
    tmp_path: Path, decision: str, mrr: bool, reason: str | None
):
    folder = _stage(tmp_path, "happy_grounded")
    routing_path = folder / "routing_decision.json"
    routing = json.loads(routing_path.read_text(encoding="utf-8"))
    routing["decision"] = decision
    routing["review_status"]["manual_review_required"] = mrr
    routing["review_status"]["review_reason"] = reason
    # Keep the rest of the fixture self-consistent for the schema validator:
    # `reasons` must line up with a review decision per the schema, but is
    # free-form for `edge_accept`. Empty it in both cases — this test only
    # cares that the routing-contradiction check fires before anything else.
    routing["reasons"] = [reason] if (decision == "edge_review_required" and reason) else []
    routing_path.write_text(json.dumps(routing, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "ledgerlinc_ocr.assembler",
         "--document-folder", str(folder)],
        capture_output=True, text=True,
    )

    assert result.returncode == 2, (
        f"expected exit 2 for ({decision!r}, {mrr!r}, {reason!r}); "
        f"got {result.returncode}; stderr={result.stderr!r}"
    )
    assert not (folder / "final_structured_payload.json").exists()
    err = _parse_stderr_json(result.stderr)
    assert err["status"] == "error"
    assert err["kind"] == "routing_contradiction", (
        f"expected kind=routing_contradiction for ({decision!r}, {mrr!r}, {reason!r}); "
        f"got {err!r}"
    )
