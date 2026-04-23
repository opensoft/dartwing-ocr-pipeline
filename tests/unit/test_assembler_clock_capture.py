"""H5 — processed_at is captured at run-start, and clock failures route to exit 3.

Prior layout embedded `now_fn()` inline while building the payload dict, after
all six invariants passed. That had two sharp edges:

1. A post-invariant clock failure leaked through the CLI's generic `Exception`
   arm as exit 1 "unexpected" — the wrong taxonomy for a code/env problem that
   happened after the inputs were already proven good.
2. `processed_at` represented "some moment mid-assembly" rather than "run
   started at", which is a looser reading of FR-007 than necessary.

The fix moves the clock call to the top of `run()` and wraps it in a
try/except that raises ``InternalError`` (exit 3, `kind="unexpected"`).
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ledgerlinc_ocr.assembler import Invocation, run
from ledgerlinc_ocr.assembler.errors import InternalError

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "assembler"


def _stage(tmp_path: Path, name: str) -> Path:
    dst = tmp_path / name
    shutil.copytree(FIXTURE_ROOT / name, dst)
    return dst


def test_clock_called_exactly_once_per_run(tmp_path: Path):
    """H5: a single clock call at run-start — not per-field during assembly."""
    folder = _stage(tmp_path, "happy_grounded")
    calls: list[datetime] = []

    def clock() -> datetime:
        t = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)
        calls.append(t)
        return t

    out_path = run(Invocation(document_folder=folder, now_utc=clock))

    assert len(calls) == 1, (
        f"expected exactly one clock call per run; got {len(calls)}. "
        f"Multiple calls would make processed_at non-deterministic relative "
        f"to other per-run timing."
    )
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["processed_at"] == "2026-04-22T12:00:00Z"


def test_clock_is_captured_before_invariants(tmp_path: Path):
    """H5: clock fires at run-start, so even a doomed run captures a time.

    Staged against a broken fixture (contract drift). Assert the clock was
    invoked before the invariant check short-circuited — proving processed_at
    semantics are "run started at", not "run completed at".
    """
    folder = _stage(tmp_path, "happy_grounded")
    # Break contract_set_version → invariant 4 fails.
    ext_path = folder / "edge_extraction_output.json"
    data = json.loads(ext_path.read_text(encoding="utf-8"))
    data["contract_set_version"] = "2.0.0"
    ext_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    calls = [0]

    def clock() -> datetime:
        calls[0] += 1
        return datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)

    from ledgerlinc_ocr.assembler.errors import ContractDriftError
    with pytest.raises(ContractDriftError):
        run(Invocation(document_folder=folder, now_utc=clock))

    assert calls[0] == 1, (
        f"clock should fire at run-start before invariants; got {calls[0]} calls. "
        f"If this is zero, the clock moved back to post-invariant position."
    )


def test_clock_failure_routes_to_internal_error(tmp_path: Path):
    """H5: clock exceptions are env/code problems, not input rejections → exit 3."""
    folder = _stage(tmp_path, "happy_grounded")

    def broken_clock() -> datetime:
        raise RuntimeError("simulated clock failure (e.g. TZ database missing)")

    with pytest.raises(InternalError) as excinfo:
        run(Invocation(document_folder=folder, now_utc=broken_clock))

    assert excinfo.value.exit_code == 3
    assert excinfo.value.kind == "unexpected"
    assert "clock failure" in str(excinfo.value).lower()
    # And no output was written.
    assert not (folder / "final_structured_payload.json").exists()
