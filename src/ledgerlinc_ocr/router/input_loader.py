"""Load and validate ``edge_extraction_output.json`` into an in-memory dict.

Implements the four hard-error conditions pinned by FR-003 and the CLI
contract:

- missing file or folder → ``MissingInputError`` (exit code 2)
- I/O / permission error on read → ``UnreadableInputError`` (exit code 2)
- non-JSON bytes or schema-invalid content → ``MalformedInputError`` (exit
  code 2)
- ``contract_set_version != "1.0.0"`` → ``VersionDriftError`` (exit code 2)

Exact-equal (not major-equal) version checking per research.md Decision 2.

No rule logic, no output, no filesystem mutation.
"""
from __future__ import annotations

import json
from pathlib import Path

from ledgerlinc_ocr.router.errors import (
    MalformedInputError,
    MissingInputError,
    UnreadableInputError,
    VersionDriftError,
)
from ledgerlinc_ocr.validator import validate_artifact

_EXPECTED_CONTRACT_SET_VERSION = "1.0.0"
_INPUT_ARTIFACT_NAME = "edge_extraction_output"


def load_and_validate(path: str | Path) -> dict:
    """Return the parsed, schema-valid input dict.

    ``path`` points to the ``edge_extraction_output.json`` file itself (not
    the folder). Callers in ``cli.py`` / ``pipeline.py`` are responsible for
    resolving the folder → file mapping.
    """
    path = Path(path)

    if not path.exists():
        raise MissingInputError(
            f"input file does not exist: {path}"
        )
    if not path.is_file():
        raise MissingInputError(
            f"input path is not a regular file: {path}"
        )

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise UnreadableInputError(
            f"could not read input file {path}: {exc}"
        ) from exc

    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnreadableInputError(
            f"input file {path} is not valid UTF-8: {exc}"
        ) from exc

    try:
        data = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise MalformedInputError(
            f"input file {path} is not valid JSON: {exc.msg} "
            f"(line {exc.lineno}, column {exc.colno})"
        ) from exc

    if not isinstance(data, dict):
        raise MalformedInputError(
            f"input file {path} must contain a JSON object at the top level; "
            f"got {type(data).__name__}"
        )

    version = data.get("contract_set_version")
    if version != _EXPECTED_CONTRACT_SET_VERSION:
        raise VersionDriftError(
            f"input file {path} reports contract_set_version={version!r}; "
            f"stage 1 router requires exactly "
            f"{_EXPECTED_CONTRACT_SET_VERSION!r}"
        )

    outcome = validate_artifact(
        path,
        _INPUT_ARTIFACT_NAME,
        version=_EXPECTED_CONTRACT_SET_VERSION,
    )
    if not outcome.passed:
        first = outcome.violations[0] if outcome.violations else None
        detail = (
            f"{first.violation_code} at {first.field_path}: {first.reason}"
            if first is not None
            else "unknown violation"
        )
        raise MalformedInputError(
            f"input file {path} failed edge_extraction_output.schema.json: "
            f"{detail} (total violations: {len(outcome.violations)})"
        )

    return data
