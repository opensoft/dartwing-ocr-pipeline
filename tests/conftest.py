"""Repo-root pytest conftest (feature 014 / T009).

Registers the `gpu` pytest marker, runs the FR-001 preflight classifier
once per session via a session-scoped fixture, and skip-gates any
`@pytest.mark.gpu`-decorated test with a reason that traces back to
the FR-001 state (FR-019).

Defensive import safety (analyze finding RR6 / RR15 / NEW.14): the
`from dartwing_ocr.preprocessing.preflight import …` statement and
the `classify(...)` call are both wrapped in `try/except Exception`
(broader than `ImportError` alone — defensive belt-and-suspenders
against transitive enum/typing failures or partial-import breakage
inside `preflight.py`). On unrecoverable failure, conftest synthesizes
a sentinel readout-shaped object with `state == "paddle_not_installed"`
(the documented default per T009 — no new enum value is added) and a
recommendation string of the form `"preflight import failed: <class>: <msg>"`.
The default-CI pytest invocation MUST never crash at collection time
because conftest could not import preflight; gpu-marked tests must
SKIP, not ERROR.

`Exception` is intentionally narrower than `BaseException` —
`KeyboardInterrupt` and `SystemExit` are NOT caught, so Ctrl+C during
conftest initialization halts the test session normally rather than
being silently swallowed.

Sub-conftests under `tests/contract_tests/`, `tests/pipeline_tests/`,
`tests/integration/*/`, and `tests/evaluator_tests/` remain
subdirectory-scoped and do not conflict with this root-level conftest.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest


# A minimal sentinel readout-shaped object used when the real preflight
# module cannot be imported. Has just enough surface (`state.value` and
# `recommendation`) for `pytest_collection_modifyitems` to format a
# meaningful skip reason. Implemented as a plain dataclass with a
# nested `state` object, NOT as `PreflightReadout`, so that conftest
# does not depend on the dataclass shape at fallback time.
@dataclass
class _SentinelState:
    value: str = "paddle_not_installed"


@dataclass
class _SentinelReadout:
    state: _SentinelState
    recommendation: str


_PREFLIGHT_IS_SUCCESS_VALUE = "ppstructurev3_init_succeeded"


def _load_preflight_readout() -> object:
    """Load and cache the preflight classifier readout, with a defensive
    fallback if `preflight.py` is missing or broken at import time.
    """
    try:
        from dartwing_ocr.preprocessing.preflight import classify  # type: ignore[import-not-found]
        return classify(attempt_ppstructurev3_init=True)
    except Exception as exc:  # noqa: BLE001 - intentional defensive scope; see RR15.
        return _SentinelReadout(
            state=_SentinelState(value="paddle_not_installed"),
            recommendation=(
                f"preflight import failed: {type(exc).__name__}: {str(exc)[:200]}"
            ),
        )


def pytest_configure(config: pytest.Config) -> None:
    """Register the `gpu` marker globally."""
    config.addinivalue_line(
        "markers",
        "gpu: requires Paddle GPU readiness per FR-001 "
        "(state ppstructurev3_init_succeeded)",
    )


@pytest.fixture(scope="session")
def preflight_readout() -> object:  # pragma: no cover - exercised indirectly
    """Session-scoped cache of one classify() call. Tests may opt-in to
    inspect the readout directly; the marker hook below uses the same
    cache."""
    return _cached_readout()


_CACHED_READOUT: Optional[object] = None


def _cached_readout() -> object:
    global _CACHED_READOUT
    if _CACHED_READOUT is None:
        _CACHED_READOUT = _load_preflight_readout()
    return _CACHED_READOUT


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip-gate `@pytest.mark.gpu` items based on the cached preflight
    state. Skip reason traces back to the FR-001 state per FR-019.
    """
    readout = _cached_readout()
    state_value = getattr(readout.state, "value", str(readout.state))
    if state_value == _PREFLIGHT_IS_SUCCESS_VALUE:
        return
    reason = (
        f"skipped: state={state_value}; "
        f"{getattr(readout, 'recommendation', '')}"
    )
    skip_marker = pytest.mark.skip(reason=reason)
    for item in items:
        if item.get_closest_marker("gpu") is not None:
            item.add_marker(skip_marker)
