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

from ledgerlinc_ocr.validator.artifact import validate_artifact
from ledgerlinc_ocr.validator.cross_artifact import (
    check_evidence_references,
    check_provenance_triad,
)
from ledgerlinc_ocr.validator.loader import ContractSet, load_contract_set
from ledgerlinc_ocr.validator.report import (
    ArtifactName,
    Severity,
    ValidationOutcome,
    Violation,
    ViolationCode,
)

_ARTIFACT_FILENAMES: dict[str, ArtifactName] = {
    "preprocess_output.json": ArtifactName.PREPROCESS_OUTPUT,
    "edge_extraction_output.json": ArtifactName.EDGE_EXTRACTION_OUTPUT,
    "routing_decision.json": ArtifactName.ROUTING_DECISION,
    "final_structured_payload.json": ArtifactName.FINAL_STRUCTURED_PAYLOAD,
    "evaluation_document.json": ArtifactName.EVALUATION_DOCUMENT,
    "expected.json": ArtifactName.EXPECTED,
}


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
                field_path="/source.pdf",
                violation_code=ViolationCode.FOLDER_SOURCE_PDF_UNREADABLE,
                reason=f"source.pdf could not be stat'd: {exc}",
                expected="FR-003 readable source.pdf",
                source_file=str(path),
            )
        ]
    if size == 0:
        return [
            Violation(
                severity=Severity.ERROR,
                target=target,
                field_path="/source.pdf",
                violation_code=ViolationCode.FOLDER_SOURCE_PDF_UNREADABLE,
                reason="source.pdf is empty (0 bytes).",
                expected="FR-003 readable source.pdf",
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
                field_path="/source.pdf",
                violation_code=ViolationCode.FOLDER_SOURCE_PDF_UNREADABLE,
                reason=f"source.pdf failed structural parse: {summary}.",
                expected="FR-003 readable source.pdf",
                source_file=str(path),
            )
        ]
    return []


def _looks_pipeline_generated(doc: dict[str, Any] | None) -> bool:
    """A file is considered pipeline-generated if it carries both pipeline_version
    and contract_set_version, suggesting it was written by the pipeline rather
    than hand-authored by an operator."""
    if not isinstance(doc, dict):
        return False
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
    expected_doc = _load_expected(folder / "expected.json")
    difficulty = None
    if expected_doc is not None and isinstance(expected_doc, dict):
        d = expected_doc.get("difficulty")
        if isinstance(d, str):
            difficulty = d
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
        doc = present_artifacts.get(_ARTIFACT_FILENAMES[filename])
        if _looks_pipeline_generated(doc):
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
