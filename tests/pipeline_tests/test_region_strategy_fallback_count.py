"""Feature 018 warm-corpus fallback-count aggregation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dartwing_ocr.pipeline.cli import main
from dartwing_ocr.pipeline.exit_codes import ExitCode
from dartwing_ocr.pipeline.runner import RunResult, Runner
from dartwing_ocr.pipeline.timing import DocumentTimings, StageTiming


MINIMAL_PDF_BYTES = b"%PDF-1.4\n% minimal test pdf\n%%EOF\n"


def _make_doc(root: Path, name: str) -> Path:
    folder = root / name
    folder.mkdir()
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    return folder


def _run_summary_from(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("kind") == "run_summary":
            return payload
    raise AssertionError(f"no run_summary found in stdout: {stdout!r}")


class _FallbackFlagRunner(Runner):
    def run_plan(self, plan, *, folder=None) -> RunResult:
        invocation = plan.cli_invocation
        invocation.region_strategy_fallback_fired = (
            invocation.document_id == "inv_001_easy"
        )
        return RunResult(
            exit_code=ExitCode.SUCCESS,
            artifacts_written=[],
            stage="schema_validation",
            routing_decision=None,
            timings=DocumentTimings(
                stages={"preprocess": StageTiming(stage="preprocess")}
            ),
        )


def test_warm_corpus_aggregates_region_strategy_fallback_count(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warm-corpus run_summary must count per-document fallback flags."""
    from dartwing_ocr.pipeline import corpus_run as corpus_run_mod

    monkeypatch.setattr(
        corpus_run_mod,
        "_maybe_register_warm_preprocess",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        corpus_run_mod,
        "_warm_initialize_live_preprocess",
        lambda _registry, _plan: None,
    )

    doc_a = _make_doc(tmp_path, "inv_001_easy")
    doc_b = _make_doc(tmp_path, "inv_002_medium")
    docs_file = tmp_path / "documents.txt"
    docs_file.write_text(f"{doc_a}\n{doc_b}\n", encoding="utf-8")

    code = main(
        [
            "run",
            "--documents-file",
            str(docs_file),
            "--preprocess-profile",
            "ppstructurev3@gpu",
            "--region-strategy",
            "header-first-v1",
            "--stop-after",
            "preprocess",
            "--overwrite",
        ],
        runner=_FallbackFlagRunner(),
    )

    assert code == 0
    summary = _run_summary_from(capsys.readouterr().out)
    assert summary["region_strategy_id"] == "header-first-v1"
    assert summary["region_strategy_fallback_count"] == 1
