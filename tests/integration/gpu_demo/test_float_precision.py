"""Phase 7 T070: float precision in DemoRunReport (R-023.21).

All wall-clock fields (every elapsed_seconds, phase_timings.*, total_runtime_seconds)
serialize to at most 3 decimal places per R-023.21.
"""

from __future__ import annotations

import io
import json
import re
from contextlib import redirect_stdout
from pathlib import Path


def _invoke_main(argv: list[str]) -> tuple[int, str]:
    from dartwing_ocr.gpu_demo.cli import main

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


def _max_decimal_places(value) -> int:
    """Return the number of decimal places after the decimal point."""
    if value is None or value == 0:
        return 0
    s = repr(float(value))
    if "." not in s:
        return 0
    after = s.split(".", 1)[1]
    if "e" in after or "E" in after:
        return 0  # scientific notation — different shape
    return len(after)


def test_check_only_floats_at_most_3_dp(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
) -> None:
    """SC-007 budget exercise: --check-only emits floats rounded to ≤3 dp."""
    code, stdout = _invoke_main([
        "--check-only",
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
    ])
    assert code == 0
    parsed = json.loads(stdout)
    # ReadinessSummary.elapsed_seconds
    assert _max_decimal_places(parsed["readiness"]["elapsed_seconds"]) <= 3
    # Each ReadinessCheck.elapsed_seconds
    for c in parsed["readiness"]["checks"]:
        assert _max_decimal_places(c["elapsed_seconds"]) <= 3, (
            f"{c['name']} elapsed_seconds has too many dp: {c['elapsed_seconds']!r}"
        )


def test_happy_path_phase_timings_at_most_3_dp(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    bypass_schema_validation,
    patch_orchestrator_composer,
    tmp_path: Path,
) -> None:
    """phase_timings.* and total_runtime_seconds rounded to ≤3 dp."""
    src = (Path(__file__).parent / "fixtures" / "ok" / "source.pdf").resolve()
    folder = tmp_path / "inv_test"
    folder.mkdir()
    (folder / "source.pdf").symlink_to(src)

    patch_orchestrator_composer(stub_pipeline_composer())
    code, stdout = _invoke_main([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(folder),
    ])
    assert code == 0
    parsed = json.loads(stdout)
    for key, val in parsed["phase_timings"].items():
        if val is not None:
            assert _max_decimal_places(val) <= 3, (
                f"phase_timings.{key} has too many dp: {val!r}"
            )
    if parsed["total_runtime_seconds"] is not None:
        assert _max_decimal_places(parsed["total_runtime_seconds"]) <= 3
