"""Regression coverage for numpy-backed Paddle result fields.

Real PPStructureV3 responses expose several collections as numpy arrays.
The wrapper must not use Python truthiness on those values, because
`bool(np.array(...))` raises `ValueError`.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from PIL import Image

from ledgerlinc_ocr.preprocessing import ocr


class _FakeEngine:
    def predict(self, _np_img):
        overall_ocr_res = SimpleNamespace(
            rec_texts=np.array(["Vendor LLC"]),
            rec_boxes=np.array(
                [[[10.0, 10.0], [90.0, 10.0], [90.0, 30.0], [10.0, 30.0]]]
            ),
            rec_scores=np.array([0.97]),
        )
        table_res = SimpleNamespace(
            html="<table><tr><td>A</td></tr></table>",
            cell_bbox=np.array([[10.0, 40.0, 90.0, 80.0]]),
        )
        region = SimpleNamespace(
            label="table",
            coordinate=np.array([[10.0, 40.0], [90.0, 40.0], [90.0, 80.0], [10.0, 80.0]]),
            score=0.88,
        )
        layout_det_res = SimpleNamespace(boxes=np.array([region], dtype=object))
        result = SimpleNamespace(
            overall_ocr_res=overall_ocr_res,
            layout_det_res=layout_det_res,
            table_res_list=np.array([table_res], dtype=object),
        )
        return [result]


def test_run_page_accepts_numpy_backed_v3_results(monkeypatch):
    monkeypatch.setattr(ocr, "_get_engine", lambda: _FakeEngine())

    image = Image.new("RGB", (100, 100), color="white")
    lines, blocks, tables, warnings = ocr.run_page(
        image=image, page_number=1, width=100, height=100,
    )

    assert warnings == []
    assert lines == [
        {
            "line_id": "p1_l1",
            "bbox": [10, 10, 90, 30],
            "text": "Vendor LLC",
            "confidence": 0.97,
        }
    ]
    assert blocks == [
        {
            "block_id": "p1_b1",
            "block_type": "table",
            "bbox": [10, 40, 90, 80],
            "reading_order": 1,
            "text": "<table><tr><td>A</td></tr></table>",
            "confidence": 0.88,
        }
    ]
    assert tables == [
        {
            "page_number": 1,
            "block_id": "p1_b1",
            "bbox": [10, 40, 90, 80],
            "rows": 1,
            "columns": 1,
            "cells": [{"row": 0, "column": 0, "bbox": [10, 40, 90, 80], "text": ""}],
        }
    ]
