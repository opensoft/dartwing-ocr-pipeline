"""T3 — bidirectional policy lock for overall_vendor_confidence weights.

The prior test coupled `overall_vendor_confidence == 0.935` to `SEMVER == "0.1.0"`,
which caught the direction "bump SEMVER without touching formula" but left the
reverse direction open — a dev could change the formula, update the expected
0.935 to a new number, and tests would still pass without any SEMVER bump.

This test closes that gap: it compares the live formula-weight constants in
`quality.py` against the frozen `SEMVER_WEIGHT_LOCK` registry in `version.py`
keyed to the current `SEMVER`. If weights change, the lock registry for the
current SEMVER mismatches → test fails → the maintainer is forced to either
revert the change or bump SEMVER + add a new lock entry (editing existing
entries is forbidden, enforced socially by the comment in version.py).
"""

from __future__ import annotations

import pytest

from ledgerlinc_ocr.assembler.quality import (
    POLICY_WEIGHT_COMPANY_NAME,
    POLICY_WEIGHT_SECONDARY_MEAN,
)
from ledgerlinc_ocr.assembler.version import SEMVER, SEMVER_WEIGHT_LOCK


def test_current_semver_has_lock_entry():
    assert SEMVER in SEMVER_WEIGHT_LOCK, (
        f"SEMVER={SEMVER!r} has no entry in SEMVER_WEIGHT_LOCK. "
        f"Add {SEMVER!r}: (weight_company_name, weight_secondary_mean) to "
        f"src/ledgerlinc_ocr/assembler/version.py — do not edit existing entries."
    )


def test_live_weights_match_locked_weights_for_current_semver():
    expected = SEMVER_WEIGHT_LOCK[SEMVER]
    actual = (POLICY_WEIGHT_COMPANY_NAME, POLICY_WEIGHT_SECONDARY_MEAN)
    assert actual == expected, (
        f"Formula weights {actual} do not match SEMVER_WEIGHT_LOCK[{SEMVER!r}]={expected}.\n"
        f"If this is unintentional: revert quality.py weight constants.\n"
        f"If intentional: bump SEMVER in version.py AND add a new entry to "
        f"SEMVER_WEIGHT_LOCK under the new SEMVER. Do not edit the existing "
        f"{SEMVER!r} entry — shipped semvers have frozen policies."
    )


def test_all_locked_weights_are_normalized():
    # Sanity: every registered weight pair should sum to 1.0 (convex combination).
    # If a future semver breaks this, the test forces a review conversation.
    for semver, (w_cn, w_sec) in SEMVER_WEIGHT_LOCK.items():
        total = w_cn + w_sec
        assert total == pytest.approx(1.0), (
            f"SEMVER_WEIGHT_LOCK[{semver!r}]=({w_cn}, {w_sec}) does not sum to 1.0. "
            f"Convex-combination policy is baked into the clip in compute_overall_"
            f"vendor_confidence; if you intentionally abandoned it, update the "
            f"formula's clip bounds and this test together."
        )
