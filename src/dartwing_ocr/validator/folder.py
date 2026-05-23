"""Folder-layout validator.

Consumes `folder.schema.json` as a JSON configuration (not a JSON Schema of a
file) and checks:
  - folder-name pattern (`inv_<NNN>_<difficulty>/`)
  - required input files (conditional on difficulty per FR-029)
  - reserved-filename collisions (a human-authored file using a name reserved
    for the pipeline is flagged)
  - that any pipeline/evaluator artifacts present also validate
  - the provenance triad across all pipeline artifacts that are present
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dartwing_ocr.evaluator.filenames import EVAL_DOC_FILENAME
from dartwing_ocr.pipeline.filenames import (
    EDGE_EXTRACTION_OUTPUT_FILENAME,
    FINAL_STRUCTURED_PAYLOAD_FILENAME,
    PREPROCESS_OUTPUT_FILENAME,
    ROUTING_DECISION_FILENAME,
)
from dartwing_ocr.validator.artifact import validate_artifact
from dartwing_ocr.validator.cross_artifact import (
    check_evidence_references,
    check_provenance_triad,
)
from dartwing_ocr.validator.loader import ContractSet, load_contract_set
from dartwing_ocr.validator.report import (
    ArtifactName,
    Severity,
    ValidationOutcome,
    Violation,
    ViolationCode,
)
from dartwing_ocr.validator.semantic_table_truth import (
    SIDECAR_FILENAME,
    SidecarErrorKind,
    validate_sidecar,
)

_EXPECTED_FILENAME = "expected.json"
_SOURCE_PDF_FIELD_PATH = "/source.pdf"
_FR_003_EXPECTED = "FR-003 readable source.pdf"

_ARTIFACT_FILENAMES: dict[str, ArtifactName] = {
    PREPROCESS_OUTPUT_FILENAME: ArtifactName.PREPROCESS_OUTPUT,
    EDGE_EXTRACTION_OUTPUT_FILENAME: ArtifactName.EDGE_EXTRACTION_OUTPUT,
    ROUTING_DECISION_FILENAME: ArtifactName.ROUTING_DECISION,
    FINAL_STRUCTURED_PAYLOAD_FILENAME: ArtifactName.FINAL_STRUCTURED_PAYLOAD,
    EVAL_DOC_FILENAME: ArtifactName.EVALUATION_DOCUMENT,
    _EXPECTED_FILENAME: ArtifactName.EXPECTED,
    "evidence_packet.json": ArtifactName.EVIDENCE_PACKET,
}

# Artifacts that carry `contract_set_version` but no `pipeline_version`
# (they are not pipeline_versioned in contract_set.json). Presence-collision
# detection must still treat them as pipeline-generated output.
_CONTRACT_ONLY_STAMPED: frozenset[ArtifactName] = frozenset(
    {ArtifactName.EVIDENCE_PACKET}
)


@dataclass(frozen=True)
class FolderContract:
    folder_name_pattern: re.Pattern[str]
    difficulty_values: frozenset[str]
    unconditional_files: tuple[str, ...]
    notes_md_by_difficulty: dict[str, str]
    reserved_generated_filenames: frozenset[str]
    corpus_root_files: frozenset[str]


def _load_folder_contract(contract_set: ContractSet) -> FolderContract:
    data = json.loads(contract_set.folder_schema.read_text(encoding="utf-8"))
    return FolderContract(
        folder_name_pattern=re.compile(data["folder_name_pattern"]),
        difficulty_values=frozenset(data["difficulty_values"]),
        unconditional_files=tuple(data["required_files"]["unconditional"]),
        notes_md_by_difficulty=dict(data["required_files"]["notes_md_by_difficulty"]),
        reserved_generated_filenames=frozenset(data["reserved_generated_filenames"]),
        corpus_root_files=frozenset(data["corpus_root_files"]),
    )


def _parse_folder_name(folder: Path, pattern: re.Pattern[str]) -> tuple[bool, str | None]:
    m = pattern.match(folder.name)
    if not m:
        return False, None
    return True, m.group(1)


def _load_expected(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _check_source_pdf_readable(path: Path, *, target: str) -> list[Violation]:
    """Enforce FR-003 readable source.pdf at the structural-parse level.

    Emits one Severity.ERROR with FOLDER_SOURCE_PDF_UNREADABLE if the file is
    zero bytes or fails to parse with pypdf. Caller ensures the file exists —
    when source.pdf is absent, FOLDER_MISSING_REQUIRED_FILE already fires and
    this check is skipped to avoid a duplicate finding for the same issue.
    """
    try:
        size = path.stat().st_size
    except OSError as exc:
        return [
            Violation(
                severity=Severity.ERROR,
                target=target,
                field_path=_SOURCE_PDF_FIELD_PATH,
                violation_code=ViolationCode.FOLDER_SOURCE_PDF_UNREADABLE,
                reason=f"source.pdf could not be stat'd: {exc}",
                expected=_FR_003_EXPECTED,
                source_file=str(path),
            )
        ]
    if size == 0:
        return [
            Violation(
                severity=Severity.ERROR,
                target=target,
                field_path=_SOURCE_PDF_FIELD_PATH,
                violation_code=ViolationCode.FOLDER_SOURCE_PDF_UNREADABLE,
                reason="source.pdf is empty (0 bytes).",
                expected=_FR_003_EXPECTED,
                source_file=str(path),
            )
        ]
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path), strict=False)
        _ = len(reader.pages)
    except Exception as exc:  # noqa: BLE001 — pypdf raises a variety of exception types
        summary = f"{type(exc).__name__}: {exc}"
        return [
            Violation(
                severity=Severity.ERROR,
                target=target,
                field_path=_SOURCE_PDF_FIELD_PATH,
                violation_code=ViolationCode.FOLDER_SOURCE_PDF_UNREADABLE,
                reason=f"source.pdf failed structural parse: {summary}.",
                expected=_FR_003_EXPECTED,
                source_file=str(path),
            )
        ]
    return []


_SIDECAR_KIND_TO_CODE: dict[SidecarErrorKind, str] = {
    SidecarErrorKind.DOCUMENT_ID_MISMATCH: ViolationCode.SIDECAR_DOCUMENT_ID_MISMATCH,
    SidecarErrorKind.ROW_VIOLATION: ViolationCode.SIDECAR_ROW_VIOLATION,
    SidecarErrorKind.SCHEMA_INVALID: ViolationCode.SIDECAR_SCHEMA_INVALID,
    SidecarErrorKind.JSON_INVALID: ViolationCode.SIDECAR_JSON_INVALID,
    SidecarErrorKind.MISSING_SIDECAR: ViolationCode.SIDECAR_ROW_VIOLATION,
}


def _sidecar_violations(folder: Path, target: str) -> list[Violation]:
    """Validate the optional semantic_table_truth.json sidecar (feature 022 / US1).

    When the file is absent, behavior is identical to v1.2.0 (FR-005). When
    present, every sidecar error is surfaced as a folder-level Violation with
    the appropriate ViolationCode so the existing ValidationOutcome machinery
    routes the error through the standard reporter.
    """
    sidecar_path = folder / SIDECAR_FILENAME
    if not sidecar_path.is_file():
        return []
    result = validate_sidecar(folder)
    out: list[Violation] = []
    for err in result.errors:
        code = _SIDECAR_KIND_TO_CODE.get(
            err.kind, ViolationCode.SIDECAR_ROW_VIOLATION
        )
        out.append(
            Violation(
                severity=Severity.ERROR,
                target=target,
                field_path=f"/{SIDECAR_FILENAME}",
                violation_code=code,
                reason=err.message,
                expected="FR-002 / FR-003 / FR-004 semantic_table_truth.json contract",
                source_file=str(sidecar_path),
            )
        )
    return out


def _looks_pipeline_generated(  # NOSONAR S3776 — pipeline-generated detection — flat conditions across each artifact stamp.
    doc: dict[str, Any] | None,
    artifact: ArtifactName | None = None,
) -> bool:
    """A file is considered pipeline-generated if it carries both pipeline_version
    and contract_set_version, suggesting it was written by the pipeline rather
    than hand-authored by an operator."""
    if not isinstance(doc, dict):
        return False
    if artifact in _CONTRACT_ONLY_STAMPED:
        return bool(doc.get("contract_set_version"))
    return bool(doc.get("pipeline_version")) and bool(doc.get("contract_set_version"))


def validate_folder(
    folder: str | Path,
    *,
    version: str | None = None,
    contract_set: ContractSet | None = None,
) -> ValidationOutcome:
    folder = Path(folder)
    if contract_set is None:
        contract_set = load_contract_set(version)
    fc = _load_folder_contract(contract_set)
    target = f"folder:{folder}"
    findings: list[Violation] = []
    sub_reports: list[ValidationOutcome] = []

    if not folder.is_dir():
        findings.append(
            Violation(
                severity=Severity.ERROR,
                target=target,
                violation_code=ViolationCode.FOLDER_MISSING_REQUIRED_FILE,
                reason=f"folder does not exist: {folder}",
                expected="FR-028 per-document folder",
            )
        )
        return ValidationOutcome.build(
            contract_set_version_checked=contract_set.version,
            target_summary=target,
            findings=findings,
        )

    matched, difficulty_from_name = _parse_folder_name(folder, fc.folder_name_pattern)
    if not matched:
        findings.append(
            Violation(
                severity=Severity.ERROR,
                target=target,
                violation_code=ViolationCode.FOLDER_NAME_INVALID,
                reason=(
                    f"folder name {folder.name!r} does not match "
                    f"{fc.folder_name_pattern.pattern}."
                ),
                expected="FR-028 folder naming convention",
            )
        )

    # Required unconditional files
    for req in fc.unconditional_files:
        if not (folder / req).is_file():
            findings.append(
                Violation(
                    severity=Severity.ERROR,
                    target=target,
                    field_path=f"/{req}",
                    violation_code=ViolationCode.FOLDER_MISSING_REQUIRED_FILE,
                    reason=f"required file {req!r} missing from folder.",
                    expected="FR-029 unconditional required files",
                )
            )

    source_pdf = folder / "source.pdf"
    if source_pdf.is_file():
        findings.extend(_check_source_pdf_readable(source_pdf, target=target))

    # Expected.json governs difficulty for conditional rules
    expected_doc = _load_expected(folder / _EXPECTED_FILENAME)
    difficulty = None
    if expected_doc is not None and isinstance(expected_doc, dict):
        d = expected_doc.get("difficulty")
        if isinstance(d, str):
            difficulty = d
        expected_document_id = expected_doc.get("document_id")
        if (
            matched
            and isinstance(expected_document_id, str)
            and expected_document_id != folder.name
        ):
            findings.append(
                Violation(
                    severity=Severity.ERROR,
                    target=target,
                    field_path="/expected.json#/document_id",
                    violation_code=ViolationCode.FOLDER_NAME_INVALID,
                    reason=(
                        f"expected.json document_id {expected_document_id!r} "
                        f"does not match folder name {folder.name!r}."
                    ),
                    expected="stage 1 document_id equals the full folder name",
                    source_file=str(folder / _EXPECTED_FILENAME),
                )
            )
    # Fall back on folder-name suffix if expected.json is missing or bad
    if difficulty is None:
        difficulty = difficulty_from_name
    if (
        difficulty
        and difficulty_from_name
        and difficulty != difficulty_from_name
    ):
        findings.append(
            Violation(
                severity=Severity.ERROR,
                target=target,
                field_path="/expected.json#/difficulty",
                violation_code=ViolationCode.FOLDER_NAME_INVALID,
                reason=(
                    f"folder suffix says {difficulty_from_name!r} but "
                    f"expected.json says {difficulty!r}."
                ),
                expected="FR-028 folder naming convention",
            )
        )

    # notes.md rule
    if difficulty in fc.notes_md_by_difficulty:
        mode = fc.notes_md_by_difficulty[difficulty]
        has_notes = (folder / "notes.md").is_file()
        if not has_notes and mode == "hard":
            findings.append(
                Violation(
                    severity=Severity.ERROR,
                    target=target,
                    field_path="/notes.md",
                    violation_code=ViolationCode.FOLDER_MISSING_REQUIRED_FILE,
                    reason=(
                        f"notes.md is required for difficulty {difficulty!r}."
                    ),
                    expected="FR-029 notes.md hard requirement",
                )
            )
        elif not has_notes and mode == "soft":
            findings.append(
                Violation(
                    severity=Severity.WARNING,
                    target=target,
                    field_path="/notes.md",
                    violation_code=ViolationCode.FOLDER_NOTES_MISSING_SOFT,
                    reason=(
                        f"notes.md is missing (soft requirement for difficulty "
                        f"{difficulty!r}); folder still passes."
                    ),
                    expected="FR-029 notes.md soft requirement",
                )
            )

    # Validate any pipeline/evaluator artifacts that are present
    present_artifacts: dict[ArtifactName, dict[str, Any]] = {}
    source_files: dict[ArtifactName, Path] = {}
    for filename, name in _ARTIFACT_FILENAMES.items():
        path = folder / filename
        if not path.is_file():
            continue
        outcome = validate_artifact(path, name, contract_set=contract_set)
        sub_reports.append(outcome)
        try:
            present_artifacts[name] = json.loads(path.read_text(encoding="utf-8"))
            source_files[name] = path
        except json.JSONDecodeError:
            # The artifact sub-report will have surfaced the parse issue via FR-036.
            pass

    # Reserved-filename collision detection
    for filename in fc.reserved_generated_filenames:
        path = folder / filename
        if not path.is_file():
            continue
        # If the file looks pipeline-generated (has pipeline_version +
        # contract_set_version), it is not a collision — just pipeline output.
        artifact_name = _ARTIFACT_FILENAMES.get(filename)
        doc = present_artifacts.get(artifact_name) if artifact_name else None
        if _looks_pipeline_generated(doc, artifact_name):
            continue
        findings.append(
            Violation(
                severity=Severity.ERROR,
                target=target,
                field_path=f"/{filename}",
                violation_code=ViolationCode.FOLDER_RESERVED_FILENAME_COLLISION,
                reason=(
                    f"{filename!r} is reserved for pipeline/evaluator output, "
                    "but the file does not carry pipeline_version + "
                    "contract_set_version stamps expected of a pipeline run."
                ),
                expected="FR-032 reserved filename handling",
                source_file=str(path),
            )
        )

    # Optional semantic_table_truth.json sidecar (feature 022 / US1).
    # When absent: behavior identical to v1.2.0 (FR-005). When present:
    # every sidecar error is surfaced as a folder-level Violation with the
    # appropriate ViolationCode mapping (validator-cli-contract.md exit
    # codes 3 / 4 / 5).
    findings.extend(_sidecar_violations(folder, target))

    # Cross-artifact rules across whatever is present
    if len(present_artifacts) >= 2:
        findings.extend(
            check_provenance_triad(
                present_artifacts, target=target, source_files=source_files
            )
        )
    if (
        ArtifactName.PREPROCESS_OUTPUT in present_artifacts
        and ArtifactName.EDGE_EXTRACTION_OUTPUT in present_artifacts
    ):
        findings.extend(
            check_evidence_references(
                present_artifacts[ArtifactName.PREPROCESS_OUTPUT],
                present_artifacts[ArtifactName.EDGE_EXTRACTION_OUTPUT],
                target=target,
                source_file=source_files.get(ArtifactName.EDGE_EXTRACTION_OUTPUT),
            )
        )

    return ValidationOutcome.build(
        contract_set_version_checked=contract_set.version,
        target_summary=target,
        findings=findings,
        sub_reports=sub_reports,
    )
