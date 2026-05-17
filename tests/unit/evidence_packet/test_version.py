from dartwing_ocr.evidence_packet.version import CONTRACT_SET_VERSION


def test_contract_set_version_matches_nullable_confidence_schema():
    assert CONTRACT_SET_VERSION == "1.2.0"
