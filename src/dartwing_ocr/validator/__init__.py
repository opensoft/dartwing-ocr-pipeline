"""Public surface for the Dartwing stage 1 contract validator.

See `specs/001-freeze-schemas-folder-contracts/contracts/module-api.md` for
the stability guarantees of these names.
"""
from __future__ import annotations

from pathlib import Path

from dartwing_ocr.validator.artifact import validate_artifact
from dartwing_ocr.validator.loader import (
    ContractSet,
    ContractSetCorruptError,
    ContractSetNotFoundError,
    InvalidArtifactNameError,
    load_contract_set,
)
from dartwing_ocr.validator.report import (
    ArtifactName,
    Severity,
    ValidationOutcome,
    Violation,
    ViolationCode,
)


def validate_folder(
    folder: str | Path,
    *,
    version: str | None = None,
) -> ValidationOutcome:
    """See contracts/module-api.md. Implemented in US2 / T054."""
    from dartwing_ocr.validator.folder import validate_folder as _impl
    return _impl(folder, version=version)


def validate_corpus(
    root: str | Path,
    *,
    version: str | None = None,
    fail_fast: bool = False,
) -> ValidationOutcome:
    """See contracts/module-api.md. Implemented in US3 / T068."""
    from dartwing_ocr.validator.corpus import validate_corpus as _impl
    return _impl(root, version=version, fail_fast=fail_fast)


__all__ = [
    "ArtifactName",
    "ContractSet",
    "ContractSetCorruptError",
    "ContractSetNotFoundError",
    "InvalidArtifactNameError",
    "Severity",
    "ValidationOutcome",
    "Violation",
    "ViolationCode",
    "load_contract_set",
    "validate_artifact",
    "validate_folder",
    "validate_corpus",
]
