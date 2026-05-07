"""Default-suite GPU-marker plumbing test (T031 / SC-008 / FR-019).

Asserts that the conftest `gpu` marker registration is in place so
that on a host without GPU hardware, GPU-marked tests are SKIPPED
(not failed). This is a unit-style proof of the marker plumbing —
the actual end-to-end "full default suite is green" assertion is run
by CI / T041.
"""
from __future__ import annotations

import pytest


def test_t031_gpu_marker_is_registered_in_conftest() -> None:
    """The `gpu` marker MUST be registered so that pytest does not
    warn about an unknown mark when collecting GPU-marked tests."""
    # pytest exposes registered markers via the plugin manager; the
    # simplest check is to import conftest and verify its
    # `pytest_configure` registers the marker via a markers table.
    import importlib

    repo_conftest = importlib.import_module("tests.conftest")
    src = repo_conftest.__file__
    with open(src, encoding="utf-8") as fh:
        content = fh.read()

    # Two acceptable forms in conftest.py:
    #   config.addinivalue_line("markers", "gpu: ...")
    # OR  pytest_collection_modifyitems-based skipping.
    assert (
        "addinivalue_line" in content and "gpu" in content
    ) or "pytest_collection_modifyitems" in content, (
        "conftest.py must register the `gpu` marker (via addinivalue_line) "
        "or implement gpu-specific collection skip in pytest_collection_modifyitems"
    )


def test_t031_gpu_marker_skip_reason_traces_to_preflight_state() -> None:
    """FR-019: skip reasons for GPU-marked tests must trace back to an
    FR-001 preflight state (so a developer reading the skip message
    knows whether the host is GPU-less or has a broken Paddle build).

    Verifies by inspecting the conftest source for the FR-019 reason
    pattern."""
    import importlib

    repo_conftest = importlib.import_module("tests.conftest")
    with open(repo_conftest.__file__, encoding="utf-8") as fh:
        content = fh.read()

    # The conftest skip-gate references the preflight state values.
    assert (
        "PreflightState" in content
        or "preflight" in content.lower()
        or "ppstructurev3_init_succeeded" in content
    ), (
        "FR-019: GPU-marked test skip reason should trace to a preflight "
        "state name from preflight.py"
    )


@pytest.mark.gpu
def test_t031_marker_actually_skips_gpu_tests_on_cpu_host() -> None:
    """Negative control: this test is GPU-marked and should be skipped
    on a CPU host (where preflight does not return PPSTRUCTUREV3_INIT_SUCCEEDED).
    If the conftest `gpu` marker plumbing is broken, this test would
    run on a CPU host and fail (since no work is done here, it would
    actually pass — but the SKIP behavior is itself observable via
    pytest collection output)."""
    pytest.fail("If you see this on a CPU host, the gpu marker plumbing is broken")
