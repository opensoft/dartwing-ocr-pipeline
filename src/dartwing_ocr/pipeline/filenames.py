"""Canonical artifact filenames.

Single source of truth for the four reserved per-document filenames
produced by the stage 1 pipeline. Centralized here so a rename is a
one-line change.

This module is import-free (only Python builtins) so it can safely be
imported from anywhere — runner, stages, validators, routers, the
extract artifact writer — without participating in any import cycle.
"""
from __future__ import annotations

PREPROCESS_OUTPUT_FILENAME = "preprocess_output.json"
EDGE_EXTRACTION_OUTPUT_FILENAME = "edge_extraction_output.json"
ROUTING_DECISION_FILENAME = "routing_decision.json"
FINAL_STRUCTURED_PAYLOAD_FILENAME = "final_structured_payload.json"
