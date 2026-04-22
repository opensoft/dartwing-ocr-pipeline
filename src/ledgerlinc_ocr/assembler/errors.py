"""Exceptions and exit codes for the final-payload assembler (009-final-payload)."""

from __future__ import annotations

EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_INPUT_REJECTED = 2
EXIT_INTERNAL_ERROR = 3


class AssemblerError(Exception):
    """Base class for all assembler failures."""

    exit_code: int = EXIT_INTERNAL_ERROR
    kind: str = "unexpected"


class InputRejectedError(AssemblerError):
    """One of the six cross-input invariants failed; no output written. Exit 2."""

    exit_code = EXIT_INPUT_REJECTED
    kind = "unexpected"


class InputMissingError(InputRejectedError):
    """`edge_extraction_output.json` or `routing_decision.json` is absent."""

    kind = "missing_input"


class InputUnreadableError(InputRejectedError):
    """An input file exists but cannot be read or JSON-parsed."""

    kind = "unreadable_input"


class InputSchemaInvalidError(InputRejectedError):
    """An input file parses but fails its own v1.0.0 schema."""

    kind = "schema_invalid_input"


class ContractDriftError(InputRejectedError):
    """One input reports `contract_set_version != "1.0.0"`."""

    kind = "contract_drift"


class DocumentIdMismatchError(InputRejectedError):
    """Inputs disagree on `document_id`."""

    kind = "document_id_mismatch"


class RoutingContradictionError(InputRejectedError):
    """Routing's `decision` and `review_status` are internally inconsistent (FR-016)."""

    kind = "routing_contradiction"


class InternalError(AssemblerError):
    """Indicates a code/contract mismatch; no output written. Exit 3."""

    exit_code = EXIT_INTERNAL_ERROR
    kind = "unexpected"


class OutputSchemaInvalidError(InternalError):
    """Assembled payload failed output-side schema validation."""

    kind = "output_schema_invalid"
