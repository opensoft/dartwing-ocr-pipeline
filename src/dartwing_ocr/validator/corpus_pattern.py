"""Canonical-pattern allowlist for scored stage 1 corpus folders (Q23 / MI-21 / R-022.15).

A folder is a scored corpus folder ONLY when its basename fully matches
``CANONICAL_FOLDER_PATTERN``. Every non-matching basename — including any extra
suffix such as ``inv_024_hard_degraded_body`` — is calibration / test-fixture
material and MUST NOT appear in scored corpus aggregation output (SC-009).

This constant is the SINGLE source of truth shared by:

* ``dartwing_ocr.validator.cli`` (the ``validate corpus`` subcommand
  partitions scored vs calibration folders using
  :func:`is_scored_corpus_folder`).
* ``dartwing_ocr.evaluator.semantic_quality_metrics`` (the run-summary
  aggregator excludes non-scored folders from the
  ``semantic_table_quality_metrics`` counts and pass rate per Q39 / MI-20).

The pattern uses the closed difficulty vocabulary defined in
``docs/stage1-vendor-identity/dataset-layout.md`` (``easy`` / ``medium`` /
``hard``). The pattern is compiled at module load; recompilation per call
would re-validate the rule for every folder name encountered during corpus
validation.
"""

from __future__ import annotations

import re
from typing import Final

CANONICAL_FOLDER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^inv_\d{3}_(easy|medium|hard)$"
)
"""Compiled regex for the canonical scored-corpus folder allowlist.

Anchored on both ends; case-sensitive. Default-exclude semantics — any
unrecognized name is treated as calibration / test-fixture material and is
never silently scored.
"""


def is_scored_corpus_folder(folder_basename: str) -> bool:
    """Return ``True`` iff ``folder_basename`` is a scored corpus folder.

    The check is a full-match against :data:`CANONICAL_FOLDER_PATTERN`. The
    rule is default-exclude per Q23 / MI-21 / SC-009: an unrecognized name
    (including any extra suffix such as ``inv_024_hard_degraded_body``)
    returns ``False``.

    Args:
        folder_basename: The bare folder name (e.g. ``"inv_001_hard"``); not a
            path. Callers should pass ``Path(folder).name`` rather than the
            full path so the rule operates on the leaf component only.

    Returns:
        ``True`` if the basename fully matches the canonical pattern;
        ``False`` otherwise (calibration / test-fixture material).
    """
    return CANONICAL_FOLDER_PATTERN.fullmatch(folder_basename) is not None
