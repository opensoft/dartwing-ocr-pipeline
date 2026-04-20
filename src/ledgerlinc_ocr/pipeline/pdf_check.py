"""PDF magic-byte verification. FR-017 / research R-005."""
from __future__ import annotations

from pathlib import Path

_PDF_MAGIC = b"%PDF-"


def is_pdf(path: Path) -> bool:
    with path.open("rb") as fh:
        return fh.read(5) == _PDF_MAGIC
