"""Exceptions and exit codes for the preprocessing slice."""

from __future__ import annotations

EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_INPUT_REJECTED = 2
EXIT_INTERNAL_ERROR = 3
# Feature 016 (T011 / contracts/cli-contract.md §4): the warmup-failed
# exit code, immediately following feature 014's preflight 10–14 range.
# **Used only by `preprocessing/cli.py` (the `ledgerlinc-preprocess`
# single-doc CLI)** when catching WarmupError raised by the hoisted
# `pipeline.run_warmup_if_active(...)` call. The pipeline package
# (`pipeline/cli.py` + `pipeline/corpus_run.py`) uses the equivalent
# `ExitCode.WARMUP_FAILED = 15` enum from `pipeline/exit_codes.py`
# instead of importing this constant — see the runner's
# `_classify_stage_exception` and the cold/warm-corpus warmup catches.
# The two sources are kept in sync at value 15 and an amendment to
# either MUST update both (Copilot PR #24 round 5).
EXIT_WARMUP_FAILED = 15


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
