"""Feature 016: opt-in GPU warmup pass for ``ppstructurev3@gpu``.

Runs exactly one PPStructureV3 inference against a fixed reference fixture
after engine construction and before the first timed document, so MIOpen
kernel-selection and COMGR compilation cost is paid up front and reported
separately from per-document OCR time via the additive
``phase_timings.warmup`` key on the first successful per-document
``run_summary`` entry.

Module-level state (``_WARMUP_RAN``, ``_CACHED_RESULT``) enforces the
once-per-process rule (FR-001 / FR-004 / `contracts/module-invariants.md` I-1
/ research R-016.10). The module is intended to be imported lazily on the
GPU branch only — CPU and stub paths MUST NOT trigger this import per
FR-011 / I-6.

Public API:

- ``WarmupResult`` — frozen dataclass returned by ``run_warmup``
- ``run_warmup(engine, *, fixture_path=None) -> WarmupResult``
- ``reset_warmup_state()`` — test-only; clears the once-per-process cache

Side effects (only when ``run_warmup`` is invoked):

- Sets ``MIOPEN_FIND_MODE=2``, ``MIOPEN_USER_DB_PATH=$HOME/.cache/miopen``,
  ``MIOPEN_CUSTOM_CACHE_DIR=$HOME/.cache/miopen``, ``MIOPEN_LOG_LEVEL=2`` —
  but ONLY when each is currently unset (operator override wins per
  research R-016.4 / R-016.5 / FR-015).
- Populates ``~/.cache/miopen`` and ``~/.cache/comgr`` as MIOpen/COMGR run.

The cause-class taxonomy attached to ``WarmupError`` is the closed set
documented in ``data-model.md`` §WarmupError. Routing rules per research
R-016.6:

- Underlying exception module starts with ``MIOpen`` or ``comgr`` →
  ``cause_class="MIOpenError"``
- Module starts with ``paddle``, ``paddleocr``, or ``paddlex`` →
  ``cause_class="PaddleError"``
- Anything else from ``engine.predict`` → ``cause_class="UnknownError"``
- Fixture load failures → ``cause_class="FixtureLoadError"``
- ``time.perf_counter()`` returns non-positive elapsed → ``cause_class="ClockAnomaly"``
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import time
import warnings as _std_warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

from ledgerlinc_ocr.preprocessing.errors import WarmupError
from ledgerlinc_ocr.preprocessing.rasterize import (
    PageRaster,
    PageRasterFailure,
    rasterize_pdf,
)
from ledgerlinc_ocr.preprocessing.version import DPI


_FIXTURE_ENV_VAR: str = "LEDGERLINC_WARMUP_FIXTURE_PATH"


def _resolve_default_fixture() -> Path:
    """Locate ``tests/stage1_vendor_identity/inv_001_easy/source.pdf``
    relative to this module's import path.

    Resolution order:

    1. ``$LEDGERLINC_WARMUP_FIXTURE_PATH`` env var (operator override —
       primary escape hatch for installed distributions where the
       repo's ``tests/`` tree is not on disk).
    2. Walk parents of this module until a ``tests/stage1_vendor_identity/
       inv_001_easy/source.pdf`` is found (the dev-from-repo path).
    3. Fall back to the relative literal path. ``run_warmup`` will then
       raise ``WarmupError(cause_class="FixtureLoadError")`` on first
       call with a message instructing operators to set the env var or
       supply ``fixture_path=`` explicitly. This is intentional fail-
       fast — the feature is not silently degraded.
    """
    env_value = os.environ.get(_FIXTURE_ENV_VAR)
    if env_value:
        return Path(env_value).expanduser()
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        candidate = (
            ancestor / "tests" / "stage1_vendor_identity" / "inv_001_easy" / "source.pdf"
        )
        if candidate.is_file():
            return candidate
    return Path("tests/stage1_vendor_identity/inv_001_easy/source.pdf")


_DEFAULT_FIXTURE_PATH: Path = _resolve_default_fixture()


_DEFAULT_ENV_VARS: tuple[tuple[str, str], ...] = (
    ("MIOPEN_FIND_MODE", "2"),
    ("MIOPEN_USER_DB_PATH", str(Path.home() / ".cache" / "miopen")),
    ("MIOPEN_CUSTOM_CACHE_DIR", str(Path.home() / ".cache" / "miopen")),
    ("MIOPEN_LOG_LEVEL", "2"),
)


_WARMUP_RAN: bool = False
_CACHED_RESULT: "Optional[WarmupResult]" = None


@dataclass(frozen=True)
class WarmupResult:
    """Result returned by ``run_warmup`` (data-model.md §WarmupResult).

    ``seconds`` is six-decimal-rounded; ``fixture_sha256`` is the sha256 of
    the rasterized PIL image bytes (NOT the source PDF) so a future
    PDF-loader change that produces the same pixels still hashes
    identically. ``fixture_sha256`` and ``fixture_path`` are diagnostic
    only — they never appear in ``run_summary`` (only ``seconds`` flows
    through to ``phase_timings.warmup``)."""

    seconds: float
    fixture_sha256: str
    fixture_path: Path


def reset_warmup_state() -> None:
    """Test-only: clear ``_WARMUP_RAN`` and ``_CACHED_RESULT`` so tests can
    invoke ``run_warmup`` repeatedly within a session without the
    once-per-process guard short-circuiting the second call."""
    global _WARMUP_RAN, _CACHED_RESULT
    _WARMUP_RAN = False
    _CACHED_RESULT = None


def get_cached_warmup_seconds() -> Optional[float]:
    """Public accessor: return ``_CACHED_RESULT.seconds`` if a warmup
    completed successfully in this process, else ``None``. Used by the
    single-doc CLI and the corpus runner to thread the captured seconds
    into ``attach_one_time_gpu_phases(..., warmup_seconds=...)``  per
    R-016.8 / contracts/run-summary-schema.md §3.

    Returns ``None`` when warmup never ran OR when warmup raised
    (the run already exited 15 in that case, so this never gets called
    on the failure path)."""
    if _CACHED_RESULT is None:
        return None
    return _CACHED_RESULT.seconds


def _apply_env_defaults() -> None:
    """Set MIOpen/COMGR default env vars only when each is currently unset
    or empty — operator override wins (research R-016.4 / R-016.5 /
    FR-015). Side-effect-free for already-set vars."""
    for name, value in _DEFAULT_ENV_VARS:
        if not os.environ.get(name):
            os.environ[name] = value


def _classify_cause(exc: Exception) -> str:
    """Map an underlying exception to one of the closed cause-class
    taxonomy values (data-model.md §WarmupError, research R-016.6).

    The paddle prefix subsumes ``paddleocr`` and ``paddlex`` because
    ``str.startswith("paddle")`` matches both — a single check is
    sufficient.
    """
    module = (type(exc).__module__ or "").lower()
    if module.startswith(("miopen", "comgr")):
        return "MIOpenError"
    if module.startswith("paddle"):
        return "PaddleError"
    return "UnknownError"


def _load_fixture(fixture_path: Path) -> tuple[np.ndarray, str]:
    """Load page 1 of ``fixture_path`` rasterized at ``DPI``. Returns
    ``(np_image, sha256_hex)`` where ``np_image`` is the RGB numpy array
    fed to ``engine.predict`` and ``sha256_hex`` is the digest of the PIL
    image bytes (per data-model.md §WarmupResult — NOT the source PDF).

    Raises ``WarmupError(cause_class="FixtureLoadError")`` on any IO / PDF
    / PIL error — fail-fast per FR-007."""
    try:
        if not fixture_path.is_file():
            # When operators run an installed distribution (no `tests/`
            # tree on disk) the auto-resolved default falls back to a
            # relative literal that does not exist. Point them at the
            # `LEDGERLINC_WARMUP_FIXTURE_PATH` escape hatch so they can
            # supply any local PDF as the warmup fixture without shipping
            # `tests/` as package data.
            raise FileNotFoundError(
                f"warmup fixture not found at {fixture_path}; set "
                f"{_FIXTURE_ENV_VAR}=/path/to/source.pdf or pass "
                f"fixture_path= explicitly when invoking from a non-repo install"
            )
        # `rasterize_pdf` is a generator that closes the underlying
        # `PdfDocument` in its `finally` clauses. Because we only consume
        # the first page, wrap the iterator in `contextlib.closing` to
        # force prompt `.close()` (which runs the generator's finally
        # blocks) instead of waiting for GC — avoids leaking pdfium
        # file handles in long-lived warmup processes (Copilot PR #24
        # round 4).
        with contextlib.closing(rasterize_pdf(fixture_path, dpi=DPI)) as pages:
            for page in pages:
                if isinstance(page, PageRasterFailure):
                    raise RuntimeError(
                        f"warmup fixture page 1 rasterize failed: {page.error}"
                    )
                assert isinstance(page, PageRaster)
                image = page.image
                try:
                    digest = hashlib.sha256(image.tobytes()).hexdigest()
                    np_img = np.array(image)
                finally:
                    # Release the PIL raster buffer once we have the
                    # numpy array + digest. Mirrors the page-loop close
                    # in `preprocessing/pipeline.py::_process_page` so
                    # repeated warmup retries don't leak large buffers.
                    try:
                        image.close()
                    except Exception:
                        pass
                return np_img, digest
            raise RuntimeError(
                f"warmup fixture {fixture_path} produced no pages"
            )
    except WarmupError:
        raise
    except Exception as exc:
        raise WarmupError(
            f"warmup fixture load failed: {type(exc).__name__}: {exc}",
            cause_class="FixtureLoadError",
            cause_module=type(exc).__module__ or "",
        ) from exc


def run_warmup(
    engine: Any,
    *,
    fixture_path: Path | None = None,
) -> WarmupResult:
    """Run exactly one PPStructureV3 warmup inference against the canonical
    fixture (research R-016.2 / contracts/module-invariants.md I-8).

    Once-per-process guard (FR-001 / FR-004 / I-1): on first invocation,
    runs ``engine.predict(np_img)`` once, measures ``time.perf_counter()``
    delta, sets module-level ``_WARMUP_RAN = True`` and caches the
    ``WarmupResult``. On second-or-later invocation in the same process,
    returns the cached result without re-invoking ``engine.predict`` and
    without re-applying env-var defaults.

    Parameters
    ----------
    engine
        The already-adopted ``paddleocr.PPStructureV3`` instance from
        ``ocr._ENGINE``. Must NOT be a freshly-constructed engine —
        caller's contract per FR-003 / I-2.
    fixture_path
        Optional override for the warmup fixture. Defaults to the resolved
        ``_DEFAULT_FIXTURE_PATH``.

    Returns
    -------
    WarmupResult
        ``seconds`` (six-decimal-rounded perf_counter delta), ``fixture_sha256``
        (diagnostic), ``fixture_path`` (diagnostic).

    Raises
    ------
    WarmupError
        On any failure during fixture load, env-var setup, clock anomaly,
        or ``engine.predict``. The ``cause_class`` is one of
        ``{"FixtureLoadError", "ClockAnomaly", "MIOpenError",
        "PaddleError", "UnknownError"}`` (data-model.md §WarmupError).
    """
    global _WARMUP_RAN, _CACHED_RESULT
    if _WARMUP_RAN:
        assert _CACHED_RESULT is not None, (
            "_WARMUP_RAN is True but _CACHED_RESULT is None — internal invariant violation"
        )
        return _CACHED_RESULT

    path = fixture_path if fixture_path is not None else _DEFAULT_FIXTURE_PATH

    _apply_env_defaults()

    np_img, digest = _load_fixture(path)

    t0 = time.perf_counter()
    try:
        # Suppresses Python-side `warnings` only (e.g., paddle deprecation
        # notices through `warnings.warn`). MIOpen/COMGR diagnostics emit
        # directly on C-side stderr and are unaffected — those are split
        # into "addressed by default config" vs "residual" per the FR-016
        # hybrid policy, not silenced here.
        with _std_warnings.catch_warnings():
            _std_warnings.simplefilter("ignore")
            engine.predict(np_img)
    except WarmupError:
        raise
    except Exception as exc:
        cause_class = _classify_cause(exc)
        raise WarmupError(
            f"warmup predict failed: {type(exc).__name__}: {exc}",
            cause_class=cause_class,
            cause_module=type(exc).__module__ or "",
        ) from exc

    elapsed = time.perf_counter() - t0
    if elapsed <= 0:
        raise WarmupError(
            f"warmup clock anomaly: perf_counter elapsed = {elapsed!r}",
            cause_class="ClockAnomaly",
            cause_module="time",
        )

    # Round to six-decimal seconds (run-summary-schema.md §2). Sub-microsecond
    # `engine.predict` (e.g., a stub returning immediately) collapses to
    # 0.0 under naive `round`, contradicting the strictly-positive
    # invariant tests assert on. Clamp to the smallest representable
    # positive 6-decimal value (1e-6) so a successful warmup always
    # surfaces non-zero seconds.
    seconds_rounded = round(elapsed, 6)
    # `elapsed` was already validated `> 0` above, so a zero result here can
    # only come from rounding-down at the six-decimal grain. `<= 0` is
    # exactly equivalent to `== 0.0` in this branch and avoids the
    # SonarCloud float-equality rule (S1244).
    if seconds_rounded <= 0:
        seconds_rounded = 1e-6
    result = WarmupResult(
        seconds=seconds_rounded,
        fixture_sha256=digest,
        fixture_path=path,
    )
    _WARMUP_RAN = True
    _CACHED_RESULT = result
    return result


__all__ = [
    "WarmupResult",
    "run_warmup",
    "reset_warmup_state",
    "get_cached_warmup_seconds",
]
