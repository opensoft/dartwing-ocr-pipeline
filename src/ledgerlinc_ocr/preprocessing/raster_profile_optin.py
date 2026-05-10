"""Feature 018: shared CLI/env-var resolution for `--raster-profile` opt-in.

Mirrors feature 016's `warmup_optin.py` and feature 017's `preset_optin.py`
patterns:

- Single source of truth for "CLI flag wins over env var" precedence
  (R-018.1 / contracts/cli-contract.md §1).
- Verbatim env-var literal-value handling — no `.strip()`, no case
  normalization (research.md R-018.1 "Env-var literal-value handling").
- CPU-safe at module load — no Paddle import, no preset registry
  introspection (FR-015 / contracts/module-invariants.md I-018.2).
- Cross-profile warn-and-proceed message helper for the CPU/stub +
  GPU-only flag case (FR-014 / contracts/cli-contract.md §3).

Public API:

- `RASTER_PROFILE_ENV_VAR` — env-var name
- `resolve_raster_profile_value(cli_value, env=None) -> str | None` —
  string resolution honoring CLI > env > unset precedence
- `is_gpu_lane(preprocess_lane) -> bool` — re-exported from
  `warmup_optin` for symmetry; lane string starts with "gpu"
- `raster_profile_warn_message(active_profile) -> str` — FR-014 stderr line
- `derive_run_summary_raster_profile_id(threaded, preprocess_lane) -> str`
  — maps the CLI's threaded value → `run_summary.raster_profile_id`
  identifier, mirroring `preset_optin.derive_run_summary_identifiers`.
"""

from __future__ import annotations

import os
from typing import Mapping

from ledgerlinc_ocr.preprocessing.identifiers import (
    CPU_DEFAULT_RASTER_PROFILE,
    LEGACY_RASTER_PROFILE,
)
from ledgerlinc_ocr.preprocessing.warmup_optin import is_gpu_lane

RASTER_PROFILE_ENV_VAR: str = "LEDGERLINC_RASTER_PROFILE"


def resolve_raster_profile_value(
    cli_value: str | None,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Return the `raster_profile_id` string the operator wants, or `None`
    if neither the CLI flag nor the env var is set.

    Precedence (R-018.1): CLI flag wins when both are set. Env-var value
    is passed verbatim — no `.strip()`, no case normalization. An empty
    string env value counts as unset (matches feature 016/017 pattern).
    """
    if cli_value is not None and cli_value != "":
        return cli_value
    src = env if env is not None else os.environ
    raw = src.get(RASTER_PROFILE_ENV_VAR, "")
    if raw == "":
        return None
    return raw


def raster_profile_warn_message(active_profile: str) -> str:
    """FR-014 / contracts/cli-contract.md §3 stderr warning for
    `--raster-profile` set on a non-GPU profile.

    Tests grep for the literal substring `--raster-profile ignored:` so
    the wording can be tightened later without breaking them.
    """
    return (
        f"warning: --raster-profile ignored: active preprocess profile is "
        f"{active_profile!r}, not 'ppstructurev3@gpu'"
    )


def derive_run_summary_raster_profile_id(
    *,
    threaded_raster_profile: str | None,
    preprocess_lane: str,
) -> str:
    """Derive ``raster_profile_id`` for ``RunSummary`` construction at
    the run-summary build sites in ``corpus_run.py`` and
    ``preprocessing/cli.py:_emit_single_doc_run_summary``.

    ``threaded_raster_profile`` is the value the CLI carried forward
    AFTER the warn-and-proceed branch (so on non-GPU profiles it will
    be ``None`` even when the operator passed a flag). Caller (the CLI)
    is responsible for the warn-and-proceed reset; this helper just
    maps the CLI's threaded value → run_summary identifier value.

    Behavior:

    - ``preprocess_lane`` is GPU and a value is threaded → return that value
    - ``preprocess_lane`` is GPU and no value threaded → return ``"legacy"``
      (the GPU-lane no-flag default per R-018.2)
    - ``preprocess_lane`` is CPU/stub → return ``"cpu-default"`` regardless
      of threaded value (warn-and-proceed already nulled it)

    Stub-adapter discrimination beyond cpu/gpu lane is the caller's
    responsibility; pass ``"stub-default"`` at the stub run-summary build
    site (see ``data-model.md`` §"Identifier-string constants").
    """
    if not is_gpu_lane(preprocess_lane):
        return CPU_DEFAULT_RASTER_PROFILE
    return threaded_raster_profile if threaded_raster_profile is not None else LEGACY_RASTER_PROFILE


__all__ = (
    "RASTER_PROFILE_ENV_VAR",
    "resolve_raster_profile_value",
    "is_gpu_lane",
    "raster_profile_warn_message",
    "derive_run_summary_raster_profile_id",
)
