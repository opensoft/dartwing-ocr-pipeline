"""Exceptions and exit codes for the preprocessing slice."""

from __future__ import annotations

from typing import Literal

EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_INPUT_REJECTED = 2
EXIT_INTERNAL_ERROR = 3
# Feature 016 (T011 / contracts/cli-contract.md §4): the warmup-failed
# exit code, immediately following feature 014's preflight 10–14 range.
# Derived from the canonical `ExitCode.WARMUP_FAILED` enum in
# `pipeline/exit_codes.py` so the two surfaces have a single source of
# truth — drift is now a type/import error, not a silent value mismatch
# (Copilot PR #24 round 6). `preprocessing/cli.py` imports this constant;
# the pipeline package uses the enum directly.
from ledgerlinc_ocr.pipeline.exit_codes import ExitCode as _ExitCode

EXIT_WARMUP_FAILED: int = int(_ExitCode.WARMUP_FAILED)
# Feature 017 (T002 / T003 / R-017.9 / contracts/cli-contract.md §4): the
# unknown-preset exit code, immediately following feature 016's WARMUP_FAILED.
# Same single-source-of-truth pattern as EXIT_WARMUP_FAILED.
EXIT_UNKNOWN_PRESET: int = int(_ExitCode.UNKNOWN_PRESET)


class PreprocessingError(Exception):
    """Base class for all preprocessing-slice failures."""

    exit_code = EXIT_INTERNAL_ERROR


class InputRejectedError(PreprocessingError):
    """Non-recoverable malformed input — exits 2, no artifact written."""

    exit_code = EXIT_INPUT_REJECTED


class NonPdfInputError(InputRejectedError):
    """File at --source-file is not a PDF (missing %PDF- magic)."""


class EncryptedPdfError(InputRejectedError):
    """PDF is password-protected / encrypted and cannot be opened."""


class MalformedPdfError(InputRejectedError):
    """PDF bytes are unreadable or structurally broken at the document level."""


class ZeroPagePdfError(InputRejectedError):
    """PDF parses but reports zero pages."""


class ArtifactInvalidError(PreprocessingError):
    """Assembled artifact failed contract validation — indicates a code/contract mismatch."""

    exit_code = EXIT_INTERNAL_ERROR


class EngineInitError(PreprocessingError):
    """FR-016 hard-fail: PPStructureV3 could not be constructed.

    Carries structured cause information so the CLI layer can emit the FR-016
    error envelope without re-parsing the exception string. The `missing_weight`
    and `weight_hoster_url` fields are populated only when the init failure is
    classified as a weight-download failure (research R-008).
    """

    exit_code = EXIT_INTERNAL_ERROR

    def __init__(
        self,
        message: str,
        cause_class: str,
        cause_module: str,
        missing_weight: str | None = None,
        weight_hoster_url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.cause_class = cause_class
        self.cause_module = cause_module
        self.missing_weight = missing_weight
        self.weight_hoster_url = weight_hoster_url


class WarmupError(PreprocessingError):
    """Feature 016 fail-fast: the explicit GPU warmup pass raised.

    Wraps any exception raised by `preprocessing.warmup.run_warmup`'s fixture
    loader, clock-anomaly check, env-default application, or the underlying
    ``engine.predict(...)`` call. The cause-class taxonomy is the closed set
    documented in `specs/016-gpu-warmup-miopen-cache/data-model.md` §WarmupError:
    ``{"FixtureLoadError", "ClockAnomaly", "MIOpenError", "PaddleError",
    "UnknownError"}``. Tests, monitoring, and downstream consumers may assert
    that ``cause_class`` is always one of these five strings.

    Caught at the runner/corpus_run boundary; surfaced as ``error: warmup
    failed: <cause_class>: <message>`` on stderr with exit code 15
    (``EXIT_WARMUP_FAILED``). Per spec FR-007 / SC-011, on this failure no
    ``run_summary`` line is emitted and no ``preprocess_output.json`` is
    written for any document that would have been timed after the failed
    warmup; the run MUST NOT silently downgrade.
    """

    exit_code = EXIT_WARMUP_FAILED

    def __init__(
        self,
        message: str,
        *,
        cause_class: str,
        cause_module: str,
    ) -> None:
        super().__init__(message)
        self.cause_class = cause_class
        self.cause_module = cause_module


class UnknownPresetError(ValueError):
    """Feature 017 fail-fast: an unknown preset value was selected.

    Raised by `preprocessing/presets.py::resolve_module_set` and
    `resolve_det_rec_variant` (feature 017), by
    `preprocessing/raster_profiles.py::resolve_raster_profile` and
    `preprocessing/region_strategies.py::resolve_region_strategy`
    (feature 018), and by
    `preprocessing/preprocess_strategies.py::resolve_preprocess_strategy`
    (feature 019), when the operator passes a value not in the
    corresponding closed registry (e.g., a typo like
    `--module-set=reduced-v99`, `--det-rec-variant=ppocrv9_imaginary`,
    `--raster-profile=reduced-v99`, `--region-strategy=header-first-v99`,
    or `--preprocess-strategy=ocr-only-v99`). Caught at the CLI parse
    boundary BEFORE any Paddle import (the lightweight ``preflight``
    module is imported earlier — it is CPU-safe and does not pull in
    Paddle until ``classify()`` actually runs); surfaced as
    ``error: unknown <preset_axis>: <preset_value!r> — valid values
    are: <comma-separated valid_values>`` on stderr with exit code 16
    (``EXIT_UNKNOWN_PRESET``). Per spec FR-013 / R-017.9 / R-017.12
    (feature 017) and FR-014 / R-018.12 (feature 018), on this
    failure no `run_summary` line is emitted, no engine is
    constructed, and no `preprocess_output.json` is written.

    Subclass of `ValueError` per data-model.md §UnknownPresetError so
    the error reads as "you passed me a bad value" semantically; the
    `exit_code` class attribute mirrors the WarmupError pattern so CLI
    catch sites can route uniformly.

    **Stability stance**: ``preset_axis`` is a closed five-element
    string literal type at the type level (two values added by
    feature 017; two more added by feature 018; one more added by
    feature 019). Adding a sixth axis is a future feature-level
    decision, not an implementation choice. ``valid_values`` is
    informational (shape contract); its content evolves as the
    registries grow, but its tuple type is stable.
    """

    exit_code = EXIT_UNKNOWN_PRESET

    def __init__(
        self,
        message: str,
        *,
        preset_axis: Literal[
            "module_set", "det_rec_variant",       # feature 017
            "raster_profile", "region_strategy",   # feature 018 (R-018.12)
            "preprocess_strategy",                 # feature 019 (R-019.12)
        ],
        preset_value: str,
        valid_values: tuple[str, ...],
    ) -> None:
        super().__init__(message)
        self.preset_axis = preset_axis
        self.preset_value = preset_value
        self.valid_values = valid_values
