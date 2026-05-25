"""Module entry point for ``python -m dartwing_ocr.gpu_demo``."""

import sys

from dartwing_ocr.gpu_demo.cli import main


if __name__ == "__main__":
    sys.exit(main())
