"""T042 / US4 AC#3: policy_version recorded on spam-gate output.

Any change to the spam-gate threshold requires bumping
``router.version.POLICY_VERSION`` and updating the expected value here
(SC-010 enforcement point).
"""
from __future__ import annotations

from pathlib import Path

from dartwing_ocr.router.version import POLICY_VERSION


def test_policy_version_recorded_on_spam_gate_output(
    tmp_path: Path, stage_fixture, run_cli, read_artifact
):
    folder = stage_fixture(tmp_path, "all_null_spam.json")
    run_cli(folder)
    art = read_artifact(folder)
    assert art["policy_version"] == POLICY_VERSION
    # Canonical shipped default — tightens the invariant so a silent drift
    # in the module constant would also be caught here.
    assert POLICY_VERSION == "stage1-routing-policy-v1.0.0"
