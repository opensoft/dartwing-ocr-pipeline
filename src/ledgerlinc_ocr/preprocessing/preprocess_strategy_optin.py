"""Feature 019: shared CLI/env-var resolution for `--preprocess-strategy` opt-in.

Sibling of `preprocessing/region_strategy_optin.py` (feature 018),
`preprocessing/raster_profile_optin.py` (feature 018), and
`preprocessing/preset_optin.py` (feature 017). Same shape:

- Single source of truth for "CLI flag wins over env var" precedence
  (R-019.1 / contracts/cli-contract.md §1).
- Verbatim env-var literal-value handling — no `.strip()`, no case
  normalization (research.md R-019.1 "Env-var literal-value handling").
- CPU-safe at module load — no Paddle import, no preset registry
  introspection (FR-014 / contracts/module-invariants.md I-019.10).
- Cross-profile warn-and-proceed message helper for the CPU/stub +
  GPU-only flag case (FR-013 / contracts/cli-contract.md §3).

Public API:

- `PREPROCESS_STRATEGY_ENV_VAR` — env-var name
- `resolve_preprocess_strategy_value(cli_value, env=None) -> str | None` —
  string resolution honoring CLI > env > unset precedence
- `is_gpu_lane(preprocess_lane) -> bool` — re-exported from
  `warmup_optin` for symmetry; lane string starts with "gpu"
- `preprocess_strategy_warn_message(active_profile) -> str` — FR-013 stderr line
- `derive_run_summary_preprocess_strategy_id(threaded, preprocess_lane) -> str`
  — maps the CLI's threaded value → `run_summary.preprocess_strategy_id`
  identifier, mirroring the raster-profile / region-strategy variants.
"""

from __future__ import annotations

import os
from typing import Mapping

from ledgerlinc_ocr.preprocessing.identifiers import (
    CPU_DEFAULT_PREPROCESS_STRATEGY,
    LEGACY_PREPROCESS_STRATEGY,
)
from ledgerlinc_ocr.preprocessing.warmup_optin import is_gpu_lane

PREPROCESS_STRATEGY_ENV_VAR: str = "LEDGERLINC_PREPROCESS_STRATEGY"


def resolve_preprocess_strategy_value(
    cli_value: str | None,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Return the `preprocess_strategy_id` string the operator wants, or
    `None` if neither the CLI flag nor the env var is set.

    Precedence (R-019.1): CLI flag wins when both are set. Env-var value
    is passed verbatim — no `.strip()`, no case normalization. An empty
    string env value counts as unset (matches feature 016/017/018 pattern).
    """
    if cli_value is not None and cli_value != "":
        return cli_value
    src = env if env is not None else os.environ
    raw = src.get(PREPROCESS_STRATEGY_ENV_VAR, "")
    if raw == "":
        return None
    return raw


def preprocess_strategy_warn_message(active_profile: str) -> str:
    """FR-013 / contracts/cli-contract.md §3 stderr warning for
    `--preprocess-strategy` set on a non-GPU profile.

    Tests grep for the literal substring `--preprocess-strategy ignored:`
    per I-019.14 so the wording can be tightened later without breaking them.
    """
    return (
        f"warning: --preprocess-strategy ignored: active preprocess profile is "
        f"{active_profile!r}, not 'ppstructurev3@gpu'"
    )


def derive_run_summary_preprocess_strategy_id(
    *,
    threaded_preprocess_strategy: str | None,
    preprocess_lane: str,
) -> str:
    """Derive ``preprocess_strategy_id`` for ``RunSummary`` construction at
    the run-summary build sites in ``corpus_run.py`` and
    ``preprocessing/cli.py:_emit_single_doc_run_summary``.

    Behavior (mirrors derive_run_summary_region_strategy_id):

    - ``preprocess_lane`` is GPU and a value is threaded → return that value
    - ``preprocess_lane`` is GPU and no value threaded → return
      ``LEGACY_PREPROCESS_STRATEGY`` (`"ppstructurev3"` per R-019.4)
    - ``preprocess_lane`` is CPU/stub → return
      ``CPU_DEFAULT_PREPROCESS_STRATEGY`` (`"cpu-default"`) regardless
      of threaded value (warn-and-proceed already nulled it)

    Stub-adapter discrimination is handled by the caller, NOT this
    function. This helper returns the CPU-default sentinel uniformly for
    all non-GPU lanes; the call site in ``corpus_run.py`` (success path
    and warm-init failure path) inspects ``plan.profiles["preprocess"]``
    and overrides to ``STUB_DEFAULT_PREPROCESS_STRATEGY`` when the
    resolved profile's ``kind`` is ``"stub"``. The
    ``preprocessing/cli.py:_emit_single_doc_run_summary`` site does the
    same. See ``data-model.md`` §"Identifier-string constants".
    """
    if not is_gpu_lane(preprocess_lane):
        return CPU_DEFAULT_PREPROCESS_STRATEGY
    return (
        threaded_preprocess_strategy
        if threaded_preprocess_strategy is not None
        else LEGACY_PREPROCESS_STRATEGY
    )


__all__ = (
    "PREPROCESS_STRATEGY_ENV_VAR",
    "resolve_preprocess_strategy_value",
    "is_gpu_lane",
    "preprocess_strategy_warn_message",
    "derive_run_summary_preprocess_strategy_id",
)
