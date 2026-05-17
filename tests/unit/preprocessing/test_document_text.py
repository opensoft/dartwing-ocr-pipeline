from dartwing_ocr.preprocessing.document_text import (
    INTER_PAGE_SEPARATOR,
    INTRA_PAGE_SEPARATOR,
    join_document_text,
)


def _block(order, text):
    return {"reading_order": order, "text": text}


def test_single_page_single_block():
    pages = [{"page_number": 1, "blocks": [_block(1, "hello")]}]
    assert join_document_text(pages) == "hello"


def test_blocks_sorted_by_reading_order():
    pages = [
        {
            "page_number": 1,
            "blocks": [_block(3, "third"), _block(1, "first"), _block(2, "second")],
        }
    ]
    assert join_document_text(pages) == "first\nsecond\nthird"


def test_pages_sorted_by_page_number():
    pages = [
        {"page_number": 2, "blocks": [_block(1, "beta")]},
        {"page_number": 1, "blocks": [_block(1, "alpha")]},
    ]
    assert join_document_text(pages) == "alpha\n\nbeta"


def test_intra_and_inter_separators_exact():
    pages = [
        {"page_number": 1, "blocks": [_block(1, "a"), _block(2, "b")]},
        {"page_number": 2, "blocks": [_block(1, "c")]},
    ]
    out = join_document_text(pages)
    assert out == f"a{INTRA_PAGE_SEPARATOR}b{INTER_PAGE_SEPARATOR}c"
    assert out == "a\nb\n\nc"


def test_empty_blocks_page_becomes_empty_string():
    pages = [
        {"page_number": 1, "blocks": []},
        {"page_number": 2, "blocks": [_block(1, "x")]},
    ]
    assert join_document_text(pages) == "\n\nx"


def test_deterministic_across_calls():
    pages = [
        {"page_number": 1, "blocks": [_block(1, "a"), _block(2, "b")]},
        {"page_number": 2, "blocks": [_block(1, "c")]},
    ]
    assert join_document_text(pages) == join_document_text(pages)
