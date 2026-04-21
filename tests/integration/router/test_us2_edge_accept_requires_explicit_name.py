"""T030 / US2 AC#5: every edge_accept document has company_name_present==true
AND company_name_inferred==false."""
from __future__ import annotations

from pathlib import Path


def test_edge_accept_requires_explicit_grounded_name(
    green_fixture: Path, run_cli, read_artifact
):
    run_cli(green_fixture)
    art = read_artifact(green_fixture)
    assert art["decision"] == "edge_accept"
    assert art["checks"]["company_name_present"] is True
    assert art["checks"]["company_name_inferred"] is False
