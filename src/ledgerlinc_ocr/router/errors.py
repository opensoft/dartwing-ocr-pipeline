"""Typed exceptions raised by the router.

The CLI surface in ``cli.py`` maps each exception class to the exit-code
taxonomy documented in ``specs/008-routing/contracts/cli-contract.md``:

- ``MissingInputError`` / ``UnreadableInputError`` / ``MalformedInputError`` /
  ``VersionDriftError`` → exit code ``2`` (bad input).
- ``ContractAssertionError`` → exit code ``3`` (bad policy / bad routing code
  — the assembled artifact disagrees with the frozen schema).

Every exception carries a ``human_message`` attribute so the CLI can write a
consistent one-line stderr diagnostic without string-formatting at the call
site.
"""
from __future__ import annotations


class RouterError(Exception):
    """Base class for router-raised errors."""

    def __init__(self, human_message: str) -> None:
        super().__init__(human_message)
        self.human_message = human_message


class MissingInputError(RouterError):
    """The input folder or input file does not exist."""


class UnreadableInputError(RouterError):
    """The input file exists but cannot be read (permission error, I/O error)."""


class MalformedInputError(RouterError):
    """The input file is not valid JSON or fails schema validation."""


class VersionDriftError(RouterError):
    """The input reports ``contract_set_version`` other than ``"1.0.0"``."""


class ContractAssertionError(RouterError):
    """The assembled output artifact failed ``routing_decision.schema.json``.

    This is an internal error — the router's code and the frozen contract set
    have drifted and MUST be reconciled (not silently hidden).
    """
