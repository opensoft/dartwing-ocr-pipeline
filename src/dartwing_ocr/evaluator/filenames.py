"""Canonical evaluator artifact filenames.

Single source of truth for the two filenames the evaluator emits, so a
rename is a one-line change. Import-free (only Python builtins) so this
module participates in no import cycles.
"""
from __future__ import annotations

EVAL_DOC_FILENAME = "evaluation_document.json"
EVAL_RUN_SUMMARY_FILENAME = "evaluation_run_summary.json"
