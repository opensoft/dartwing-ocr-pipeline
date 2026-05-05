"""Copilot review item 1: warm-init for live preprocessing only fires when
the live adapter is actually capable, not when a stub-fallback factory
is in place.

This guards against default warm-corpus runs pre-loading PPStructureV3
in environments where Paddle is installed but no opt-in registration
has happened.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def reset_registry():
    from ledgerlinc_ocr.pipeline import stages as stages_mod

    stages_mod.reset_live_registry()
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
    """The seeded stub-fallback factory must NOT trigger warm initialization
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
        ollama_url="http://placeholder",
        log_level=args.log_level,
        timeout=args.timeout,
        ollama_cpu_url=None,
        ollama_jetson_url=None,
    )
    plan, _, msg = _build_resolved_plan(
        args,
        invocation=placeholder,
        documents=(Path("/tmp/placeholder"),),
        warm_corpus=True,
    )
    assert plan is not None, f"plan resolution failed: {msg}"

    registry = WarmProfileRegistry.empty()
    corpus_run_mod._maybe_register_warm_preprocess(registry, plan)
    # Capability gate: stub fallback in foundation phase => no factory
    # registered => warm init is a no-op.
    assert registry.factories == {}
    assert registry.initialization_timings_ns == {}


def test_explicit_register_ppstructurev3_cpu_unlocks_warm_init():
    """Once the opt-in helper registers a real adapter, warm-init MAY fire."""
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
        ollama_url="http://placeholder",
        log_level=args.log_level,
        timeout=args.timeout,
        ollama_cpu_url=None,
        ollama_jetson_url=None,
    )
    plan, _, _ = _build_resolved_plan(
        args,
        invocation=placeholder,
        documents=(Path("/tmp/placeholder"),),
        warm_corpus=True,
    )
    assert plan is not None

    registry = WarmProfileRegistry.empty()
    corpus_run_mod._maybe_register_warm_preprocess(registry, plan)
    # With the opt-in registration, the warm-corpus path registers the
    # PPStructureV3 warm-instance factory.
    assert ("preprocess", "ppstructurev3", "cpu") in registry.factories


def test_is_live_capable_default_state():
    """In a freshly-reset registry no triple is live-capable; only the seeded
    stub fallbacks are present.
    """
    from ledgerlinc_ocr.pipeline.stages import is_live_capable

    assert not is_live_capable("preprocess", "ppstructurev3", "cpu")
    assert not is_live_capable("extract", "ollama", "gpu")
    assert not is_live_capable("routing", "rules", "cpu")
    assert not is_live_capable("final_payload", "assembler", "cpu")
