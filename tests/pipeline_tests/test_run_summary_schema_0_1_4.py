"""Run-summary schema 0.1.4 patch-bump tests (feature 017 / T004 / T014 /
T021 / T026 / FR-008 / FR-009 / FR-010 / R-017.8 / R-017.5 / R-017.7).

Sibling of `test_run_summary_schema_0_1_3.py` (feature 016) and
`test_run_summary_schema_0_1_2.py` (feature 015). Adds the 0.1.4-specific
regression checks: codebase-level `SCHEMA_VERSION = "0.1.4"`, three new
additive top-level fields (`module_set_id`, `det_rec_variant_id`,
`ppstructure_modules_invoked`) emitted on every run, fixed emission
order between `preprocess_lane` and the closing brace, default values
reflecting CPU-lane defaults from `preprocessing/identifiers.py`.

T014 lands the `module_set_id` slice; T021 extends with
`det_rec_variant_id`; T026 extends with `ppstructure_modules_invoked`
field-level checks. All three slices live in this same file (cumulative
verification).

All tests are CPU-safe (no Paddle import, no GPU dependency).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

timing = pytest.importorskip("ledgerlinc_ocr.pipeline.timing")

from ledgerlinc_ocr.pipeline.timing import (  # noqa: E402
    RunSummary,
    SCHEMA_VERSION,
)
from ledgerlinc_ocr.preprocessing.identifiers import (  # noqa: E402
    AUDIT_SUB_MODULE_VOCABULARY,
    CPU_DEFAULT_DET_REC_VARIANT,
    CPU_DEFAULT_MODULE_SET,
)


# ---------------------------------------------------------------------------
# T014 / I-9 / FR-008 / R-017.8: codebase-level SCHEMA_VERSION bump 0.1.3 → 0.1.4
# ---------------------------------------------------------------------------


def test_schema_version_is_0_1_4_codebase_level() -> None:
    """`SCHEMA_VERSION` is exactly `"0.1.4"` for every run of the new
    binary regardless of preset selection (per R-017.8 +
    `contracts/run-summary-schema.md` §1)."""
    assert timing.SCHEMA_VERSION == "0.1.4", (
        f"feature 017 must bump SCHEMA_VERSION from 0.1.3 to 0.1.4 "
        f"(got {timing.SCHEMA_VERSION!r})"
    )
    assert SCHEMA_VERSION == "0.1.4"


def test_run_summary_emits_0_1_4_in_json_line() -> None:
    """A serialized `run_summary` line carries `schema_version: "0.1.4"`
    on the wire."""
    summary = _make_minimal_run_summary()
    line = summary.as_json_line()
    parsed = json.loads(line)
    assert parsed["schema_version"] == "0.1.4"


# ---------------------------------------------------------------------------
# T014 / Plan §I-8: three new top-level fields are emitted on every run
# ---------------------------------------------------------------------------


def test_module_set_id_present_on_every_run() -> None:
    """Per FR-008 / FR-010 / Plan §I-8: `module_set_id` is required on
    every run_summary line (absence is itself a regression signal)."""
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    assert "module_set_id" in parsed


def test_det_rec_variant_id_present_on_every_run() -> None:
    """Per FR-008 / FR-010 / Plan §I-8: `det_rec_variant_id` is required
    on every run_summary line."""
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    assert "det_rec_variant_id" in parsed


def test_ppstructure_modules_invoked_present_on_every_run() -> None:
    """Per FR-001 / FR-009 / Plan §I-8: `ppstructure_modules_invoked` is
    required on every run_summary line. CPU/stub default is `[]`."""
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    assert "ppstructure_modules_invoked" in parsed


# ---------------------------------------------------------------------------
# T014 / R-017.5: CPU/stub default identifier values
# ---------------------------------------------------------------------------


def test_cpu_lane_defaults_are_cpu_default_strings() -> None:
    """Default `RunSummary` (no overrides) reflects the CPU lane —
    `module_set_id="cpu-default"` and `det_rec_variant_id="cpu-default"`
    per R-017.5."""
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    assert parsed["module_set_id"] == CPU_DEFAULT_MODULE_SET == "cpu-default"
    assert parsed["det_rec_variant_id"] == CPU_DEFAULT_DET_REC_VARIANT == "cpu-default"


def test_ppstructure_modules_invoked_defaults_to_empty_list() -> None:
    """CPU/stub default for `ppstructure_modules_invoked` is `[]`
    (per R-017.7 + Plan §I-6: explicit empty list signals "audit not
    run on this lane", distinct from "audit ran and found nothing")."""
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    assert parsed["ppstructure_modules_invoked"] == []


def test_stub_default_can_be_set_explicitly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Stub-adapter warm-corpus summaries use the real stub override path,
    not the CPU defaults."""
    from ledgerlinc_ocr.pipeline.corpus import DocumentEntry, WarmProfileRegistry
    from ledgerlinc_ocr.pipeline.corpus_run import _emit_warm_init_failure_summary
    from ledgerlinc_ocr.pipeline.failure_policy import FailurePolicy
    from ledgerlinc_ocr.pipeline.ollama_lanes import resolve_endpoints
    from ledgerlinc_ocr.pipeline.profiles import parse_profile
    from ledgerlinc_ocr.pipeline.runner import CLIInvocation, ResolvedRunPlan
    from ledgerlinc_ocr.pipeline.slice_control import ExecutionSlice

    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    invocation = CLIInvocation(
        input_pdf=folder / "source.pdf",
        destination_folder=folder,
        document_id="inv_001_easy",
        overwrite=False,
        pipeline_version=None,
        policy_version="p0",
        contract_set_version="1.2.0",
        ollama_url="http://localhost:11434",
        log_level="INFO",
        timeout=60,
    )
    plan = ResolvedRunPlan(
        mode="warm_corpus",
        cli_invocation=invocation,
        profiles={
            "preprocess": parse_profile("preprocess", "stub"),
            "extract": parse_profile("extract", "stub"),
            "routing": parse_profile("routing", "stub"),
            "final_payload": parse_profile("final_payload", "stub"),
        },
        slice_=ExecutionSlice(start_at="preprocess", stop_after="final_payload"),
        ollama_endpoints=resolve_endpoints(
            gpu_flag=None,
            cpu_flag=None,
            jetson_flag=None,
        ),
        failure_policy=FailurePolicy(mode="continue"),
        stack_preset_name=None,
        documents=(folder,),
    )
    docs = (DocumentEntry(raw=str(folder), resolved=folder),)

    _emit_warm_init_failure_summary(
        documents=docs,
        plan=plan,
        registry=WarmProfileRegistry.empty(),
        message="stub summary probe",
        emit_failure=lambda _record: None,
    )
    parsed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert parsed["module_set_id"] == "stub-default"
    assert parsed["det_rec_variant_id"] == "stub-default"


# ---------------------------------------------------------------------------
# T014 / contracts/run-summary-schema.md §3: emission order is fixed
# ---------------------------------------------------------------------------


def test_three_new_fields_emit_after_preprocess_lane_in_order() -> None:
    """The three new top-level fields land in fixed order between
    `preprocess_lane` and the run_summary's terminating brace, in the
    order `module_set_id` → `det_rec_variant_id` →
    `ppstructure_modules_invoked` (contracts/run-summary-schema.md §3)."""
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    keys = list(parsed.keys())
    # Locate preprocess_lane index; the three new fields follow it in order
    pl_idx = keys.index("preprocess_lane")
    assert keys[pl_idx + 1] == "module_set_id"
    assert keys[pl_idx + 2] == "det_rec_variant_id"
    assert keys[pl_idx + 3] == "ppstructure_modules_invoked"
    # Last 4 keys overall (no fields after ppstructure_modules_invoked)
    assert keys[-4:] == [
        "preprocess_lane",
        "module_set_id",
        "det_rec_variant_id",
        "ppstructure_modules_invoked",
    ]


# ---------------------------------------------------------------------------
# T014 / Plan §I-9: schema version bumped on every emission, regardless of state
# ---------------------------------------------------------------------------


def test_schema_version_unchanged_across_preset_selections() -> None:
    """`schema_version` is `"0.1.4"` for every emission regardless of
    which preset the run used — fixed at the codebase level (Plan §I-9)."""
    for module_set_id, det_rec_variant_id in [
        ("cpu-default", "cpu-default"),
        ("stub-default", "stub-default"),
        ("legacy", "legacy"),  # GPU defaults
        ("reduced-v1", "ppocrv5-mobile"),  # GPU reduced + lighter
    ]:
        summary = _make_minimal_run_summary()
        summary.module_set_id = module_set_id
        summary.det_rec_variant_id = det_rec_variant_id
        parsed = json.loads(summary.as_json_line())
        assert parsed["schema_version"] == "0.1.4"


# ---------------------------------------------------------------------------
# T026 / Plan §I-6: ppstructure_modules_invoked subset + lex-sorted invariant
# ---------------------------------------------------------------------------


def test_ppstructure_modules_invoked_is_list_type() -> None:
    """`ppstructure_modules_invoked` is a JSON array (Python list) on
    every run."""
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    assert isinstance(parsed["ppstructure_modules_invoked"], list)


def test_ppstructure_modules_invoked_is_canonicalized_on_emit() -> None:
    """Audit lists on the wire are de-duplicated, lex-sorted, and remain
    within the closed vocabulary."""
    summary = _make_minimal_run_summary()
    summary.ppstructure_modules_invoked = [
        "ocr_rec",
        "layout_detection",
        "ocr_rec",
        "ocr_det",
    ]
    parsed = json.loads(summary.as_json_line())
    assert parsed["ppstructure_modules_invoked"] == [
        "layout_detection",
        "ocr_det",
        "ocr_rec",
    ]
    assert set(parsed["ppstructure_modules_invoked"]) <= set(AUDIT_SUB_MODULE_VOCABULARY)


def test_ppstructure_modules_invoked_drops_unknown_strings_at_emit() -> None:
    """The serializer is the last line of defense for the closed-vocabulary
    contract. A buggy caller that puts arbitrary strings into the field
    must not be able to leak them onto the wire — emit-time intersection
    with `AUDIT_SUB_MODULE_VOCABULARY` enforces R-017.7."""
    summary = _make_minimal_run_summary()
    summary.ppstructure_modules_invoked = [
        "layout_detection",
        "totally_bogus_module",
        "ocr_rec",
        "another_garbage_value",
    ]
    parsed = json.loads(summary.as_json_line())
    assert parsed["ppstructure_modules_invoked"] == ["layout_detection", "ocr_rec"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_run_summary() -> RunSummary:
    """A minimal RunSummary suitable for emission/serialization tests.
    Default profile is CPU; overrides set explicitly on the result."""
    return RunSummary(
        stack_preset=None,
        resolved_profiles={"preprocess": "ppstructurev3@cpu"},
        execution_slice={"start_at": "preprocess", "stop_after": "preprocess"},
        on_failure="continue",
        documents_total=0,
        documents_succeeded=0,
        documents_failed=0,
    )
