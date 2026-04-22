"""Exceptions and exit codes for the final-payload assembler (009-final-payload)."""

from __future__ import annotations

from typing import ClassVar

EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_INPUT_REJECTED = 2
EXIT_INTERNAL_ERROR = 3


class AssemblerError(Exception):
    """Base class for all assembler failures."""

    exit_code: ClassVar[int] = EXIT_INTERNAL_ERROR
    kind: ClassVar[str] = "unexpected"


class InputRejectedError(AssemblerError):
    """One of the cross-input invariants failed; no output written. Exit 2.

    Concrete subclasses MUST set a non-empty `kind` string — the base class
    deliberately has no default so a forgotten override fails loudly rather
    than leaking the wrong taxonomy to stderr.
    """

    exit_code: ClassVar[int] = EXIT_INPUT_REJECTED
    # No class-level `kind` default. Enforced in __init__ below.
    kind: ClassVar[str | None] = None  # type: ignore[assignment]

    def __init__(self, *args: object) -> None:
        resolved = getattr(type(self), "kind", None)
        if not isinstance(resolved, str) or not resolved:
            raise NotImplementedError(
                f"{type(self).__name__} must set a non-empty `kind` class attribute"
            )
        super().__init__(*args)


class InputMissingError(InputRejectedError):
    """`edge_extraction_output.json` or `routing_decision.json` is absent."""

    kind: ClassVar[str] = "missing_input"


class InputUnreadableError(InputRejectedError):
    """An input file exists but cannot be read or JSON-parsed."""

    kind: ClassVar[str] = "unreadable_input"


class InputSchemaInvalidError(InputRejectedError):
    """An input file parses but fails its own v1.0.0 schema."""

    kind: ClassVar[str] = "schema_invalid_input"


class ContractDriftError(InputRejectedError):
    """One input reports `contract_set_version != "1.0.0"`."""

    kind: ClassVar[str] = "contract_drift"


class DocumentIdMismatchError(InputRejectedError):
    """Inputs disagree on `document_id`."""

    kind: ClassVar[str] = "document_id_mismatch"


class RoutingContradictionError(InputRejectedError):
    """Routing's `decision` and `review_status` are internally inconsistent (FR-016)."""

    kind: ClassVar[str] = "routing_contradiction"


class InternalError(AssemblerError):
    """Indicates a code/contract mismatch; no output written. Exit 3."""

    exit_code: ClassVar[int] = EXIT_INTERNAL_ERROR
    kind: ClassVar[str] = "unexpected"


class OutputSchemaInvalidError(InternalError):
    """Assembled payload failed output-side schema validation."""

    kind: ClassVar[str] = "output_schema_invalid"
