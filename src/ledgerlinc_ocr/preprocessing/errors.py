"""Exceptions and exit codes for the preprocessing slice."""

from __future__ import annotations

EXIT_OK = 0
EXIT_INPUT_REJECTED = 2
EXIT_INTERNAL_ERROR = 3


class PreprocessingError(Exception):
    """Base class for all preprocessing-slice failures."""

    exit_code = EXIT_INTERNAL_ERROR


class InputRejectedError(PreprocessingError):
    """Non-recoverable malformed input (non-PDF, encrypted, zero pages, unreadable)."""

    exit_code = EXIT_INPUT_REJECTED


class ArtifactInvalidError(PreprocessingError):
    """Assembled artifact failed contract validation — indicates a code/contract mismatch."""

    exit_code = EXIT_INTERNAL_ERROR
