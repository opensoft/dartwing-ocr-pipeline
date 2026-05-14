"""Tier 2 cross-artifact rules.

These rules cannot be expressed cleanly in JSON Schema because they span
multiple artifact files or require comparing values across them.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dartwing_ocr.validator.report import (
    ArtifactName,
    Severity,
    Violation,
    ViolationCode,
)


def check_provenance_triad(
    artifacts: dict[ArtifactName, dict[str, Any]],
    *,
    target: str,
    source_files: dict[ArtifactName, Path] | None = None,
) -> list[Violation]:
    relevant: dict[ArtifactName, dict[str, Any]] = {}
    for name in (
        ArtifactName.EXPECTED,
        ArtifactName.EDGE_EXTRACTION_OUTPUT,
        ArtifactName.ROUTING_DECISION,
        ArtifactName.FINAL_STRUCTURED_PAYLOAD,
    ):
        if name in artifacts:
            relevant[name] = artifacts[name]
    if len(relevant) < 2:
        return []

    source_files = source_files or {}
    findings: list[Violation] = []
    facts: dict[ArtifactName, dict[str, Any]] = {}
    for name, doc in relevant.items():
        facts[name] = _extract_triad_facts(name, doc)

    presents = {name: f["present"] for name, f in facts.items() if f["present"] is not None}
    inferreds = {name: f["inferred"] for name, f in facts.items() if f["inferred"] is not None}
    reviews = {name: f["manual_review_required"] for name, f in facts.items() if f["manual_review_required"] is not None}
    reasons = {name: f["review_reason"] for name, f in facts.items() if "review_reason" in f}

    def _add(reason: str, field_path: str, touched: set[ArtifactName]) -> None:
        src = None
        for n in touched:
            if n in source_files:
                src = str(source_files[n])
                break
        findings.append(
            Violation(
                severity=Severity.ERROR,
                target=target,
                field_path=field_path,
                violation_code=ViolationCode.PROVENANCE_TRIAD_INCONSISTENT,
                reason=reason,
                expected="FR-035 provenance triad cross-artifact",
                source_file=src,
            )
        )

    if len(set(presents.values())) > 1:
        _add(
            "company_name.present disagrees across artifacts: "
            + ", ".join(f"{n.value}={v}" for n, v in presents.items()),
            "/vendor_candidate/company_name/present",
            set(presents.keys()),
        )
    if len(set(inferreds.values())) > 1:
        _add(
            "company_name.inferred disagrees across artifacts: "
            + ", ".join(f"{n.value}={v}" for n, v in inferreds.items()),
            "/vendor_candidate/company_name/inferred",
            set(inferreds.keys()),
        )
    if len(set(reviews.values())) > 1:
        _add(
            "manual_review_required disagrees across artifacts: "
            + ", ".join(f"{n.value}={v}" for n, v in reviews.items()),
            "/review_status/manual_review_required",
            set(reviews.keys()),
        )
    if len({reasons[k] for k in reasons}) > 1:
        _add(
            "review_reason disagrees across artifacts: "
            + ", ".join(f"{n.value}={v!r}" for n, v in reasons.items()),
            "/review_status/review_reason",
            set(reasons.keys()),
        )

    if presents and all(v is False for v in presents.values()):
        if inferreds and not all(v is True for v in inferreds.values()):
            _add(
                "present=false requires inferred=true across all artifacts.",
                "/vendor_candidate/company_name/inferred",
                set(inferreds.keys()),
            )
        if reviews and not all(v is True for v in reviews.values()):
            _add(
                "present=false requires manual_review_required=true across all artifacts.",
                "/review_status/manual_review_required",
                set(reviews.keys()),
            )

    return findings


def _extract_triad_facts(
    name: ArtifactName, doc: dict[str, Any]
) -> dict[str, Any]:
    present: bool | None = None
    inferred: bool | None = None
    mrr: bool | None = None
    reason: Any = "<unset>"

    if name is ArtifactName.EXPECTED:
        evc = doc.get("expected_vendor_candidate") or {}
        cn = evc.get("company_name") or {}
        er = doc.get("expected_review") or {}
        present = cn.get("present") if "present" in cn else None
        inferred = cn.get("inferred") if "inferred" in cn else None
        mrr = er.get("manual_review_required") if "manual_review_required" in er else None
        reason = er.get("review_reason") if "review_reason" in er else "<unset>"
    else:
        vc = doc.get("vendor_candidate") or {}
        cn = vc.get("company_name") or {}
        rs = doc.get("review_status") or {}
        present = cn.get("present") if "present" in cn else None
        inferred = cn.get("inferred") if "inferred" in cn else None
        mrr = rs.get("manual_review_required") if "manual_review_required" in rs else None
        reason = rs.get("review_reason") if "review_reason" in rs else "<unset>"

    out: dict[str, Any] = {
        "present": present,
        "inferred": inferred,
        "manual_review_required": mrr,
    }
    if reason != "<unset>":
        out["review_reason"] = reason
    return out


def check_evidence_references(
    preprocess: dict[str, Any],
    extraction: dict[str, Any],
    *,
    target: str,
    source_file: Path | None = None,
) -> list[Violation]:
    available = _collect_evidence_ids(preprocess)
    used = _collect_used_evidence(extraction)
    findings: list[Violation] = []
    seen: set[tuple[str, str]] = set()
    for eid, field_path in used:
        if eid in available:
            continue
        key = (eid, field_path)
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            Violation(
                severity=Severity.ERROR,
                target=target,
                field_path=field_path,
                violation_code=ViolationCode.EVIDENCE_REFERENCE_UNRESOLVED,
                reason=(
                    f"evidence id {eid!r} does not resolve to any block_id or "
                    "line_id in the companion preprocess_output."
                ),
                expected="FR-008 stable evidence identifiers",
                source_file=str(source_file) if source_file else None,
            )
        )
    return findings


def _collect_evidence_ids(preprocess: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for page in preprocess.get("pages") or []:
        for block in page.get("blocks") or []:
            if "block_id" in block:
                ids.add(block["block_id"])
        for line in page.get("raw_ocr_lines") or []:
            if "line_id" in line:
                ids.add(line["line_id"])
    return ids


def _collect_used_evidence(
    extraction: dict[str, Any],
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def _walk(node: Any, path: list[str]) -> None:
        if isinstance(node, dict):
            ev = node.get("evidence")
            if isinstance(ev, list):
                for i, eid in enumerate(ev):
                    if isinstance(eid, str):
                        out.append((eid, "/" + "/".join(path + ["evidence", str(i)])))
            for k, v in node.items():
                if k == "evidence":
                    continue
                _walk(v, path + [str(k)])
        elif isinstance(node, list):
            for i, v in enumerate(node):
                _walk(v, path + [str(i)])

    _walk(extraction, [])
    return out


def check_document_count(
    run_summary: dict[str, Any],
    *,
    target: str,
    source_file: Path | None = None,
) -> list[Violation]:
    """T065: evaluation_run_summary.document_count must equal len(documents[])."""
    declared = run_summary.get("document_count")
    documents = run_summary.get("documents")
    if not isinstance(declared, int) or not isinstance(documents, list):
        return []  # Tier 1 schema will already have flagged the malformed shape.
    if declared == len(documents):
        return []
    return [
        Violation(
            severity=Severity.ERROR,
            target=target,
            field_path="/document_count",
            violation_code=ViolationCode.DOCUMENT_COUNT_MISMATCH,
            reason=(
                f"declared document_count={declared} disagrees with documents[] "
                f"length={len(documents)}."
            ),
            expected="edge case #9 document_count consistency",
            source_file=str(source_file) if source_file else None,
        )
    ]
