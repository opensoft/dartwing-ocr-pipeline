"""Runtime quality_status derivation (T060, R-023.20).

Reads the evidence-gate state from feature 014/020 preprocessing's
``run_summary["evidence_gate_documents"][<document_id>]["state"]`` field and
the ``manual_review_required`` flag from the assembled
``final_structured_payload.json``. Calls into ``quality_status.derive_quality_status``
to produce the final ``(QualityStatus, QualityStatusSource)`` pair.

Used by the orchestrator on the success path; respects the bi-conditional
invariant that quality is non-null IFF ``runtime_outcome == "success"``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from dartwing_ocr.gpu_demo.enums import QualityStatus, QualityStatusSource
from dartwing_ocr.gpu_demo.quality_status import (
    EvaluatorVerdict,
    derive_quality_status,
)


def _read_final_payload_manual_review(folder: Path) -> bool:
    """Read ``manual_review_required`` from final_structured_payload.json.

    Defaults to ``True`` on parse failure — preserves safety (manual review
    is never silently skipped).
    """
    path = folder / "final_structured_payload.json"
    if not path.exists():
        return True
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    value = body.get("manual_review_required") if isinstance(body, dict) else None
    return bool(value) if isinstance(value, bool) else True


def _read_gate_state_from_run_summary(
    preprocess_run_summary: Optional[dict[str, Any]],
    document_id: str,
) -> str:
    """Extract the evidence-gate state for the given document.

    Returns one of ``"sufficient"`` / ``"borderline"`` / ``"insufficient"``
    when feature 020's run_summary v0.1.7 surfaces a usable verdict.
    Defaults to ``"insufficient"`` when the verdict is missing (safety).
    """
    if not isinstance(preprocess_run_summary, dict):
        return "insufficient"
    documents = preprocess_run_summary.get("evidence_gate_documents")
    if not isinstance(documents, dict):
        return "insufficient"
    entry = documents.get(document_id)
    if not isinstance(entry, dict):
        return "insufficient"
    state = entry.get("state")
    if isinstance(state, str) and state in {"sufficient", "borderline", "insufficient"}:
        return state
    return "insufficient"


def derive(
    *,
    document_folder: Path,
    document_id: str,
    preprocess_run_summary: Optional[dict[str, Any]],
    evaluator_result: Optional[EvaluatorVerdict] = None,
) -> tuple[QualityStatus, QualityStatusSource]:
    """Compute the final (QualityStatus, QualityStatusSource) pair.

    Pulls the evidence-gate state from the in-process preprocessing run_summary
    (passed by the orchestrator) and reads ``manual_review_required`` from
    the on-disk final_structured_payload.json. Optional evaluator verdict
    augments per R-023.20's downgrade-only rule.
    """
    gate_state = _read_gate_state_from_run_summary(preprocess_run_summary, document_id)
    manual_review_required = _read_final_payload_manual_review(document_folder)
    return derive_quality_status(
        gate_state=gate_state,
        manual_review_required=manual_review_required,
        evaluator_result=evaluator_result,
    )
