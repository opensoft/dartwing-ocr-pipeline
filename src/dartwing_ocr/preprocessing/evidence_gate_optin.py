"""CLI/env-var resolution for `--evidence-gate-skip-fallback`."""

from __future__ import annotations

import os
import sys
from typing import IO, Mapping, Optional

EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR: str = "DARTWING_EVIDENCE_GATE_SKIP_FALLBACK"

_TRUTHY_VALUES: frozenset[str] = frozenset({"1", "true", "yes", "on"})
_FALSY_VALUES: frozenset[str] = frozenset({"0", "false", "no", "off", ""})


def resolve_evidence_gate_skip_fallback(
    cli_value: bool,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Resolve the opt-in. CLI True wins. Otherwise consult the env var.

    Per cli-contract.md §1, unrecognized env-var values raise ValueError;
    callers translate that to exit code 2.
    """
    if cli_value:
        return True
    env_map = env if env is not None else os.environ
    raw = env_map.get(EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR, "")
    normalized = raw.strip().lower()
    if normalized in _TRUTHY_VALUES:
        return True
    if normalized in _FALSY_VALUES:
        return False
    raise ValueError(
        f"{EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR}={raw!r} is not a recognized "
        f"boolean value (expected one of: "
        f"{sorted(_TRUTHY_VALUES | (_FALSY_VALUES - {''}))} or unset)"
    )


def evidence_gate_skip_fallback_warn_message(active_profile: str) -> str:
    return (
        f"warning: --evidence-gate-skip-fallback ignored: active profile is not "
        f"ppstructurev3@gpu (got {active_profile!r})"
    )


def apply_skip_fallback_optin(
    *,
    cli_value: bool,
    is_gpu_profile: bool,
    active_profile_name: str,
    env: Mapping[str, str] | None = None,
    stream: IO[str] | None = None,
) -> bool:
    """Resolve the opt-in and emit the MI-22 warn line on non-GPU profiles.

    Returns the effective opt-in (False whenever the warn fired). Raises
    ValueError on an unrecognized env value — callers should let it propagate
    and convert to exit code 2.
    """
    resolved = resolve_evidence_gate_skip_fallback(cli_value, env=env)
    if not resolved:
        return False
    if is_gpu_profile:
        return True
    print(
        evidence_gate_skip_fallback_warn_message(active_profile_name),
        file=stream if stream is not None else sys.stderr,
    )
    return False
