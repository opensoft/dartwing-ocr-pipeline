"""Unit tests for the rasterize module (T067).

Covers FR-004 (300 DPI), FR-005 (post-rotation width/height), FR-005a
(metadata fallback), FR-006 (rotation snap vocabulary), and the
document-level error boundaries for US3.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ledgerlinc_ocr.preprocessing import rasterize
from ledgerlinc_ocr.preprocessing.errors import (
    EncryptedPdfError,
    MalformedPdfError,
    NonPdfInputError,
    ZeroPagePdfError,
)

HERE = Path(__file__).resolve().parent
FIXTURE_ROOT = HERE.parents[1] / "fixtures" / "preprocessing"


def _us1_pdf() -> Path:
    src = FIXTURE_ROOT / "inv_001" / "source.pdf"
    if not src.exists():
        sys.path.insert(0, str(FIXTURE_ROOT))
        from make_us1_single_page import build as build_us1  # type: ignore

        return build_us1()
    return src


def _us3(name: str) -> Path:
    sys.path.insert(0, str(FIXTURE_ROOT))
    from make_us3_fixtures import build_all  # type: ignore

    target = FIXTURE_ROOT / name / "source.pdf"
    if not target.exists():
        build_all()
    return target


def test_snap_rotation_canonical_values_unchanged():
    for angle in (0, 90, 180, 270):
        snapped, changed = rasterize._snap_rotation(angle)
        assert snapped == angle
        assert changed is False


def test_snap_rotation_out_of_vocab_snaps_to_nearest():
    for raw, expected in [(87.0, 90), (3.0, 0), (184.0, 180), (272.5, 270), (359.0, 0)]:
        snapped, changed = rasterize._snap_rotation(raw)
        assert snapped == expected
        assert changed is True


def test_metadata_fallback_uses_points_scaled_to_dpi():
    # 612 × 792 points (US Letter) → 2550 × 3300 at 300 DPI.
    fake_page = SimpleNamespace(get_size=lambda: (612.0, 792.0))
    w, h = rasterize._metadata_fallback_dims(fake_page)
    assert (w, h) == (2550, 3300)


def test_metadata_fallback_minimum_one_when_unreadable():
    class Broken:
        def get_size(self):
            raise RuntimeError("unreadable")

    w, h = rasterize._metadata_fallback_dims(Broken())
    assert w == 1 and h == 1


def test_rasterize_us1_at_300_dpi_produces_post_rotation_dims():
    # rasterize_pdf is a generator (FR-005a / R-011); materialize for assertions.
    rasters = list(rasterize.rasterize_pdf(_us1_pdf()))
    assert len(rasters) == 1
    page = rasters[0]
    assert isinstance(page, rasterize.PageRaster)
    # Pillow writes at 150 DPI metadata, but we render at 300 DPI, so the page
    # image must be at least as large as the fixture's original 1275 × 1650.
    assert page.width >= 1275
    assert page.height >= 1650
    assert page.rotation_detected in {0, 90, 180, 270}
    assert page.rotation_snapped is False


def test_non_pdf_input_raises(tmp_path):
    bad = tmp_path / "bogus.pdf"
    bad.write_text("totally not a pdf", encoding="utf-8")
    with pytest.raises(NonPdfInputError):
        rasterize.open_pdf(bad)


def test_malformed_pdf_raises():
    with pytest.raises(MalformedPdfError):
        rasterize.open_pdf(_us3("inv_033_malformed"))


def test_encrypted_pdf_raises():
    with pytest.raises(EncryptedPdfError):
        rasterize.open_pdf(_us3("inv_032_encrypted"))


def test_zero_page_or_malformed_raises():
    """pypdfium2 cannot tell a true zero-page PDF apart from a malformed one —
    both must still fail loud as InputRejectedError subclasses, never silently."""
    from ledgerlinc_ocr.preprocessing.errors import InputRejectedError

    with pytest.raises(InputRejectedError):
        rasterize.open_pdf(_us3("inv_035_zero_page"))
