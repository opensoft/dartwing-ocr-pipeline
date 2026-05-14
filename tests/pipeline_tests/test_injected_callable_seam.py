"""US4 Acceptance Scenario 1: injected stage callables short-circuit the
profile registry while still honoring slice + prerequisite + overwrite +
timing.

Spec FR-012; Research R-014; design.md CHK024.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from dartwing_ocr.pipeline.cli import main
from dartwing_ocr.pipeline.exit_codes import ExitCode
from dartwing_ocr.pipeline.runner import (
    CLIInvocation,
    Runner,
    RunResult,
    StageRunOutput,
)


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


def _stage_folder(tmp_path: Path, name: str = "inv_001_easy") -> Path:
    folder = tmp_path / name
    folder.mkdir()
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    return folder


def test_injected_preprocess_callable_overrides_profile_registry(tmp_path: Path):
    """An injected preprocess callable wins over the profile-registry lookup."""
    from dartwing_ocr.pipeline.stages import default_preprocess

    folder = _stage_folder(tmp_path, "inv_001_easy")
    invocations: list[str] = []

    def custom_preprocess(invocation: CLIInvocation, artifacts: dict) -> dict:
        invocations.append("preprocess")
        out = default_preprocess(invocation, artifacts)
        out["pipeline_version"] = "injected-test-v0"
        return out

    runner = Runner(preprocess=custom_preprocess)
    code = main(
        [
            "run",
            "--document-folder", str(folder),
            "--preprocess-profile", "ppstructurev3@cpu",  # would route to live registry
            "--extract-profile", "stub",
            "--routing-profile", "stub",
            "--final-payload-profile", "stub",
            "--overwrite",
        ],
        runner=runner,
    )
    assert code == 0
    assert invocations == ["preprocess"]
    artifact = json.loads((folder / "preprocess_output.json").read_text())
    assert artifact["pipeline_version"] == "injected-test-v0"


def test_injected_callable_seam_works_alongside_slice_control(tmp_path: Path):
    """Injected extract callable runs only when extract is in the slice."""
    from dartwing_ocr.pipeline.stages import default_extraction, default_preprocess

    folder = _stage_folder(tmp_path, "inv_002_easy")

    extract_calls: list[int] = []

    def counting_extract(invocation, artifacts):
        extract_calls.append(1)
        return default_extraction(invocation, artifacts)

    runner = Runner(extraction=counting_extract)

    # First: stop after preprocess -- extract MUST NOT fire.
    code = main(
        [
            "run",
            "--document-folder", str(folder),
            "--stop-after", "preprocess",
            "--preprocess-profile", "stub",
            "--overwrite",
        ],
        runner=runner,
    )
    assert code == 0
    assert extract_calls == []

    # Now run the full slice including extract -- it must fire exactly once.
    code = main(
        [
            "run",
            "--document-folder", str(folder),
            "--preprocess-profile", "stub",
            "--extract-profile", "stub",
            "--routing-profile", "stub",
            "--final-payload-profile", "stub",
            "--overwrite",
        ],
        runner=runner,
    )
    assert code == 0
    assert extract_calls == [1]


def test_stage_run_output_skips_runner_rewrite(tmp_path: Path):
    """Adapters that already wrote their artifact are not rewritten by Runner."""
    from dartwing_ocr.pipeline.stages import default_preprocess

    folder = _stage_folder(tmp_path, "inv_009_easy")
    written = ""

    def already_written_preprocess(
        invocation: CLIInvocation, artifacts: dict
    ) -> StageRunOutput:
        nonlocal written
        payload = default_preprocess(invocation, artifacts)
        out_path = invocation.destination_folder / "preprocess_output.json"
        written = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        out_path.write_text(written, encoding="utf-8")
        return StageRunOutput(payload=payload, artifact_path=out_path)

    runner = Runner(preprocess=already_written_preprocess)
    code = main(
        [
            "run",
            "--document-folder", str(folder),
            "--stop-after", "preprocess",
            "--preprocess-profile", "stub",
            "--overwrite",
        ],
        runner=runner,
    )

    assert code == 0
    assert (folder / "preprocess_output.json").read_text(encoding="utf-8") == written


def test_pre011_runner_run_seam_still_works(tmp_path: Path):
    """Tests that override Runner.run(invocation) (the 002-era seam) continue
    to short-circuit the new profile-resolution path in cold mode.
    """
    folder = _stage_folder(tmp_path, "inv_003_easy")

    class _CapturingRunner(Runner):
        def __init__(self) -> None:
            super().__init__()
            self.captured: CLIInvocation | None = None

        def run(self, invocation: CLIInvocation) -> RunResult:
            self.captured = invocation
            return RunResult(
                exit_code=ExitCode.SUCCESS,
                artifacts_written=[],
                stage="schema_validation",
                routing_decision={
                    "decision": "edge_accept",
                    "review_status": {
                        "manual_review_required": False,
                        "review_reason": None,
                    },
                },
            )

    runner = _CapturingRunner()
    code = main(
        [
            "run",
            "--document-folder", str(folder),
            "--ollama-url", "http://example.test:11434",
            "--overwrite",
        ],
        runner=runner,
    )
    assert code == 0
    assert runner.captured is not None
    assert runner.captured.ollama_url == "http://example.test:11434"
    # The runner's run() was called -- profiles not pulled from the
    # registry because legacy run() captured it directly.
