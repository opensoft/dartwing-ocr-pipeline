"""Exceptions and exit codes for the preprocessing slice."""

from __future__ import annotations

EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_INPUT_REJECTED = 2
EXIT_INTERNAL_ERROR = 3


class PreprocessingError(Exception):
    """Base class for all preprocessing-slice failures."""

    exit_code = EXIT_INTERNAL_ERROR


class InputRejectedError(PreprocessingError):
    """Non-recoverable malformed input — exits 2, no artifact written."""

    exit_code = EXIT_INPUT_REJECTED


class NonPdfInputError(InputRejectedError):
    """File at --source-file is not a PDF (missing %PDF- magic)."""


class EncryptedPdfError(InputRejectedError):
    """PDF is password-protected / encrypted and cannot be opened."""


class MalformedPdfError(InputRejectedError):
    """PDF bytes are unreadable or structurally broken at the document level."""


class ZeroPagePdfError(InputRejectedError):
    """PDF parses but reports zero pages."""


class ArtifactInvalidError(PreprocessingError):
    """Assembled artifact failed contract validation — indicates a code/contract mismatch."""

    exit_code = EXIT_INTERNAL_ERROR
