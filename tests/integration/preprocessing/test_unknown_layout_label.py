"""FR-006 unknown-label: unmapped V3 layout label falls back to `text` + warning.

The warning does NOT downgrade `ingestion_sources.paddleocr_vl.status`. This
test exercises `ocr._extract_blocks_and_tables` directly since the unknown-label
path lives inside ocr.run_page's helper and not in the pipeline.
"""

from __future__ import annotations

from types import SimpleNamespace

from ledgerlinc_ocr.preprocessing import ocr


def _fake_layout_det_res_with_unmapped_label() -> SimpleNamespace:
    """V3-shaped layout_det_res with one region carrying a label that is not
    in PPSTRUCTURE_LABEL_TO_BLOCK_TYPE (e.g., a future V3 class).
    """
    region = SimpleNamespace(
        label="weird_future_class",
        coordinate=[10, 10, 200, 100],
        score=0.82,
    )
    return SimpleNamespace(boxes=[region])


def test_unknown_label_maps_to_text_and_emits_warning():
    layout = _fake_layout_det_res_with_unmapped_label()
    blocks, tables, warnings = ocr._extract_blocks_and_tables(
        layout, [], page_number=1, width=800, height=1000,
    )
    # Single block, mapped to text fallback.
    assert len(blocks) == 1
    assert blocks[0]["block_type"] == "text"
    # Warning with pinned format.
    assert warnings == ["page 1: [unknown_layout_label] label=weird_future_class"]
    # No tables produced by this fallback.
    assert tables == []


def test_known_v3_label_does_not_emit_unknown_warning():
    """`paragraph_title` is in the remediated mapping (research R-003) → no warning."""
    region = SimpleNamespace(label="paragraph_title", coordinate=[0, 0, 100, 20], score=0.9)
    layout = SimpleNamespace(boxes=[region])
    blocks, _tables, warnings = ocr._extract_blocks_and_tables(
        layout, [], page_number=1, width=100, height=100,
    )
    assert blocks[0]["block_type"] == "title"
    assert warnings == []


def test_unknown_label_warning_uses_fr020_format():
    """FR-020: warning starts with `page N: [unknown_layout_label] `."""
    region = SimpleNamespace(label="made_up_class", coordinate=[0, 0, 10, 10], score=0.5)
    layout = SimpleNamespace(boxes=[region])
    _blocks, _tables, warnings = ocr._extract_blocks_and_tables(
        layout, [], page_number=7, width=100, height=100,
    )
    assert warnings[0].startswith("page 7: [unknown_layout_label] ")
    assert "label=made_up_class" in warnings[0]
