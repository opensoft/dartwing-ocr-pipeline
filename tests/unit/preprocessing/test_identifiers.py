import re

import pytest

from ledgerlinc_ocr.preprocessing.identifiers import block_id, line_id

BLOCK_RE = re.compile(r"^p\d+_b\d+$")
LINE_RE = re.compile(r"^p\d+_l\d+$")


def test_block_id_shape():
    assert block_id(1, 1) == "p1_b1"
    assert block_id(12, 7) == "p12_b7"
    assert BLOCK_RE.match(block_id(3, 4))


def test_line_id_shape():
    assert line_id(1, 1) == "p1_l1"
    assert line_id(9, 42) == "p9_l42"
    assert LINE_RE.match(line_id(2, 5))


@pytest.mark.parametrize("page,idx", [(0, 1), (1, 0), (-1, 1), (1, -1)])
def test_invalid_inputs_raise(page, idx):
    with pytest.raises(ValueError):
        block_id(page, idx)
    with pytest.raises(ValueError):
        line_id(page, idx)


def test_ids_stable_across_calls():
    assert block_id(5, 3) == block_id(5, 3)
    assert line_id(5, 3) == line_id(5, 3)
