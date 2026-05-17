"""Feature 020 / T048 / US6 (SC-006 / SC-007 / FR-019 / MI-20):
legacy byte-identity guard for ``preprocess_output.json`` on the
no-skip-fallback path.

MI-20: when the user does NOT pass ``--evidence-gate-skip-fallback`` and
no truthy env var enables shape (b) suppression, feature 020 MUST NOT
alter any byte of the four canonical artifacts. The gate is observability
only on the legacy path — it reads ``preprocess_output.json``, contributes
state-distribution counters to the ``run_summary`` stdout line, and does
NOT write back. Round-tripping the same fixture twice MUST produce a
byte-identical ``preprocess_output.json``.

The baseline at
``tests/fixtures/feature_020_baseline/preprocess_output_cpu_default_inv_001_easy.json``
is committed to the repo (regenerable from the ``tmp_pdf_bytes`` fixture
in ``conftest.py`` plus a cold CPU stub-adapter run). A missing baseline
is a real failure, not a recovery scenario — the test fails loudly so
the regeneration path lands as a deliberate, separately-reviewed action.

Skip-fallback note: the ``--evidence-gate-skip-fallback`` flag and the
``LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK`` env var are introduced by
US4 (parallel PR). On this branch they do not exist; the default
(legacy) path is the only path. This test therefore exercises the
default-path invariant; US4 lands a companion test for the opt-in
suppression path that is symmetric.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ledgerlinc_ocr.pipeline.cli import main


_FIXTURE_DIR = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "feature_020_baseline"
)
_BASELINE_FILENAME = "preprocess_output_cpu_default_inv_001_easy.json"

# Pin pipeline_version to the value embedded in the committed baseline
# so a routine package version bump does not invalidate the byte-identity
# guard. The invariant under test is "the gate does not mutate
# preprocess_output.json on the default path", NOT "the package version
# string stays at 0.1.0 forever" — pinning isolates the former from the
# latter (Copilot review feedback).
_BASELINE_PIPELINE_VERSION = "0.1.0"


def _baseline_path() -> Path:
    return _FIXTURE_DIR / _BASELINE_FILENAME


def _gate_skip_fallback_active() -> bool:
    """True iff a truthy ``LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK`` env var
    is set. US4 introduces this flag; on this branch it should never be
    truthy in CI. We guard the test anyway so a developer who sets the
    env var locally does not get a false-positive byte-identity failure
    (the opt-in path is allowed to differ from the legacy path).
    """
    val = os.environ.get("LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK", "")
    return val.strip().lower() in ("1", "true", "yes", "on")


def _run_pipeline_for_inv_001_easy(
    parent: Path, *, subdir: str, pdf_bytes: bytes
) -> Path:
    """Run the default-profile (cpu stub) pipeline against a freshly
    created ``inv_001_easy`` folder under ``parent / subdir`` and return
    the path to the emitted ``preprocess_output.json``. The ``subdir``
    layer lets one test create two side-by-side runs without folder
    collision."""
    folder = parent / subdir / "inv_001_easy"
    folder.mkdir(parents=True)
    (folder / "source.pdf").write_bytes(pdf_bytes)
    code = main(
        [
            "run",
            "--document-folder",
            str(folder),
            "--overwrite",
            "--pipeline-version",
            _BASELINE_PIPELINE_VERSION,
        ]
    )
    assert code == 0, f"baseline pipeline run failed (exit={code})"
    artifact = folder / "preprocess_output.json"
    assert artifact.exists(), "preprocess_output.json was not written"
    return artifact


def test_legacy_path_preprocess_output_is_byte_identical_across_runs(
    tmp_path: Path,
    tmp_pdf_bytes: bytes,
) -> None:
    """MI-20 round-trip determinism: two independent runs of the
    default-profile pipeline against the same fixture produce
    byte-identical ``preprocess_output.json`` content.

    The gate observes the artifact but writes nothing back — so the
    second run's output MUST match the first run's output to the byte.
    """
    if _gate_skip_fallback_active():
        pytest.skip(
            "LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK is truthy; "
            "this test guards the legacy / default path only — the "
            "opt-in suppression path is covered by US4."
        )

    first_artifact = _run_pipeline_for_inv_001_easy(
        tmp_path, subdir="run1", pdf_bytes=tmp_pdf_bytes
    )
    first_bytes = first_artifact.read_bytes()

    second_artifact = _run_pipeline_for_inv_001_easy(
        tmp_path, subdir="run2", pdf_bytes=tmp_pdf_bytes
    )
    second_bytes = second_artifact.read_bytes()

    assert first_bytes == second_bytes, (
        "MI-20 violation: two default-profile runs against the same "
        "inv_001_easy fixture produced different preprocess_output.json "
        "bytes. The gate must not alter the canonical artifact on the "
        "legacy / default path. (first_len={}, second_len={})".format(
            len(first_bytes), len(second_bytes)
        )
    )


def test_legacy_path_matches_committed_baseline(
    tmp_path: Path,
    tmp_pdf_bytes: bytes,
) -> None:
    """SC-007 / FR-019: the default-path ``preprocess_output.json``
    matches the committed baseline byte-for-byte.

    The baseline was captured on the post-feature-020 branch tip with no
    opt-in flag and no truthy env var; it freezes the gate-observable
    artifact shape. A future regression that accidentally writes
    gate-derived fields into the artifact, or alters serialization of
    any existing field, will diff against this baseline.

    A missing baseline file is a real failure: this guard depends on
    the committed fixture, and a stealth regeneration path would defeat
    the guard's purpose. Re-baselining is a deliberate, reviewed action
    (see the regeneration procedure in this module's docstring).
    """
    if _gate_skip_fallback_active():
        pytest.skip(
            "LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK is truthy; "
            "legacy-path baseline does not apply."
        )

    baseline = _baseline_path()
    assert baseline.exists(), (
        f"committed baseline {baseline} is missing. Re-baselining is a "
        "deliberate, separately-reviewed action — restore the file from "
        "git, or regenerate it via a cold CPU stub-adapter run against "
        "the tmp_pdf_bytes fixture and review the diff before committing."
    )

    artifact = _run_pipeline_for_inv_001_easy(
        tmp_path, subdir="match-baseline", pdf_bytes=tmp_pdf_bytes
    )
    actual = artifact.read_bytes()
    expected = baseline.read_bytes()

    if actual != expected:
        try:
            actual_obj = json.loads(actual)
            expected_obj = json.loads(expected)
            actual_keys = sorted(actual_obj.keys()) if isinstance(actual_obj, dict) else None
            expected_keys = sorted(expected_obj.keys()) if isinstance(expected_obj, dict) else None
            detail = (
                f"actual top-level keys: {actual_keys!r}; "
                f"expected top-level keys: {expected_keys!r}"
            )
        except json.JSONDecodeError:
            detail = (
                f"actual_len={len(actual)} expected_len={len(expected)}"
            )
        pytest.fail(
            "SC-007 / FR-019 violation: default-path "
            "preprocess_output.json drifted from the committed baseline. "
            f"{detail}"
        )
