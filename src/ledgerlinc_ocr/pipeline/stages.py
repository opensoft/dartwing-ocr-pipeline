"""Default stub stage callables and the profile->adapter registry.

Each stub writes a minimal schema-valid artifact for its stage. Real model
inference is wired in by user-story phases (US6 ppstructurev3@cpu, US1
ollama@gpu / rules@cpu / assembler@cpu, US3 ollama@cpu, etc.) by registering
live adapters for the matching ``(stage, implementation, lane)`` triples.

Stage signatures
----------------
Every stage callable takes `(invocation: CLIInvocation, artifacts_so_far: dict)`
and returns either a dict matching its v1.2.0 artifact schema or a
``StageRunOutput`` for adapters that already wrote their canonical artifact.
The runner writes plain dicts and trusts ``StageRunOutput`` paths that already
exist.

Schema-invalidity toggle
------------------------
The runner passes through injected stage callables verbatim, so tests can swap
in a stub that writes an intentionally invalid artifact to exercise
SCHEMA_VALIDATION_FAILURE.

Adapter registry (Research R-014)
---------------------------------
``resolve_stage_callable(stage, profile, plan)`` looks up a callable for a
resolved ``StageProfile``. Stub profiles always resolve to the stub callables
in this module. Live profiles consult ``_LIVE_REGISTRY``; user-story phases
register live adapters there. Unregistered live triples raise
``DeferredImplementationError`` (R-013): argument validation accepts the
profile but execution fails fast with a named missing-implementation error.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from ledgerlinc_ocr import __version__ as _package_version
from ledgerlinc_ocr.pipeline.filenames import EDGE_EXTRACTION_OUTPUT_FILENAME
from ledgerlinc_ocr.pipeline.profiles import Stage, StageProfile

_SOURCE_PDF = "source.pdf"
_STUB_BLOCK_TEXT = "stub block"
# Local alias kept so existing call sites don't need to change visibility.
_EDGE_EXTRACTION_OUTPUT_FILENAME = EDGE_EXTRACTION_OUTPUT_FILENAME

if TYPE_CHECKING:
    from ledgerlinc_ocr.pipeline.runner import CLIInvocation, ResolvedRunPlan


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stub_pipeline_version(invocation: "CLIInvocation") -> str:
    return invocation.pipeline_version or _package_version


def default_preprocess(
    invocation: "CLIInvocation", artifacts_so_far: dict[str, Any]
) -> dict[str, Any]:
    return {
        "contract_set_version": invocation.contract_set_version,
        "pipeline_version": _stub_pipeline_version(invocation),
        "document_id": invocation.document_id,
        "source_type": "pdf",
        "source_file": _SOURCE_PDF,
        "page_count": 1,
        "pages": [
            {
                "page_number": 1,
                "width": 850,
                "height": 1100,
                "rotation_detected": 0,
                "blocks": [
                    {
                        "block_id": "p1_b1",
                        "block_type": "text",
                        "bbox": [0, 0, 100, 20],
                        "reading_order": 1,
                        "text": _STUB_BLOCK_TEXT,
                        "confidence": 0.9,
                    }
                ],
                "raw_ocr_lines": [
                    {
                        "line_id": "p1_l1",
                        "bbox": [0, 0, 100, 20],
                        "text": _STUB_BLOCK_TEXT,
                        "confidence": 0.9,
                    }
                ],
            }
        ],
        "document_text": _STUB_BLOCK_TEXT,
        "tables": [],
        "quality": {
            "scan_quality": "good",
            "skew_detected": False,
            "noise_level": "low",
        },
        "ingestion_sources": {
            "paddleocr_vl": {"enabled": False, "status": "not_implemented"},
            "falcon_ocr": {"enabled": False, "status": "not_implemented"},
            "falcon_perception": {"enabled": False, "status": "not_implemented"},
        },
        "warnings": [],
    }


def _empty_value_confidence_evidence() -> dict[str, Any]:
    return {"value": None, "confidence": 0.0, "evidence": []}


def _empty_value_confidence() -> dict[str, Any]:
    return {"value": None, "confidence": 0.0}


def default_extraction(
    invocation: "CLIInvocation", artifacts_so_far: dict[str, Any]
) -> dict[str, Any]:
    company_name = {
        "value": "Stub Vendor Co.",
        "present": True,
        "inferred": False,
        "confidence": 0.9,
        "evidence": ["p1_b1"],
    }
    return {
        "contract_set_version": invocation.contract_set_version,
        "pipeline_version": _stub_pipeline_version(invocation),
        "document_id": invocation.document_id,
        "processed_at": _now_iso(),
        "model_runtime": {
            "provider": "stub",
            "model_name": "stub-extractor",
            "model_version": "0.0.0",
            "runtime": "stub",
        },
        "vote_metadata": {
            "voter_id": "stub-voter-1",
            "voter_role": "primary_extractor",
            "consensus_mode": "single_voter_baseline",
        },
        "document_type": {"value": "invoice", "confidence": 0.9},
        "vendor_candidate": {
            "company_name": company_name,
            "address": {
                k: _empty_value_confidence_evidence()
                for k in ("street_1", "street_2", "city", "state", "postal_code", "country")
            },
            "tax_ids": {
                k: _empty_value_confidence_evidence()
                for k in ("ein", "state_tax_id", "vat_id", "other_tax_id")
            },
            "website": _empty_value_confidence_evidence(),
            "phone": _empty_value_confidence_evidence(),
            "email": _empty_value_confidence_evidence(),
        },
        "invoice_header_fields": {
            "invoice_number": _empty_value_confidence_evidence(),
            "invoice_date": _empty_value_confidence_evidence(),
            "total_amount": {
                "value": None,
                "currency": None,
                "confidence": 0.0,
                "evidence": [],
            },
        },
        "extraction_notes": [],
        "warnings": [],
        "status": "success",
    }


def default_routing(
    invocation: "CLIInvocation", artifacts_so_far: dict[str, Any]
) -> dict[str, Any]:
    extraction = artifacts_so_far[_EDGE_EXTRACTION_OUTPUT_FILENAME]
    company_name = extraction["vendor_candidate"]["company_name"]

    present = bool(company_name.get("present"))
    inferred = bool(company_name.get("inferred"))

    if not present and inferred:
        decision = "edge_review_required"
        manual_review_required = True
        review_reason: str | None = "company_name_inferred"
        reasons = ["company_name_inferred"]
    else:
        decision = "edge_accept"
        manual_review_required = False
        review_reason = None
        reasons = []

    return {
        "contract_set_version": invocation.contract_set_version,
        "pipeline_version": _stub_pipeline_version(invocation),
        "policy_version": invocation.policy_version,
        "document_id": invocation.document_id,
        "processed_at": _now_iso(),
        "status": "success",
        "decision": decision,
        "consensus_summary": {
            "mode": "single_voter_baseline",
            "agreement_level": "not_applicable",
        },
        "scores": {
            "company_name_score": float(company_name.get("confidence", 0.0)),
            "address_score": 0.0,
            "tax_id_score": 0.0,
            "contact_score": 0.0,
            "overall_vendor_identity_score": float(
                company_name.get("confidence", 0.0)
            ),
        },
        "checks": {
            "company_name_present": present,
            "company_name_inferred": inferred,
            "address_has_minimum_components": False,
            "at_least_one_tax_id_present": False,
            "website_or_email_present": False,
            "post_extraction_spam_gate_passed": True,
        },
        "review_status": {
            "manual_review_required": manual_review_required,
            "review_reason": review_reason,
        },
        "reasons": reasons,
    }


def default_final_payload(
    invocation: "CLIInvocation", artifacts_so_far: dict[str, Any]
) -> dict[str, Any]:
    extraction = artifacts_so_far[_EDGE_EXTRACTION_OUTPUT_FILENAME]
    routing = artifacts_so_far["routing_decision.json"]
    vc = extraction["vendor_candidate"]

    def strip_evidence(field: dict[str, Any]) -> dict[str, Any]:
        return {"value": field["value"], "confidence": field["confidence"]}

    flat_company = {
        "value": vc["company_name"]["value"],
        "present": vc["company_name"]["present"],
        "inferred": vc["company_name"]["inferred"],
        "confidence": vc["company_name"]["confidence"],
    }

    return {
        "contract_set_version": invocation.contract_set_version,
        "pipeline_version": _stub_pipeline_version(invocation),
        "document_id": invocation.document_id,
        "processed_at": _now_iso(),
        "document_type": "invoice",
        "vendor_candidate": {
            "company_name": flat_company,
            "address": {k: strip_evidence(v) for k, v in vc["address"].items()},
            "tax_ids": {k: strip_evidence(v) for k, v in vc["tax_ids"].items()},
            "website": strip_evidence(vc["website"]),
            "phone": strip_evidence(vc["phone"]),
            "email": strip_evidence(vc["email"]),
        },
        "review_status": {
            "manual_review_required": routing["review_status"][
                "manual_review_required"
            ],
            "review_reason": routing["review_status"]["review_reason"],
        },
        "quality_summary": {
            "overall_vendor_confidence": routing["scores"][
                "overall_vendor_identity_score"
            ],
            "explicit_name_found": flat_company["present"] and not flat_company["inferred"],
            "consensus_level": "single_voter_baseline",
            "secondary_identifiers_found": [],
        },
        "trace": {
            "source_file": _SOURCE_PDF,
            "preprocess_output_file": "preprocess_output.json",
            "edge_extraction_output_file": _EDGE_EXTRACTION_OUTPUT_FILENAME,
            "routing_decision_file": "routing_decision.json",
        },
    }


# --- Profile -> adapter registry (Research R-014) -----------------------


class DeferredImplementationError(RuntimeError):
    """Raised by adapters whose live implementation is sequenced for FR-034 step 4.

    The CLI dispatch layer maps this to ``ExitCode.USAGE_ERROR`` (10) per
    Research R-013: the user selected a recognized profile but its live
    runtime is not part of this slice. The error message MUST name the
    profile and reference FR-034 step 4 so an operator can tell which
    stage/profile failed without code inspection (Spec FR-031).
    """


# Type alias for a stage callable invoked by the runner. The concrete return
# type includes ``StageRunOutput`` from ``runner.py``; keep this alias broad to
# avoid a runtime import cycle in the registry module.
StageCallable = Callable[["CLIInvocation", dict[str, Any]], Any]

# Type alias for an adapter factory. Adapters are registered as factories
# that take the resolved ``ResolvedRunPlan`` (so they can read lane URLs,
# pipeline_version, etc.) and return a ``StageCallable`` for the runner.
AdapterFactory = Callable[["ResolvedRunPlan"], StageCallable]


# Stub callables -- one per stage. ``stub`` profiles always resolve to these.
_STUB_REGISTRY: dict[Stage, StageCallable] = {
    "preprocess": default_preprocess,
    "extract": default_extraction,
    "routing": default_routing,
    "final_payload": default_final_payload,
}

# Profiles whose live implementation is sequenced for FR-034 step 4 (the
# secondary-lane slice). Selecting these profiles in this slice triggers
# a deterministic ``DeferredImplementationError`` -- the live adapter
# does not "fall back" to the stub callable. Per Spec FR-035 + Research
# R-013 / R-014.
DEFERRED_LIVE_PROFILES: frozenset[tuple[Stage, str, str | None]] = frozenset({
    ("preprocess", "edge-ocr", "jetson"),
    ("extract", "ollama", "jetson"),
    ("extract", "ensemble", "workstation"),
})

# Live adapter registry. Keys are ``(stage, implementation, lane)`` triples
# from ``profiles.SUPPORTED_PROFILES``. The default no-flag path registers
# the in-slice real adapters at module load. Tests can request
# ``stub_fallback_only`` through ``reset_live_registry`` when they need a
# fully offline registry baseline.
_LIVE_REGISTRY: dict[tuple[Stage, str, str | None], AdapterFactory] = {}

# Capability registry: (stage, implementation, lane) triples whose registered
# adapter is a real live adapter, not a stub-fallback wrapper. Consumers
# (notably ``corpus_run._maybe_register_warm_preprocess``) check this set
# before triggering heavy initialization paths.
_LIVE_CAPABILITIES: set[tuple[Stage, str, str | None]] = set()


def is_live_capable(
    stage: Stage, implementation: str, lane: str | None
) -> bool:
    """True iff a real live adapter is registered for the triple.

    Returns False when only a test-only stub fallback is in place so
    warm-corpus and similar paths avoid heavy live initialization.
    """
    return (stage, implementation, lane) in _LIVE_CAPABILITIES


def _stub_fallback_factory(stage: Stage) -> AdapterFactory:
    """Return an AdapterFactory that hands back the stage's stub callable."""
    stub = _STUB_REGISTRY[stage]

    def _factory(_plan: "ResolvedRunPlan") -> StageCallable:
        return stub

    return _factory


def _seed_default_stub_fallbacks() -> None:
    """Register offline stub fallbacks for default live triples."""
    for stage, impl, lane in [
        ("preprocess", "ppstructurev3", "cpu"),
        ("extract", "ollama", "gpu"),
        ("extract", "ollama", "cpu"),
        ("routing", "rules", "cpu"),
        ("final_payload", "assembler", "cpu"),
    ]:
        _LIVE_REGISTRY[(stage, impl, lane)] = _stub_fallback_factory(stage)


_seed_default_stub_fallbacks()


# ---------------------------------------------------------------------------
# Live adapters (T031, T039-T041, T046, T051): each wraps an existing
# per-stage module's entry point per Research R-014. They are registered
# at module load so a no-flag run of the CLI dispatches to them.
# ---------------------------------------------------------------------------


def _ppstructurev3_factory(lane: str) -> AdapterFactory:
    """Return a live PPStructureV3 preprocessing adapter for one lane.

    ``lane`` is the artifact lane segment consumed by
    ``ledgerlinc_ocr.preprocessing.pipeline.Invocation``: ``"cpu"`` for the
    default CPU adapter, ``"gpu0"`` for the workstation GPU adapter.
    """
    import json
    from ledgerlinc_ocr.preprocessing.pipeline import (
        Invocation as PreInvocation,
        run as preprocessing_run,
    )

    def factory(_plan: "ResolvedRunPlan") -> StageCallable:
        def adapter(
            invocation: "CLIInvocation", artifacts_so_far: dict[str, Any]
        ) -> Any:
            # Feature 015 (T021): pass the Runner's active StageTiming
            # into pipeline.run so the per-phase keys (`rasterization`,
            # `artifact_write`, plus `total` via measure_total) are
            # recorded on the same map the Runner is using for the
            # coarse `infer` phase. corpus_run.py drains this map after
            # the call to build the run_summary `phase_timings` block.
            from ledgerlinc_ocr.pipeline.timing import current_stage_timing

            # Feature 016 (Copilot PR #24 round 2 finding 1): warmup is
            # NOT threaded through the adapter anymore. `_run_inner` no
            # longer fires warmup; the cold pipeline CLI hoists warmup
            # via `pipeline.run_warmup_if_active()` BEFORE the runner's
            # `measure_total` window opens, so warmup duration is
            # excluded from per-doc `phase_timings.total` per
            # FR-007 / SC-004. `Invocation.warmup` remains as a
            # CLI-intent flag for diagnostics only.
            # Feature 018 (B1 fix): thread raster_profile_id + region_strategy_id
            # from the CLIInvocation through to the PreInvocation so the
            # orchestrator's region-first / reduced-DPI branches actually
            # fire under the live adapter (R-018.1 / R-018.2 / R-018.4).
            # Without this, the CLI flags resolve correctly but the
            # adapter would silently drop them at the boundary.
            pre_invocation = PreInvocation(
                document_folder=invocation.destination_folder,
                source_file=_SOURCE_PDF,
                pipeline_version=invocation.pipeline_version,
                preprocess_lane=lane,
                module_set_id=invocation.module_set_id,
                det_rec_variant_id=invocation.det_rec_variant_id,
                raster_profile_id=invocation.raster_profile_id,
                region_strategy_id=invocation.region_strategy_id,
            )
            try:
                out_path = preprocessing_run(
                    pre_invocation,
                    stage_timing=current_stage_timing(),
                )
            finally:
                invocation.region_strategy_fallback_fired = (
                    pre_invocation.region_strategy_fallback_fired
                )
            from ledgerlinc_ocr.pipeline.runner import StageRunOutput

            return StageRunOutput(
                payload=json.loads(out_path.read_text(encoding="utf-8")),
                artifact_path=out_path,
            )

        return adapter

    return factory


def _ppstructurev3_cpu_factory(_plan: "ResolvedRunPlan") -> StageCallable:
    """T031: live (preprocess, ppstructurev3, cpu) adapter wrapping
    ``ledgerlinc_ocr.preprocessing.pipeline.run``.

    Construction is per-call: PPStructureV3 init happens inside the
    upstream module the first time ``run()`` is invoked. Warm-corpus
    callers should reuse the warmed engine via ``WarmProfileRegistry``;
    cold one-off callers pay the init cost once.
    """
    return _ppstructurev3_factory("cpu")(_plan)


def _ollama_extract_factory(lane: str) -> Callable[["ResolvedRunPlan"], StageCallable]:
    """T039 / T046: live (extract, ollama, <lane>) adapter wrapping
    ``ledgerlinc_ocr.extract.pipeline.run``.

    Loads the default voter config from the on-disk YAML in
    ``src/ledgerlinc_ocr/extract/voters/configs/gemma-edge.yaml`` and
    instantiates an ``OllamaVoter`` against the lane URL resolved by
    ``OllamaLaneEndpoints.for_lane(lane)``. The chosen lane URL is
    passed via the env-var ``OLLAMA_BASE_URL`` because OllamaVoter reads
    it from there if no ``base_url`` is supplied; we explicitly pass
    ``base_url`` so the env is not relied on at call time.
    """
    def factory(plan: "ResolvedRunPlan") -> StageCallable:
        import json

        from ledgerlinc_ocr.extract.config import load_voter_config
        from ledgerlinc_ocr.extract.pipeline import run as extract_run
        from ledgerlinc_ocr.extract.voters.ollama import OllamaVoter

        url = plan.ollama_endpoints.for_lane(lane)
        voter_config, voter_config_path, _extensions = load_voter_config(
            "gemma-edge",
        )
        # Resolve template_path relative to the voter config file.
        template_path = (
            voter_config_path.parent / voter_config.prompt.template_path
        ).resolve()
        voter = OllamaVoter(base_url=url)

        def adapter(
            invocation: "CLIInvocation", artifacts_so_far: dict[str, Any]
        ) -> Any:
            # Forward invocation.pipeline_version so --pipeline-version is
            # honored by edge_extraction_output.json the same way it is
            # honored by the other stages (Copilot review item 5).
            out_path = extract_run(
                folder_path=invocation.destination_folder,
                voter_config=voter_config,
                voter=voter,
                template_path=template_path,
                pipeline_version=invocation.pipeline_version,
                contract_set_version=invocation.contract_set_version,
            )
            from ledgerlinc_ocr.pipeline.runner import StageRunOutput

            return StageRunOutput(
                payload=json.loads(out_path.read_text(encoding="utf-8")),
                artifact_path=out_path,
            )

        return adapter

    return factory


def register_ollama_gpu() -> None:
    """Register the live (extract, ollama, gpu) adapter."""
    register_live_adapter(
        stage="extract",
        implementation="ollama",
        lane="gpu",
        factory=_ollama_extract_factory("gpu"),
    )
    _LIVE_CAPABILITIES.add(("extract", "ollama", "gpu"))


def register_ollama_cpu() -> None:
    """Register the optional live (extract, ollama, cpu) adapter."""
    register_live_adapter(
        stage="extract",
        implementation="ollama",
        lane="cpu",
        factory=_ollama_extract_factory("cpu"),
    )
    _LIVE_CAPABILITIES.add(("extract", "ollama", "cpu"))


def _routing_rules_cpu_factory(plan: "ResolvedRunPlan") -> StageCallable:
    """T040: live (routing, rules, cpu) adapter wrapping
    ``ledgerlinc_ocr.router.pipeline.run``. Pure-deterministic, no init cost.
    """
    from ledgerlinc_ocr.router.pipeline import run as router_run
    from ledgerlinc_ocr.router.version import (
        build_pipeline_version as build_routing_pipeline_version,
    )

    def adapter(
        invocation: "CLIInvocation", artifacts_so_far: dict[str, Any]
    ) -> Any:
        path, artifact = router_run(
            invocation.destination_folder,
            pipeline_version=(
                invocation.pipeline_version or build_routing_pipeline_version()
            ),
            policy_version=invocation.policy_version,
            contract_set_version=invocation.contract_set_version,
        )
        from ledgerlinc_ocr.pipeline.runner import StageRunOutput

        return StageRunOutput(payload=artifact, artifact_path=path)

    return adapter


def _final_payload_assembler_cpu_factory(_plan: "ResolvedRunPlan") -> StageCallable:
    """T041: live (final_payload, assembler, cpu) adapter wrapping
    ``ledgerlinc_ocr.assembler.pipeline.run``.
    """
    import json
    from ledgerlinc_ocr.assembler.pipeline import (
        Invocation as AssInvocation,
        run as assembler_run,
    )

    def adapter(
        invocation: "CLIInvocation", artifacts_so_far: dict[str, Any]
    ) -> Any:
        out_path = assembler_run(
            AssInvocation(
                document_folder=invocation.destination_folder,
                pipeline_version=invocation.pipeline_version,
                contract_set_version=invocation.contract_set_version,
            )
        )
        from ledgerlinc_ocr.pipeline.runner import StageRunOutput

        return StageRunOutput(
            payload=json.loads(out_path.read_text(encoding="utf-8")),
            artifact_path=out_path,
        )

    return adapter


# Note: the default GPU extract adapter is registered at module load for US1.
# CPU extraction remains opt-in via ``register_ollama_cpu`` for the lane-
# comparison slice.


def register_live_adapter(
    *,
    stage: Stage,
    implementation: str,
    lane: str | None,
    factory: AdapterFactory,
) -> None:
    """Register a live adapter factory for ``(stage, implementation, lane)``.

    Idempotent: registering the same triple twice replaces the prior
    factory (used by tests that swap in fakes).
    """
    _LIVE_REGISTRY[(stage, implementation, lane)] = factory


def _make_deferred_callable(
    stage: Stage, profile: StageProfile
) -> StageCallable:
    """Return a callable that hard-fails with a DeferredImplementationError."""
    raw = profile.raw_value

    def _adapter(
        invocation: "CLIInvocation", artifacts_so_far: dict[str, Any]
    ) -> dict[str, Any]:
        # Live implementation deferred (Research R-013 / R-014; Spec FR-035).
        # The message names the profile and the deferral so the operator
        # can route the request correctly per Spec FR-031.
        if raw == "ensemble@workstation":
            detail = (
                "ensemble@workstation requires voter endpoints; configuration "
                "is delivered in the secondary-lane slice (FR-034 step 4) -- "
                "set the explicit per-stage profile or --stack-preset to a "
                "supported workstation preset"
            )
        else:
            detail = (
                f"{raw} live adapter is sequenced for FR-034 step 4 "
                f"(see specs/011-stage-runtime-profiles/research.md R-014); "
                f"select a supported in-slice profile for this stage"
            )
        raise DeferredImplementationError(detail)

    return _adapter


def resolve_stage_callable(
    *,
    stage: Stage,
    profile: StageProfile,
    plan: "ResolvedRunPlan",
) -> StageCallable:
    """Resolve a ``StageProfile`` to the runner-facing callable.

    Resolution order (R-013 / R-014):
      * stub profiles -> ``_STUB_REGISTRY``
      * deferred live profiles (Spec FR-035) -> a callable that raises
        ``DeferredImplementationError`` with the profile name and the
        FR-034 step 4 deferral note (per Spec FR-031)
      * other live profiles with a registered factory -> factory(plan)
      * other live profiles with no registered factory -> a callable
        that raises ``DeferredImplementationError``
    """
    if profile.kind == "stub":
        return _STUB_REGISTRY[stage]

    key = (stage, profile.implementation, profile.lane)
    if key in DEFERRED_LIVE_PROFILES:
        return _make_deferred_callable(stage, profile)
    factory = _LIVE_REGISTRY.get(key)
    if factory is None:
        return _make_deferred_callable(stage, profile)
    return factory(plan)


def _register_default_live_adapters() -> None:
    register_ppstructurev3_cpu()
    register_ppstructurev3_gpu()
    register_ollama_gpu()
    register_routing_rules_cpu()
    register_final_payload_assembler_cpu()


def reset_live_registry(*, stub_fallback_only: bool = False) -> None:
    """Test helper: drop registered adapters and restore the default registry.

    ``stub_fallback_only=True`` gives unit tests a fully offline baseline
    while production defaults remain the real in-slice adapters.
    """
    _LIVE_REGISTRY.clear()
    _LIVE_CAPABILITIES.clear()
    _seed_default_stub_fallbacks()
    if not stub_fallback_only:
        _register_default_live_adapters()


def register_routing_rules_cpu() -> None:
    """Register the live (routing, rules, cpu) adapter."""
    register_live_adapter(
        stage="routing",
        implementation="rules",
        lane="cpu",
        factory=_routing_rules_cpu_factory,
    )
    _LIVE_CAPABILITIES.add(("routing", "rules", "cpu"))


def register_final_payload_assembler_cpu() -> None:
    """Register the live (final_payload, assembler, cpu) adapter."""
    register_live_adapter(
        stage="final_payload",
        implementation="assembler",
        lane="cpu",
        factory=_final_payload_assembler_cpu_factory,
    )
    _LIVE_CAPABILITIES.add(("final_payload", "assembler", "cpu"))

# The ppstructurev3 factory is registered by default and exported so tests can
# reset/re-register it without reaching into private helpers.
def register_ppstructurev3_cpu() -> None:
    """Register the live ppstructurev3@cpu adapter."""
    register_live_adapter(
        stage="preprocess",
        implementation="ppstructurev3",
        lane="cpu",
        factory=_ppstructurev3_cpu_factory,
    )
    _LIVE_CAPABILITIES.add(("preprocess", "ppstructurev3", "cpu"))


def register_ppstructurev3_gpu() -> None:
    """Register the live ppstructurev3@gpu adapter.

    The adapter stays opt-in because DEFAULT_PROFILES still selects
    ppstructurev3@cpu. When selected, preprocessing.pipeline performs the
    FR-001 preflight gate before artifact writes and binds PPStructureV3 to
    gpu:0 via lane segment ``gpu0``.
    """
    register_live_adapter(
        stage="preprocess",
        implementation="ppstructurev3",
        lane="gpu",
        factory=_ppstructurev3_factory("gpu0"),
    )
    _LIVE_CAPABILITIES.add(("preprocess", "ppstructurev3", "gpu"))


_register_default_live_adapters()


__all__ = [
    "AdapterFactory",
    "DEFERRED_LIVE_PROFILES",
    "DeferredImplementationError",
    "StageCallable",
    "default_extraction",
    "default_final_payload",
    "default_preprocess",
    "default_routing",
    "is_live_capable",
    "register_final_payload_assembler_cpu",
    "register_live_adapter",
    "register_ollama_cpu",
    "register_ollama_gpu",
    "register_ppstructurev3_cpu",
    "register_ppstructurev3_gpu",
    "register_routing_rules_cpu",
    "reset_live_registry",
    "resolve_stage_callable",
]
