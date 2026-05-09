"""Feature 017: shared CLI/env-var resolution for `--module-set` and
`--det-rec-variant` opt-ins.

Mirrors feature 016's `warmup_optin.py` pattern:

- Single source of truth for "CLI flag wins over env var" precedence
  (R-017.1 / contracts/cli-contract.md §1).
- Verbatim env-var literal-value handling — no `.strip()`, no case
  normalization (research.md R-017.1 "Env-var literal-value handling").
- CPU-safe at module load — no Paddle import, no preset registry
  introspection (FR-014 / contracts/module-invariants.md I-3).
- Cross-profile warn-and-proceed message helper for the CPU/stub +
  GPU-only flag case (FR-013 / contracts/cli-contract.md §3).

Public API:

- `MODULE_SET_ENV_VAR` / `DET_REC_VARIANT_ENV_VAR` — env-var names
- `resolve_module_set_value(cli_value, env=None) -> str | None` — string
  resolution honoring CLI > env > unset precedence
- `resolve_det_rec_variant_value(cli_value, env=None) -> str | None`
- `is_gpu_lane(preprocess_lane) -> bool` — re-exported from
  `warmup_optin` for symmetry; lane string starts with "gpu"
- `module_set_warn_message(active_profile) -> str` — FR-013 stderr line
- `det_rec_variant_warn_message(active_profile) -> str` — FR-013 stderr line
"""

from __future__ import annotations

import os
from typing import Optional


MODULE_SET_ENV_VAR: str = "LEDGERLINC_MODULE_SET"
DET_REC_VARIANT_ENV_VAR: str = "LEDGERLINC_DET_REC_VARIANT"


def resolve_module_set_value(
    cli_value: Optional[str],
    env: Optional[dict[str, str]] = None,
) -> Optional[str]:
    """Return the `module_set_id` string the operator wants, or `None` if
    neither the CLI flag nor the env var is set.

    Precedence (R-017.1): CLI flag wins when both are set. Env-var value
    is passed verbatim — no `.strip()`, no case normalization. An empty
    string env value counts as unset (matches feature 016 `warmup_optin`).
    """
    if cli_value is not None and cli_value != "":
        return cli_value
    src = env if env is not None else os.environ
    raw = src.get(MODULE_SET_ENV_VAR, "")
    if raw == "":
        return None
    return raw


def resolve_det_rec_variant_value(
    cli_value: Optional[str],
    env: Optional[dict[str, str]] = None,
) -> Optional[str]:
    """Return the `det_rec_variant_id` string the operator wants, or
    `None` if neither the CLI flag nor the env var is set.

    Same precedence + verbatim handling as `resolve_module_set_value`.
    """
    if cli_value is not None and cli_value != "":
        return cli_value
    src = env if env is not None else os.environ
    raw = src.get(DET_REC_VARIANT_ENV_VAR, "")
    if raw == "":
        return None
    return raw


def is_gpu_lane(preprocess_lane: str) -> bool:
    """True if the resolved preprocess lane string indicates GPU.

    Mirrors feature 016's `warmup_optin.is_gpu_lane`. A lane starting
    with "gpu" (e.g., "gpu0", "gpu1") routes through GPU; "cpu" and
    stub-adapter sentinels do not.
    """
    return isinstance(preprocess_lane, str) and preprocess_lane.startswith("gpu")


def module_set_warn_message(active_profile: str) -> str:
    """FR-013 / contracts/cli-contract.md §3 stderr warning for `--module-set`
    set on a non-GPU profile.

    Tests grep for the literal substring `--module-set ignored:` so the
    wording can be tightened later without breaking them.
    """
    return (
        f"warning: --module-set ignored: active preprocess profile is "
        f"{active_profile!r}, not 'ppstructurev3@gpu'"
    )


def det_rec_variant_warn_message(active_profile: str) -> str:
    """FR-013 / contracts/cli-contract.md §3 stderr warning for
    `--det-rec-variant` set on a non-GPU profile."""
    return (
        f"warning: --det-rec-variant ignored: active preprocess profile is "
        f"{active_profile!r}, not 'ppstructurev3@gpu'"
    )


__all__ = (
    "MODULE_SET_ENV_VAR",
    "DET_REC_VARIANT_ENV_VAR",
    "resolve_module_set_value",
    "resolve_det_rec_variant_value",
    "is_gpu_lane",
    "module_set_warn_message",
    "det_rec_variant_warn_message",
)
