"""FIX 3 / C2 — the 7th invariant: assembled payload must pass its own schema.

Before this test, no coverage exercised the output-side schema validation.
If the `validate_output(...)` call in `pipeline.run(...)` were silently
deleted, every other test would still pass because they happen to produce
valid output from valid input. This test forces a schema-invalid value
into the assembled payload and asserts the invariant rejects it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from dartwing_ocr.assembler import Invocation, run
from dartwing_ocr.assembler import quality as quality_module
from dartwing_ocr.assembler.errors import OutputSchemaInvalidError

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "assembler"


def _stage(tmp_path: Path, name: str) -> Path:
    dst = tmp_path / name
    shutil.copytree(FIXTURE_ROOT / name, dst)
    return dst


def test_output_schema_invariant_raises_on_out_of_range_confidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Monkey-patch overall_vendor_confidence to return 2.0 (schema max = 1.0).

    FR-022 pins `overall_vendor_confidence` to `[0.0, 1.0]` in the output
    schema. A value of 2.0 must be rejected by the 7th invariant.
    """
    folder = _stage(tmp_path, "happy_grounded")

    monkeypatch.setattr(
        quality_module,
        "compute_overall_vendor_confidence",
        lambda extractor, secondary_ids: 2.0,
    )

    with pytest.raises(OutputSchemaInvalidError) as exc_info:
        run(Invocation(document_folder=folder))

    assert exc_info.value.kind == "output_schema_invalid"
    assert exc_info.value.exit_code == 3

    # No payload file may have been written.
    assert not (folder / "final_structured_payload.json").exists()


def test_output_schema_invariant_cli_exit_code_and_kind(tmp_path: Path) -> None:
    """CLI-level end-to-end: same monkey-patch, asserted via subprocess.

    We inject the monkey-patch via a small bootstrap script so the patch
    survives across the `python -m dartwing_ocr.assembler` invocation.
    """
    folder = _stage(tmp_path, "happy_grounded")

    bootstrap = tmp_path / "bootstrap_break_output.py"
    bootstrap.write_text(
        "import sys\n"
        "from dartwing_ocr.assembler import quality as q\n"
        "q.compute_overall_vendor_confidence = lambda extractor, secondary_ids: 2.0\n"
        "from dartwing_ocr.assembler import cli\n"
        "sys.exit(cli.main())\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(bootstrap),
            "--document-folder",
            str(folder),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 3, (
        f"expected exit 3, got {result.returncode}; stderr={result.stderr!r}"
    )
    assert not (folder / "final_structured_payload.json").exists()

    # Find the JSON error line in stderr (last non-empty JSON object).
    err = None
    for line in reversed(result.stderr.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            err = json.loads(line)
            break
    assert err is not None, f"no JSON error line in stderr: {result.stderr!r}"
    assert err["status"] == "error"
    assert err["kind"] == "output_schema_invalid"
