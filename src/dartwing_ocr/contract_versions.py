"""Shared contract-set version helpers for stage 1 artifacts."""

from __future__ import annotations

from typing import Any

from dartwing_ocr.validator.loader import (
    ContractSetCorruptError,
    ContractSetNotFoundError,
    load_contract_set,
)
from dartwing_ocr.validator.version import InvalidSemverError, parse_semver

ACTIVE_CONTRACT_SET_VERSION = "1.2.0"
STAGE1_CONTRACT_MAJOR = 1


class ContractVersionError(ValueError):
    """Raised when an artifact declares an unsupported contract set."""


def require_stage1_contract_version(value: Any, *, artifact_label: str) -> str:
    """Return ``value`` when it is an installed stage 1 v1.x contract set."""
    if not isinstance(value, str):
        raise ContractVersionError(
            f"{artifact_label} declares contract_set_version={value!r}; "
            "expected a semver string"
        )
    try:
        major, _, _ = parse_semver(value)
    except InvalidSemverError as exc:
        raise ContractVersionError(
            f"{artifact_label} declares contract_set_version={value!r}; "
            "expected a semver string"
        ) from exc
    if major != STAGE1_CONTRACT_MAJOR:
        raise ContractVersionError(
            f"{artifact_label} declares contract_set_version={value!r}; "
            f"expected stage 1 v{STAGE1_CONTRACT_MAJOR}.x"
        )
    try:
        load_contract_set(value)
    except (ContractSetNotFoundError, ContractSetCorruptError) as exc:
        raise ContractVersionError(
            f"{artifact_label} declares contract_set_version={value!r}, "
            "but that contract set is not installed"
        ) from exc
    return value


def require_matching_contract_version(
    *,
    found: str,
    expected: str | None,
    artifact_label: str,
) -> str:
    """Validate an optional caller-selected contract version against input."""
    if expected is None:
        return found
    expected = require_stage1_contract_version(
        expected, artifact_label="requested contract set"
    )
    if found != expected:
        raise ContractVersionError(
            f"{artifact_label} declares contract_set_version={found!r}; "
            f"requested contract_set_version={expected!r}"
        )
    return found
