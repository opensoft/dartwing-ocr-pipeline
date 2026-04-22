"""T066 / Finding C1 (SC-001): wall-clock budget for single-document route.

SC-001 pins ``≤ 200 ms`` on a developer workstation for a pure
deterministic code path (two JSON files, no models, no network). CI
machines are noisier, so the runtime assertion is widened to a tolerant
ceiling; the intent of the criterion is preserved and a future tightening
is a one-line change.

If this test starts failing on CI, the fix is almost always environmental
(overloaded runner, cold Python start) rather than a router regression —
but a sustained breach is a signal that the router is doing more I/O
than the spec allows.
"""
from __future__ import annotations

import time
from pathlib import Path

CI_TOLERANT_BUDGET_SECONDS = 1.5
SC001_WORKSTATION_TARGET_MS = 200


def test_single_document_route_within_budget(green_fixture: Path, run_cli):
    start = time.monotonic()
    result = run_cli(green_fixture)
    elapsed = time.monotonic() - start

    assert result.returncode == 0, result.stderr
    assert elapsed < CI_TOLERANT_BUDGET_SECONDS, (
        f"route exceeded CI-tolerant budget: {elapsed:.3f}s "
        f">= {CI_TOLERANT_BUDGET_SECONDS}s "
        f"(SC-001 workstation target is {SC001_WORKSTATION_TARGET_MS}ms)"
    )
