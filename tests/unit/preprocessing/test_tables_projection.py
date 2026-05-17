"""FR-021 / R-014: tables[] projection into v1.0.0 schema shape.

The V3 engine can emit richer table content than the frozen schema carries
(raw HTML string, per-cell metadata, per-cell scores). Everything beyond the
v1.0.0 shape MUST be discarded at the persistence boundary in
`_extract_blocks_and_tables`.
"""

from __future__ import annotations

from types import SimpleNamespace

from dartwing_ocr.preprocessing.ocr import _extract_blocks_and_tables


def _table_region(label: str = "table", coord=None) -> SimpleNamespace:
    return SimpleNamespace(
        label=label,
        coordinate=coord or [[0, 0], [100, 0], [100, 200], [0, 200]],
        score=0.99,
    )


def _table_result(html: str, cell_bboxes: list, **richer_fields) -> SimpleNamespace:
    """Fake V3 table result carrying the v1.0.0 fields plus deliberate
    richer content that must be discarded."""
    attrs: dict = {"html": html, "cell_bbox": cell_bboxes}
    # Synthetic V3-only fields that the projection MUST drop.
    attrs.update(richer_fields)
    return SimpleNamespace(**attrs)


class TestBlockTextDiscardsRawHtml:
    def test_raw_html_not_persisted_in_block_text(self):
        html = (
            "<table>"
            "<tr><td>Alpha</td><td>Beta</td></tr>"
            "<tr><td>Gamma</td><td>Delta</td></tr>"
            "</table>"
        )
        cells = [[[0, 0], [50, 0], [50, 100], [0, 100]]] * 4
        layout = SimpleNamespace(boxes=[_table_region()])
        blocks, _tables, _warn = _extract_blocks_and_tables(
            layout,
            [_table_result(html, cells, table_score=0.98)],
            page_number=1,
            width=200,
            height=400,
        )
        assert len(blocks) == 1
        assert blocks[0]["block_type"] == "table"
        assert blocks[0]["text"] == "", (
            f"raw HTML leaked into block.text: {blocks[0]['text'][:80]!r}"
        )


class TestTablesTopLevelShape:
    def test_rows_columns_derived_via_parse_table_dims(self):
        html = (
            "<table>"
            "<tr><td>A</td><td>B</td></tr>"
            "<tr><td>C</td><td>D</td></tr>"
            "<tr><td>E</td><td>F</td></tr>"
            "</table>"
        )
        layout = SimpleNamespace(boxes=[_table_region()])
        _blocks, tables, _warn = _extract_blocks_and_tables(
            layout,
            [_table_result(html, [])],
            page_number=1,
            width=200,
            height=400,
        )
        assert len(tables) == 1
        assert tables[0]["rows"] == 3
        assert tables[0]["columns"] == 2

    def test_tables_keys_subset_of_v1_0_0(self):
        """tables[*] MUST NOT carry `html`, `table_score`, or V3-only fields."""
        html = "<table><tr><td>X</td></tr></table>"
        cells = [[[0, 0], [50, 0], [50, 20], [0, 20]]]
        layout = SimpleNamespace(boxes=[_table_region()])
        _blocks, tables, _warn = _extract_blocks_and_tables(
            layout,
            [
                _table_result(
                    html,
                    cells,
                    table_score=0.99,
                    cell_scores=[0.91],
                    v3_only_metadata={"spans": [[1, 2]]},
                )
            ],
            page_number=1,
            width=200,
            height=400,
        )
        allowed = {"page_number", "block_id", "bbox", "rows", "columns", "cells"}
        for t in tables:
            leaked = set(t.keys()) - allowed
            assert leaked == set(), (
                f"V3-only fields leaked into tables[*]: {leaked}"
            )

    def test_block_id_pattern(self):
        html = "<table><tr><td>X</td></tr></table>"
        layout = SimpleNamespace(boxes=[_table_region()])
        _blocks, tables, _warn = _extract_blocks_and_tables(
            layout,
            [_table_result(html, [])],
            page_number=7,
            width=200,
            height=400,
        )
        assert tables[0]["page_number"] == 7
        assert tables[0]["block_id"].startswith("p7_b")


class TestCellsProjection:
    def test_cells_projected_to_v1_0_0_shape(self):
        html = "<table><tr><td>A</td><td>B</td></tr></table>"
        cells_src = [
            [[0, 0], [50, 0], [50, 20], [0, 20]],
            [[50, 0], [100, 0], [100, 20], [50, 20]],
        ]
        layout = SimpleNamespace(boxes=[_table_region()])
        _blocks, tables, _warn = _extract_blocks_and_tables(
            layout,
            [_table_result(html, cells_src, cell_type="header")],
            page_number=1,
            width=200,
            height=400,
        )
        assert "cells" in tables[0]
        allowed = {"row", "column", "bbox", "text"}
        for cell in tables[0]["cells"]:
            leaked = set(cell.keys()) - allowed
            assert leaked == set(), (
                f"V3-only per-cell metadata leaked: {leaked}"
            )
            assert isinstance(cell["row"], int)
            assert isinstance(cell["column"], int)
            assert isinstance(cell["bbox"], list) and len(cell["bbox"]) == 4
            assert isinstance(cell["text"], str)

    def test_no_cells_key_when_cell_bboxes_empty(self):
        html = "<table><tr><td>X</td></tr></table>"
        layout = SimpleNamespace(boxes=[_table_region()])
        _blocks, tables, _warn = _extract_blocks_and_tables(
            layout,
            [_table_result(html, [])],
            page_number=1,
            width=200,
            height=400,
        )
        # An empty cell_bbox list → no `cells` key at all (keeps artifacts minimal).
        assert "cells" not in tables[0]


class TestParseTableDims:
    """Spot-check the regex used by the projection."""

    def test_empty_html_returns_zero(self):
        from dartwing_ocr.preprocessing.ocr import _parse_table_dims

        assert _parse_table_dims("") == (0, 0)

    def test_single_row_single_cell(self):
        from dartwing_ocr.preprocessing.ocr import _parse_table_dims

        assert _parse_table_dims("<table><tr><td>X</td></tr></table>") == (1, 1)

    def test_mixed_th_td(self):
        from dartwing_ocr.preprocessing.ocr import _parse_table_dims

        html = (
            "<table>"
            "<tr><th>A</th><th>B</th></tr>"
            "<tr><td>1</td><td>2</td></tr>"
            "</table>"
        )
        assert _parse_table_dims(html) == (2, 2)
