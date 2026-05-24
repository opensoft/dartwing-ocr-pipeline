"""Feature 022 (US5) — ``validate corpus`` partitioned reporting block.

The validator CLI's ``validate corpus`` subcommand needs to:

1. Walk every immediate subdirectory of the corpus root.
2. Partition each subdirectory into a SCORED set (basename fully matches
   :data:`corpus_pattern.CANONICAL_FOLDER_PATTERN`) or a CALIBRATION set
   (every other basename — default-exclude per Q23 / MI-21 / SC-009).
3. Run per-document validation (:func:`folder.validate_folder`) on BOTH
   partitions — calibration ≠ skipped. Only the scored partition
   contributes to the displayed scored-aggregation counts.
4. Track sidecar present / accepted / rejected counters scoped to the
   scored set only (per the contract block annotation ``(in scored set)``).
5. Emit a reporting block per
   ``specs/022-ocr-semantic-quality-gate/contracts/validator-cli-contract.md``
   §`validate corpus` in either text or JSON form.
6. Compute an exit code per the contract's "lowest non-zero of all
   encountered failures" rule (0 / 1 / 3 / 4 / 5 / 6).

This module is the single owner of that surface. The CLI dispatcher
(:mod:`dartwing_ocr.validator.cli`) is a thin wrapper around it so
:func:`cli.main`'s cognitive complexity stays within Sonar python:S3776
thresholds and the partition logic has a focused testable home.

Pure stdlib + the existing validator stack (no Paddle, no network — MI-1).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from dartwing_ocr.validator.corpus_pattern import (
    CANONICAL_FOLDER_PATTERN,
    is_scored_corpus_folder,
)
from dartwing_ocr.validator.folder import validate_folder
from dartwing_ocr.validator.loader import ContractSet, load_contract_set
from dartwing_ocr.validator.report import (
    ValidationOutcome,
    ValidationOutcomeCounts,
    Violation,
    ViolationCode,
)
from dartwing_ocr.validator.semantic_table_truth import SIDECAR_FILENAME

# Per-violation-code → CLI exit-code mapping for the corpus reporter.
# Mirrors the table in validator-cli-contract.md §`validate corpus`.
# Lower codes win when multiple are present.
_SIDECAR_VIOLATION_TO_EXIT_CODE: Final[dict[str, int]] = {
    ViolationCode.SIDECAR_DOCUMENT_ID_MISMATCH: 3,
    ViolationCode.SIDECAR_ROW_VIOLATION: 4,
    ViolationCode.SIDECAR_SCHEMA_INVALID: 5,
    ViolationCode.SIDECAR_JSON_INVALID: 5,
}

EXIT_CODE_PASS: Final[int] = 0
EXIT_CODE_MANDATORY_ARTIFACT_FAILURE: Final[int] = 1
EXIT_CODE_CORPUS_ROOT_MISSING: Final[int] = 6


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FolderEntry:
    """One subfolder discovered under the corpus root.

    Attributes:
        folder: Absolute path to the subfolder.
        is_scored: ``True`` iff the basename matches
            :data:`corpus_pattern.CANONICAL_FOLDER_PATTERN`. False values
            land in the calibration partition.
        outcome: The :class:`ValidationOutcome` returned by
            :func:`folder.validate_folder`. Always populated — calibration
            folders are validated, not skipped.
        sidecar_present: ``True`` iff ``<folder>/semantic_table_truth.json``
            existed on disk at discovery time.
        sidecar_accepted: ``True`` iff the sidecar was present AND the
            outcome carries no sidecar-class violations.
    """

    folder: Path
    is_scored: bool
    outcome: ValidationOutcome
    sidecar_present: bool
    sidecar_accepted: bool


@dataclass(frozen=True)
class PartitionStats:
    """Counts derived from one partition's :class:`FolderEntry` list."""

    count: int
    valid: int
    invalid: int


@dataclass(frozen=True)
class SidecarStats:
    """Sidecar counters scoped to the SCORED set only (per the contract's
    ``(in scored set)`` annotation on the ``Sidecars present`` line)."""

    present: int
    accepted: int
    rejected: int


@dataclass(frozen=True)
class CorpusReport:
    """Full output of :func:`build_corpus_report`."""

    root: Path
    root_missing: bool
    contract_set_version: str
    entries: tuple[FolderEntry, ...] = field(default_factory=tuple)
    # Per Codex P1 review on PR #50 (2026-05-24): the pre-US5
    # validate_corpus() validated a root-level evaluation_run_summary.json
    # if present and appended it as a sub-report. Restore that behavior
    # here so corpus runs continue to surface schema-invalid run summaries
    # at the root level (regression guard for the pre-US5 contract).
    root_eval_run_summary: ValidationOutcome | None = None

    @property
    def scored_entries(self) -> tuple[FolderEntry, ...]:
        return tuple(e for e in self.entries if e.is_scored)

    @property
    def calibration_entries(self) -> tuple[FolderEntry, ...]:
        return tuple(e for e in self.entries if not e.is_scored)

    @property
    def scored_stats(self) -> PartitionStats:
        return _partition_stats(self.scored_entries)

    @property
    def calibration_stats(self) -> PartitionStats:
        return _partition_stats(self.calibration_entries)

    @property
    def sidecar_stats(self) -> SidecarStats:
        # Scoped to the scored set per the contract block annotation.
        present = sum(1 for e in self.scored_entries if e.sidecar_present)
        accepted = sum(
            1 for e in self.scored_entries if e.sidecar_present and e.sidecar_accepted
        )
        rejected = present - accepted
        return SidecarStats(present=present, accepted=accepted, rejected=rejected)


def _partition_stats(entries: tuple[FolderEntry, ...]) -> PartitionStats:
    count = len(entries)
    valid = sum(1 for e in entries if e.outcome.passed)
    invalid = count - valid
    return PartitionStats(count=count, valid=valid, invalid=invalid)


# ---------------------------------------------------------------------------
# Build (walk corpus + validate)
# ---------------------------------------------------------------------------


def _walk_violation_codes(outcome: ValidationOutcome):
    """Yield every violation code in ``outcome`` and its sub-reports."""
    for v in outcome.violations:
        yield v.violation_code
    for sub in outcome.sub_reports:
        yield from _walk_violation_codes(sub)


def compute_outcome_exit_code(outcome: ValidationOutcome) -> int:
    """Return the exit code for a single :class:`ValidationOutcome`.

    Implements the same "lowest non-zero of {1, 3, 4, 5}" rule used by
    :func:`compute_exit_code` for corpus reports, applied to one folder
    outcome. ``0`` when ``outcome.passed`` is True, otherwise the lowest
    sidecar-class code (3 / 4 / 5) present in any nested violation, or
    ``1`` when no sidecar codes are present.

    Per Codex P1 review on PR #50 (2026-05-24): unifies the previously
    duplicated ``cli._folder_or_corpus_exit_code`` logic so the
    sidecar-violation-to-exit-code mapping has exactly one owner. The
    ``validate folder`` CLI dispatcher and the ``validate corpus``
    per-entry walker both reduce to this primitive.
    """
    if outcome.passed:
        return EXIT_CODE_PASS
    sidecar_codes: set[int] = set()
    for code in _walk_violation_codes(outcome):
        mapped = _SIDECAR_VIOLATION_TO_EXIT_CODE.get(code)
        if mapped is not None:
            sidecar_codes.add(mapped)
    if sidecar_codes:
        return min(sidecar_codes)
    return EXIT_CODE_MANDATORY_ARTIFACT_FAILURE


def _sidecar_was_rejected(outcome: ValidationOutcome) -> bool:
    """True iff the folder's outcome carries any sidecar-class violation."""
    for code in _walk_violation_codes(outcome):
        if code in _SIDECAR_VIOLATION_TO_EXIT_CODE:
            return True
    return False


def _is_folder_basename_pattern_violation(violation: Violation) -> bool:
    """True iff the violation is specifically about the folder basename
    failing the canonical folder-name pattern.

    Per Codex P1 + Sourcery review on PR #50 (2026-05-24):
    ``FOLDER_NAME_INVALID`` is OVERLOADED across three distinct conditions
    in ``folder.py``:

    1. Folder basename doesn't match the canonical pattern (``field_path
       is None`` — emitted at the folder level)
    2. ``expected.json`` ``document_id`` doesn't match folder basename
       (``field_path == "/expected.json#/document_id"``)
    3. ``expected.json`` ``difficulty`` doesn't match folder suffix
       (``field_path == "/expected.json#/difficulty"``)

    Only case (1) is tautological for calibration folders (the basename
    is precisely what put them in the calibration partition). Cases (2)
    and (3) are LEGITIMATE expected.json consistency issues that MUST
    NOT be suppressed even on calibration folders. This helper
    distinguishes (1) from (2)/(3) by inspecting ``field_path``.
    """
    if violation.violation_code != ViolationCode.FOLDER_NAME_INVALID:
        return False
    # Cases (2) and (3) carry a non-empty field_path that targets the
    # expected.json artifact. Case (1) leaves field_path None (the
    # folder-level violation, not an artifact-field violation).
    return not violation.field_path


def _strip_folder_name_violations(outcome: ValidationOutcome) -> ValidationOutcome:
    """Return a copy of ``outcome`` with calibration-tautological
    FOLDER_NAME_INVALID violations suppressed.

    Calibration folders fall outside the canonical scored-corpus pattern
    (Q23 / MI-21 — `^inv_\\d{3}_(easy|medium|hard)$`) but may match the
    broader folder.schema.json pattern (which also allows `missing_name`
    suffixes and previously generated the violation). Reporting the
    name-pattern violation against a calibration folder is a tautology
    that obscures REAL validation issues (missing artifacts, schema-
    invalid files, sidecar errors).

    Per Codex P1 review on PR #50 (2026-05-24): the strip is narrowed
    via :func:`_is_folder_basename_pattern_violation` — only case (1)
    folder-basename violations are dropped; expected.json document_id /
    difficulty mismatches (cases 2 and 3, also coded
    ``FOLDER_NAME_INVALID``) remain because they are NOT tautological
    and they guard expected.json consistency on calibration folders.

    Per Sourcery review on PR #50: the strip is applied RECURSIVELY to
    ``sub_reports`` too, in case future sub-validators surface the same
    violation code in nested artifact outcomes.
    """
    kept_errors = [
        v for v in outcome.violations
        if not _is_folder_basename_pattern_violation(v)
    ]
    kept_warnings = list(outcome.warnings)
    # Recursive strip across sub_reports (Sourcery PR #50 2026-05-24).
    stripped_subs = [_strip_folder_name_violations(s) for s in outcome.sub_reports]
    sub_has_error = any(not s.passed for s in stripped_subs)
    sub_error_count = sum(s.counts.error for s in stripped_subs)
    sub_warning_count = sum(s.counts.warning for s in stripped_subs)
    return ValidationOutcome(
        contract_set_version_checked=outcome.contract_set_version_checked,
        target_summary=outcome.target_summary,
        passed=not kept_errors and not sub_has_error,
        violations=kept_errors,
        warnings=kept_warnings,
        counts=ValidationOutcomeCounts(
            error=len(kept_errors) + sub_error_count,
            warning=len(kept_warnings) + sub_warning_count,
        ),
        sub_reports=stripped_subs,
    )


def _build_entry(folder: Path, contract_set: ContractSet) -> FolderEntry:
    """Validate one subfolder and synthesize its :class:`FolderEntry`.

    Extracted from :func:`build_corpus_report` to keep that function's
    cognitive complexity below the Sonar python:S3776 threshold of 15.

    Calibration folders (basename not matching the canonical allowlist)
    have FOLDER_NAME_INVALID violations stripped from their outcome via
    :func:`_strip_folder_name_violations` so the contract-mandated
    mandatory-artifact validation reports cleanly without re-flagging
    the basename that put the folder in the calibration partition.
    """
    outcome = validate_folder(folder, contract_set=contract_set)
    is_scored = is_scored_corpus_folder(folder.name)
    if not is_scored:
        outcome = _strip_folder_name_violations(outcome)
    sidecar_path = folder / SIDECAR_FILENAME
    sidecar_present = sidecar_path.is_file()
    sidecar_accepted = sidecar_present and not _sidecar_was_rejected(outcome)
    return FolderEntry(
        folder=folder,
        is_scored=is_scored,
        outcome=outcome,
        sidecar_present=sidecar_present,
        sidecar_accepted=sidecar_accepted,
    )


def build_corpus_report(
    root: str | Path,
    *,
    version: str | None = None,
    contract_set: ContractSet | None = None,
) -> CorpusReport:
    """Walk ``root`` and validate every immediate subdirectory.

    Both scored and calibration partitions are validated — calibration
    is NEVER silently skipped. The returned :class:`CorpusReport` lets
    the CLI render the contract-pinned reporting block in either text
    or JSON form.

    Args:
        root: Corpus root directory.
        version: Optional contract-set version override; defaults to the
            current pinned version.
        contract_set: Pre-loaded contract set (avoids the file read on
            repeated calls during tests).

    Returns:
        A :class:`CorpusReport`. When ``root`` is not a directory the
        result carries ``root_missing=True`` and zero entries; callers
        should map that to exit code 6 per contract.
    """
    root_path = Path(root)
    if contract_set is None:
        contract_set = load_contract_set(version)
    if not root_path.is_dir():
        return CorpusReport(
            root=root_path,
            root_missing=True,
            contract_set_version=contract_set.version,
        )

    subfolders = sorted(p for p in root_path.iterdir() if p.is_dir())
    entries = tuple(_build_entry(p, contract_set) for p in subfolders)

    # Per Codex P1 review on PR #50 (2026-05-24): pre-US5 validate_corpus
    # appended a root-level evaluation_run_summary.json validation as a
    # sub-report. Restore that behavior so a schema-invalid run summary
    # at the corpus root still surfaces as a corpus-level failure.
    root_summary_path = root_path / "evaluation_run_summary.json"
    root_eval_outcome: ValidationOutcome | None = None
    if root_summary_path.is_file():
        # Defer import to runtime; validate_artifact / ArtifactName live
        # in sibling modules and the import path is heavy at module load.
        from dartwing_ocr.validator.artifact import validate_artifact
        from dartwing_ocr.validator.report import ArtifactName

        root_eval_outcome = validate_artifact(
            root_summary_path,
            ArtifactName.EVALUATION_RUN_SUMMARY,
            contract_set=contract_set,
        )

    return CorpusReport(
        root=root_path,
        root_missing=False,
        contract_set_version=contract_set.version,
        entries=entries,
        root_eval_run_summary=root_eval_outcome,
    )


# ---------------------------------------------------------------------------
# Exit-code derivation per the contract's lowest-non-zero rule
# ---------------------------------------------------------------------------


def _collect_failure_codes(
    report: CorpusReport,
) -> tuple[bool, set[int], bool]:
    """Scan ``report`` once and return three values used by
    :func:`compute_exit_code`:

    * ``has_any_failure``: True iff at least one entry's outcome failed.
    * ``sidecar_codes``: set of mapped exit codes (3 / 4 / 5) seen in any
      failing entry.
    * ``has_non_sidecar_failure``: True iff at least one failing entry
      carries a violation code NOT mapped into ``sidecar_codes``.

    Extracted from :func:`compute_exit_code` so each function stays
    well under Sonar python:S3776's cognitive-complexity threshold of 15.
    """
    sidecar_codes: set[int] = set()
    has_any_failure = False
    has_non_sidecar_failure = False
    # Per Codex P1 PR #50 (2026-05-24): a failing root-level
    # evaluation_run_summary.json validation counts as a non-sidecar
    # corpus-level failure (exit code 1) — same severity it had under
    # the pre-US5 validate_corpus.
    if report.root_eval_run_summary is not None and not report.root_eval_run_summary.passed:
        has_any_failure = True
        has_non_sidecar_failure = True
    for entry in report.entries:
        if entry.outcome.passed:
            continue
        has_any_failure = True
        for code in _walk_violation_codes(entry.outcome):
            mapped = _SIDECAR_VIOLATION_TO_EXIT_CODE.get(code)
            if mapped is None:
                has_non_sidecar_failure = True
            else:
                sidecar_codes.add(mapped)
    return has_any_failure, sidecar_codes, has_non_sidecar_failure


def compute_exit_code(report: CorpusReport) -> int:
    """Return the CLI exit code per validator-cli-contract.md §`validate corpus`.

    Rule: lowest non-zero among ``{1, 3, 4, 5, 6}`` of all encountered
    failures. ``0`` only when every validated folder passes AND the root
    existed.
    """
    if report.root_missing:
        return EXIT_CODE_CORPUS_ROOT_MISSING

    has_any_failure, sidecar_codes, has_non_sidecar_failure = (
        _collect_failure_codes(report)
    )
    if not has_any_failure:
        return EXIT_CODE_PASS

    if sidecar_codes:
        # Mandatory-artifact failures on scored folders also fold into the
        # lowest-non-zero set as code 1 per the contract — add it only
        # when a non-sidecar violation was seen, otherwise the sidecar
        # codes are the only candidates.
        if has_non_sidecar_failure:
            sidecar_codes.add(EXIT_CODE_MANDATORY_ARTIFACT_FAILURE)
        return min(sidecar_codes)
    return EXIT_CODE_MANDATORY_ARTIFACT_FAILURE


# ---------------------------------------------------------------------------
# Rendering — text + JSON
# ---------------------------------------------------------------------------


def _format_text_header(report: CorpusReport) -> list[str]:
    lines = [
        f"Corpus root: {report.root}",
        f"Contract set: {report.contract_set_version}",
    ]
    if report.root_missing:
        lines.append("Result: FAIL (corpus root not found)")
    return lines


def _format_partition_lines(
    label: str, stats: PartitionStats, suffix: str = ""
) -> list[str]:
    """Render one partition's three-line block per the contract sample.

    The label is left-padded to a fixed column so the counts align
    across both partitions (Scored / Calibration). The count is then
    right-padded into a small column of its own so the optional
    ``suffix`` (e.g. the pattern annotation on the scored line)
    starts at the same character offset regardless of how many digits
    the count has — matching the contract block sample:

        Scored corpus folders:   20  (pattern: ^inv_\\d{3}_(easy|medium|hard)$)
        Calibration folders:      2
    """
    head = f"  {label:<22} {stats.count:>3}{suffix}"
    return [
        head,
        f"    Valid:                  {stats.valid:>3}",
        f"    Invalid:                {stats.invalid:>3}",
    ]


def render_text(report: CorpusReport) -> str:
    """Render the reporting block per validator-cli-contract.md §`validate corpus`.

    Layout exactly matches the contract sample:

        Corpus root: <path>
          Scored corpus folders:   <N>  (pattern: ^inv_\\d{3}_(easy|medium|hard)$)
            Valid:                  <n>
            Invalid:                <n>
          Calibration folders:      <N>
            Valid:                   <n>
            Invalid:                 <n>
          Sidecars present:          <N>  (in scored set)
          Sidecars accepted:         <n>
          Sidecars rejected:         <n>
    """
    lines = _format_text_header(report)
    if report.root_missing:
        return "\n".join(lines)

    scored = report.scored_stats
    calibration = report.calibration_stats
    sidecars = report.sidecar_stats

    lines.extend(
        _format_partition_lines(
            "Scored corpus folders:",
            scored,
            f"  (pattern: {CANONICAL_FOLDER_PATTERN.pattern})",
        )
    )
    lines.extend(_format_partition_lines("Calibration folders:", calibration))
    lines.append(
        f"  Sidecars present:        {sidecars.present:>3}  (in scored set)"
    )
    lines.append(f"  Sidecars accepted:       {sidecars.accepted:>3}")
    lines.append(f"  Sidecars rejected:       {sidecars.rejected:>3}")
    return "\n".join(lines)


def _entry_to_dict(entry: FolderEntry) -> dict:
    return {
        "folder": entry.folder.name,
        "partition": "scored" if entry.is_scored else "calibration",
        "passed": entry.outcome.passed,
        "sidecar_present": entry.sidecar_present,
        "sidecar_accepted": entry.sidecar_accepted,
        "error_count": entry.outcome.counts.error,
        "warning_count": entry.outcome.counts.warning,
    }


def render_json(report: CorpusReport) -> str:
    """Render the reporting block as a JSON document for machine consumers."""
    payload: dict = {
        "corpus_root": str(report.root),
        "contract_set_version": report.contract_set_version,
        "root_missing": report.root_missing,
    }
    if report.root_missing:
        return json.dumps(payload, indent=2, sort_keys=False)

    scored = report.scored_stats
    calibration = report.calibration_stats
    sidecars = report.sidecar_stats
    payload.update(
        {
            "scored": {
                "count": scored.count,
                "valid": scored.valid,
                "invalid": scored.invalid,
                "pattern": CANONICAL_FOLDER_PATTERN.pattern,
            },
            "calibration": {
                "count": calibration.count,
                "valid": calibration.valid,
                "invalid": calibration.invalid,
            },
            "sidecars": {
                "present": sidecars.present,
                "accepted": sidecars.accepted,
                "rejected": sidecars.rejected,
                "scope": "scored_set",
            },
            "folders": [_entry_to_dict(e) for e in report.entries],
        }
    )
    return json.dumps(payload, indent=2, sort_keys=False)


__all__ = [
    "CorpusReport",
    "EXIT_CODE_CORPUS_ROOT_MISSING",
    "EXIT_CODE_MANDATORY_ARTIFACT_FAILURE",
    "EXIT_CODE_PASS",
    "FolderEntry",
    "PartitionStats",
    "SidecarStats",
    "build_corpus_report",
    "compute_exit_code",
    "compute_outcome_exit_code",
    "render_json",
    "render_text",
]
