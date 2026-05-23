"""Validator for the optional ``semantic_table_truth.json`` per-document sidecar.

Feature 022 (US1). The sidecar carries authored table/body row truth consumed
by the deterministic semantic quality gate (separate from ``expected.json``,
which retains its vendor-identity-only shape — FR-006 / MI-23).

Validation pipeline (FR-002 / FR-003 / FR-004 + Clarifications Q11 / Q41 +
security-clarify Q-SEC-2/B):

1. Check the file exists at ``<folder>/semantic_table_truth.json``.
2. Parse it as JSON (``json.JSONDecodeError`` ⇒ ``JSON_INVALID``).
3. Validate against ``v1.3.0/semantic_table_truth.schema.json`` loaded via
   the existing :mod:`dartwing_ocr.validator.loader`.
4. Check ``document_id`` matches the folder basename (Q41 — error names
   BOTH values).
5. Check all ``row_id`` values are unique (Q11 — error names the duplicate
   value AND both indices).
6. Row-by-row checks reporting ALL violations, not just the first
   (Q41 + validator-cli-contract.md §Error message content).

Each violation lands as a :class:`SidecarError` on the returned
:class:`SemanticTruthValidationResult`. The CLI maps the highest-priority
error class to the exit code (3 / 4 / 5) per
``contracts/validator-cli-contract.md``.

This module is import-safe (no Paddle, no network — MI-1). It uses only
``re``, ``json``, ``pathlib``, ``dataclasses``, ``enum`` from stdlib plus
the already-declared ``jsonschema`` dependency.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Final

from jsonschema import Draft202012Validator

from dartwing_ocr.validator.loader import ContractSet, load_contract_set
from dartwing_ocr.validator.report import ArtifactName

SIDECAR_FILENAME: Final[str] = "semantic_table_truth.json"
"""Reserved-on-disk filename for the sidecar (data-model §1)."""

EXPECTED_CELL_DECIMAL_REGEX: Final[re.Pattern[str]] = re.compile(r"^\d+\.\d{2}$")
"""Validates sidecar-authored ``unit_price`` / ``amount`` (data-model §9 / Q9)."""

IDENTIFIER_SAFETY_REGEX: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9_-]{1,64}$"
)
"""Safety pattern for ``document_id`` and ``row_id`` (data-model §9 /
security-clarify Q-SEC-2/B). Alphanumeric + dash/underscore, ≤64 chars."""

SAFETY_PATTERN_TEXT: Final[str] = "^[A-Za-z0-9_-]{1,64}$"
"""Source-text of the safety pattern; embedded verbatim in error messages
so machine-readable parsers can grep for it (validator-cli-contract.md §Q41)."""


class SidecarErrorKind(str, Enum):
    """Closed enum identifying the class of a sidecar validation error.

    The CLI maps these to exit codes per validator-cli-contract.md:

    * ``MISSING_SIDECAR``      → exit 4
    * ``JSON_INVALID``         → exit 5
    * ``SCHEMA_INVALID``       → exit 5
    * ``DOCUMENT_ID_MISMATCH`` → exit 3
    * ``ROW_VIOLATION``        → exit 4
    """

    MISSING_SIDECAR = "MISSING_SIDECAR"
    JSON_INVALID = "JSON_INVALID"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    DOCUMENT_ID_MISMATCH = "DOCUMENT_ID_MISMATCH"
    ROW_VIOLATION = "ROW_VIOLATION"


@dataclass(frozen=True)
class SidecarError:
    """One sidecar validation finding.

    Attributes:
        kind: closed enum identifying the error class (drives CLI exit code).
        message: Q41-conforming, one-line, machine-readable error message.
            For ``DOCUMENT_ID_MISMATCH`` errors the message MUST name BOTH
            the declared value and the folder basename. For ``ROW_VIOLATION``
            errors it MUST name the offending ``row_id`` (or ``[<index>]``
            when ``row_id`` is absent / unparseable), the failed field, and a
            one-line reason.
        row_id: ``row_id`` value when known (``None`` for top-level errors).
        row_index: 0-based array index of the offending row when applicable.
        field: cell name (``unit_price``, ``amount``, …) when applicable.
    """

    kind: SidecarErrorKind
    message: str
    row_id: str | None = None
    row_index: int | None = None
    field: str | None = None


@dataclass(frozen=True)
class SemanticTruthValidationResult:
    """Aggregate result returned by :func:`validate_sidecar`.

    ``errors`` collects EVERY violation encountered — not just the first
    (Q41 / validator-cli-contract.md §Error message content). ``passed``
    reflects the conjunction: a sidecar passes iff no errors were
    recorded.
    """

    folder: Path
    sidecar_path: Path
    errors: tuple[SidecarError, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return not self.errors

    def exit_code(self) -> int:
        """Compute the CLI exit code per validator-cli-contract.md §
        ``validate semantic-truth``.

        Returns the lowest non-zero code among all encountered error
        classes. Order of precedence reflects the contract's table — code 3
        (document_id mismatch) is the lowest non-zero failure.
        """
        if not self.errors:
            return 0
        kinds = {e.kind for e in self.errors}
        if SidecarErrorKind.DOCUMENT_ID_MISMATCH in kinds:
            return 3
        if (
            SidecarErrorKind.ROW_VIOLATION in kinds
            or SidecarErrorKind.MISSING_SIDECAR in kinds
        ):
            return 4
        if (
            SidecarErrorKind.SCHEMA_INVALID in kinds
            or SidecarErrorKind.JSON_INVALID in kinds
        ):
            return 5
        return 1


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_sidecar_schema(contract_set: ContractSet | None) -> dict:
    """Resolve and parse the v1.3.0 sidecar schema via the existing loader."""
    cs = contract_set or load_contract_set("1.3.0")
    schema_path = cs.artifact_schemas.get(ArtifactName.SEMANTIC_TABLE_TRUTH)
    if schema_path is None:
        # Defensive: the v1.3.0 contract set MUST list this artifact.
        raise RuntimeError(
            "v1.3.0 contract set does not register semantic_table_truth schema"
        )
    return json.loads(Path(schema_path).read_text(encoding="utf-8"))


def _row_identifier(row: Any, index: int) -> str:
    """Return the row identifier used in error messages.

    If the row carries a string ``row_id`` that survived JSON parsing the
    identifier is rendered as ``'<row_id>'``; otherwise the array index is
    rendered as ``[<index>]`` per Q41.
    """
    if isinstance(row, dict):
        rid = row.get("row_id")
        if isinstance(rid, str) and rid:
            return f"'{rid}'"
    return f"[{index}]"


def _format_schema_error_message(err: Any) -> str:
    """Render a jsonschema ``ValidationError`` as a one-line message that
    embeds the failing JSON Pointer + a verbatim reason.

    The Q-SEC-2/B safety pattern text is propagated verbatim so test cases
    can grep for it.
    """
    pointer = "/" + "/".join(str(p) for p in err.absolute_path) if err.absolute_path else "/"
    raw = err.message.replace("\n", " ").strip()
    return f"schema violation at {pointer}: {raw}"


def _document_id_mismatch_message(
    declared: str | None, folder_basename: str, sidecar_path: Path
) -> str:
    """Build the Q41 mismatch message — MUST name BOTH values."""
    declared_repr = repr(declared) if declared is not None else "<missing>"
    return (
        "document_id mismatch — declared: "
        f"{declared_repr}, folder: '{folder_basename}', file: {sidecar_path}"
    )


def _duplicate_row_id_message(
    row_id: str, first_index: int, duplicate_index: int
) -> str:
    """Build the Q41 duplicate-row_id message — names value AND both indices."""
    return (
        f"row violation — row_id: '{row_id}', field: 'row_id', reason: duplicate "
        f"row_id '{row_id}' at index {duplicate_index} (first seen at index {first_index})"
    )


def _row_field_violation_message(
    row_identifier: str, field: str, value: Any, pattern_text: str
) -> str:
    """Build the Q41 row-field violation message — names row, field, and the
    pattern in a one-line, machine-readable form."""
    value_repr = repr(value) if not isinstance(value, str) else f"'{value}'"
    return (
        f"row violation — row_id: {row_identifier}, field: '{field}', reason: "
        f"value {value_repr} does not match pattern {pattern_text}"
    )


def _missing_row_id_message(index: int) -> str:
    return (
        f"row violation — row_id: [{index}]  (row_id absent or not parseable), "
        "field: 'row_id', reason: required field 'row_id' missing from row object"
    )


# ---------------------------------------------------------------------------
# Per-row supplementary checks
# ---------------------------------------------------------------------------


def _check_row_uniqueness(rows: list[Any]) -> list[SidecarError]:
    """Return a ROW_VIOLATION error for every duplicate ``row_id`` encountered.

    Iterates rows in declaration order; the first occurrence is the
    "first_seen" anchor. Every subsequent duplicate produces its own error
    naming the duplicate value AND both indices (Q11 / Q41).
    """
    out: list[SidecarError] = []
    seen: dict[str, int] = {}
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        rid = row.get("row_id")
        if not isinstance(rid, str) or not rid:
            continue
        if rid in seen:
            first = seen[rid]
            out.append(
                SidecarError(
                    kind=SidecarErrorKind.ROW_VIOLATION,
                    message=_duplicate_row_id_message(rid, first, i),
                    row_id=rid,
                    row_index=i,
                    field="row_id",
                )
            )
        else:
            seen[rid] = i
    return out


def _check_per_row_cell_shapes(
    rows: list[Any],
) -> list[SidecarError]:
    """Re-run the cell-level pattern checks in Python after jsonschema.

    The schema already enforces the regex via ``pattern``, but to honor the
    "report ALL violations not just the first" requirement (Q41 /
    validator-cli-contract.md), we also emit a row-violation-flavored error
    naming the row_id + field + pattern for currency-shape mismatches. The
    schema's raw error is also present (with SCHEMA_INVALID kind); both
    surface so the CLI exit-code mapping is robust regardless of validation
    order.
    """
    out: list[SidecarError] = []
    cell_fields = ("unit_price", "amount")
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        identifier = _row_identifier(row, i)
        rid = row.get("row_id") if isinstance(row.get("row_id"), str) else None
        for f in cell_fields:
            if f not in row:
                continue
            v = row[f]
            if isinstance(v, str) and not EXPECTED_CELL_DECIMAL_REGEX.match(v):
                out.append(
                    SidecarError(
                        kind=SidecarErrorKind.ROW_VIOLATION,
                        message=_row_field_violation_message(
                            identifier, f, v, r"^\d+\.\d{2}$"
                        ),
                        row_id=rid,
                        row_index=i,
                        field=f,
                    )
                )
        # row_id absence: surface as a row-violation naming [<index>] per Q41.
        if "row_id" not in row:
            out.append(
                SidecarError(
                    kind=SidecarErrorKind.ROW_VIOLATION,
                    message=_missing_row_id_message(i),
                    row_id=None,
                    row_index=i,
                    field="row_id",
                )
            )
        else:
            rv = row["row_id"]
            if isinstance(rv, str) and rv and not IDENTIFIER_SAFETY_REGEX.match(rv):
                out.append(
                    SidecarError(
                        kind=SidecarErrorKind.ROW_VIOLATION,
                        message=_row_field_violation_message(
                            identifier, "row_id", rv, SAFETY_PATTERN_TEXT
                        ),
                        row_id=rv,
                        row_index=i,
                        field="row_id",
                    )
                )
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_sidecar(
    folder_path: str | Path,
    *,
    contract_set: ContractSet | None = None,
) -> SemanticTruthValidationResult:
    """Validate the optional ``semantic_table_truth.json`` in ``folder_path``.

    Args:
        folder_path: per-document folder whose basename MUST equal the
            sidecar's declared ``document_id`` (Q41).
        contract_set: optional pre-loaded v1.3.0 contract set. When omitted
            the function loads ``load_contract_set("1.3.0")``.

    Returns:
        A :class:`SemanticTruthValidationResult` carrying every encountered
        violation. ``result.passed`` is ``True`` only when no error was
        recorded. The result does NOT raise on validation failure — the CLI
        maps the error classes to exit codes.
    """
    folder = Path(folder_path)
    sidecar_path = folder / SIDECAR_FILENAME
    errors: list[SidecarError] = []
    folder_basename = folder.name

    if not sidecar_path.is_file():
        errors.append(
            SidecarError(
                kind=SidecarErrorKind.MISSING_SIDECAR,
                message=(
                    f"missing sidecar — no semantic_table_truth.json in "
                    f"'{folder}'"
                ),
            )
        )
        return SemanticTruthValidationResult(
            folder=folder, sidecar_path=sidecar_path, errors=tuple(errors)
        )

    raw_text = sidecar_path.read_text(encoding="utf-8")
    try:
        doc = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        errors.append(
            SidecarError(
                kind=SidecarErrorKind.JSON_INVALID,
                message=(
                    f"JSON parse error in {sidecar_path}: {exc.msg} "
                    f"(line {exc.lineno}, col {exc.colno})"
                ),
            )
        )
        return SemanticTruthValidationResult(
            folder=folder, sidecar_path=sidecar_path, errors=tuple(errors)
        )

    # Schema validation (collect ALL violations).
    schema = _load_sidecar_schema(contract_set)
    validator = Draft202012Validator(schema)
    for err in validator.iter_errors(doc):
        errors.append(
            SidecarError(
                kind=SidecarErrorKind.SCHEMA_INVALID,
                message=_format_schema_error_message(err),
            )
        )

    # document_id ↔ folder basename match (Q41).
    declared = doc.get("document_id") if isinstance(doc, dict) else None
    if isinstance(declared, str) and declared != folder_basename:
        errors.append(
            SidecarError(
                kind=SidecarErrorKind.DOCUMENT_ID_MISMATCH,
                message=_document_id_mismatch_message(
                    declared, folder_basename, sidecar_path
                ),
            )
        )

    # Row-level supplementary checks. We run these even when the schema
    # surfaced row-level issues so the result enumerates ALL violations
    # (Q41 / validator-cli-contract.md §Error message content).
    rows = doc.get("rows") if isinstance(doc, dict) else None
    if isinstance(rows, list):
        errors.extend(_check_row_uniqueness(rows))
        errors.extend(_check_per_row_cell_shapes(rows))

    return SemanticTruthValidationResult(
        folder=folder, sidecar_path=sidecar_path, errors=tuple(errors)
    )


__all__ = [
    "EXPECTED_CELL_DECIMAL_REGEX",
    "IDENTIFIER_SAFETY_REGEX",
    "SAFETY_PATTERN_TEXT",
    "SIDECAR_FILENAME",
    "SemanticTruthValidationResult",
    "SidecarError",
    "SidecarErrorKind",
    "validate_sidecar",
]
