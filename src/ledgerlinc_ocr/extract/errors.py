"""Typed errors for the edge-extraction pipeline.

Each class pairs a human-readable message with an optional `detail` dict for
downstream consumers (stderr formatter, exit-code mapper, telemetry). No
logic, no imports beyond stdlib.
"""

from __future__ import annotations


class ExtractionError(Exception):
    """Base for every typed extraction error."""

    def __init__(self, message: str, *, detail: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail: dict = dict(detail) if detail else {}

    def __str__(self) -> str:
        return self.message


class InputContractDrift(ExtractionError):
    """`preprocess_output.json` declares an unsupported `contract_set_version`
    or is missing / schema-invalid."""


class OllamaUnreachable(ExtractionError):
    """Host Ollama is unreachable: connection refused, DNS failure, timeout,
    or `OLLAMA_BASE_URL` not configured."""


class OllamaModelUnavailable(ExtractionError):
    """The configured model tag is not present on the reachable Ollama endpoint."""


class MalformedResponse(ExtractionError):
    """Voter returned a body that is not usable as-is but may be repairable."""


class UnrepairableResponse(ExtractionError):
    """Voter response is not valid JSON and the minimal repair pipeline failed."""


class VoterConfigInvalid(ExtractionError):
    """Voter config YAML failed to parse or failed pydantic validation."""


class ArtifactAssemblyError(ExtractionError):
    """Assembled artifact failed schema validation before write (should be
    unreachable — reconcile.py post-conditions prevent it)."""


class FolderWriteError(ExtractionError):
    """Filesystem error while writing `edge_extraction_output.json`."""
