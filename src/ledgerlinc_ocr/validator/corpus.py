"""Corpus validator.

Walks the corpus root, runs `validate_folder` on every per-document folder
that matches the folder-name pattern, validates the root-level
`evaluation_run_summary.json` if present, and aggregates into a single
`ValidationOutcome` with `sub_reports`.
"""
from __future__ import annotations

import re
from pathlib import Path

from ledgerlinc_ocr.validator.artifact import validate_artifact
from ledgerlinc_ocr.validator.folder import validate_folder
from ledgerlinc_ocr.validator.loader import ContractSet, load_contract_set
from ledgerlinc_ocr.validator.report import (
    ArtifactName,
    ValidationOutcome,
)

_FOLDER_PATTERN = re.compile(r"^inv_\d{3}_(easy|medium|hard|missing_name)$")


def validate_corpus(
    root: str | Path,
    *,
    version: str | None = None,
    fail_fast: bool = False,
    contract_set: ContractSet | None = None,
) -> ValidationOutcome:
    root = Path(root)
    if contract_set is None:
        contract_set = load_contract_set(version)
    target = f"corpus:{root}"
    sub_reports: list[ValidationOutcome] = []

    if not root.is_dir():
        return ValidationOutcome.build(
            contract_set_version_checked=contract_set.version,
            target_summary=target,
            findings=[],
            sub_reports=[],
        )

    # Per-document folders in sorted order for determinism
    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        if not _FOLDER_PATTERN.match(child.name):
            continue
        outcome = validate_folder(child, contract_set=contract_set)
        sub_reports.append(outcome)
        if fail_fast and not outcome.passed:
            break

    summary_path = root / "evaluation_run_summary.json"
    if summary_path.is_file():
        sub_reports.append(
            validate_artifact(
                summary_path,
                ArtifactName.EVALUATION_RUN_SUMMARY,
                contract_set=contract_set,
            )
        )

    return ValidationOutcome.build(
        contract_set_version_checked=contract_set.version,
        target_summary=target,
        findings=[],
        sub_reports=sub_reports,
    )
