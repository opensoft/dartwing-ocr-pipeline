"""T059 (US5): unit tests for the `validate corpus` reporting block.

Verifies that the extended ``validate corpus`` subcommand:

1. Partitions every subfolder of the supplied corpus root into a SCORED
   set (basename matches ``CANONICAL_FOLDER_PATTERN`` per Q23 / MI-21)
   and a CALIBRATION set (every other name, including the named
   ``inv_024_hard_degraded_body`` example from spec.md US5 / SC-009).
2. Emits the reporting block specified in
   ``specs/022-ocr-semantic-quality-gate/contracts/validator-cli-contract.md``
   §`validate corpus`: scored count + valid/invalid sub-lines,
   calibration count + valid/invalid sub-lines, then sidecar
   present / accepted / rejected counters (sidecars present only in the
   SCORED set are counted toward the displayed "Sidecars present" line,
   per the contract block annotation).
3. Returns the exit code per the "lowest non-zero of all encountered
   failures" rule (codes 0 / 1 / 3 / 4 / 5 / 6).
4. Supports BOTH ``--text`` (default) and ``--json`` output modes.

These tests exercise the CLI subprocess so we cover the dispatch wiring
end-to-end (argparse → corpus reporter → exit code).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GOOD_FIXTURE_FOLDER = (
    REPO_ROOT
    / "tests"
    / "contract_tests"
    / "fixtures"
    / "good"
    / "folders"
    / "inv_001_easy"
)


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------


def _run_validate_corpus(
    root: Path, *, json_output: bool = False
) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -m dartwing_ocr.validator validate corpus <root>``.

    Uses the same minimal-env subprocess pattern as the US1 integration
    tests so the test never inherits a polluted PYTHONPATH.
    """
    argv = [
        sys.executable,
        "-m",
        "dartwing_ocr.validator",
        "validate",
        "corpus",
        str(root),
    ]
    if json_output:
        argv.append("--json")
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(REPO_ROOT / "src"), "PATH": "/usr/bin:/bin"},
    )


# Per Sonar PR #50 fix-pass 2026-05-24: _seed_folder + _write_sidecar
# previously duplicated across two test files. Shared in
# tests/helpers/corpus_fixtures.py; re-exported here so the test bodies
# below stay readable.
from helpers.corpus_fixtures import seed_corpus_folder as _seed_folder  # noqa: E402
from helpers.corpus_fixtures import write_sidecar as _write_sidecar  # noqa: E402


def _good_sidecar(document_id: str) -> dict:
    return {
        "document_id": document_id,
        "rows": [
            {"row_id": "row-1", "required_row_text_tokens": ["widget"]},
        ],
    }


def _build_synthetic_corpus(
    tmp_path: Path,
    *,
    scored_folders: tuple[str, ...] = ("inv_001_easy", "inv_002_easy"),
    calibration_folders: tuple[str, ...] = ("inv_024_hard_degraded_body",),
) -> Path:
    """Build a corpus root with the requested mix of scored and
    calibration folders. Returns the corpus root path."""
    root = tmp_path / "corpus"
    root.mkdir()
    for name in scored_folders:
        _seed_folder(root, name)
    for name in calibration_folders:
        _seed_folder(root, name)
    return root


# ---------------------------------------------------------------------------
# Reporting-block content (text output)
# ---------------------------------------------------------------------------


def test_text_output_partitions_scored_vs_calibration(tmp_path: Path) -> None:
    """For 2 scored + 1 calibration folder, the text report MUST list both
    partitions with the contract-pinned labels."""
    root = _build_synthetic_corpus(tmp_path)

    result = _run_validate_corpus(root)

    out = result.stdout
    assert "Scored corpus folders:" in out, result.stdout + result.stderr
    assert "Calibration folders:" in out, result.stdout + result.stderr
    # Counts: 2 scored on the Scored line (count appears on the same
    # line as the label; alignment-tolerant check via splitlines() to
    # avoid coupling to whitespace width).
    scored_line = next(
        line for line in out.splitlines() if "Scored corpus folders:" in line
    )
    assert "2" in scored_line, scored_line
    # Pattern annotation per the contract block sample
    assert "^inv_\\d{3}_(easy|medium|hard)$" in out


def test_text_output_includes_sidecar_counters(tmp_path: Path) -> None:
    """Sidecar counters (present / accepted / rejected) MUST appear in the
    text report."""
    root = _build_synthetic_corpus(tmp_path)
    # Add a sidecar to ONE scored folder so present == 1.
    _write_sidecar(root / "inv_001_easy", _good_sidecar("inv_001_easy"))

    result = _run_validate_corpus(root)

    out = result.stdout
    assert "Sidecars present:" in out, result.stdout + result.stderr
    assert "Sidecars accepted:" in out, result.stdout + result.stderr
    assert "Sidecars rejected:" in out, result.stdout + result.stderr


def test_text_output_calibration_count_equals_one(tmp_path: Path) -> None:
    """The named ``inv_024_hard_degraded_body`` calibration folder MUST be
    reported in the calibration partition with count 1."""
    root = _build_synthetic_corpus(tmp_path)

    result = _run_validate_corpus(root)

    out = result.stdout
    # The exact count column may vary in alignment; check the number
    # appears AND that the calibration partition is named.
    assert "Calibration folders:" in out
    # Count appears on the same line as "Calibration folders:"
    calib_line = next(
        line for line in out.splitlines() if "Calibration folders:" in line
    )
    assert "1" in calib_line, calib_line


# ---------------------------------------------------------------------------
# Reporting-block content (JSON output)
# ---------------------------------------------------------------------------


def test_json_output_emits_partition_payload(tmp_path: Path) -> None:
    """The JSON output MUST be a structured payload that lists scored and
    calibration counts, sidecar counters, and the per-folder breakdown."""
    root = _build_synthetic_corpus(tmp_path)
    _write_sidecar(root / "inv_001_easy", _good_sidecar("inv_001_easy"))

    result = _run_validate_corpus(root, json_output=True)
    assert result.returncode in (0, 1, 3, 4, 5), result.stderr

    payload = json.loads(result.stdout)
    assert "scored" in payload, payload
    assert "calibration" in payload, payload
    assert "sidecars" in payload, payload
    assert payload["scored"]["count"] == 2, payload
    assert payload["calibration"]["count"] == 1, payload
    assert payload["sidecars"]["present"] == 1, payload
    # Pattern is exposed so external automation can verify the source-of-truth allowlist.
    assert payload["scored"]["pattern"] == "^inv_\\d{3}_(easy|medium|hard)$", payload


def test_json_output_lists_each_folder_with_partition_tag(tmp_path: Path) -> None:
    """The JSON output MUST enumerate each folder with its partition tag,
    so calibration vs scored is explicit per folder."""
    root = _build_synthetic_corpus(tmp_path)

    result = _run_validate_corpus(root, json_output=True)
    payload = json.loads(result.stdout)

    folders = payload.get("folders", [])
    by_name = {entry["folder"]: entry for entry in folders}
    assert by_name["inv_001_easy"]["partition"] == "scored"
    assert by_name["inv_002_easy"]["partition"] == "scored"
    assert by_name["inv_024_hard_degraded_body"]["partition"] == "calibration"


# ---------------------------------------------------------------------------
# Exit-code lowest-non-zero rule
# ---------------------------------------------------------------------------


def test_exit_code_zero_when_all_folders_valid(tmp_path: Path) -> None:
    """Pass case: all folders valid → exit 0."""
    root = _build_synthetic_corpus(tmp_path)

    result = _run_validate_corpus(root)
    assert result.returncode == 0, (result.stdout, result.stderr)


def test_exit_code_six_when_corpus_root_missing(tmp_path: Path) -> None:
    """Corpus root does not exist → exit 6 per contract."""
    missing = tmp_path / "does_not_exist"

    result = _run_validate_corpus(missing)
    assert result.returncode == 6, (result.stdout, result.stderr)


def test_json_output_when_corpus_root_missing_is_valid_payload(
    tmp_path: Path,
) -> None:
    """Per Sourcery review on PR #50 (2026-05-24): the ``--json`` mode for
    a missing corpus root MUST still emit a parseable JSON object that
    declares ``root_missing: true`` and the requested root path — so
    automation can distinguish "root not found" from "root present but
    failed validation" without parsing stderr."""
    missing = tmp_path / "does_not_exist"

    result = _run_validate_corpus(missing, json_output=True)
    assert result.returncode == 6, (result.stdout, result.stderr)

    payload = json.loads(result.stdout)
    assert payload["root_missing"] is True, payload
    assert payload["corpus_root"] == str(missing), payload
    # The partition + sidecar payload sections MUST be absent — there is
    # nothing to report when the root doesn't exist.
    assert "scored" not in payload, payload
    assert "calibration" not in payload, payload
    assert "sidecars" not in payload, payload
    assert "folders" not in payload, payload


def test_exit_code_three_when_sidecar_document_id_mismatch(tmp_path: Path) -> None:
    """A scored folder with a sidecar whose ``document_id`` mismatches its
    folder basename produces exit code 3 per the contract table."""
    root = _build_synthetic_corpus(tmp_path)
    # Declared != folder basename ⇒ document_id mismatch (exit 3).
    _write_sidecar(root / "inv_001_easy", _good_sidecar("inv_999_hard"))

    result = _run_validate_corpus(root)
    assert result.returncode == 3, (result.stdout, result.stderr)


def test_exit_code_lowest_non_zero_when_both_3_and_4_present(
    tmp_path: Path,
) -> None:
    """When BOTH a document_id-mismatch (code 3) AND a row-violation
    (code 4) are encountered, the CLI MUST return the LOWEST non-zero
    code per validator-cli-contract.md §`validate corpus` (3 wins)."""
    root = _build_synthetic_corpus(tmp_path)
    # inv_001_easy → exit-3 candidate (document_id mismatch).
    _write_sidecar(root / "inv_001_easy", _good_sidecar("inv_999_hard"))
    # inv_002_easy → exit-4 candidate (duplicate row_id).
    _write_sidecar(
        root / "inv_002_easy",
        {
            "document_id": "inv_002_easy",
            "rows": [
                {"row_id": "row-1", "required_row_text_tokens": ["a"]},
                {"row_id": "row-1", "required_row_text_tokens": ["b"]},
            ],
        },
    )

    result = _run_validate_corpus(root)
    assert result.returncode == 3, (result.stdout, result.stderr)


# ---------------------------------------------------------------------------
# Sidecars-present count is in-scored-set only
# ---------------------------------------------------------------------------


def test_sidecars_present_count_is_scored_set_only_per_contract(
    tmp_path: Path,
) -> None:
    """Per the contract sample block ``Sidecars present:  1  (in scored
    set)`` — sidecars on calibration folders DO NOT contribute to the
    displayed ``present`` counter, even though the gate still runs on
    them (Q39 / MI-20 separates "gate runs" from "scored-aggregation
    counts"). The CLI reporter mirrors that separation."""
    root = _build_synthetic_corpus(tmp_path)
    # Sidecar on calibration ONLY.
    _write_sidecar(
        root / "inv_024_hard_degraded_body",
        _good_sidecar("inv_024_hard_degraded_body"),
    )

    result = _run_validate_corpus(root, json_output=True)
    payload = json.loads(result.stdout)

    assert payload["sidecars"]["present"] == 0, payload
