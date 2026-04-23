"""Pinned version strings for the stage 1 deterministic router.

These constants are load-bearing — they are written verbatim into every
``routing_decision.json`` artifact and reviewed at PR time per FR-005 and
SC-010. Any change to a rule, threshold, or canonical reason string MUST be
accompanied by a ``POLICY_VERSION`` bump (see research.md Decision 3).
"""
from __future__ import annotations

POLICY_VERSION: str = "stage1-routing-policy-v1.0.0"
"""Identifier for the rule set applied. Bumped whenever rules, thresholds, or
canonical reason strings change (FR-005). PR-review gate per SC-010."""

_PIPELINE_VERSION: str = "stage1-routing-v0.1.0"
"""Build identifier for the router. Bumped on router-code releases (research
Decision 4). Separate from POLICY_VERSION: one identifies the build, the
other identifies the rule set."""


def build_pipeline_version() -> str:
    """Return the canonical ``pipeline_version`` string for this build."""
    return _PIPELINE_VERSION
