"""Final structured payload assembler (Stage 1 Vendor-Identity)."""

from dartwing_ocr.assembler.pipeline import Invocation, run
from dartwing_ocr.assembler.version import build_pipeline_version

__all__ = ["Invocation", "run", "build_pipeline_version"]
