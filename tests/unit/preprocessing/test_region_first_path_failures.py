"""CPU-safe tests for feature 018 region-first edge cases."""

from __future__ import annotations

from pathlib import Path

from ledgerlinc_ocr.preprocessing import pipeline
from ledgerlinc_ocr.preprocessing.region_strategies import resolve_region_strategy


class _FakePage:
    def __init__(self, *, width_pt: float = 72.0, height_pt: float = 144.0) -> None:
        self._width_pt = width_pt
        self._height_pt = height_pt

    def get_size(self) -> tuple[float, float]:
        return self._width_pt, self._height_pt

    def get_rotation(self) -> int:
        return 90

    def close(self) -> None:
        return None


class _FakeDoc:
    def __init__(self, page_count: int = 2) -> None:
        self._pages = [_FakePage() for _ in range(page_count)]

    def __len__(self) -> int:
        return len(self._pages)

    def __getitem__(self, index: int) -> _FakePage:
        return self._pages[index]

    def get_page(self, index: int) -> _FakePage:
        return self._pages[index]

    def close(self) -> None:
        return None


def test_region_first_crop_failure_emits_schema_shaped_failed_page(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A page-band render failure should match full-page failure containment.

    The region-first path must return page records instead of raising, and
    90-degree page geometry must match full-page render dimensions.
    """
    monkeypatch.setattr(pipeline.rasterize, "open_pdf", lambda _path: _FakeDoc())

    def _raise_crop_failure(**_kwargs):
        raise RuntimeError("crop render failed")

    monkeypatch.setattr(
        pipeline.rasterize,
        "rasterize_page_band",
        _raise_crop_failure,
    )

    pages, warnings, tables, lines, pages_with_output, silent_empty, trigger = (
        pipeline._run_region_first_path(
            pdf_path=tmp_path / "source.pdf",
            region_strategy=resolve_region_strategy("header-first-v1"),
            dpi=72,
            invocation=pipeline.Invocation(document_folder=tmp_path),
        )
    )

    assert trigger is False
    assert tables == []
    assert lines == []
    assert pages_with_output == 0
    assert silent_empty is False
    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert pages[0]["width"] == 144
    assert pages[0]["height"] == 72
    assert pages[0]["blocks"] == []
    assert pages[0]["raw_ocr_lines"] == []
    assert pages[1]["page_number"] == 2
    assert pages[1]["width"] == 144
    assert pages[1]["height"] == 72
    assert pages[1]["blocks"] == []
    assert pages[1]["raw_ocr_lines"] == []
    assert warnings == ["page 1: rasterization failed: RuntimeError: crop render failed"]
