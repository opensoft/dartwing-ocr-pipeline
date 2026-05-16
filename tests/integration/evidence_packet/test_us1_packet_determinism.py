"""US1 AC#2 + SC-002: ten runs produce byte-identical evidence_packet.json."""
from __future__ import annotations

import logging

from dartwing_ocr.evidence_packet import assemble_from_folder


def test_ac2_byte_identical_ten_runs(folder_with_preprocess, caplog):
    folder = folder_with_preprocess("with_regex_hits.json")
    packet_path = folder / "evidence_packet.json"

    with caplog.at_level(logging.DEBUG, logger="dartwing_ocr"):
        assemble_from_folder(folder)
        baseline = packet_path.read_bytes()
        assert len(baseline) > 0

        for _ in range(9):
            assemble_from_folder(folder)
            assert packet_path.read_bytes() == baseline
