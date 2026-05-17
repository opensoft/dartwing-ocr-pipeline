"""Feature 018: shared CLI/env-var resolution for `--region-strategy` opt-in.

Sibling of `preprocessing/raster_profile_optin.py` (feature 018) and
`preprocessing/preset_optin.py` (feature 017). Same shape:

- Single source of truth for "CLI flag wins over env var" precedence
  (R-018.1 / contracts/cli-contract.md §1).
- Verbatim env-var literal-value handling — no `.strip()`, no case
  normalization (research.md R-018.1 "Env-var literal-value handling").
- CPU-safe at module load — no Paddle import, no preset registry
  introspection (FR-015 / contracts/module-invariants.md I-018.2).
- Cross-profile warn-and-proceed message helper for the CPU/stub +
  GPU-only flag case (FR-014 / contracts/cli-contract.md §3).

Public API:

- `REGION_STRATEGY_ENV_VAR` — env-var name
- `resolve_region_strategy_value(cli_value, env=None) -> str | None` —
  string resolution honoring CLI > env > unset precedence
- `is_gpu_lane(preprocess_lane) -> bool` — re-exported from
  `warmup_optin` for symmetry; lane string starts with "gpu"
- `region_strategy_warn_message(active_profile) -> str` — FR-014 stderr line
- `derive_run_summary_region_strategy_id(threaded, preprocess_lane) -> str`
  — maps the CLI's threaded value → `run_summary.region_strategy_id`
  identifier, mirroring the raster-profile / preset variants.
"""

from __future__ import annotations

import os
from typing import Mapping

from dartwing_ocr.preprocessing.identifiers import (
    CPU_DEFAULT_REGION_STRATEGY,
    LEGACY_REGION_STRATEGY,
)
from dartwing_ocr.preprocessing.warmup_optin import is_gpu_lane

REGION_STRATEGY_ENV_VAR: str = "DARTWING_REGION_STRATEGY"


def resolve_region_strategy_value(
    cli_value: str | None,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Return the `region_strategy_id` string the operator wants, or
    `None` if neither the CLI flag nor the env var is set.

    Precedence (R-018.1): CLI flag wins when both are set. Env-var value
    is passed verbatim — no `.strip()`, no case normalization. An empty
    string env value counts as unset (matches feature 016/017 pattern).
    """
    if cli_value is not None and cli_value != "":
        return cli_value
    src = env if env is not None else os.environ
    raw = src.get(REGION_STRATEGY_ENV_VAR, "")
    if raw == "":
        return None
    return raw


def region_strategy_warn_message(active_profile: str) -> str:
    """FR-014 / contracts/cli-contract.md §3 stderr warning for
    `--region-strategy` set on a non-GPU profile.

    Tests grep for the literal substring `--region-strategy ignored:`
    so the wording can be tightened later without breaking them.
    """
    return (
        f"warning: --region-strategy ignored: active preprocess profile is "
        f"{active_profile!r}, not 'ppstructurev3@gpu'"
    )


def derive_run_summary_region_strategy_id(
    *,
    threaded_region_strategy: str | None,
    preprocess_lane: str,
) -> str:
    """Derive ``region_strategy_id`` for ``RunSummary`` construction at
    the run-summary build sites in ``corpus_run.py`` and
    ``preprocessing/cli.py:_emit_single_doc_run_summary``.

    Behavior (mirrors derive_run_summary_raster_profile_id):

    - ``preprocess_lane`` is GPU and a value is threaded → return that value
    - ``preprocess_lane`` is GPU and no value threaded → return
      ``"full-page"`` (the GPU-lane no-flag default per R-018.4)
    - ``preprocess_lane`` is CPU/stub → return ``"cpu-default"`` regardless
      of threaded value (warn-and-proceed already nulled it)

    Stub-adapter discrimination beyond cpu/gpu lane is the caller's
    responsibility; pass ``"stub-default"`` at the stub run-summary build
    site (see ``data-model.md`` §"Identifier-string constants").
    """
    if not is_gpu_lane(preprocess_lane):
        return CPU_DEFAULT_REGION_STRATEGY
    return (
        threaded_region_strategy
        if threaded_region_strategy is not None
        else LEGACY_REGION_STRATEGY
    )


__all__ = (
    "REGION_STRATEGY_ENV_VAR",
    "resolve_region_strategy_value",
    "is_gpu_lane",
    "region_strategy_warn_message",
    "derive_run_summary_region_strategy_id",
)
