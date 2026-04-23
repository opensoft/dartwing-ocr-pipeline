"""US4 — structural table extraction (FR-011, FR-011a, FR-024)."""

from __future__ import annotations

from typing import Any

FORBIDDEN_BUSINESS_KEYS = {
    "vendor",
    "vendor_name",
    "company_name",
    "invoice_number",
    "invoice_date",
    "total",
    "total_amount",
    "line_items",
    "subtotal",
    "tax",
    "amount_due",
    "currency",
}


def _walk(obj: Any):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def test_ac1_table_captured(us4_with_table_artifact):
    art = us4_with_table_artifact
    assert isinstance(art["tables"], list)
    assert len(art["tables"]) >= 1, "at least one table block expected on the with-table fixture"

    first = art["tables"][0]
    assert first["page_number"] == 1
    assert first["block_id"].startswith("p1_b")
    # Block referenced by block_id must exist on that page with block_type == "table".
    page1 = art["pages"][0]
    matching = [b for b in page1["blocks"] if b["block_id"] == first["block_id"]]
    assert matching, f"block_id {first['block_id']} not found on page 1"
    assert matching[0]["block_type"] == "table"
    # bbox must mirror the referenced block's bbox exactly.
    assert first["bbox"] == matching[0]["bbox"]


def test_ac2_no_tables_empty_array(us4_no_table_artifact):
    assert us4_no_table_artifact["tables"] == []


def test_ac3_tables_have_only_pinned_keys(us4_with_table_artifact):
    """FR-011a: tables[*] objects carry exactly page_number/block_id/bbox/rows/columns[/cells]."""
    allowed = {"page_number", "block_id", "bbox", "rows", "columns", "cells"}
    required = {"page_number", "block_id", "bbox", "rows", "columns"}
    cell_allowed = {"row", "column", "bbox", "text"}

    for t in us4_with_table_artifact["tables"]:
        keys = set(t.keys())
        assert keys.issubset(allowed), f"unexpected keys in table: {keys - allowed}"
        assert required.issubset(keys), f"missing required keys: {required - keys}"
        assert isinstance(t["rows"], int) and t["rows"] >= 0
        assert isinstance(t["columns"], int) and t["columns"] >= 0
        assert isinstance(t["bbox"], list) and len(t["bbox"]) == 4
        if "cells" in t:
            # Structural delta: V3 emits nested cell records instead of the
            # V2-era flat `cell_bbox` tuples.
            for cell in t["cells"]:
                cell_keys = set(cell.keys())
                assert cell_keys.issubset(cell_allowed), (
                    f"unexpected keys in cell: {cell_keys - cell_allowed}"
                )
            first_cell = t["cells"][0]
            assert isinstance(first_cell["row"], int) and first_cell["row"] >= 0
            assert isinstance(first_cell["column"], int) and first_cell["column"] >= 0
            assert isinstance(first_cell["bbox"], list) and len(first_cell["bbox"]) == 4
            assert isinstance(first_cell["text"], str)


def test_ac3_no_business_keys_anywhere(us4_with_table_artifact, us4_no_table_artifact):
    """FR-024 / FR-011a: business-field keys must not appear anywhere in the artifact."""
    for art in (us4_with_table_artifact, us4_no_table_artifact):
        seen = set(_walk(art))
        leaked = seen & FORBIDDEN_BUSINESS_KEYS
        assert leaked == set(), f"business keys leaked into artifact: {leaked}"
