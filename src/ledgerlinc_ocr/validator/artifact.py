"""Artifact-level validation.

Tier 1 runs `jsonschema.Draft202012Validator` and translates each
`ValidationError` into a `Violation`. A small post-processing pass refines
codes based on field path (e.g. `SCHEMA_ENUM_VIOLATION` under `challenge_tags`
becomes `CHALLENGE_TAG_UNKNOWN`) and enforces a handful of rules that are
easier in Python than in JSON Schema (empty string in extracted value fields ⇒
`NULL_VS_EMPTY_STRING`, missing `pipeline_version` / `policy_version`).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ledgerlinc_ocr.validator.loader import (
    ContractSet,
    InvalidArtifactNameError,
    load_contract_set,
)
from ledgerlinc_ocr.validator.report import (
    ArtifactName,
    Severity,
    ValidationOutcome,
    Violation,
    ViolationCode,
)
from ledgerlinc_ocr.validator.version import is_compatible

_JSONSCHEMA_KEYWORD_TO_CODE: dict[str, str] = {
    "required": ViolationCode.SCHEMA_REQUIRED_MISSING,
    "type": ViolationCode.SCHEMA_TYPE_MISMATCH,
    "enum": ViolationCode.SCHEMA_ENUM_VIOLATION,
    "pattern": ViolationCode.SCHEMA_PATTERN_VIOLATION,
    "additionalProperties": ViolationCode.SCHEMA_ADDITIONAL_PROPERTIES,
    "unevaluatedProperties": ViolationCode.SCHEMA_ADDITIONAL_PROPERTIES,
    "const": ViolationCode.SCHEMA_ENUM_VIOLATION,
}


def _json_pointer(path_deque) -> str:
    parts = [str(p).replace("~", "~0").replace("/", "~1") for p in path_deque]
    return "/" + "/".join(parts) if parts else ""


def _refine_code(base_code: str, field_path: str, *, message: str) -> str:
    """Translate a raw schema-keyword code into a domain-specific code where obvious."""
    # challenge_tags list items → CHALLENGE_TAG_UNKNOWN
    if base_code == ViolationCode.SCHEMA_ENUM_VIOLATION and "/challenge_tags/" in field_path:
        return ViolationCode.CHALLENGE_TAG_UNKNOWN
    # tax_ids extra keys → TAX_ID_TYPE_INVALID
    if (
        base_code == ViolationCode.SCHEMA_ADDITIONAL_PROPERTIES
        and "/tax_ids" in field_path
    ):
        return ViolationCode.TAX_ID_TYPE_INVALID
    # Missing vote_metadata specifically (required-keyword failure at root)
    if (
        base_code == ViolationCode.SCHEMA_REQUIRED_MISSING
        and "'vote_metadata'" in message
    ):
        return ViolationCode.VOTE_METADATA_MISSING
    # Missing contract_set_version
    if (
        base_code == ViolationCode.SCHEMA_REQUIRED_MISSING
        and "'contract_set_version'" in message
    ):
        return ViolationCode.CONTRACT_SET_VERSION_MISSING
    # Missing pipeline_version
    if (
        base_code == ViolationCode.SCHEMA_REQUIRED_MISSING
        and "'pipeline_version'" in message
    ):
        return ViolationCode.PIPELINE_VERSION_MISSING
    # Missing policy_version
    if (
        base_code == ViolationCode.SCHEMA_REQUIRED_MISSING
        and "'policy_version'" in message
    ):
        return ViolationCode.POLICY_VERSION_MISSING
    # expected.* additionalProperties — predictions/confidence leaked in
    if (
        base_code == ViolationCode.SCHEMA_ADDITIONAL_PROPERTIES
        and "/expected_vendor_candidate" in field_path
    ):
        return ViolationCode.EXPECTED_HAS_PREDICTIONS
    return base_code


def _walk_empty_strings(
    node: Any, path: list[str], out: list[tuple[str, str]]
) -> None:
    """Collect empty-string leaves where ``""`` is being used as null.

    The contract-set null discipline applies to extracted scalar value slots
    such as ``vendor_candidate.phone.value``. It does not apply to evidence text
    slots in ``preprocess_output``: ``block.text`` and ``raw_ocr_lines[].text``
    are frozen as strings by the preprocess schema and may legitimately be
    empty when layout/OCR geometry produces no contained text.
    """
    if isinstance(node, dict):
        for k, v in node.items():
            safe_k = str(k).replace("~", "~0").replace("/", "~1")
            _walk_empty_strings(v, path + [safe_k], out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk_empty_strings(v, path + [str(i)], out)
    elif isinstance(node, str) and node == "" and path and path[-1] == "value":
        out.append(("/" + "/".join(path), ""))


def _missing_name_triad_violation(
    data: dict, target: str, source_file: Path | None
) -> Violation | None:
    vc = data.get("vendor_candidate") or {}
    cn = vc.get("company_name") or {}
    rs = data.get("review_status") or {}
    if cn.get("present") is not False:
        return None
    inferred_ok = cn.get("inferred") is True
    review_ok = rs.get("manual_review_required") is True
    if inferred_ok and review_ok:
        return None
    return Violation(
        severity=Severity.ERROR,
        target=target,
        field_path="/vendor_candidate/company_name",
        violation_code=ViolationCode.MISSING_NAME_TRIAD_VIOLATION,
        reason=(
            "company_name.present = false requires inferred = true AND "
            "review_status.manual_review_required = true."
        ),
        expected="FR-019 final payload missing-name triad",
        source_file=str(source_file) if source_file else None,
    )


def _review_reason_when_required(
    data: dict, target: str, source_file: Path | None
) -> Violation | None:
    rs = data.get("review_status") or {}
    if rs.get("manual_review_required") is True and rs.get("review_reason") in (None, ""):
        return Violation(
            severity=Severity.ERROR,
            target=target,
            field_path="/review_status/review_reason",
            violation_code=ViolationCode.REVIEW_REASON_NULL_WHEN_REQUIRED,
            reason=(
                "review_reason must be non-null when manual_review_required is true."
            ),
            expected="FR-017 routing_decision review_reason",
            source_file=str(source_file) if source_file else None,
        )
    return None


def _missing_name_triad_on_expected(
    data: dict, target: str, source_file: Path | None
) -> Violation | None:
    if data.get("difficulty") != "missing_name":
        return None
    evc = data.get("expected_vendor_candidate") or {}
    cn = evc.get("company_name") or {}
    er = data.get("expected_review") or {}
    ok = (
        cn.get("present") is False
        and cn.get("inferred") is True
        and er.get("manual_review_required") is True
        and er.get("review_reason") == "company_name_inferred"
    )
    if ok:
        return None
    return Violation(
        severity=Severity.ERROR,
        target=target,
        field_path="/expected_vendor_candidate/company_name",
        violation_code=ViolationCode.MISSING_NAME_TRIAD_VIOLATION,
        reason=(
            "difficulty=missing_name requires company_name.present=false, "
            "inferred=true, manual_review_required=true, "
            "review_reason='company_name_inferred'."
        ),
        expected="FR-024 expected missing_name triad",
        source_file=str(source_file) if source_file else None,
    )


def _version_violations(
    data: dict,
    contract_set: ContractSet,
    artifact: ArtifactName,
    target: str,
    source_file: Path | None,
) -> list[Violation]:
    out: list[Violation] = []
    csv = data.get("contract_set_version")
    if csv is None:
        out.append(
            Violation(
                severity=Severity.ERROR,
                target=target,
                field_path="/contract_set_version",
                violation_code=ViolationCode.CONTRACT_SET_VERSION_MISSING,
                reason="contract_set_version is required on every persisted artifact.",
                expected="FR-005a contract_set_version on every artifact",
                source_file=str(source_file) if source_file else None,
            )
        )
    elif not is_compatible(csv, contract_set.version):
        out.append(
            Violation(
                severity=Severity.ERROR,
                target=target,
                field_path="/contract_set_version",
                violation_code=ViolationCode.CONTRACT_SET_VERSION_INCOMPATIBLE,
                reason=(
                    f"artifact stamped {csv!r} is incompatible with validator "
                    f"target {contract_set.version!r} (major mismatch)."
                ),
                expected="FR-037 contract-set version compatibility",
                source_file=str(source_file) if source_file else None,
            )
        )
    if (
        artifact in contract_set.pipeline_versioned_artifacts
        and data.get("pipeline_version") in (None, "")
    ):
        out.append(
            Violation(
                severity=Severity.ERROR,
                target=target,
                field_path="/pipeline_version",
                violation_code=ViolationCode.PIPELINE_VERSION_MISSING,
                reason="pipeline_version is required on pipeline-produced artifacts.",
                expected="FR-004 pipeline_version",
                source_file=str(source_file) if source_file else None,
            )
        )
    if (
        artifact in contract_set.policy_versioned_artifacts
        and data.get("policy_version") in (None, "")
    ):
        out.append(
            Violation(
                severity=Severity.ERROR,
                target=target,
                field_path="/policy_version",
                violation_code=ViolationCode.POLICY_VERSION_MISSING,
                reason="policy_version is required on the routing_decision artifact.",
                expected="FR-005 policy_version",
                source_file=str(source_file) if source_file else None,
            )
        )
    return out


def _resolve_artifact(contract: ArtifactName | str) -> ArtifactName:
    if isinstance(contract, ArtifactName):
        return contract
    try:
        return ArtifactName(contract)
    except ValueError as exc:
        raise InvalidArtifactNameError(
            f"{contract!r} is not a known stage-1 artifact name."
        ) from exc


def _load_artifact_file(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_for(contract_set: ContractSet, artifact: ArtifactName) -> dict:
    schema_path = contract_set.artifact_schemas[artifact]
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _schema_findings(
    data: dict,
    schema: dict,
    *,
    target: str,
    source_file: Path | None,
) -> list[Violation]:
    findings: list[Violation] = []
    validator = Draft202012Validator(schema)
    for err in validator.iter_errors(data):
        raw_keyword = err.validator or ""
        base_code = _JSONSCHEMA_KEYWORD_TO_CODE.get(
            raw_keyword, ViolationCode.SCHEMA_GENERIC
        )
        field_path = _json_pointer(err.absolute_path)
        refined = _refine_code(base_code, field_path, message=err.message)
        findings.append(
            Violation(
                severity=Severity.ERROR,
                target=target,
                field_path=field_path,
                violation_code=refined,
                reason=err.message,
                expected=None,
                source_file=str(source_file) if source_file else None,
            )
        )
    return findings


def _null_vs_empty_string_findings(
    data: dict, *, target: str, source_file: Path | None
) -> list[Violation]:
    empties: list[tuple[str, str]] = []
    _walk_empty_strings(data, [], empties)
    findings: list[Violation] = []
    for field_path, _ in empties:
        findings.append(
            Violation(
                severity=Severity.ERROR,
                target=target,
                field_path=field_path,
                violation_code=ViolationCode.NULL_VS_EMPTY_STRING,
                reason="Absent values must be null, not empty strings.",
                expected="FR-003 null vs empty string",
                source_file=str(source_file) if source_file else None,
            )
        )
    return findings


def validate_artifact(
    path: str | Path,
    contract: ArtifactName | str,
    *,
    version: str | None = None,
    contract_set: ContractSet | None = None,
) -> ValidationOutcome:
    """Validate a single JSON artifact at `path` against its named contract."""
    artifact = _resolve_artifact(contract)
    # Load (or reload) the contract set when either no set was passed in or
    # the supplied set disagrees with an explicit `version` argument.
    if contract_set is None or (version is not None and contract_set.version != version):
        contract_set = load_contract_set(version)
    path = Path(path)
    data = _load_artifact_file(path)
    target = f"artifact:{artifact.value}"
    source_file = path
    findings: list[Violation] = []

    findings.extend(
        _version_violations(data, contract_set, artifact, target, source_file)
    )
    findings.extend(
        _schema_findings(
            data, _schema_for(contract_set, artifact), target=target, source_file=source_file
        )
    )
    findings.extend(
        _null_vs_empty_string_findings(data, target=target, source_file=source_file)
    )

    if artifact is ArtifactName.FINAL_STRUCTURED_PAYLOAD:
        v = _missing_name_triad_violation(data, target, source_file)
        if v:
            findings.append(v)
    if artifact is ArtifactName.ROUTING_DECISION:
        v = _review_reason_when_required(data, target, source_file)
        if v:
            findings.append(v)
    if artifact is ArtifactName.EXPECTED:
        v = _missing_name_triad_on_expected(data, target, source_file)
        if v:
            findings.append(v)
    if artifact is ArtifactName.EVALUATION_RUN_SUMMARY:
        from ledgerlinc_ocr.validator.cross_artifact import check_document_count
        findings.extend(
            check_document_count(data, target=target, source_file=source_file)
        )

    return ValidationOutcome.build(
        contract_set_version_checked=contract_set.version,
        target_summary=target,
        findings=findings,
    )
