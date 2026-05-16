"""End-to-end router orchestrator.

``run`` wires the pure modules in this package into a single pass:

    load_and_validate → compute_checks → compute_scores → apply_rules
                      → assemble artifact → validate + atomic write

Pure functions live in ``checks.py``, ``scores.py``, ``rules.py``; the only
I/O is in ``input_loader.py`` and ``artifact.py``. This module is the seam
between them.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from dartwing_ocr.router.artifact import assemble_and_write
from dartwing_ocr.router.checks import compute_checks
from dartwing_ocr.router.input_loader import load_and_validate
from dartwing_ocr.router.rules import apply_rules
from dartwing_ocr.router.scores import compute_scores

_DEFAULT_INPUT_FILE = "edge_extraction_output.json"

_CONSENSUS_SUMMARY = {
    "mode": "single_voter_baseline",
    "agreement_level": "not_applicable",
}


def _utc_now_z_second() -> str:
    """Return ``YYYY-MM-DDThh:mm:ssZ`` in UTC per research Decision 8."""
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_artifact(
    *,
    input_dict: dict,
    checks: dict,
    scores: dict,
    rule_result,
    pipeline_version: str,
    policy_version: str,
    contract_set_version: str,
    processed_at: str,
) -> dict:
    """Assemble the routing_decision dict in the schema's required key order."""
    return {
        "contract_set_version": contract_set_version,
        "pipeline_version": pipeline_version,
        "policy_version": policy_version,
        "document_id": input_dict["document_id"],
        "processed_at": processed_at,
        "status": rule_result.status,
        "decision": rule_result.decision,
        "consensus_summary": dict(_CONSENSUS_SUMMARY),
        "scores": scores,
        "checks": checks,
        "review_status": {
            "manual_review_required": rule_result.manual_review_required,
            "review_reason": rule_result.review_reason,
        },
        "reasons": list(rule_result.reasons),
    }


def run(
    folder: str | Path,
    *,
    pipeline_version: str,
    policy_version: str,
    input_file: str = _DEFAULT_INPUT_FILE,
    contract_set_version: str | None = None,
    now_fn=_utc_now_z_second,
) -> tuple[Path, dict]:
    """Route one per-document folder.

    Returns ``(artifact_path, artifact_dict)`` on success. Exceptions from
    ``load_and_validate`` / ``assemble_and_write`` propagate unchanged so the
    CLI surface can map them to exit codes.
    """
    folder = Path(folder)
    input_path = folder / input_file

    input_dict = load_and_validate(
        input_path,
        contract_set_version=contract_set_version,
    )
    checks = compute_checks(input_dict)
    scores = compute_scores(input_dict)
    rule_result = apply_rules(checks, scores, input_dict)

    artifact = _build_artifact(
        input_dict=input_dict,
        checks=checks,
        scores=scores,
        rule_result=rule_result,
        pipeline_version=pipeline_version,
        policy_version=policy_version,
        contract_set_version=input_dict["contract_set_version"],
        processed_at=now_fn(),
    )

    path = assemble_and_write(folder, artifact)
    return path, artifact
