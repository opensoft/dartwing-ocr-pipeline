"""Fixed trace block — four relative filenames (data-model.md §TraceBlock, US5)."""

from __future__ import annotations


def build_trace() -> dict:
    return {
        "source_file": "source.pdf",
        "preprocess_output_file": "preprocess_output.json",
        "edge_extraction_output_file": "edge_extraction_output.json",
        "routing_decision_file": "routing_decision.json",
    }
