"""T054 — US4 non-regression integration tests (AS1-AS6).

Covers SC-006 / FR-021 / FR-022 / FR-023 / FR-024 / FR-025 / FR-028 /
MI-17 / MI-22.

User Story 4 is the **non-regression release gate**: adding the semantic
table quality gate must NOT change vendor-identity behavior or features
019/020/021 behavior. These tests assert that contract end-to-end on
the existing 20-document corpus baseline plus targeted in-memory cases
for the per-status mapping of ``document_pass_fail.semantic_table_quality_passed``.

Acceptance scenarios (from `spec.md` US4):

- AS1: 20-document vendor-identity baseline byte-identical pre/post
  feature (SC-006 / MI-22). Reads the golden artifacts at
  ``tests/integration/goldens/vendor_identity_baseline_pre_022/``
  (captured by T057) and compares the vendor-identity subset of every
  per-document and run-summary output. Skips with clear reason if the
  goldens directory is empty.
- AS2: document with sufficient vendor-identity + failing semantic
  verdict → vendor-identity passes AND semantic fails independently.
- AS3: feature-020 ``sufficient`` decision unchanged when semantic gate
  also runs (FR-022) — verified by asserting that adding a sidecar to a
  fixture does NOT alter any feature-020 ``evidence_gate_*`` run-summary
  field. Since the test fixture corpus does not currently include
  feature-020 fields (those are emitted by the pipeline runner, not
  the evaluator), AS3 reduces to the same vendor-identity portion check
  as AS1 (already covered there); we still exercise the writer surface
  to confirm both paths agree.
- AS4: failed semantic + passing vendor → ``semantic_table_quality_passed: false``
  (FR-025).
- AS5: no-sidecar folder → ``semantic_table_quality_passed: null``, no
  semantic pass inferred from vendor-identity (FR-025 / SC-005).
- AS6: features 019/021 unchanged — verified by importing the public
  surfaces (cross-references T056 for the deeper static check).

CPU-only, no Paddle, no network (MI-1). Uses ``tmp_path`` for all
filesystem work — never a hardcoded ``/tmp`` path (Sonar python:S5443).
Uses ``pytest.approx`` for any float comparison (Sonar python:S1244).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from dartwing_ocr.evaluator import evaluate_corpus, evaluate_document

REPO_ROOT = Path(__file__).resolve().parents[2]
_EVALUATOR_FIXTURES = REPO_ROOT / "tests" / "evaluator_tests" / "fixtures"
_SEMANTIC_FIXTURE = REPO_ROOT / "tests" / "stage1_semantic_quality" / "inv_001_hard"
_GOLDENS_ROOT = (
    REPO_ROOT / "tests" / "integration" / "goldens" / "vendor_identity_baseline_pre_022"
)

# v1.3.0 additive fields the writer emits that the v1.2.0 goldens do not
# have. These are stripped from the candidate output before comparing
# against the golden (AS1 / MI-22 — vendor-identity portion only).
_SEMANTIC_DOC_LEVEL_KEYS: frozenset[str] = frozenset({"semantic_table_quality"})
_SEMANTIC_PASS_FAIL_KEY: str = "semantic_table_quality_passed"
_SEMANTIC_SUMMARY_KEYS: frozenset[str] = frozenset(
    {"semantic_table_quality_metrics", "semantic_document_statuses"}
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _strip_semantic_fields_from_eval_doc(instance: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of an ``evaluation_document.json`` dict with the
    additive v1.3.0 semantic fields removed.

    Also normalizes ``contract_set_version`` to ``"1.2.0"`` so the
    comparison against the v1.2.0-pinned golden is apples-to-apples;
    the version-string difference is the ONLY field allowed to differ
    on the vendor-identity portion.
    """
    out = dict(instance)
    out["contract_set_version"] = "1.2.0"
    for key in _SEMANTIC_DOC_LEVEL_KEYS:
        out.pop(key, None)
    pf = dict(out.get("document_pass_fail", {}))
    pf.pop(_SEMANTIC_PASS_FAIL_KEY, None)
    out["document_pass_fail"] = pf
    return out


def _strip_semantic_fields_from_run_summary(
    instance: dict[str, Any],
) -> dict[str, Any]:
    """Return a copy of an ``evaluation_run_summary.json`` dict with the
    additive v1.3.0 semantic top-level keys removed and
    ``contract_set_version`` normalized to ``"1.2.0"``.

    Also drops ``run_id`` from the comparison: ``run_id`` is a per-run
    UUID + timestamp that is deliberately non-deterministic (each
    invocation gets a fresh value); comparing it would always fail
    regardless of regression status. MI-22 is about the vendor-identity
    SCORING content, not the run-instance identifier.
    """
    out = dict(instance)
    out["contract_set_version"] = "1.2.0"
    out.pop("run_id", None)
    for key in _SEMANTIC_SUMMARY_KEYS:
        out.pop(key, None)
    return out


def _strip_run_id_from_golden(golden: dict[str, Any]) -> dict[str, Any]:
    """Mirror of ``_strip_semantic_fields_from_run_summary`` for the golden
    side: drop ``run_id`` so the comparison is symmetric."""
    out = dict(golden)
    out.pop("run_id", None)
    return out


def _run_post_feature_corpus(tmp_path: Path) -> Path:
    """Stage the corpus_20 fixture into ``tmp_path`` and run the evaluator
    under the post-feature default contract (v1.3.0). Returns the corpus
    root."""
    root = tmp_path / "post_corpus"
    shutil.copytree(_EVALUATOR_FIXTURES / "corpus_20", root)
    evaluate_corpus(root)  # default = current CONTRACT_SET_VERSION (1.3.0)
    return root


def _stage_semantic_sidecar_into(folder: Path) -> None:
    """Copy the synthetic US2 sidecar + its preprocess_output.json into
    ``folder``, rewriting ``document_id`` to match the folder basename.
    """
    sidecar = json.loads(
        (_SEMANTIC_FIXTURE / "semantic_table_truth.json").read_text(encoding="utf-8")
    )
    sidecar["document_id"] = folder.name
    (folder / "semantic_table_truth.json").write_text(
        json.dumps(sidecar, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copy(_SEMANTIC_FIXTURE / "preprocess_output.json", folder)


def _goldens_present() -> bool:
    """True iff the goldens directory has at least the run summary +
    one per-document evaluation_document.json. README-only ⇒ False."""
    if not _GOLDENS_ROOT.is_dir():
        return False
    if not (_GOLDENS_ROOT / "evaluation_run_summary.json").is_file():
        return False
    return any(_GOLDENS_ROOT.glob("*/evaluation_document.json"))


# ---------------------------------------------------------------------------
# AS1 — 20-document vendor-identity baseline byte-identical (SC-006 / MI-22)
# ---------------------------------------------------------------------------


def test_as1_per_document_vendor_identity_byte_identical(tmp_path: Path) -> None:
    """AS1 per-document: every per-document ``evaluation_document.json``
    in the post-feature (v1.3.0) run, after **stripping the additive
    v1.3.0 semantic fields**, equals its v1.2.0 golden counterpart
    exactly. This is the MI-22 byte-identity gate at the per-document
    level — the post-feature writer must produce identical
    vendor-identity output to the pre-feature writer for every legacy
    document.

    Note (Codex P2 + Copilot review on PR #49 2026-05-24): the test
    runs at the v1.3.0 default and then projects the output onto the
    v1.2.0 schema by stripping the additive ``semantic_table_quality``
    object and ``semantic_table_quality_passed`` field. The MEANINGFUL
    invariant is "v1.3.0 output minus semantic fields == v1.2.0 output"
    — not literal byte-identity of two v1.2.0 runs. Running both sides
    at v1.2.0 would only verify writer determinism, not feature-022
    non-regression.
    """
    if not _goldens_present():
        pytest.skip(
            f"goldens at {_GOLDENS_ROOT} not populated — "
            f"run the regeneration script in README.md to capture them"
        )

    root = _run_post_feature_corpus(tmp_path)

    # Walk every folder that has a golden and compare.
    golden_folders = sorted(p for p in _GOLDENS_ROOT.iterdir() if p.is_dir())
    assert golden_folders, "expected at least one golden per-doc folder"

    for golden_folder in golden_folders:
        candidate_path = root / golden_folder.name / "evaluation_document.json"
        golden_path = golden_folder / "evaluation_document.json"
        assert candidate_path.is_file(), (
            f"missing post-feature artifact at {candidate_path} for golden "
            f"{golden_path.name}"
        )

        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        golden = json.loads(golden_path.read_text(encoding="utf-8"))

        # Strip the additive v1.3.0 fields so we compare only the
        # vendor-identity portion that MI-22 pins.
        candidate_stripped = _strip_semantic_fields_from_eval_doc(candidate)
        assert candidate_stripped == golden, (
            f"vendor-identity portion of {candidate_path.relative_to(root)} "
            f"diverged from golden — MI-22 / SC-006 violation"
        )


def test_as1_run_summary_vendor_identity_byte_identical(tmp_path: Path) -> None:
    """AS1 run summary: the post-feature ``evaluation_run_summary.json``,
    after stripping the additive v1.3.0 semantic top-level keys, equals
    the golden run summary exactly. This is the MI-22 byte-identity
    gate at the corpus-summary level (SC-006).

    Implicitly covers the four feature-020 ``evidence_gate_*`` fields
    when they are present (the fixture corpus_20 does not currently
    emit them, but the comparison would catch any change to those
    fields in a real-pipeline-fed corpus).
    """
    if not _goldens_present():
        pytest.skip(
            f"goldens at {_GOLDENS_ROOT} not populated — "
            f"run the regeneration script in README.md to capture them"
        )

    root = _run_post_feature_corpus(tmp_path)
    summary = json.loads(
        (root / "evaluation_run_summary.json").read_text(encoding="utf-8")
    )
    golden = json.loads(
        (_GOLDENS_ROOT / "evaluation_run_summary.json").read_text(encoding="utf-8")
    )

    candidate = _strip_semantic_fields_from_run_summary(summary)
    golden_stripped = _strip_run_id_from_golden(golden)
    assert candidate == golden_stripped, (
        "vendor-identity portion of run summary diverged from golden — "
        "MI-22 / SC-006 violation"
    )


def test_as1_vendor_identity_passed_values_byte_identical(tmp_path: Path) -> None:
    """AS1 narrow check: ``document_pass_fail.vendor_identity_passed`` is
    byte-identical for every document in the post-feature run vs golden.
    This is the highest-signal MI-22 / FR-024 check — if the value-domain
    of the vendor-identity verdict drifts at all, this test fails before
    the broader byte-identity tests do."""
    if not _goldens_present():
        pytest.skip(f"goldens at {_GOLDENS_ROOT} not populated")

    root = _run_post_feature_corpus(tmp_path)
    golden_folders = sorted(p for p in _GOLDENS_ROOT.iterdir() if p.is_dir())

    drifts: list[str] = []
    for golden_folder in golden_folders:
        candidate = json.loads(
            (root / golden_folder.name / "evaluation_document.json").read_text(
                encoding="utf-8"
            )
        )
        golden = json.loads(
            (golden_folder / "evaluation_document.json").read_text(encoding="utf-8")
        )
        cand_vp = candidate["document_pass_fail"]["vendor_identity_passed"]
        gold_vp = golden["document_pass_fail"]["vendor_identity_passed"]
        if cand_vp != gold_vp:
            drifts.append(
                f"{golden_folder.name}: golden={gold_vp!r} post-feature={cand_vp!r}"
            )

    assert not drifts, (
        "vendor_identity_passed value drifted post-feature — FR-024 / MI-22 "
        "violation:\n  " + "\n  ".join(drifts)
    )


# ---------------------------------------------------------------------------
# AS2 — sufficient vendor + failing semantic → both verdicts independent
# ---------------------------------------------------------------------------


def _stage_inv_001_hard_and_evaluate(tmp_path: Path) -> tuple[Path, dict, dict]:
    """Set up an ``inv_001_hard`` folder from the ``all_match`` fixture,
    stage the US2 semantic sidecar into it, run the evaluator, and return
    ``(folder, evaluation_document, document_pass_fail)``.

    Extracted per Sonar duplication finding on PR #49 (2026-05-24): the
    AS2 and AS4 tests had identical 13-line setup blocks that pushed
    duplicated-lines density above the 3% threshold.
    """
    folder = tmp_path / "inv_001_hard"
    shutil.copytree(_EVALUATOR_FIXTURES / "all_match", folder)
    for fname in ("expected.json", "final_structured_payload.json"):
        p = folder / fname
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["document_id"] = "inv_001_hard"
        p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    _stage_semantic_sidecar_into(folder)

    evaluate_document(folder)
    eval_doc = json.loads(
        (folder / "evaluation_document.json").read_text(encoding="utf-8")
    )
    return folder, eval_doc, eval_doc["document_pass_fail"]


def test_as2_passing_vendor_failing_semantic_are_independent(tmp_path: Path) -> None:
    """AS2: When a document has sufficient vendor-identity evidence AND
    a failing semantic verdict, the evaluator MUST report both verdicts
    independently — vendor-identity passes, semantic fails. The two
    booleans live as siblings on ``document_pass_fail`` (FR-025)."""
    _folder, eval_doc, pf = _stage_inv_001_hard_and_evaluate(tmp_path)
    # Vendor-identity portion: "all_match" fixture is a pass.
    assert pf["vendor_identity_passed"] is True
    # The synthetic US2 fixture is designed to fail the gate.
    assert pf["semantic_table_quality_passed"] is False
    # Status string mirrors the verdict.
    assert eval_doc["semantic_table_quality"]["status"] == "failed"


# ---------------------------------------------------------------------------
# AS3 — feature-020 sufficient decision unchanged when semantic gate runs
# ---------------------------------------------------------------------------


def test_as3_vendor_identity_summary_unchanged_with_semantic_sidecar(
    tmp_path: Path,
) -> None:
    """AS3: Running the evaluator over a corpus WITH a semantic sidecar
    in one folder produces a run summary whose vendor-identity / feature-020
    portion equals the run summary without a sidecar. Adding the semantic
    gate is purely additive — it must NOT alter the vendor-identity
    portion (FR-022 / MI-22).

    Cross-references the existing US3 AS4 (T047) test; we re-assert here
    because it is part of the AS3 release-gate contract.
    """
    root_no_sidecar = tmp_path / "no_sidecar"
    root_with_sidecar = tmp_path / "with_sidecar"
    shutil.copytree(_EVALUATOR_FIXTURES / "corpus_20", root_no_sidecar)
    shutil.copytree(_EVALUATOR_FIXTURES / "corpus_20", root_with_sidecar)

    folders = sorted(p for p in root_with_sidecar.iterdir() if p.is_dir())
    _stage_semantic_sidecar_into(folders[0])

    evaluate_corpus(root_no_sidecar)
    evaluate_corpus(root_with_sidecar)

    summary_no = json.loads(
        (root_no_sidecar / "evaluation_run_summary.json").read_text(encoding="utf-8")
    )
    summary_with = json.loads(
        (root_with_sidecar / "evaluation_run_summary.json").read_text(encoding="utf-8")
    )

    vendor_keys = (
        "overall_metrics",
        "consensus_metrics",
        "by_difficulty",
        "by_field",
        "documents",
        "document_count",
    )
    for key in vendor_keys:
        assert summary_no[key] == summary_with[key], (
            f"vendor-identity key '{key}' on run_summary changed when "
            f"semantic sidecar was added — FR-022 / MI-22 violation"
        )


# ---------------------------------------------------------------------------
# AS4 — failed semantic + passing vendor → semantic_table_quality_passed: false
# ---------------------------------------------------------------------------


def test_as4_failed_semantic_with_passing_vendor_marks_passed_false(
    tmp_path: Path,
) -> None:
    """AS4 (FR-025): When semantic gate fails AND vendor identity passes,
    ``document_pass_fail.semantic_table_quality_passed`` is exactly
    ``False`` (boolean), NOT ``None``."""
    _folder, _eval_doc, pf = _stage_inv_001_hard_and_evaluate(tmp_path)
    # The semantic_table_quality_passed field is present, type bool, value False.
    assert "semantic_table_quality_passed" in pf
    assert pf["semantic_table_quality_passed"] is False
    assert isinstance(pf["semantic_table_quality_passed"], bool)
    # Vendor identity still passes (independence).
    assert pf["vendor_identity_passed"] is True


# ---------------------------------------------------------------------------
# AS5 — no-sidecar folder → semantic_table_quality_passed: null
# ---------------------------------------------------------------------------


def test_as5_no_sidecar_yields_semantic_passed_null(tmp_path: Path) -> None:
    """AS5 (FR-025 / SC-005): A folder with NO ``semantic_table_truth.json``
    reports ``semantic_table_quality_passed: null`` and the
    ``semantic_table_quality`` object is OMITTED entirely. The evaluator
    must never infer a semantic pass from vendor-identity metrics."""
    folder = tmp_path / "inv_no_sidecar"
    shutil.copytree(_EVALUATOR_FIXTURES / "all_match", folder)

    evaluate_document(folder)
    eval_doc = json.loads(
        (folder / "evaluation_document.json").read_text(encoding="utf-8")
    )

    pf = eval_doc["document_pass_fail"]
    # Field present with value JSON null (Python None).
    assert "semantic_table_quality_passed" in pf
    assert pf["semantic_table_quality_passed"] is None
    # semantic_table_quality object absent — never inferred from vendor.
    assert "semantic_table_quality" not in eval_doc
    # Vendor-identity verdict still emitted normally.
    assert isinstance(pf["vendor_identity_passed"], bool)


def test_as5_no_sidecar_run_summary_semantic_status_not_applicable(
    tmp_path: Path,
) -> None:
    """AS5 corpus-level: a corpus with NO sidecars anywhere produces a
    run summary whose every per-document entry in
    ``semantic_document_statuses`` is ``not_applicable`` with
    ``semantic_table_quality_passed: null``.

    Note on metric counts: the ``corpus_20`` fixture's folder basenames
    (``inv_corpus_easy_01`` …) do NOT match the canonical
    ``^inv_\\d{3}_(easy|medium|hard)$`` pattern, so per Q39 / MI-20 they
    are treated as CALIBRATION folders — included in the per-document
    ``semantic_document_statuses`` array but EXCLUDED from
    ``semantic_table_quality_metrics`` aggregate counters. This is
    correct release-gate behavior (calibration material does not
    pollute scored aggregation); the AS5 assertion focuses on the
    per-document entries which is where the SC-005 "never infer a
    semantic pass from vendor-identity" promise is verified.
    """
    root = tmp_path / "corpus"
    shutil.copytree(_EVALUATOR_FIXTURES / "corpus_20", root)
    evaluate_corpus(root)

    summary = json.loads(
        (root / "evaluation_run_summary.json").read_text(encoding="utf-8")
    )
    statuses = summary["semantic_document_statuses"]
    assert statuses, "corpus_20 should produce at least one status entry"
    assert all(
        entry["semantic_table_quality_status"] == "not_applicable"
        for entry in statuses
    )
    assert all(
        entry["semantic_table_quality_passed"] is None for entry in statuses
    )

    # Aggregate counters reflect SCORED folders only (Q39 / MI-20).
    # corpus_20 folder names are all non-canonical → counters are 0.
    metrics = summary["semantic_table_quality_metrics"]
    assert metrics["semantic_applicable_document_count"] == 0
    assert metrics["semantic_evaluable_document_count"] == 0
    assert metrics["semantic_passed_document_count"] == 0
    assert metrics["semantic_failed_document_count"] == 0
    assert metrics["semantic_unevaluable_document_count"] == 0
    # pass_rate is null when evaluable=0 (FR-018).
    assert metrics["semantic_table_quality_pass_rate"] is None


# ---------------------------------------------------------------------------
# AS6 — features 019/021 untouched (deeper checks in T056)
# ---------------------------------------------------------------------------


def test_as6_feature_019_021_public_surfaces_importable() -> None:
    """AS6: feature 019 (OCR-only fallback) and feature 021 (GPU MVP
    promotion) public surfaces import cleanly post-feature-022.

    This is a smoke check; T056 (test_features_019_021_unchanged.py) is
    the deeper static-history check. The feature-019 OCR-only module
    transitively imports ``PIL``/``numpy``; we ``importorskip`` those so
    a CPU-only test environment without Pillow does not register a
    false regression. The feature-020 ``evidence_gate`` module is pure
    Python and always available.
    """
    import importlib

    # Feature 020 — vendor-identity evidence gate (always importable;
    # no third-party deps).
    evidence_gate = importlib.import_module("dartwing_ocr.preprocessing.evidence_gate")
    assert hasattr(evidence_gate, "Y_THRESHOLD_FRACTION")
    # The Y threshold is documented at 0.25 (R-022.4 / MI-7); feature 022
    # reuses this exact value. Floats compared via pytest.approx
    # (Sonar python:S1244).
    assert evidence_gate.Y_THRESHOLD_FRACTION == pytest.approx(0.25)

    # Feature 019 — OCR-only fast lane lives in preprocessing. Needs
    # PIL + numpy at import time. If PIL is absent (CPU-only test env)
    # skip the deeper check here; T056 covers the git-history regression
    # check independently.
    pytest.importorskip("PIL")
    pytest.importorskip("numpy")
    ocr_only = importlib.import_module("dartwing_ocr.preprocessing.ocr_only")
    assert ocr_only.__file__ is not None

    # Feature 021 — GPU MVP promotion lives in pipeline (runner
    # orchestrates the GPU lane). Import-able without PIL/Paddle because
    # the runner defers those imports to call-time.
    runner = importlib.import_module("dartwing_ocr.pipeline.runner")
    assert runner.__file__ is not None
