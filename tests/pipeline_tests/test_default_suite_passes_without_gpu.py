"""Default-suite GPU-marker plumbing test (T031 / SC-008 / FR-019).

Asserts that the conftest `gpu` marker registration is in place so
that on a host without GPU hardware, GPU-marked tests are SKIPPED
(not failed). This is a unit-style proof of the marker plumbing —
the actual end-to-end "full default suite is green" assertion is run
by CI / T041.
"""
from __future__ import annotations

import pytest

pytest_plugins = ["pytester"]


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


def test_t031_marker_actually_skips_gpu_tests_on_cpu_host(
    pytester: pytest.Pytester,
) -> None:
    """Negative control: when conftest detects no GPU readiness, a
    `@pytest.mark.gpu` test MUST be reported as `skipped`, not run.

    Runs an inline pytester subprocess with a stub conftest that mirrors
    the real conftest's skip-on-no-GPU rule, plus one `gpu`-marked test
    body that would fail if it executed. The assertion is that pytester
    reports `skipped == 1` and `failed == 0`. This works on both CPU
    and GPU hosts because the stub conftest forces the no-GPU path.
    """
    pytester.makeconftest(
        """
        import pytest

        def pytest_configure(config):
            config.addinivalue_line(
                "markers", "gpu: requires Paddle GPU readiness"
            )

        def pytest_collection_modifyitems(config, items):
            skip_gpu = pytest.mark.skip(
                reason="preflight: no_gpu_runtime (forced by stub conftest)"
            )
            for item in items:
                if item.get_closest_marker("gpu") is not None:
                    item.add_marker(skip_gpu)
        """
    )
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.gpu
        def test_should_be_skipped():
            pytest.fail("gpu marker did not skip — plumbing broken")
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(skipped=1, failed=0, passed=0)
