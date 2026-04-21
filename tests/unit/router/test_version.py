"""T012: Unit tests for router version constants."""
from __future__ import annotations

from ledgerlinc_ocr.router.version import POLICY_VERSION, build_pipeline_version


def test_policy_version_is_nonempty_string():
    assert isinstance(POLICY_VERSION, str)
    assert len(POLICY_VERSION) > 0


def test_policy_version_matches_research_decision_3():
    assert POLICY_VERSION == "stage1-routing-policy-v1.0.0"


def test_build_pipeline_version_returns_nonempty_string():
    result = build_pipeline_version()
    assert isinstance(result, str)
    assert len(result) > 0


def test_build_pipeline_version_has_canonical_prefix():
    assert build_pipeline_version().startswith("stage1-routing-v")


def test_pipeline_version_is_stable():
    first = build_pipeline_version()
    second = build_pipeline_version()
    assert first == second


def test_policy_version_is_stable():
    from ledgerlinc_ocr.router import version as version_mod

    assert version_mod.POLICY_VERSION == POLICY_VERSION
