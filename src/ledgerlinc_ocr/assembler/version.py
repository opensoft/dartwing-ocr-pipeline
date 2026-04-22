"""Pipeline-version string for the final-payload assembler (research Decision 3).

``SEMVER_WEIGHT_LOCK`` (T3) is a historical registry that pins the
``overall_vendor_confidence`` formula weights to each shipped SEMVER. The
bidirectional policy-lock test asserts that the weights currently declared
in ``quality.py`` match the entry registered here for the current SEMVER.

*Rules for editing this file*:

- To change formula weights: bump ``SEMVER`` AND add a NEW entry in
  ``SEMVER_WEIGHT_LOCK`` under the new SEMVER.
- Do NOT edit an existing entry. Shipped SEMVERs have frozen policies —
  the whole point of the lock is to make silent drift visible in diff.
"""

from __future__ import annotations

SLICE_PREFIX = "009-final-payload"
SEMVER = "0.1.0"

# T3 — historical weight lock. Keyed by SEMVER. Each entry is a tuple of
# (weight_company_name, weight_secondary_mean). Frozen once shipped.
SEMVER_WEIGHT_LOCK: dict[str, tuple[float, float]] = {
    "0.1.0": (0.5, 0.5),
}


def build_pipeline_version(semver: str = SEMVER) -> str:
    """Return `"009-final-payload@<semver>"`. Default matches current stage-1 policy."""
    return f"{SLICE_PREFIX}@{semver}"
