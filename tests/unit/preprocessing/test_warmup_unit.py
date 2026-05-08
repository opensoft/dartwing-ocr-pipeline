"""Feature 016 (T012 / US1): CPU-safe unit tests for ``preprocessing.warmup``.

These tests exercise the warmup module against a stub engine (no paddle, no
MIOpen, no GPU). They cover the contracts in:

- ``contracts/module-invariants.md`` I-1 (one warmup pass per process)
- ``contracts/module-invariants.md`` I-4 (no fold into caller phase_timings)
- ``contracts/module-invariants.md`` I-7 (env-var defaults scoped, operator override wins)
- ``contracts/module-invariants.md`` I-8 (fixture digest stable)
- ``data-model.md`` §WarmupError (closed cause-class taxonomy)
- ``research.md`` R-016.6 (cause-class routing rules)

The tests use the real warmup fixture
(``tests/stage1_vendor_identity/inv_001_easy/source.pdf``) so the loader path
is exercised end-to-end. The engine is a lightweight stub class with a
counter; no `paddleocr` or `paddle` is imported.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

# Skip the entire file if the optional preprocessing deps (PIL / numpy /
# pypdfium2) are unavailable — matches the conftest defensive-import pattern
# used by other unit tests under tests/unit/preprocessing/. The CPU test
# suite under devcontainer / CI has these installed.
pytest.importorskip("PIL")
pytest.importorskip("numpy")
pytest.importorskip("pypdfium2")

from ledgerlinc_ocr.preprocessing import warmup as warmup_mod
from ledgerlinc_ocr.preprocessing.errors import WarmupError


@pytest.fixture(autouse=True)
def _reset_warmup_state():
    """Reset the once-per-process module-level state before AND after each
    test so tests are independent (the production guarantee is that
    `_WARMUP_RAN` only flips back via `reset_warmup_state()`)."""
    warmup_mod.reset_warmup_state()
    yield
    warmup_mod.reset_warmup_state()


@pytest.fixture
def _restore_miopen_env(monkeypatch):
    """Save and restore the four MIOpen env vars that `_apply_env_defaults`
    may set, so a test that mutates them does not leak into sibling tests."""
    saved = {
        name: os.environ.get(name)
        for name in (
            "MIOPEN_FIND_MODE",
            "MIOPEN_USER_DB_PATH",
            "MIOPEN_CUSTOM_CACHE_DIR",
            "MIOPEN_LOG_LEVEL",
        )
    }
    yield
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


class _StubEngine:
    """Minimal stand-in for `paddleocr.PPStructureV3`. Records the count
    and the input shape of each `predict(...)` call. Optional `raises` lets
    a test inject an exception."""

    def __init__(self, raises: Exception | None = None) -> None:
        self.calls = 0
        self.raises = raises
        self.last_input_shape: tuple[int, ...] | None = None

    def predict(self, np_img: Any) -> list[Any]:
        self.calls += 1
        try:
            self.last_input_shape = tuple(np_img.shape)
        except Exception:
            self.last_input_shape = None
        if self.raises is not None:
            raise self.raises
        # Mimic V3's iterable result; warmup discards it.
        return []


# ---------------------------------------------------------------------------
# Once-per-process guard (I-1, FR-001, FR-004)
# ---------------------------------------------------------------------------


def test_run_warmup_calls_predict_exactly_once_then_caches() -> None:
    """First invocation calls `engine.predict` exactly once; second
    invocation returns the cached `WarmupResult` and does NOT re-invoke
    predict (I-1 / FR-001 / FR-004)."""
    engine = _StubEngine()
    result1 = warmup_mod.run_warmup(engine)
    result2 = warmup_mod.run_warmup(engine)

    assert engine.calls == 1, (
        f"expected exactly 1 predict call across two run_warmup invocations; "
        f"got {engine.calls}"
    )
    assert result1 is result2, "second call must return the cached WarmupResult"


def test_run_warmup_records_six_decimal_seconds() -> None:
    """`WarmupResult.seconds` is six-decimal-rounded per
    `contracts/run-summary-schema.md` §2."""
    engine = _StubEngine()
    result = warmup_mod.run_warmup(engine)
    rounded = round(result.seconds, 6)
    assert result.seconds == rounded, (
        f"seconds must be six-decimal-rounded; got {result.seconds!r}"
    )
    assert result.seconds > 0, "seconds must be strictly positive"


def test_get_cached_warmup_seconds_returns_none_initially() -> None:
    """Before the first `run_warmup`, `get_cached_warmup_seconds()` returns
    None (no cached result)."""
    assert warmup_mod.get_cached_warmup_seconds() is None


def test_get_cached_warmup_seconds_returns_value_after_warmup() -> None:
    engine = _StubEngine()
    result = warmup_mod.run_warmup(engine)
    assert warmup_mod.get_cached_warmup_seconds() == result.seconds


# ---------------------------------------------------------------------------
# Cause-class taxonomy (data-model.md §WarmupError, research R-016.6)
# ---------------------------------------------------------------------------


def test_warmup_error_wraps_unknown_failure() -> None:
    """A predict failure whose underlying exception module is not paddle*
    or MIOpen* maps to cause_class='UnknownError' per R-016.6 catch-all."""
    err = RuntimeError("synthetic failure")
    engine = _StubEngine(raises=err)
    with pytest.raises(WarmupError) as exc_info:
        warmup_mod.run_warmup(engine)
    assert exc_info.value.cause_class == "UnknownError", (
        f"expected cause_class='UnknownError'; got {exc_info.value.cause_class!r}"
    )
    assert exc_info.value.cause_module == type(err).__module__
    assert "synthetic failure" in str(exc_info.value)


def test_warmup_error_routes_paddle_failure_to_paddle_error() -> None:
    """An exception whose module starts with `paddleocr` / `paddlex` /
    `paddle` routes to cause_class='PaddleError' per R-016.6."""

    class _FakePaddleError(Exception):
        pass

    _FakePaddleError.__module__ = "paddleocr.subpkg"
    err = _FakePaddleError("paddle internal")
    engine = _StubEngine(raises=err)
    with pytest.raises(WarmupError) as exc_info:
        warmup_mod.run_warmup(engine)
    assert exc_info.value.cause_class == "PaddleError"


def test_warmup_error_routes_miopen_failure_to_miopen_error() -> None:
    """An exception whose module starts with `MIOpen` (case-insensitive)
    or `comgr` routes to cause_class='MIOpenError' per R-016.6."""

    class _FakeMIOpenError(Exception):
        pass

    _FakeMIOpenError.__module__ = "MIOpen.kernel_db"
    err = _FakeMIOpenError("kernel selection failed")
    engine = _StubEngine(raises=err)
    with pytest.raises(WarmupError) as exc_info:
        warmup_mod.run_warmup(engine)
    assert exc_info.value.cause_class == "MIOpenError"


def test_warmup_error_routes_comgr_failure_to_miopen_error() -> None:
    """The MIOpenError taxonomy bucket also covers `comgr*` modules."""

    class _FakeComgrError(Exception):
        pass

    _FakeComgrError.__module__ = "comgr.compile"
    err = _FakeComgrError("HIP shader compile failed")
    engine = _StubEngine(raises=err)
    with pytest.raises(WarmupError) as exc_info:
        warmup_mod.run_warmup(engine)
    assert exc_info.value.cause_class == "MIOpenError"


def test_warmup_error_on_missing_fixture(tmp_path: Path) -> None:
    """A non-existent fixture path raises WarmupError(cause_class=
    'FixtureLoadError'); fail-fast per FR-007."""
    engine = _StubEngine()
    bad_path = tmp_path / "does-not-exist.pdf"
    with pytest.raises(WarmupError) as exc_info:
        warmup_mod.run_warmup(engine, fixture_path=bad_path)
    assert exc_info.value.cause_class == "FixtureLoadError"
    # On fixture-load failure we MUST NOT have called the engine.
    assert engine.calls == 0


def test_warmup_error_does_not_set_warmup_ran_flag() -> None:
    """A failed warmup MUST NOT flip `_WARMUP_RAN` to True — a subsequent
    retry is allowed (no silent caching of failure state)."""
    engine = _StubEngine(raises=RuntimeError("boom"))
    with pytest.raises(WarmupError):
        warmup_mod.run_warmup(engine)
    # Subsequent retry with a working engine succeeds.
    good_engine = _StubEngine()
    result = warmup_mod.run_warmup(good_engine)
    assert good_engine.calls == 1
    assert result.seconds > 0


# ---------------------------------------------------------------------------
# Fixture digest stability (I-8)
# ---------------------------------------------------------------------------


def test_fixture_digest_stable_across_invocations() -> None:
    """The sha256 digest stored on `WarmupResult.fixture_sha256` is stable
    across two independent invocations on the same fixture (I-8)."""
    engine_a = _StubEngine()
    result_a = warmup_mod.run_warmup(engine_a)
    digest_a = result_a.fixture_sha256

    warmup_mod.reset_warmup_state()

    engine_b = _StubEngine()
    result_b = warmup_mod.run_warmup(engine_b)
    digest_b = result_b.fixture_sha256

    assert digest_a == digest_b, (
        f"fixture sha256 must be stable across invocations; "
        f"a={digest_a!r}, b={digest_b!r}"
    )
    assert len(digest_a) == 64, "sha256 hex must be 64 characters"


# ---------------------------------------------------------------------------
# I-4: no fold into caller phase_timings
#
# `run_warmup` accepts no caller-supplied phase_timings dict, so a direct
# "did the dict change?" assertion would be tautological. The real I-4
# guarantee — that warmup's seconds flow into run_summary only via
# `attach_one_time_gpu_phases(record, readout, warmup_seconds=...)` and
# never inflate `phase_timings.total` / per-document phase keys — is
# enforced at the schema layer in
# `tests/pipeline_tests/test_run_summary_schema_0_1_3.py`. Keeping a
# unit-level placeholder here so the I-4 contract has a labeled landing
# spot in this file.
# ---------------------------------------------------------------------------


def test_run_warmup_returns_seconds_only_via_warmup_result() -> None:
    """Surface contract: the only seconds value `run_warmup` exposes is
    `WarmupResult.seconds` (six-decimal-rounded perf_counter delta).
    `run_warmup` does not accept or mutate a caller `phase_timings` dict —
    callers thread `WarmupResult.seconds` through
    `pipeline.timing.attach_one_time_gpu_phases(..., warmup_seconds=...)`
    on the run_summary side. This is the unit-level half of I-4; the
    schema-level half lives in `test_run_summary_schema_0_1_3.py`."""
    engine = _StubEngine()
    result = warmup_mod.run_warmup(engine)
    assert isinstance(result, warmup_mod.WarmupResult)
    assert isinstance(result.seconds, float)
    assert result.seconds == round(result.seconds, 6)
    # The cached accessor returns the same seconds — no separate path.
    assert warmup_mod.get_cached_warmup_seconds() == result.seconds


# ---------------------------------------------------------------------------
# Env-var defaults (I-7, R-016.4 / R-016.5, FR-015 operator-override-wins)
# ---------------------------------------------------------------------------


def test_run_warmup_applies_env_defaults_when_unset(_restore_miopen_env) -> None:
    """When `MIOPEN_FIND_MODE` (and siblings) are unset, `run_warmup`
    sets them to the feature defaults (R-016.4 / R-016.5)."""
    for name in (
        "MIOPEN_FIND_MODE",
        "MIOPEN_USER_DB_PATH",
        "MIOPEN_CUSTOM_CACHE_DIR",
        "MIOPEN_LOG_LEVEL",
    ):
        os.environ.pop(name, None)

    engine = _StubEngine()
    warmup_mod.run_warmup(engine)

    assert os.environ.get("MIOPEN_FIND_MODE") == "2"
    assert os.environ.get("MIOPEN_LOG_LEVEL") == "2"
    # The path-shaped vars should be non-empty (resolved to $HOME/.cache/miopen).
    assert os.environ.get("MIOPEN_USER_DB_PATH"), "MIOPEN_USER_DB_PATH must be set"
    assert os.environ.get("MIOPEN_CUSTOM_CACHE_DIR"), "MIOPEN_CUSTOM_CACHE_DIR must be set"


def test_run_warmup_preserves_operator_set_env(_restore_miopen_env) -> None:
    """Operator override wins (FR-015 / R-016.4 / R-016.5): if
    `MIOPEN_FIND_MODE=99` is already set, `run_warmup` MUST NOT clobber
    it back to '2'."""
    os.environ["MIOPEN_FIND_MODE"] = "99"

    engine = _StubEngine()
    warmup_mod.run_warmup(engine)

    assert os.environ.get("MIOPEN_FIND_MODE") == "99", (
        "operator-set MIOPEN_FIND_MODE must not be overwritten by warmup defaults"
    )
