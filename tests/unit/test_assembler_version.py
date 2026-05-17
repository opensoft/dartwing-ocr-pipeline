"""Unit tests for assembler version builder (Phase 2 T010)."""

from dartwing_ocr.assembler.version import SEMVER, build_pipeline_version


def test_default_semver_matches_current_policy():
    assert build_pipeline_version() == "009-final-payload@0.1.0"
    assert SEMVER == "0.1.0"


def test_custom_semver_override():
    assert build_pipeline_version("0.2.0") == "009-final-payload@0.2.0"
