import pytest

from ledgerlinc_ocr.preprocessing.ingestion_sources import build_ingestion_sources


def test_all_pages_succeeded_status_success():
    result = build_ingestion_sources(pages_total=3, pages_with_paddleocr_output=3)
    assert result["paddleocr_vl"] == {"enabled": True, "status": "success"}
    assert result["falcon_ocr"] == {"enabled": False, "status": "not_implemented"}
    assert result["falcon_perception"] == {"enabled": False, "status": "not_implemented"}


def test_at_least_one_page_status_success():
    result = build_ingestion_sources(pages_total=5, pages_with_paddleocr_output=1)
    assert result["paddleocr_vl"]["status"] == "success"


def test_zero_pages_status_failure():
    result = build_ingestion_sources(pages_total=3, pages_with_paddleocr_output=0)
    assert result["paddleocr_vl"]["status"] == "failure"


def test_keys_exactly_three():
    result = build_ingestion_sources(pages_total=1, pages_with_paddleocr_output=1)
    assert set(result.keys()) == {"paddleocr_vl", "falcon_ocr", "falcon_perception"}


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        build_ingestion_sources(pages_total=0, pages_with_paddleocr_output=0)
    with pytest.raises(ValueError):
        build_ingestion_sources(pages_total=2, pages_with_paddleocr_output=3)
    with pytest.raises(ValueError):
        build_ingestion_sources(pages_total=2, pages_with_paddleocr_output=-1)
