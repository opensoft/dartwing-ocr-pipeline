"""US1 AC#5 + SC-006 + SC-007: DEBUG writes, default does not; non-packet files untouched."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from dartwing_ocr.evidence_packet import assemble_from_folder


def _hash_folder_excluding_packet(folder: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    for path in sorted(folder.iterdir()):
        if path.name == "evidence_packet.json":
            continue
        digests[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def test_ac5_default_does_not_write(folder_with_preprocess):
    folder = folder_with_preprocess("minimal_valid.json")
    (folder / "extra_sibling.txt").write_text("sidecar content")
    before = _hash_folder_excluding_packet(folder)

    assemble_from_folder(folder)

    assert not (folder / "evidence_packet.json").exists()
    after = _hash_folder_excluding_packet(folder)
    assert before == after


def test_ac5_debug_writes(folder_with_preprocess, caplog):
    folder = folder_with_preprocess("minimal_valid.json")
    (folder / "extra_sibling.txt").write_text("sidecar content")
    before = _hash_folder_excluding_packet(folder)

    with caplog.at_level(logging.DEBUG, logger="dartwing_ocr"):
        assemble_from_folder(folder)

    packet_path = folder / "evidence_packet.json"
    assert packet_path.exists()
    assert packet_path.stat().st_size > 0
    after = _hash_folder_excluding_packet(folder)
    assert before == after
