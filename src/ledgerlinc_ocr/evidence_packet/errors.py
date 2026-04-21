"""Typed errors for the evidence-packet assembler.

Exit-code mapping is the CLI's job (see cli.py), not these exceptions'.
"""
from __future__ import annotations

from pathlib import Path


class PacketAssemblyError(Exception):
    """Base class for every assembler error. Library callers can catch the family."""

    def __init__(self, message: str, *, path: Path | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.path = path


class PreprocessInputMissing(PacketAssemblyError):
    """The folder has no readable preprocess_output.json, or the file is not JSON."""


class PreprocessInputInvalid(PacketAssemblyError):
    """preprocess_output.json parsed but failed schema validation."""


class PacketInvalid(PacketAssemblyError):
    """The assembled packet failed its own output schema (a programmer bug)."""
