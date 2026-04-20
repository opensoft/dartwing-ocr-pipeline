import re

from ledgerlinc_ocr.preprocessing.version import (
    DPI,
    SLICE_PREFIX,
    build_pipeline_version,
)

VERSION_RE = re.compile(
    r"^stage1-preprocess-v\d+\.\d+\.\d+\+paddleocr[\w.\-]+\.[0-9a-f]{7}\.dpi\d+$"
)


def test_default_version_shape_and_dpi():
    v = build_pipeline_version(
        semver="v0.1.0", paddleocr_version="2.10.0", weights_hash7="abc1234"
    )
    assert VERSION_RE.match(v), v
    assert v.endswith(f".dpi{DPI}")
    assert v.startswith(f"{SLICE_PREFIX}-v0.1.0+paddleocr2.10.0.abc1234.dpi")


def test_weights_hash_is_embedded():
    v = build_pipeline_version(
        semver="v0.1.0", paddleocr_version="2.10.0", weights_hash7="deadbee"
    )
    assert ".deadbee." in v


def test_dpi_override_changes_suffix():
    v = build_pipeline_version(
        semver="v0.1.0", paddleocr_version="2.10.0", weights_hash7="abc1234", dpi=400
    )
    assert v.endswith(".dpi400")


def test_dpi_constant_is_300():
    assert DPI == 300


def test_default_pulls_installed_paddleocr_version():
    v = build_pipeline_version(semver="v0.1.0", weights_hash7="abc1234")
    assert "paddleocr" in v
    assert ".abc1234." in v
