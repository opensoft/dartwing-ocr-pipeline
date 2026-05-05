"""Copilot review item 1: warm-init for live preprocessing only fires when
the live adapter is actually capable, not when a stub-fallback factory
is in place.

This also guards the explicit test-only stub-fallback registry mode from
pre-loading PPStructureV3.
"""
from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path

import pytest

_PLACEHOLDER_OLLAMA_URL = "https://placeholder.invalid"
_PLACEHOLDER_DOCUMENTS = (Path("placeholder"),)


@pytest.fixture(autouse=True)
def reset_registry():
    from ledgerlinc_ocr.pipeline import stages as stages_mod

    stages_mod.reset_live_registry(stub_fallback_only=True)
    yield
    stages_mod.reset_live_registry()


def _build_args() -> argparse.Namespace:
    return argparse.Namespace(
        overwrite=False,
        pipeline_version="test",
        policy_version="test",
        contract_set_version="1.0.0",
        ollama_url=None,
        log_level="warning",
        timeout=30,
        ollama_cpu_url=None,
        ollama_jetson_url=None,
        preprocess_profile="ppstructurev3@cpu",
        extract_profile="stub",
        routing_profile="stub",
        final_payload_profile="stub",
        stack_preset=None,
        start_at=None,
        stop_after=None,
        on_failure=None,
    )


def test_default_run_with_stub_fallback_does_not_warm_init():
    """The test-only stub-fallback factory must NOT trigger warm initialization
    of PPStructureV3, even when the resolved profile name is
    ``ppstructurev3@cpu``.
    """
    from ledgerlinc_ocr.pipeline import corpus_run as corpus_run_mod
    from ledgerlinc_ocr.pipeline.corpus import WarmProfileRegistry
    from ledgerlinc_ocr.pipeline.cli import _build_resolved_plan
    from ledgerlinc_ocr.pipeline.runner import CLIInvocation

    args = _build_args()
    placeholder = CLIInvocation(
        input_pdf=Path("placeholder/source.pdf"),
        destination_folder=Path("placeholder"),
        document_id="placeholder",
        overwrite=args.overwrite,
        pipeline_version=args.pipeline_version,
        policy_version=args.policy_version,
        contract_set_version=args.contract_set_version,
        ollama_url=_PLACEHOLDER_OLLAMA_URL,
        log_level=args.log_level,
        timeout=args.timeout,
        ollama_cpu_url=None,
        ollama_jetson_url=None,
    )
    plan, _, msg = _build_resolved_plan(
        args,
        invocation=placeholder,
        documents=_PLACEHOLDER_DOCUMENTS,
        warm_corpus=True,
    )
    assert plan is not None, f"plan resolution failed: {msg}"

    registry = WarmProfileRegistry.empty()
    corpus_run_mod._maybe_register_warm_preprocess(registry, plan)
    # Capability gate: test-only stub fallback => no factory registered =>
    # warm init is a no-op.
    assert registry.factories == {}
    assert registry.initialization_timings_ns == {}


def test_explicit_register_ppstructurev3_cpu_unlocks_warm_init():
    """Once a real adapter is registered, warm-init MAY fire."""
    from ledgerlinc_ocr.pipeline import corpus_run as corpus_run_mod
    from ledgerlinc_ocr.pipeline import stages as stages_mod
    from ledgerlinc_ocr.pipeline.corpus import WarmProfileRegistry
    from ledgerlinc_ocr.pipeline.cli import _build_resolved_plan
    from ledgerlinc_ocr.pipeline.runner import CLIInvocation

    stages_mod.register_ppstructurev3_cpu()
    assert stages_mod.is_live_capable("preprocess", "ppstructurev3", "cpu")

    args = _build_args()
    placeholder = CLIInvocation(
        input_pdf=Path("placeholder/source.pdf"),
        destination_folder=Path("placeholder"),
        document_id="placeholder",
        overwrite=args.overwrite,
        pipeline_version=args.pipeline_version,
        policy_version=args.policy_version,
        contract_set_version=args.contract_set_version,
        ollama_url=_PLACEHOLDER_OLLAMA_URL,
        log_level=args.log_level,
        timeout=args.timeout,
        ollama_cpu_url=None,
        ollama_jetson_url=None,
    )
    plan, _, _ = _build_resolved_plan(
        args,
        invocation=placeholder,
        documents=_PLACEHOLDER_DOCUMENTS,
        warm_corpus=True,
    )
    assert plan is not None

    registry = WarmProfileRegistry.empty()
    corpus_run_mod._maybe_register_warm_preprocess(registry, plan)
    # With the opt-in registration, the warm-corpus path registers the
    # PPStructureV3 warm-instance factory.
    assert ("preprocess", "ppstructurev3", "cpu") in registry.factories


def test_failed_warm_init_is_not_cached_as_success(monkeypatch: pytest.MonkeyPatch):
    """A failed PPStructureV3 warm-up leaves no cached instance or timing."""
    from ledgerlinc_ocr.pipeline import corpus_run as corpus_run_mod
    from ledgerlinc_ocr.pipeline import stages as stages_mod
    from ledgerlinc_ocr.pipeline.corpus import WarmProfileRegistry
    from ledgerlinc_ocr.pipeline.cli import _build_resolved_plan
    from ledgerlinc_ocr.pipeline.runner import CLIInvocation

    stages_mod.register_ppstructurev3_cpu()

    def boom():
        raise RuntimeError("engine unavailable")

    fake_ocr = types.ModuleType("ledgerlinc_ocr.preprocessing.ocr")
    fake_ocr._get_engine = boom
    monkeypatch.setitem(sys.modules, "ledgerlinc_ocr.preprocessing.ocr", fake_ocr)
    args = _build_args()
    placeholder = CLIInvocation(
        input_pdf=Path("placeholder/source.pdf"),
        destination_folder=Path("placeholder"),
        document_id="placeholder",
        overwrite=args.overwrite,
        pipeline_version=args.pipeline_version,
        policy_version=args.policy_version,
        contract_set_version=args.contract_set_version,
        ollama_url=_PLACEHOLDER_OLLAMA_URL,
        log_level=args.log_level,
        timeout=args.timeout,
        ollama_cpu_url=None,
        ollama_jetson_url=None,
    )
    plan, _, _ = _build_resolved_plan(
        args,
        invocation=placeholder,
        documents=_PLACEHOLDER_DOCUMENTS,
        warm_corpus=True,
    )
    assert plan is not None

    registry = WarmProfileRegistry.empty()
    corpus_run_mod._maybe_register_warm_preprocess(registry, plan)
    message = corpus_run_mod._warm_initialize_live_preprocess(registry, plan)

    assert message == "engine unavailable"
    assert registry.instances == {}
    assert registry.initialization_timings_ns == {}


def test_failed_warm_init_aborts_once_before_document_loop(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
):
    """A setup-time PPStructureV3 failure is reported once, not per document."""
    from ledgerlinc_ocr.pipeline import stages as stages_mod
    from ledgerlinc_ocr.pipeline.cli import main
    from ledgerlinc_ocr.pipeline.exit_codes import ExitCode

    stages_mod.register_ppstructurev3_cpu()
    calls = 0

    def boom():
        nonlocal calls
        calls += 1
        raise RuntimeError("engine unavailable")

    fake_ocr = types.ModuleType("ledgerlinc_ocr.preprocessing.ocr")
    fake_ocr._get_engine = boom
    monkeypatch.setitem(sys.modules, "ledgerlinc_ocr.preprocessing.ocr", fake_ocr)

    docs_file = tmp_path / "corpus.txt"
    folders = [tmp_path / "inv_001_easy", tmp_path / "inv_002_easy"]
    for folder in folders:
        folder.mkdir()
        (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    docs_file.write_text("\n".join(folder.name for folder in folders), encoding="utf-8")

    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--preprocess-profile", "ppstructurev3@cpu",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])

    assert code == int(ExitCode.PROCESSING_FAILURE)
    captured = capsys.readouterr()
    summary = json.loads(captured.out.strip().splitlines()[-1])
    assert calls == 1
    assert summary["documents_succeeded"] == 0
    assert summary["documents_failed"] == 1
    assert summary["per_document"][0]["failed_stage"] == "preprocess"
    assert not (folders[0] / "preprocess_output.json").exists()
    assert not (folders[1] / "preprocess_output.json").exists()


def test_is_live_capable_default_state():
    """The test-only stub-fallback reset leaves no triple live-capable."""
    from ledgerlinc_ocr.pipeline.stages import is_live_capable

    assert not is_live_capable("preprocess", "ppstructurev3", "cpu")
    assert not is_live_capable("extract", "ollama", "gpu")
    assert not is_live_capable("routing", "rules", "cpu")
    assert not is_live_capable("final_payload", "assembler", "cpu")
