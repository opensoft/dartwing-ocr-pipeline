"""Entry point for ``python -m ledgerlinc_ocr.router``."""
from __future__ import annotations

import sys

from ledgerlinc_ocr.router.cli import main

if __name__ == "__main__":
    sys.exit(main())
