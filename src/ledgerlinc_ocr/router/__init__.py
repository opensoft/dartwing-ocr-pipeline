"""Stage 1 deterministic router for the LedgerLinc OCR pipeline.

Reads one per-document folder's ``edge_extraction_output.json`` and emits
``routing_decision.json`` into the same folder, preserving the input artifact's
stage 1 contract set.

No new third-party dependency: this package uses only the existing
``jsonschema``/``pydantic`` surface via ``ledgerlinc_ocr.validator`` plus the
Python 3.12 standard library (research.md Decision 1).
"""
