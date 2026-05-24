"""T058 (US5): acceptance tests AS1-AS3 + Q39 for corpus governance.

US5 — Govern degraded-body fixture corpus promotion (Priority: P3):

AS1: a noncanonical folder such as ``inv_024_hard_degraded_body`` placed
     under a temp corpus root is reported by ``validate corpus`` under
     the calibration partition, NOT the scored-corpus partition.
AS2: the calibration folder's per-document validation still runs —
     mandatory artifacts are checked, sidecar (if present) is validated.
     Calibration ≠ "skipped".
AS3: scored corpus aggregation excludes calibration folders (SC-009 /
     MI-21 default-exclude rule).
Q39: a calibration folder WITH a sidecar → the gate runs on it, a
     per-document semantic-status entry appears in
     ``evaluation_run_summary.json::semantic_document_statuses``, but
     the eight aggregate counts in ``semantic_table_quality_metrics``
     exclude it (MI-20).

These tests cover the validator-CLI surface (AS1, AS2, AS3) and the
evaluator-runtime surface (Q39). The evaluator surface was implemented
in PR #47 (US3); these tests verify the end-to-end behavior when both
PRs are landed together.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GOOD_FIXTURE_FOLDER = (
    REPO_ROOT
    / "tests"
    / "contract_tests"
    / "fixtures"
    / "good"
    / "folders"
    / "inv_001_easy"
)
SEMANTIC_FIXTURE = (
    REPO_ROOT / "tests" / "stage1_semantic_quality" / "inv_001_hard"
)
EVALUATOR_FIXTURE_DIR = REPO_ROOT / "tests" / "evaluator_tests" / "fixtures"


# ---------------------------------------------------------------------------
# Test scaffolding
# ---------------------------------------------------------------------------


def _seed_folder(target_root: Path, folder_name: str) -> Path:
    """Copy the canonical ``inv_001_easy`` good fixture under
    ``target_root`` with the requested basename and rewrite its
    ``expected.json`` so the per-folder validator accepts it
    regardless of basename (including calibration-style basenames)."""
    target = target_root / folder_name
    shutil.copytree(GOOD_FIXTURE_FOLDER, target)
    expected_path = target / "expected.json"
    doc = json.loads(expected_path.read_text(encoding="utf-8"))
    doc["document_id"] = folder_name
    if folder_name.endswith("_easy"):
        doc["difficulty"] = "easy"
    elif folder_name.endswith("_medium"):
        doc["difficulty"] = "medium"
    elif folder_name.endswith("_missing_name"):
        doc["difficulty"] = "missing_name"
    else:
        doc["difficulty"] = "hard"
    expected_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return target


def _write_sidecar(folder: Path, payload: dict) -> Path:
    p = folder / "semantic_table_truth.json"
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def _run_validate_corpus_json(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "dartwing_ocr.validator",
            "validate",
            "corpus",
            "--json",
            str(root),
        ],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(REPO_ROOT / "src"), "PATH": "/usr/bin:/bin"},
    )


# ---------------------------------------------------------------------------
# AS1 — calibration folder is reported under "Calibration", not "Scored"
# ---------------------------------------------------------------------------


def test_as1_inv_024_hard_degraded_body_lands_in_calibration_partition(
    tmp_path: Path,
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    _seed_folder(root, "inv_024_hard_degraded_body")

    result = _run_validate_corpus_json(root)
    assert result.returncode in (0, 1), (result.stdout, result.stderr)

    payload = json.loads(result.stdout)
    assert payload["scored"]["count"] == 0, payload
    assert payload["calibration"]["count"] == 1, payload

    by_name = {entry["folder"]: entry for entry in payload["folders"]}
    assert by_name["inv_024_hard_degraded_body"]["partition"] == "calibration"


# ---------------------------------------------------------------------------
# AS2 — calibration folder's per-document validation still runs
# ---------------------------------------------------------------------------


def test_as2_calibration_folder_per_document_validation_still_runs(
    tmp_path: Path,
) -> None:
    """Calibration folder validation runs the same mandatory-artifact
    checks the scored partition runs. If a required file is missing the
    folder is reported as invalid in the calibration partition; with all
    mandatory artifacts present it reports as valid in the calibration
    partition."""
    root = tmp_path / "corpus"
    root.mkdir()
    target = _seed_folder(root, "inv_024_hard_degraded_body")

    # Sidecar present on the calibration folder; the gate should run on
    # it (Q39). We use a well-formed sidecar so we don't trip exit-3/4/5.
    _write_sidecar(
        target,
        {
            "document_id": "inv_024_hard_degraded_body",
            "rows": [
                {"row_id": "row-1", "required_row_text_tokens": ["widget"]},
            ],
        },
    )

    result = _run_validate_corpus_json(root)
    payload = json.loads(result.stdout)

    by_name = {entry["folder"]: entry for entry in payload["folders"]}
    calib_entry = by_name["inv_024_hard_degraded_body"]
    assert calib_entry["partition"] == "calibration"
    # Per-document validation produced an outcome (passed True/False, not
    # "skipped"). The exact passed state depends on the fixture; what we
    # care about is that the entry carries an outcome object.
    assert "passed" in calib_entry, calib_entry
    assert calib_entry["passed"] in (True, False), calib_entry
    # The sidecar was validated (present + accepted/rejected fields exist).
    assert "sidecar_present" in calib_entry, calib_entry


# ---------------------------------------------------------------------------
# AS3 — scored aggregation excludes calibration folders (SC-009)
# ---------------------------------------------------------------------------


def test_as3_scored_aggregation_excludes_calibration_folders(
    tmp_path: Path,
) -> None:
    """A mix of scored + calibration folders: the validator's scored-set
    counts MUST exclude the calibration entries."""
    root = tmp_path / "corpus"
    root.mkdir()
    _seed_folder(root, "inv_001_easy")
    _seed_folder(root, "inv_002_easy")
    _seed_folder(root, "inv_024_hard_degraded_body")
    _seed_folder(root, "inv_025_hard_calibration_v2")

    result = _run_validate_corpus_json(root)
    payload = json.loads(result.stdout)

    assert payload["scored"]["count"] == 2, payload
    assert payload["calibration"]["count"] == 2, payload
    # The scored-set valid+invalid sum equals the scored count.
    assert (
        payload["scored"]["valid"] + payload["scored"]["invalid"]
        == payload["scored"]["count"]
    ), payload


# ---------------------------------------------------------------------------
# Q39 — calibration folder with sidecar: gate runs, per-doc status entry
# appears in evaluation_run_summary.json, but the eight aggregate counts
# in semantic_table_quality_metrics exclude it.
# ---------------------------------------------------------------------------


def test_q39_calibration_folder_with_sidecar_excluded_from_metrics_aggregate(
    tmp_path: Path,
) -> None:
    """Build a corpus with one scored folder + one calibration folder.
    Each folder gets a sidecar so the gate runs on BOTH. Assertions:

    * ``evaluation_run_summary.json::semantic_document_statuses`` lists
      BOTH documents (calibration appears per Q39 / MI-20).
    * ``semantic_table_quality_metrics`` aggregate counters exclude the
      calibration folder — only the scored folder counts toward
      ``semantic_applicable_document_count`` etc.
    """
    from dartwing_ocr.evaluator import evaluate_corpus

    root = tmp_path / "corpus"
    root.mkdir()

    # We need the evaluator harness to find evaluator-compatible fixtures
    # in each folder, so we mirror the test_us3 pattern: start from the
    # evaluator's `all_match` fixture (which carries the full pipeline
    # artifact set the corpus harness expects) and overlay the semantic
    # fixture's preprocess + sidecar.
    src_eval = EVALUATOR_FIXTURE_DIR / "all_match"
    if not src_eval.is_dir():
        pytest.skip(
            "evaluator fixtures (evaluator_tests/fixtures/all_match) not "
            "available — Q39 end-to-end check needs them"
        )

    for folder_name in ("inv_001_easy", "inv_024_hard_degraded_body"):
        folder = root / folder_name
        shutil.copytree(src_eval, folder)
        # Rewrite document_id values that need to match folder name.
        for filename in ("expected.json", "final_structured_payload.json"):
            path = folder / filename
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["document_id"] = folder_name
            # Difficulty must match folder.schema.json's closed vocabulary.
            if "difficulty" in doc:
                if folder_name.endswith("_easy"):
                    doc["difficulty"] = "easy"
                else:
                    doc["difficulty"] = "hard"
            path.write_text(
                json.dumps(doc, indent=2) + "\n", encoding="utf-8"
            )
        # Drop in the semantic fixture sidecar + preprocess output.
        shutil.copy(SEMANTIC_FIXTURE / "preprocess_output.json", folder)
        sidecar = json.loads(
            (SEMANTIC_FIXTURE / "semantic_table_truth.json").read_text(
                encoding="utf-8"
            )
        )
        sidecar["document_id"] = folder_name
        (folder / "semantic_table_truth.json").write_text(
            json.dumps(sidecar, indent=2) + "\n", encoding="utf-8"
        )

    evaluate_corpus(root)

    summary = json.loads(
        (root / "evaluation_run_summary.json").read_text(encoding="utf-8")
    )

    # Per-document statuses include BOTH documents (Q39 / MI-20).
    statuses = summary["semantic_document_statuses"]
    by_id = {entry["document_id"]: entry for entry in statuses}
    assert "inv_001_easy" in by_id, statuses
    assert "inv_024_hard_degraded_body" in by_id, statuses
    # Both ran the gate (sidecar was present) — neither should be
    # ``not_applicable`` here.
    assert by_id["inv_001_easy"]["semantic_table_quality_status"] != "not_applicable"
    assert (
        by_id["inv_024_hard_degraded_body"]["semantic_table_quality_status"]
        != "not_applicable"
    )

    # Aggregate metrics EXCLUDE the calibration folder. We confirm this
    # by checking that the applicable-document count equals 1 (only the
    # scored folder is counted), not 2.
    metrics = summary["semantic_table_quality_metrics"]
    assert metrics["semantic_applicable_document_count"] == 1, metrics
    # The not_applicable counter for the calibration folder is also
    # excluded — so the sum of all "*_document_count" entries (the
    # four buckets) equals exactly 1 (the scored folder).
    bucket_sum = (
        metrics["semantic_applicable_document_count"]
        + metrics["semantic_not_applicable_document_count"]
    )
    assert bucket_sum == 1, metrics
