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


class EngineInitError(PreprocessingError):
    """FR-016 hard-fail: PPStructureV3 could not be constructed.

    Carries structured cause information so the CLI layer can emit the FR-016
    error envelope without re-parsing the exception string. The `missing_weight`
    and `weight_hoster_url` fields are populated only when the init failure is
    classified as a weight-download failure (research R-008).
    """

    exit_code = EXIT_INTERNAL_ERROR

    def __init__(
        self,
        message: str,
        cause_class: str,
        cause_module: str,
        missing_weight: str | None = None,
        weight_hoster_url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.cause_class = cause_class
        self.cause_module = cause_module
        self.missing_weight = missing_weight
        self.weight_hoster_url = weight_hoster_url
