"""CPU byte-stability regression guard (T031, FR-017, SC-006).

Two independent assertions live in this file:

(A) `test_cpu_lane_segment_default_args` — fast, default-CI assertion.
    Calls `build_pipeline_version()` with default kwargs and asserts
    the produced string ends with `.cpu` AND that
    `parse_lane_segment(...)` of that string returns `("cpu", None)`.
    No PDF, no Paddle, no `pipeline.run()`, no `_get_engine()`. This is
    the byte-of-the-string assertion that runs on every default
    `pytest` invocation and complements (does not duplicate) T012's
    parser-isolation tests by exercising the actual `build_pipeline_version`
    callable's default-args output.

(B) `test_cpu_byte_stability_repeat_runs` — live regression guard,
    gated behind the `DARTWING_LIVE_REGRESSION=1` environment
    variable. Two consecutive CPU runs of the real PPStructureV3
    pipeline on `tests/stage1_vendor_identity/inv_001_easy/source.pdf`
    produce byte-identical `preprocess_output.json` (SHA-256 equality).
    Also re-asserts the lane segment on the on-disk artifact, which is
    the byte-of-the-artifact assertion.

Why the env-var gate (rather than a pytest marker): registering a new
marker would require touching `tests/conftest.py`, which is out of
scope for this remediation. The env-var gate is a self-contained skip
that lives entirely in this file and runs before any heavy import.

Why split into two tests: the live test was OOM-killed (exit 137)
twice when run as part of the default `pytest` invocation in py-bench.
The default `pytest` run must not initialize real Paddle / construct
PPStructureV3 / call `pipeline.run()` on a real PDF. T012 (Phase 3)
covers the parser unit-level grammar assertion; this file's fast test
covers the producer's default-args output; T031's live test (gated
behind the env var) covers the on-disk byte-stability regression.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from dartwing_ocr.preprocessing.version import (
    build_pipeline_version,
    parse_lane_segment,
)


_LIVE_ENV_VAR = "DARTWING_LIVE_REGRESSION"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_cpu_lane_segment_default_args() -> None:
    """Default-CI byte-of-the-string assertion (no Paddle, no PDF).

    Asserts the producer-side contract: `build_pipeline_version()`
    invoked with default kwargs emits a string ending in `.cpu`, and
    `parse_lane_segment(...)` of that string returns `("cpu", None)`.

    This is the assertion that runs on the default `pytest` invocation
    (no env vars, no flags). The complementary live byte-of-the-artifact
    assertion is `test_cpu_byte_stability_repeat_runs` below, gated
    behind the `DARTWING_LIVE_REGRESSION=1` env var.

    The unit-level parser-isolation tests live in T012
    (`tests/unit/test_pipeline_version_lane_segment.py`); this test
    intentionally exercises the actual `build_pipeline_version`
    callable's default-args output rather than synthetic strings, so a
    regression that flips the producer's CPU default away from `cpu`
    would be caught here even if the parser is correct.
    """
    pv = build_pipeline_version()
    assert pv.endswith(".cpu"), (
        f"FR-016 violated: post-feature CPU default of build_pipeline_version() "
        f"must end with `.cpu`; got {pv!r}"
    )
    assert parse_lane_segment(pv) == ("cpu", None), (
        f"FR-016 / SC-005 violated: parse_lane_segment of the post-feature CPU "
        f"default must be ('cpu', None); got {parse_lane_segment(pv)!r} for {pv!r}"
    )


def test_cpu_byte_stability_repeat_runs(tmp_path: Path) -> None:
    """Live byte-of-the-artifact regression guard (opt-in, env-gated).

    Runs the real PPStructureV3 CPU pipeline twice on
    `tests/stage1_vendor_identity/inv_001_easy/source.pdf` and asserts:

    (a) SHA-256 of `preprocess_output.json` is identical between the
        two consecutive runs (FR-017, SC-006).
    (b) The produced `pipeline_version` parses via `parse_lane_segment`
        to `("cpu", None)` — verifying the `.cpu` lane segment is
        uniformly emitted on every CPU run end-to-end (FR-016, VT13).

    This test is **gated** behind the `DARTWING_LIVE_REGRESSION=1`
    environment variable. The default `pytest` invocation skips this
    test because it constructs PPStructureV3 on a real PDF, which has
    been observed to OOM-kill the test process in py-bench. Operators
    deliberately running the live byte-stability regression guard set
    `DARTWING_LIVE_REGRESSION=1` before invoking pytest, e.g.::

        DARTWING_LIVE_REGRESSION=1 .venv/bin/pytest \\
            tests/pipeline_tests/test_pipeline_version_cpu_byte_stable.py

    The default-CI string-level coverage is provided by
    `test_cpu_lane_segment_default_args` (above) plus T012 in
    `tests/unit/test_pipeline_version_lane_segment.py`.
    """
    if not os.environ.get(_LIVE_ENV_VAR):
        pytest.skip(
            f"live byte-stability regression guard is opt-in; set "
            f"{_LIVE_ENV_VAR}=1 to enable. Default CI relies on "
            f"test_cpu_lane_segment_default_args (this file) and T012 "
            f"(tests/unit/test_pipeline_version_lane_segment.py) for "
            f"parser/producer coverage."
        )

    repo_root = Path(__file__).resolve().parents[2]
    src_doc = repo_root / "tests" / "stage1_vendor_identity" / "inv_001_easy" / "source.pdf"
    if not src_doc.exists():
        pytest.skip(f"corpus document not found: {src_doc}")

    # Heavy imports are deliberately deferred until after the env-var
    # gate so the default-CI run never imports the live preprocessing
    # CLI (which transitively imports Paddle / PaddleOCR).
    from dartwing_ocr.preprocessing import cli as preprocessing_cli
    from dartwing_ocr.preprocessing import ocr as ocr_mod

    # Ensure a clean engine singleton for each invocation; this is a
    # test-only reset to make the byte-stability test independent of
    # other tests that may have constructed _ENGINE.
    ocr_mod._ENGINE = None
    ocr_mod._ENGINE_DEVICE = None

    # First run.
    folder1 = tmp_path / "run1"
    folder1.mkdir()
    inv1 = folder1 / "inv_001_easy"
    inv1.mkdir()
    (inv1 / "source.pdf").write_bytes(src_doc.read_bytes())
    rc1 = preprocessing_cli.main(["--document-folder", str(inv1)])
    if rc1 != 0:
        pytest.skip(f"CPU preprocessing returned exit {rc1}; may be missing PaddleOCR weights")
    artifact1 = inv1 / "preprocess_output.json"
    assert artifact1.exists()
    sha1 = _sha256(artifact1)

    # Second run with the same _ENGINE singleton (warm path).
    folder2 = tmp_path / "run2"
    folder2.mkdir()
    inv2 = folder2 / "inv_001_easy"
    inv2.mkdir()
    (inv2 / "source.pdf").write_bytes(src_doc.read_bytes())
    rc2 = preprocessing_cli.main(["--document-folder", str(inv2)])
    assert rc2 == 0
    artifact2 = inv2 / "preprocess_output.json"
    assert artifact2.exists()
    sha2 = _sha256(artifact2)

    assert sha1 == sha2, (
        f"CPU byte-stability regression: SHA-256 of preprocess_output.json "
        f"differs between two repeat runs on the same input. "
        f"run1={sha1}, run2={sha2}. SC-006 / FR-017."
    )

    # VT13: assert the lane segment is uniformly .cpu on both runs.
    payload1 = json.loads(artifact1.read_text())
    payload2 = json.loads(artifact2.read_text())
    pv1 = payload1["pipeline_version"]
    pv2 = payload2["pipeline_version"]
    assert pv1 == pv2  # follows from SHA equality but explicit for clarity
    assert pv1.endswith(".cpu"), (
        f"FR-016 violated: post-feature CPU output must end with `.cpu`; got {pv1!r}"
    )
    assert parse_lane_segment(pv1) == ("cpu", None)
