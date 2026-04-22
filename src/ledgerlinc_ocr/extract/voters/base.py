"""Voter-adapter seam: the one-method Protocol every voter implements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class RawModelResponse:
    body: str
    duration_ms: int
    model_echo: str | None
    done: bool


@runtime_checkable
class VoterAdapter(Protocol):
    """Pluggable voter seam. One method, no other ceremony.

    Implementations MUST be stateless per call (the pipeline may reuse a single
    instance across invocations).
    """

    def call(self, rendered_prompt: str, config: "Any") -> RawModelResponse:  # noqa: F821
        ...
