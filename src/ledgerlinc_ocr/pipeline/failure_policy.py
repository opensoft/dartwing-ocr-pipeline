"""--on-failure policy parsing.

Spec FR-028. Research R-008 / R-010.

In warm-corpus mode, the default is ``continue``. In cold single-document
mode, the flag is accepted but is a no-op (single document failure is
already surfaced through exit code + stderr failure record).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Mode = Literal["continue", "fail-fast"]
ACCEPTED_MODES: tuple[Mode, ...] = ("continue", "fail-fast")


class FailurePolicyError(ValueError):
    """Raised when --on-failure receives an unrecognized mode."""


@dataclass(frozen=True)
class FailurePolicy:
    mode: Mode

    @property
    def fail_fast(self) -> bool:
        return self.mode == "fail-fast"


def parse_on_failure(value: str | None, *, warm_corpus: bool) -> FailurePolicy:
    """Parse --on-failure, defaulting to ``continue`` in warm-corpus mode.

    Cold mode treats the flag as a no-op semantically; we still parse and
    return a policy so the CLI can record it in metadata, but the value
    is irrelevant once dispatch reaches the cold one-document path.
    """
    if value is None:
        # Default per R-008.
        return FailurePolicy(mode="continue" if warm_corpus else "fail-fast")
    normalized = value.strip().lower()
    if normalized not in ACCEPTED_MODES:
        raise FailurePolicyError(
            f"--on-failure={value!r}: must be one of "
            f"{list(ACCEPTED_MODES)}"
        )
    return FailurePolicy(mode=normalized)  # type: ignore[arg-type]


__all__ = ["ACCEPTED_MODES", "FailurePolicy", "FailurePolicyError", "Mode", "parse_on_failure"]
