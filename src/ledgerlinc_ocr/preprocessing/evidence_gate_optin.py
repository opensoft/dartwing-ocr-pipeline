"""Feature 020: shared CLI/env-var resolution for `--evidence-gate-skip-fallback` opt-in.

Sibling of `preprocessing/preprocess_strategy_optin.py` (feature 019),
`preprocessing/region_strategy_optin.py` (feature 018),
`preprocessing/raster_profile_optin.py` (feature 018), and
`preprocessing/preset_optin.py` (feature 017). Same shape:

- Single source of truth for "CLI flag wins over env var" precedence
  (R-020.1 / contracts/cli-contract.md §1).
- Truthy env-var vocabulary `{"1", "true", "yes", "on"}`, case-
  insensitive after `.strip().lower()` (R-020.1 / cli-contract.md §1).
  Anything else (including empty / unset / unrecognized) → ``False``.
- CPU-safe at module load — no Paddle import, no preprocessing.evidence_gate
  import; only Python stdlib (FR-014 / contracts/module-invariants.md MI-4 /
  MI-5).
- Cross-profile warn-and-proceed message helper for the CPU/stub +
  GPU-only flag case (R-020.12 / contracts/cli-contract.md §3 / MI-22).

Public API:

- `EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR` — env-var name
- `resolve_evidence_gate_skip_fallback(cli_value, env=None) -> bool` —
  boolean resolution honoring CLI > env > unset precedence
- `evidence_gate_skip_fallback_warn_message(active_profile) -> str` —
  R-020.12 / MI-22 stderr line with the grep-able marker
  `--evidence-gate-skip-fallback ignored:`
"""

from __future__ import annotations

import os
from typing import Mapping, Optional

EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR: str = "LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK"

# Truthy vocabulary per R-020.1 / cli-contract.md §1. Case-insensitive
# after `.strip().lower()`. Anything else (including `"2"`, `"enabled"`,
# `""`, unset) → False. Wider than feature 016's warmup vocabulary
# (`{"1","true","yes"}`) — adds `"on"` per R-020.1 / clarifications
# session: the four-value set matches the most common boolean-env-var
# vocabulary in the broader Python ecosystem and is the contract called
# out by tests grepping the optin module.
_TRUTHY_VALUES: frozenset[str] = frozenset({"1", "true", "yes", "on"})


def _is_truthy_env(value: Optional[str]) -> bool:
    """Return True iff ``value`` (after ``.strip().lower()``) is in the
    truthy vocabulary. ``None`` / empty / anything-else returns ``False``
    silently — ambiguous values are NOT errors per R-020.1 /
    cli-contract.md §1."""
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY_VALUES


def resolve_evidence_gate_skip_fallback(
    cli_value: bool | None,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Return ``True`` iff the operator opted into skip-fallback via the
    CLI flag OR the env var.

    Precedence (R-020.1):

    - ``cli_value=True``  → ``True`` regardless of env (CLI wins).
    - ``cli_value=False`` → fall through to env-var truthiness.
    - ``cli_value=None``  → fall through to env-var truthiness (same as
      ``False`` for this boolean axis; the ``None`` overload exists so
      callers can pass ``getattr(args, "evidence_gate_skip_fallback",
      None)`` symmetrically with the string-axis sibling helpers).

    Empty-string env value counts as unset (matches feature
    016/017/018/019 pattern). Unrecognized env value → ``False``
    (cli-contract.md §1 silent-tolerance).
    """
    if cli_value is True:
        return True
    env_map = env if env is not None else os.environ
    raw = env_map.get(EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR, "")
    if raw == "":
        return False
    return _is_truthy_env(raw)


def evidence_gate_skip_fallback_warn_message(active_profile: str) -> str:
    """R-020.12 / contracts/cli-contract.md §3 / MI-22 stderr warning
    for ``--evidence-gate-skip-fallback`` set on a non-GPU profile.

    Tests grep for the literal substring
    ``--evidence-gate-skip-fallback ignored:`` per MI-22 so the wording
    can be tightened later without breaking them. The active-profile
    name is interpolated for operator clarity (mirrors features
    017/018/019 warn-and-proceed messages).
    """
    return (
        f"warning: --evidence-gate-skip-fallback ignored: active profile is not "
        f"ppstructurev3@gpu (got {active_profile!r})"
    )


__all__ = (
    "EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR",
    "resolve_evidence_gate_skip_fallback",
    "evidence_gate_skip_fallback_warn_message",
)
