"""Exit-code table and error→code mapping per research.md §R-011."""

from __future__ import annotations

from .errors import (
    ArtifactAssemblyError,
    ExtractionError,
    FolderWriteError,
    InputContractDrift,
    MalformedResponse,
    OllamaModelUnavailable,
    OllamaUnreachable,
    UnrepairableResponse,
    VoterConfigInvalid,
)

EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_INPUT_CONTRACT_DRIFT = 2
EXIT_OLLAMA_UNREACHABLE = 3
EXIT_MODEL_UNAVAILABLE = 4
EXIT_UNREPAIRABLE_RESPONSE = 5
EXIT_VOTER_CONFIG_INVALID = 6
EXIT_FOLDER_WRITE = 7

_MAP: dict[type[BaseException], int] = {
    InputContractDrift: EXIT_INPUT_CONTRACT_DRIFT,
    OllamaUnreachable: EXIT_OLLAMA_UNREACHABLE,
    OllamaModelUnavailable: EXIT_MODEL_UNAVAILABLE,
    MalformedResponse: EXIT_UNREPAIRABLE_RESPONSE,
    UnrepairableResponse: EXIT_UNREPAIRABLE_RESPONSE,
    VoterConfigInvalid: EXIT_VOTER_CONFIG_INVALID,
    ArtifactAssemblyError: EXIT_UNEXPECTED,
    FolderWriteError: EXIT_FOLDER_WRITE,
}


def for_error(exc: BaseException) -> int:
    """Map an exception instance to its R-011 exit code."""

    for cls, code in _MAP.items():
        if isinstance(exc, cls):
            return code
    if isinstance(exc, ExtractionError):
        return EXIT_UNEXPECTED
    return EXIT_UNEXPECTED
