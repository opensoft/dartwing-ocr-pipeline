def test_ac3_source_flags(us1_artifact):
    sources = us1_artifact["ingestion_sources"]
    assert sources["paddleocr_vl"] == {"enabled": True, "status": "success"}
    assert sources["falcon_ocr"] == {"enabled": False, "status": "not_implemented"}
    assert sources["falcon_perception"] == {"enabled": False, "status": "not_implemented"}
    assert set(sources.keys()) == {"paddleocr_vl", "falcon_ocr", "falcon_perception"}
