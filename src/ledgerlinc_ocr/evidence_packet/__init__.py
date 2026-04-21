"""Evidence-packet public API.

Two entry points:

* :func:`assemble_from_preprocess` — pure transform (dict → dict).
* :func:`assemble_from_folder` — filesystem wrapper that reads a preprocess
  artifact from a per-document folder and optionally persists the resulting
  packet alongside it.

Persistence is gated by the ``ledgerlinc_ocr`` logger effective level: the
packet is only written when that logger is enabled for ``DEBUG`` (or lower).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ledgerlinc_ocr.evidence_packet import serialization as _serialization
from ledgerlinc_ocr.evidence_packet.assembler import (
    assemble_from_preprocess as assemble_from_preprocess,
)
from ledgerlinc_ocr.evidence_packet.errors import (
    PacketAssemblyError as PacketAssemblyError,
)
from ledgerlinc_ocr.evidence_packet.errors import (
    PacketInvalid as PacketInvalid,
)
from ledgerlinc_ocr.evidence_packet.errors import (
    PreprocessInputInvalid as PreprocessInputInvalid,
)
from ledgerlinc_ocr.evidence_packet.errors import (
    PreprocessInputMissing as PreprocessInputMissing,
)
from ledgerlinc_ocr.evidence_packet.version import PACKET_FILENAME

__all__ = [
    "assemble_from_folder",
    "assemble_from_preprocess",
    "PacketAssemblyError",
    "PreprocessInputMissing",
    "PreprocessInputInvalid",
    "PacketInvalid",
]

_PREPROCESS_FILENAME = "preprocess_output.json"
_PACKAGE_LOGGER = "ledgerlinc_ocr"


def assemble_from_folder(folder: Path) -> dict[str, Any]:
    """Assemble an evidence packet from a per-document folder.

    Reads ``<folder>/preprocess_output.json``, assembles the packet, and — when
    the ``ledgerlinc_ocr`` logger is at ``DEBUG`` or lower — writes
    ``<folder>/evidence_packet.json`` atomically.
    """
    folder_path = Path(folder).resolve()
    preprocess_path = folder_path / _PREPROCESS_FILENAME

    try:
        with preprocess_path.open("rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise PreprocessInputMissing(
            f"could not read {preprocess_path}: {exc}",
            path=preprocess_path,
        ) from exc

    try:
        preprocess_output = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PreprocessInputMissing(
            f"preprocess_output.json is not valid UTF-8 JSON: {exc}",
            path=preprocess_path,
        ) from exc

    packet = assemble_from_preprocess(preprocess_output)

    if logging.getLogger(_PACKAGE_LOGGER).isEnabledFor(logging.DEBUG):
        _serialization.write_packet_atomic(packet, folder_path / PACKET_FILENAME)

    return packet
