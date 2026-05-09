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

from ledgerlinc_ocr.preprocessing.warmup_optin import is_gpu_lane

MODULE_SET_ENV_VAR: str = "LEDGERLINC_MODULE_SET"
DET_REC_VARIANT_ENV_VAR: str = "LEDGERLINC_DET_REC_VARIANT"


def resolve_module_set_value(
    cli_value: str | None,
    env: dict[str, str] | None = None,
) -> str | None:
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
    cli_value: str | None,
    env: dict[str, str] | None = None,
) -> str | None:
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


def derive_run_summary_identifiers(
    *,
    threaded_module_set: str | None,
    threaded_det_rec_variant: str | None,
    preprocess_lane: str,
) -> tuple[str, str]:
    """Derive ``(module_set_id, det_rec_variant_id)`` for ``RunSummary``
    construction at the run-summary build sites in ``corpus_run.py`` and
    ``preprocessing/cli.py:_emit_single_doc_run_summary``.

    ``threaded_module_set`` / ``threaded_det_rec_variant`` are the values
    the CLI carried forward AFTER the warn-and-proceed branch (so on
    non-GPU profiles they will be ``None`` even when the operator passed
    a flag). Caller (the CLI) is responsible for the warn-and-proceed
    reset; this helper just maps the CLI's threaded value → run_summary
    identifier value.

    Behavior:

    - ``preprocess_lane`` is GPU and a value is threaded → return that value
    - ``preprocess_lane`` is GPU and no value threaded → return "legacy"
      (the GPU-lane no-flag default per R-017.2 / R-017.4)
    - ``preprocess_lane`` is CPU/stub → return ("cpu-default", "cpu-default")
      regardless of threaded value (warn-and-proceed already nulled it)

    Stub-adapter discrimination beyond cpu/gpu lane is the caller's
    responsibility; pass ``"stub-default"`` literals at the stub run-summary
    build site (see ``data-model.md`` §"CPU/stub identifier constants").
    """
    if not is_gpu_lane(preprocess_lane):
        return ("cpu-default", "cpu-default")
    module_set_id = threaded_module_set if threaded_module_set is not None else "legacy"
    det_rec_variant_id = threaded_det_rec_variant if threaded_det_rec_variant is not None else "legacy"
    return (module_set_id, det_rec_variant_id)


__all__ = (
    "MODULE_SET_ENV_VAR",
    "DET_REC_VARIANT_ENV_VAR",
    "resolve_module_set_value",
    "resolve_det_rec_variant_value",
    "is_gpu_lane",
    "module_set_warn_message",
    "det_rec_variant_warn_message",
    "derive_run_summary_identifiers",
)
