"""Atomic packet serialization. Delegates to preprocessing.artifact.write_atomic."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dartwing_ocr.preprocessing.artifact import write_atomic as _write_atomic


def write_packet_atomic(packet: dict[str, Any], out_path: Path) -> Path:
    _write_atomic(packet, out_path)
    return Path(out_path)
