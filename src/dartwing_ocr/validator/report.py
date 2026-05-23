"""Violation, ValidationOutcome, and the stable violation-code vocabulary.

Matches `specs/001-freeze-schemas-folder-contracts/contracts/report.schema.json`
and `contracts/module-api.md` 1:1. Frozen at contract-set 1.0.0.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

REPORT_VERSION: str = "1.0.0"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class ArtifactName(str, Enum):
    PREPROCESS_OUTPUT = "preprocess_output"
    EDGE_EXTRACTION_OUTPUT = "edge_extraction_output"
    ROUTING_DECISION = "routing_decision"
    FINAL_STRUCTURED_PAYLOAD = "final_structured_payload"
    EXPECTED = "expected"
    EVALUATION_DOCUMENT = "evaluation_document"
    EVALUATION_RUN_SUMMARY = "evaluation_run_summary"
    EVIDENCE_PACKET = "evidence_packet"
    # Added at v1.3.0 (feature 022) — optional per-document sidecar consumed
    # by the semantic quality gate. The artifact has no `pipeline_version` or
    # `contract_set_version` stamp; it is hand-authored by a fixture author.
    SEMANTIC_TABLE_TRUTH = "semantic_table_truth"


class ViolationCode:
    """Stable machine codes. Referenced by harness/CI. Frozen at contract-set 1.0.0.

    Adding a new code is a minor version bump. Renaming or removing requires major.
    """

    # Tier 1 — JSON Schema mapping
    SCHEMA_REQUIRED_MISSING = "SCHEMA_REQUIRED_MISSING"
    SCHEMA_TYPE_MISMATCH = "SCHEMA_TYPE_MISMATCH"
    SCHEMA_ENUM_VIOLATION = "SCHEMA_ENUM_VIOLATION"
    SCHEMA_PATTERN_VIOLATION = "SCHEMA_PATTERN_VIOLATION"
    SCHEMA_ADDITIONAL_PROPERTIES = "SCHEMA_ADDITIONAL_PROPERTIES"
    SCHEMA_GENERIC = "SCHEMA_GENERIC"

    # Null-vs-empty-string (FR-003)
    NULL_VS_EMPTY_STRING = "NULL_VS_EMPTY_STRING"

    # Version stamping
    CONTRACT_SET_VERSION_MISSING = "CONTRACT_SET_VERSION_MISSING"
    CONTRACT_SET_VERSION_INCOMPATIBLE = "CONTRACT_SET_VERSION_INCOMPATIBLE"
    PIPELINE_VERSION_MISSING = "PIPELINE_VERSION_MISSING"
    POLICY_VERSION_MISSING = "POLICY_VERSION_MISSING"

    # Domain-specific
    CHALLENGE_TAG_UNKNOWN = "CHALLENGE_TAG_UNKNOWN"
    TAX_ID_TYPE_INVALID = "TAX_ID_TYPE_INVALID"
    VOTE_METADATA_MISSING = "VOTE_METADATA_MISSING"
    REVIEW_REASON_NULL_WHEN_REQUIRED = "REVIEW_REASON_NULL_WHEN_REQUIRED"
    EXPECTED_HAS_PREDICTIONS = "EXPECTED_HAS_PREDICTIONS"
    MISSING_NAME_TRIAD_VIOLATION = "MISSING_NAME_TRIAD_VIOLATION"

    # Tier 2 cross-artifact
    PROVENANCE_TRIAD_INCONSISTENT = "PROVENANCE_TRIAD_INCONSISTENT"
    EVIDENCE_REFERENCE_UNRESOLVED = "EVIDENCE_REFERENCE_UNRESOLVED"
    DOCUMENT_COUNT_MISMATCH = "DOCUMENT_COUNT_MISMATCH"

    # Folder
    FOLDER_MISSING_REQUIRED_FILE = "FOLDER_MISSING_REQUIRED_FILE"
    FOLDER_NOTES_MISSING_SOFT = "FOLDER_NOTES_MISSING_SOFT"
    FOLDER_NAME_INVALID = "FOLDER_NAME_INVALID"
    FOLDER_RESERVED_FILENAME_COLLISION = "FOLDER_RESERVED_FILENAME_COLLISION"
    FOLDER_SOURCE_PDF_UNREADABLE = "FOLDER_SOURCE_PDF_UNREADABLE"

    # Semantic table truth sidecar (feature 022 / US1)
    SIDECAR_DOCUMENT_ID_MISMATCH = "SIDECAR_DOCUMENT_ID_MISMATCH"
    SIDECAR_ROW_VIOLATION = "SIDECAR_ROW_VIOLATION"
    SIDECAR_SCHEMA_INVALID = "SIDECAR_SCHEMA_INVALID"
    SIDECAR_JSON_INVALID = "SIDECAR_JSON_INVALID"


_ALL_VIOLATION_CODES: frozenset[str] = frozenset(
    v for k, v in vars(ViolationCode).items()
    if not k.startswith("_") and isinstance(v, str)
)


def is_known_violation_code(code: str) -> bool:
    return code in _ALL_VIOLATION_CODES


class Violation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    severity: Severity
    target: str
    field_path: str = ""
    violation_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    reason: str = Field(min_length=1)
    expected: str | None = None
    source_file: str | None = None


class ValidationOutcomeCounts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    error: int = Field(ge=0)
    warning: int = Field(ge=0)


class ValidationOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_version: str = REPORT_VERSION
    contract_set_version_checked: str
    target_summary: str
    passed: bool
    violations: list[Violation] = Field(default_factory=list)
    warnings: list[Violation] = Field(default_factory=list)
    counts: ValidationOutcomeCounts
    sub_reports: list["ValidationOutcome"] = Field(default_factory=list)

    @classmethod
    def build(
        cls,
        *,
        contract_set_version_checked: str,
        target_summary: str,
        findings: list[Violation],
        sub_reports: list["ValidationOutcome"] | None = None,
    ) -> "ValidationOutcome":
        errors = [v for v in findings if v.severity == Severity.ERROR]
        warnings = [v for v in findings if v.severity == Severity.WARNING]
        sub = sub_reports or []
        sub_has_error = any(not s.passed for s in sub)
        return cls(
            contract_set_version_checked=contract_set_version_checked,
            target_summary=target_summary,
            passed=not errors and not sub_has_error,
            violations=errors,
            warnings=warnings,
            counts=ValidationOutcomeCounts(
                error=len(errors) + sum(s.counts.error for s in sub),
                warning=len(warnings) + sum(s.counts.warning for s in sub),
            ),
            sub_reports=sub,
        )

    def to_json(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def render_text(outcome: ValidationOutcome) -> str:
    """Human-readable CLI rendering of a ValidationOutcome."""
    lines: list[str] = []
    status = "PASS" if outcome.passed else "FAIL"
    lines.append(f"Target: {outcome.target_summary}")
    lines.append(f"Contract set: {outcome.contract_set_version_checked}")
    lines.append(
        f"Result: {status} ({outcome.counts.error} errors, {outcome.counts.warning} warnings)"
    )
    lines.append("")
    for finding in list(outcome.violations) + list(outcome.warnings):
        lines.append(f"  {finding.severity.value:<7} {finding.violation_code}")
        if finding.field_path:
            lines.append(f"         at {finding.field_path}")
        lines.append(f"         reason: {finding.reason}")
        if finding.expected:
            lines.append(f"         expected: {finding.expected}")
        if finding.source_file:
            lines.append(f"         file: {finding.source_file}")
    for sub in outcome.sub_reports:
        lines.append("")
        lines.append("--- sub-report ---")
        lines.append(render_text(sub))
    return "\n".join(lines)
