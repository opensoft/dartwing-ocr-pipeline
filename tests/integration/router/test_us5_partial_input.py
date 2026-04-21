"""T049 / US5 AC#1, AC#2: status=success → output success; status=partial → output partial.

Output ``status`` mirrors input ``status`` per FR-020 (success → success,
partial → partial, failure → partial per research Decision 11 — but that
is covered in T050). When upstream reports ``partial``, the informational
reason ``upstream_status_partial`` is appended to ``reasons``.
"""
from __future__ import annotations

from pathlib import Path


def test_success_input_yields_success_output(
    green_fixture: Path, run_cli, read_artifact
):
    result = run_cli(green_fixture)
    assert result.returncode == 0, result.stderr
    art = read_artifact(green_fixture)
    assert art["status"] == "success"
    assert "upstream_status_partial" not in art["reasons"]


def test_partial_input_yields_partial_output_with_informational_reason(
    tmp_path: Path, stage_fixture, run_cli, read_artifact
):
    folder = stage_fixture(tmp_path, "partial_upstream.json")
    result = run_cli(folder)
    assert result.returncode == 0, result.stderr
    art = read_artifact(folder)
    assert art["status"] == "partial"
    assert "upstream_status_partial" in art["reasons"]
    # Partial upstream with otherwise-green vendor identity still accepts.
    assert art["decision"] == "edge_accept"
