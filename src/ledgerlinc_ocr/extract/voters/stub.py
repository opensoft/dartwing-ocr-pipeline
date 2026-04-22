"""Stub voter: reads a canned fixture JSON instead of calling Ollama.

Used by the US4 pluggability test and by CI lanes that cannot reach a real
Ollama endpoint. The fixture path is carried through the `x_fixture_path`
extension key on the voter config (see contracts/voter-config.md §Stub voter).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import MalformedResponse
from .base import RawModelResponse, VoterAdapter


class StubVoter(VoterAdapter):
    """Return the contents of a fixture file as the model body.

    Construct with either a `fixture_path` override (used by tests) or
    `extensions={"x_fixture_path": "..."}` pulled from the voter config.
    """

    def __init__(
        self,
        *,
        fixture_path: str | Path | None = None,
        extensions: dict[str, Any] | None = None,
        config_dir: Path | None = None,
    ) -> None:
        resolved = fixture_path
        if resolved is None and extensions is not None:
            resolved = extensions.get("x_fixture_path")
        if resolved is None:
            raise MalformedResponse(
                "stub voter requires x_fixture_path in the voter config",
                detail={"hint": "set x_fixture_path: <relative-or-absolute path>"},
            )

        path = Path(resolved)
        if not path.is_absolute() and config_dir is not None:
            path = (config_dir / path).resolve()
        self._path = path

    def call(self, rendered_prompt: str, config: Any) -> RawModelResponse:
        try:
            body = self._path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise MalformedResponse(
                f"stub fixture not found: {self._path}",
                detail={"path": str(self._path)},
            ) from exc
        except OSError as exc:
            raise MalformedResponse(
                f"stub fixture could not be read: {self._path}",
                detail={"path": str(self._path), "os_error": str(exc)},
            ) from exc

        return RawModelResponse(
            body=body,
            duration_ms=0,
            model_echo=None,
            done=True,
        )
