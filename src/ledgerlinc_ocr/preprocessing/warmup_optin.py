"""CPU-safe activation-surface helper for the GPU warmup opt-in.

This module's only purpose is to parse the ``--gpu-warmup`` CLI flag and the
``LEDGERLINC_GPU_WARMUP`` env var into a single boolean per the rules in
research R-016.1 / ``contracts/cli-contract.md`` §1 / ``data-model.md``
§"Activation-surface state machine":

- CLI flag (boolean) wins when both surfaces are present.
- Env-var truthiness whitelist (after ``.strip().lower()``):
  ``{"1", "true", "yes"}``.
- Anything else (including ``2``, ``on``, ``enabled``, empty, unset) → ``False``.

This module is **CPU-safe** — it imports nothing from MIOpen, paddle, numpy,
PIL, or ``preprocessing.warmup``. It is imported on every CLI invocation
(GPU or otherwise) so the warn-and-proceed path on CPU/stub (FR-010) can
detect the opt-in without lazy-loading the heavyweight ``warmup`` module.
"""

from __future__ import annotations

import os
from typing import Mapping, Optional

_TRUTHY_VALUES: frozenset[str] = frozenset({"1", "true", "yes"})
_WARMUP_ENV_VAR: str = "LEDGERLINC_GPU_WARMUP"


def _is_truthy_env(value: Optional[str]) -> bool:
    """Return True iff ``value`` is in the truthiness whitelist after
    ``.strip().lower()``. ``None``/empty/anything-else returns False
    silently — ambiguous values are NOT errors per cli-contract.md §1."""
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY_VALUES


def is_warmup_optin_set(
    cli_flag: bool,
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    """Return True iff the warmup opt-in is set via the CLI flag OR the env
    var. CLI wins when both are present (cli_flag=True returns True
    regardless of env)."""
    if cli_flag:
        return True
    env_map = env if env is not None else os.environ
    return _is_truthy_env(env_map.get(_WARMUP_ENV_VAR))


def is_gpu_lane(preprocess_lane: str) -> bool:
    """Return True iff ``preprocess_lane`` is a GPU lane (``"gpu0"``,
    ``"gpu1"``, etc.). Used by the CPU/stub warn-and-proceed branch to
    short-circuit the warmup invocation per FR-010 / SC-007."""
    return (
        isinstance(preprocess_lane, str)
        and preprocess_lane.startswith("gpu")
        and preprocess_lane[3:].isdigit()
    )


def warn_and_proceed_message(active_profile_name: str) -> str:
    """Return the canonical FR-010 stderr warn-and-proceed line. The literal
    prefix ``--gpu-warmup ignored:`` is part of the contract per
    contracts/cli-contract.md §3 — tests grep for this exact string."""
    return (
        f"warning: --gpu-warmup ignored: active preprocess profile is "
        f"{active_profile_name!r}, not 'ppstructurev3@gpu'"
    )


__all__ = [
    "is_warmup_optin_set",
    "is_gpu_lane",
    "warn_and_proceed_message",
]
