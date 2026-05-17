"""Contract-set loader + artifact schema validation (reuses dartwing_ocr.validator)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from dartwing_ocr.validator.loader import ArtifactName, ContractSet, load_contract_set

from dartwing_ocr.evaluator.exceptions import SchemaValidationError
from dartwing_ocr.evaluator.scoring import CONTRACT_SET_VERSION


@lru_cache(maxsize=4)
def get_contract_set(version: str = CONTRACT_SET_VERSION) -> ContractSet:
    """Load and cache the frozen contract set at `version`."""
    return load_contract_set(version)


@lru_cache(maxsize=32)
def _schema_for(artifact: ArtifactName, version: str) -> dict[str, Any]:
    schema_path = get_contract_set(version).artifact_schemas[artifact]
    with schema_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_expected_schema(version: str = CONTRACT_SET_VERSION) -> dict[str, Any]:
    return _schema_for(ArtifactName.EXPECTED, version)


def load_final_payload_schema(version: str = CONTRACT_SET_VERSION) -> dict[str, Any]:
    return _schema_for(ArtifactName.FINAL_STRUCTURED_PAYLOAD, version)


def load_evaluation_document_schema(version: str = CONTRACT_SET_VERSION) -> dict[str, Any]:
    return _schema_for(ArtifactName.EVALUATION_DOCUMENT, version)


def load_evaluation_run_summary_schema(version: str = CONTRACT_SET_VERSION) -> dict[str, Any]:
    return _schema_for(ArtifactName.EVALUATION_RUN_SUMMARY, version)


def validate_against_schema(
    instance: Any,
    schema: dict[str, Any],
    *,
    source: Path | str,
    artifact_label: str,
) -> None:
    """Validate `instance` against `schema`. Raise SchemaValidationError on any violation."""
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if not errors:
        return
    messages = []
    for err in errors:
        pointer = "/" + "/".join(str(p) for p in err.absolute_path)
        messages.append(f"{pointer or '/'}: {err.message}")
    raise SchemaValidationError(
        f"{artifact_label} at {source} failed schema validation:\n  "
        + "\n  ".join(messages)
    )
