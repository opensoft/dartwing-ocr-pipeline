def test_ac4_quality_populated_no_warnings(us1_artifact):
    q = us1_artifact["quality"]
    assert q["scan_quality"] in {"good", "fair", "poor"}
    assert q["noise_level"] in {"low", "medium", "high"}
    assert isinstance(q["skew_detected"], bool)
    assert us1_artifact["warnings"] == []


def test_ac5_document_text_reading_order(us1_artifact):
    doc_text = us1_artifact["document_text"]
    assert isinstance(doc_text, str)

    page = us1_artifact["pages"][0]
    blocks = sorted(page["blocks"], key=lambda b: b["reading_order"])
    expected = "\n".join(b["text"] for b in blocks)
    assert doc_text == expected, (doc_text, expected)


def test_ac5_reading_order_contiguous_from_one(us1_artifact):
    page = us1_artifact["pages"][0]
    orders = sorted(b["reading_order"] for b in page["blocks"])
    if orders:
        assert orders == list(range(1, len(orders) + 1))
