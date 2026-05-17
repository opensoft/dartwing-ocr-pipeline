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

The baseline is captured under
``tests/fixtures/feature_020_baseline/preprocess_output_cpu_default_inv_001_easy.json``
on the first run and reused thereafter. This validates the MI-20
byte-identity property (no gate-induced drift) — it does NOT compare
against a pre-feature-020 ground truth (the legacy code path cannot be
run retroactively from this branch). The pre-feature-020 RunSummary
baseline at ``tests/fixtures/feature_020_baseline/run_summary_pre_020.json``
covers the additive-superset story for the RunSummary contract.

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


MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\n"
    b"xref\n0 3\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000053 00000 n \n"
    b"trailer<</Size 3/Root 1 0 R>>\n"
    b"startxref\n100\n%%EOF\n"
)


_FIXTURE_DIR = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "feature_020_baseline"
)
_BASELINE_FILENAME = "preprocess_output_cpu_default_inv_001_easy.json"


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


def _run_pipeline_for_inv_001_easy(parent: Path, *, subdir: str) -> Path:
    """Run the default-profile (cpu stub) pipeline against a freshly
    created ``inv_001_easy`` folder under ``parent / subdir`` and return
    the path to the emitted ``preprocess_output.json``. The ``subdir``
    layer lets one test create two side-by-side runs without folder
    collision."""
    folder = parent / subdir / "inv_001_easy"
    folder.mkdir(parents=True)
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    code = main(["run", "--document-folder", str(folder), "--overwrite"])
    assert code == 0, f"baseline pipeline run failed (exit={code})"
    artifact = folder / "preprocess_output.json"
    assert artifact.exists(), "preprocess_output.json was not written"
    return artifact


def _capture_baseline_if_missing(artifact: Path) -> None:
    """First-run helper: write the baseline file from the current run's
    artifact when no baseline exists yet. On CI the baseline file MUST
    already exist (committed to the repo) so this branch is unreachable.
    The defensive write only fires the first time a developer runs the
    test locally after a clean checkout."""
    baseline = _baseline_path()
    if baseline.exists():
        return
    baseline.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_bytes(artifact.read_bytes())


def test_legacy_path_preprocess_output_is_byte_identical_across_runs(
    tmp_path: Path,
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

    first_artifact = _run_pipeline_for_inv_001_easy(tmp_path, subdir="run1")
    first_bytes = first_artifact.read_bytes()
    # Capture the baseline on first ever local run; CI baseline is
    # committed to the repo so this is a no-op there.
    _capture_baseline_if_missing(first_artifact)

    second_artifact = _run_pipeline_for_inv_001_easy(tmp_path, subdir="run2")
    second_bytes = second_artifact.read_bytes()

    assert first_bytes == second_bytes, (
        "MI-20 violation: two default-profile runs against the same "
        "inv_001_easy fixture produced different preprocess_output.json "
        "bytes. The gate must not alter the canonical artifact on the "
        "legacy / default path. (first_len={}, second_len={})".format(
            len(first_bytes), len(second_bytes)
        )
    )


def test_legacy_path_matches_committed_baseline(tmp_path: Path) -> None:
    """SC-007 / FR-019: the default-path ``preprocess_output.json``
    matches the committed baseline byte-for-byte.

    The baseline was captured on the post-feature-020 branch tip with no
    opt-in flag and no truthy env var; it freezes the gate-observable
    artifact shape. A future regression that accidentally writes
    gate-derived fields into the artifact, or alters serialization of
    any existing field, will diff against this baseline.

    If the baseline file does not exist yet (clean checkout, first ever
    local run), the prior test in this module captured it on its way
    through; we skip rather than fail because the second-run comparison
    here would compare bytes against bytes just written. CI always has
    the committed baseline so this skip path is local-developer only.
    """
    if _gate_skip_fallback_active():
        pytest.skip(
            "LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK is truthy; "
            "legacy-path baseline does not apply."
        )

    baseline = _baseline_path()
    if not baseline.exists():
        pytest.skip(
            f"baseline {baseline.name} not yet committed; the round-trip "
            "test above will capture it on first run. Re-run this test "
            "after the baseline lands in the repo."
        )

    artifact = _run_pipeline_for_inv_001_easy(tmp_path, subdir="match-baseline")
    actual = artifact.read_bytes()
    expected = baseline.read_bytes()

    if actual != expected:
        # Best-effort diagnostic: parse both as JSON and show the
        # top-level key set diff. Falls back to raw byte lengths if
        # either side is not valid JSON.
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
