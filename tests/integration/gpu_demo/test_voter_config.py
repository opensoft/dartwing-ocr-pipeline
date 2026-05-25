"""Phase 7 T071: multi-voter handling (R-023 §6 single-voter precondition).

A voter config with multiple voters produces a WARN line; the demo proceeds
with the first voter's model.
"""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


def _invoke_main_capture(argv: list[str]) -> tuple[int, str, str]:
    from dartwing_ocr.gpu_demo.cli import main

    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


def test_multi_voter_warns_and_uses_first(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    tmp_path: Path,
) -> None:
    multi_voter = tmp_path / "voter_config.yaml"
    multi_voter.write_text(
        """
voters:
  - name: primary
    model: qwen2.5-vl:7b
  - name: secondary
    model: phi-4-mini
""".strip()
    )
    code, stdout, stderr = _invoke_main_capture([
        "--check-only",
        "--voter-config", str(multi_voter),
    ])
    assert code == 0  # readiness passes; the WARN doesn't affect exit code
    # WARN line names the second voter as the ignored one.
    warn_lines = [ln for ln in stderr.splitlines() if ln.startswith("WARN:")]
    assert any("voter config has multiple voters" in ln for ln in warn_lines), (
        f"expected multi-voter WARN; got stderr:\n{stderr}"
    )
    # Report's expected_extraction_model should be the first voter's model.
    import json as _json

    parsed = _json.loads(stdout)
    assert parsed["expected_extraction_model"] == "qwen2.5-vl:7b"
