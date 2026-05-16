"""Corpus aggregator — lazy per-doc evaluation + run summary dataclasses."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from ledgerlinc_ocr.evaluator.compare import FieldResult
from ledgerlinc_ocr.evaluator.document import DocumentEvaluation, evaluate_document
from ledgerlinc_ocr.evaluator.exceptions import EmptyCorpusError
from ledgerlinc_ocr.evaluator.filenames import (
    EVAL_DOC_FILENAME,
    EVAL_RUN_SUMMARY_FILENAME,
)
from ledgerlinc_ocr.evaluator.gates import DocumentPassFail
from ledgerlinc_ocr.evaluator.io import read_json, write_json, write_text
from ledgerlinc_ocr.evaluator.schema import (
    load_evaluation_document_schema,
    load_evaluation_run_summary_schema,
    validate_against_schema,
)
from ledgerlinc_ocr.evaluator.scoring import (
    CONTRACT_SET_VERSION,
    ComparisonSummary,
    SCORED_FIELDS,
    ResultLabel,
    compute_document_score,
)

# Local aliases (keep call sites private).
_EVAL_DOC_FILENAME = EVAL_DOC_FILENAME
_EVAL_RUN_SUMMARY_FILENAME = EVAL_RUN_SUMMARY_FILENAME


@dataclass(frozen=True, slots=True)
class DifficultyStats:
    document_count: int
    field_accuracy: float
    overall_document_pass_rate: float


@dataclass(frozen=True, slots=True)
class OverallMetrics:
    field_accuracy: float
    vendor_identity_pass_rate: float
    review_routing_pass_rate: float
    overall_document_pass_rate: float


@dataclass(frozen=True, slots=True)
class ConsensusMetrics:
    single_voter_baseline_runs: int
    majority_vote_documents: int
    split_decision_documents: int
    unanimous_field_rate: float | None = None
    two_of_three_majority_rate: float | None = None
    split_decision_rate: float | None = None


@dataclass(frozen=True, slots=True)
class DocumentListEntry:
    document_id: str
    overall_passed: bool
    field_accuracy: float


_DIFFICULTY_KEYS: tuple[str, ...] = ("easy", "medium", "hard", "missing_name")


@dataclass(frozen=True, slots=True)
class RunSummary:
    contract_set_version: str
    run_id: str
    pipeline_version: str | None
    policy_version: str | None
    document_count: int
    overall_metrics: OverallMetrics
    consensus_metrics: ConsensusMetrics
    by_difficulty: dict[str, DifficultyStats]
    by_field: dict[str, float]
    documents: tuple[DocumentListEntry, ...]

    def __post_init__(self) -> None:
        if set(self.by_difficulty.keys()) != set(_DIFFICULTY_KEYS):
            raise ValueError(
                f"by_difficulty must have exactly the keys "
                f"{_DIFFICULTY_KEYS}; got {sorted(self.by_difficulty.keys())}"
            )
        if len(self.documents) != self.document_count:
            raise ValueError(
                f"len(documents)={len(self.documents)} != document_count={self.document_count}"
            )
        doc_ids = [d.document_id for d in self.documents]
        if doc_ids != sorted(doc_ids):
            raise ValueError("documents must be sorted by document_id ascending")

    def to_persistable_dict(self) -> dict[str, object]:
        """Serializable dict matching evaluation_run_summary.schema.json."""
        out: dict[str, object] = {
            "contract_set_version": self.contract_set_version,
            "run_id": self.run_id,
        }
        if self.pipeline_version is not None:
            out["pipeline_version"] = self.pipeline_version
        if self.policy_version is not None:
            out["policy_version"] = self.policy_version
        out["document_count"] = self.document_count
        out["overall_metrics"] = {
            "field_accuracy": self.overall_metrics.field_accuracy,
            "vendor_identity_pass_rate": self.overall_metrics.vendor_identity_pass_rate,
            "review_routing_pass_rate": self.overall_metrics.review_routing_pass_rate,
            "overall_document_pass_rate": self.overall_metrics.overall_document_pass_rate,
        }
        consensus: dict[str, object] = {
            "single_voter_baseline_runs": self.consensus_metrics.single_voter_baseline_runs,
            "majority_vote_documents": self.consensus_metrics.majority_vote_documents,
            "split_decision_documents": self.consensus_metrics.split_decision_documents,
        }
        if self.consensus_metrics.unanimous_field_rate is not None:
            consensus["unanimous_field_rate"] = self.consensus_metrics.unanimous_field_rate
        if self.consensus_metrics.two_of_three_majority_rate is not None:
            consensus["two_of_three_majority_rate"] = (
                self.consensus_metrics.two_of_three_majority_rate
            )
        if self.consensus_metrics.split_decision_rate is not None:
            consensus["split_decision_rate"] = self.consensus_metrics.split_decision_rate
        out["consensus_metrics"] = consensus
        out["by_difficulty"] = {
            key: {
                "document_count": self.by_difficulty[key].document_count,
                "field_accuracy": self.by_difficulty[key].field_accuracy,
                "overall_document_pass_rate": self.by_difficulty[key].overall_document_pass_rate,
            }
            for key in _DIFFICULTY_KEYS
        }
        out["by_field"] = dict(self.by_field)
        out["documents"] = [
            {
                "document_id": d.document_id,
                "overall_passed": d.overall_passed,
                "field_accuracy": d.field_accuracy,
            }
            for d in self.documents
        ]
        return out


def list_document_folders(root: Path) -> list[Path]:
    """Return immediate subdirectories of `root` that contain `expected.json`,
    sorted ascending by folder name. Raise EmptyCorpusError when none exist."""
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"corpus root is not a directory: {root}")
    folders = sorted(
        p for p in root.iterdir() if p.is_dir() and (p / "expected.json").is_file()
    )
    if not folders:
        raise EmptyCorpusError(f"no document folders with expected.json found under {root}")
    return folders


def _hydrate_document_evaluation(
    instance: dict[str, object], folder: Path
) -> DocumentEvaluation:
    """Build a `DocumentEvaluation` from a schema-validated `evaluation_document.json`
    instance. Dataclass invariants are re-enforced. `document_score` is recomputed
    from `field_results` (not persisted in the artifact)."""
    cs = instance["comparison_summary"]  # type: ignore[index]
    summary = ComparisonSummary(
        applicable_field_count=cs["applicable_field_count"],
        matched_field_count=cs["matched_field_count"],
        mismatched_field_count=cs["mismatched_field_count"],
        missing_prediction_count=cs["missing_prediction_count"],
        unexpected_prediction_count=cs["unexpected_prediction_count"],
        field_accuracy=cs["field_accuracy"],
    )
    pf = instance["document_pass_fail"]  # type: ignore[index]
    pass_fail = DocumentPassFail(
        vendor_identity_passed=pf["vendor_identity_passed"],
        review_routing_passed=pf["review_routing_passed"],
        overall_passed=pf["overall_passed"],
    )
    raw_results: dict[str, dict[str, object]] = instance["field_results"]  # type: ignore[assignment]
    field_results = tuple(
        FieldResult(
            field_name=name,
            expected=raw_results[name]["expected"],
            actual=raw_results[name]["actual"],
            result=ResultLabel(raw_results[name]["result"]),
        )
        for name in SCORED_FIELDS
    )
    return DocumentEvaluation(
        contract_set_version=instance["contract_set_version"],  # type: ignore[arg-type]
        document_id=instance["document_id"],  # type: ignore[arg-type]
        difficulty=instance["difficulty"],  # type: ignore[arg-type]
        challenge_tags=tuple(instance["challenge_tags"]),  # type: ignore[arg-type]
        comparison_summary=summary,
        document_pass_fail=pass_fail,
        field_results=field_results,
        notes=tuple(instance["notes"]),  # type: ignore[arg-type]
        document_score=compute_document_score(field_results),
        folder_path=folder,
    )


def _ensure_document_evaluation(
    folder: Path,
    *,
    lazy: bool,
    contract_set_version: str,
    refresh: bool = False,
) -> DocumentEvaluation:
    """Return the DocumentEvaluation for `folder`. If an existing
    `evaluation_document.json` validates, read-and-reuse it (no re-eval);
    otherwise fall back to `evaluate_document` in lazy mode, or raise
    FileNotFoundError in strict mode.

    When `refresh=True`, any existing `evaluation_document.json` is ignored
    and the document is always re-evaluated from scratch. This bypasses the
    lazy-mode cache and forces regeneration regardless of whether the
    on-disk artifact is schema-valid."""
    eval_path = folder / _EVAL_DOC_FILENAME
    if refresh:
        outcome = evaluate_document(folder, contract_set_version=contract_set_version)
        assert outcome.evaluation is not None
        return outcome.evaluation
    if eval_path.is_file():
        try:
            instance = read_json(eval_path)
            validate_against_schema(
                instance,
                load_evaluation_document_schema(contract_set_version),
                source=eval_path,
                artifact_label=_EVAL_DOC_FILENAME,
            )
        except Exception:
            if not lazy:
                raise
            outcome = evaluate_document(folder, contract_set_version=contract_set_version)
            assert outcome.evaluation is not None
            return outcome.evaluation
        else:
            # Cache hit — reuse the validated on-disk artifact.
            return _hydrate_document_evaluation(instance, folder)
    if not lazy:
        raise FileNotFoundError(
            f"--no-lazy: missing evaluation_document.json at {eval_path}"
        )
    outcome = evaluate_document(folder, contract_set_version=contract_set_version)
    assert outcome.evaluation is not None
    return outcome.evaluation


def _field_accuracy(field_results: tuple[FieldResult, ...]) -> float:
    applicable = 0
    matched = 0
    partial = 0
    for fr in field_results:
        if fr.result is ResultLabel.NOT_APPLICABLE:
            continue
        applicable += 1
        if fr.result is ResultLabel.MATCH:
            matched += 1
        elif fr.result is ResultLabel.PARTIAL_MATCH:
            partial += 1
    if applicable == 0:
        return 0.0
    return round((matched + 0.5 * partial) / applicable, 6)


def build_by_difficulty(
    evaluations: tuple[DocumentEvaluation, ...],
) -> dict[str, DifficultyStats]:
    """Emit exactly four keys (easy/medium/hard/missing_name) in fixed order."""
    buckets: dict[str, list[DocumentEvaluation]] = {k: [] for k in _DIFFICULTY_KEYS}
    for ev in evaluations:
        buckets[ev.difficulty].append(ev)
    out: dict[str, DifficultyStats] = {}
    for key in _DIFFICULTY_KEYS:
        docs = buckets[key]
        count = len(docs)
        if count == 0:
            out[key] = DifficultyStats(
                document_count=0, field_accuracy=0.0, overall_document_pass_rate=0.0
            )
            continue
        accuracies = [ev.comparison_summary.field_accuracy for ev in docs]
        passes = sum(1 for ev in docs if ev.document_pass_fail.overall_passed)
        out[key] = DifficultyStats(
            document_count=count,
            field_accuracy=round(sum(accuracies) / count, 6),
            overall_document_pass_rate=round(passes / count, 6),
        )
    return out


def build_by_field(
    evaluations: tuple[DocumentEvaluation, ...],
) -> dict[str, float]:
    """Corpus-wide unweighted accuracy per dotted SCORED_FIELDS key (research §12)."""
    per_field_applicable: dict[str, int] = dict.fromkeys(SCORED_FIELDS, 0)
    per_field_match: dict[str, int] = dict.fromkeys(SCORED_FIELDS, 0)
    per_field_partial: dict[str, int] = dict.fromkeys(SCORED_FIELDS, 0)
    for ev in evaluations:
        for fr in ev.field_results:
            if fr.result is ResultLabel.NOT_APPLICABLE:
                continue
            per_field_applicable[fr.field_name] += 1
            if fr.result is ResultLabel.MATCH:
                per_field_match[fr.field_name] += 1
            elif fr.result is ResultLabel.PARTIAL_MATCH:
                per_field_partial[fr.field_name] += 1
    out: dict[str, float] = {}
    for key in SCORED_FIELDS:
        applicable = per_field_applicable[key]
        if applicable == 0:
            out[key] = 0.0
            continue
        acc = (per_field_match[key] + 0.5 * per_field_partial[key]) / applicable
        out[key] = round(acc, 6)
    return out


def build_overall_metrics(
    evaluations: tuple[DocumentEvaluation, ...],
) -> OverallMetrics:
    count = len(evaluations)
    if count == 0:
        return OverallMetrics(
            field_accuracy=0.0,
            vendor_identity_pass_rate=0.0,
            review_routing_pass_rate=0.0,
            overall_document_pass_rate=0.0,
        )
    accuracies = [ev.comparison_summary.field_accuracy for ev in evaluations]
    vi = sum(1 for ev in evaluations if ev.document_pass_fail.vendor_identity_passed)
    rr = sum(1 for ev in evaluations if ev.document_pass_fail.review_routing_passed)
    overall = sum(1 for ev in evaluations if ev.document_pass_fail.overall_passed)
    return OverallMetrics(
        field_accuracy=round(sum(accuracies) / count, 6),
        vendor_identity_pass_rate=round(vi / count, 6),
        review_routing_pass_rate=round(rr / count, 6),
        overall_document_pass_rate=round(overall / count, 6),
    )


def build_consensus_metrics(document_count: int) -> ConsensusMetrics:
    """Stage 1 single-voter baseline — ensemble rates omitted (FR-016)."""
    return ConsensusMetrics(
        single_voter_baseline_runs=document_count,
        majority_vote_documents=0,
        split_decision_documents=0,
    )


def build_documents_list(
    evaluations: tuple[DocumentEvaluation, ...],
) -> tuple[DocumentListEntry, ...]:
    entries = [
        DocumentListEntry(
            document_id=ev.document_id,
            overall_passed=ev.document_pass_fail.overall_passed,
            field_accuracy=ev.comparison_summary.field_accuracy,
        )
        for ev in evaluations
    ]
    entries.sort(key=lambda e: e.document_id)
    return tuple(entries)


def generate_run_id() -> str:
    """`run_` + UTC-ISO-8601-with-microseconds + `Z_` + uuid4().hex[:8] (research §9)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stamp = now.isoformat(timespec="microseconds") + "Z"
    suffix = uuid.uuid4().hex[:8]
    return f"run_{stamp}_{suffix}"


def evaluate_corpus(
    root: Path,
    *,
    contract_set_version: str | None = None,
    lazy: bool = True,
    refresh: bool = False,
    document_folders: Iterable[Path] | None = None,
) -> "RunSummaryOutcome":  # type: ignore[name-defined]  # noqa: F821
    """Evaluate every per-document folder under `root` and write
    `evaluation_run_summary.json` (FR-015–FR-017).

    Lazy mode (default) auto-invokes `evaluate_document` for any folder missing
    a valid `evaluation_document.json`. Strict mode (`lazy=False`) requires
    every folder to carry a pre-built evaluation_document.json and raises
    FileNotFoundError on the first missing one.

    When `refresh=True`, any existing `evaluation_document.json` on disk is
    ignored and every document is re-evaluated from scratch. Use this after
    evaluator code or scoring weights change without a contract-version bump,
    so operators do not silently trust stale cached results. `refresh` wins
    over the lazy/strict cache-hit path regardless of `lazy`.

    Any hard error aborts the run without writing the summary (FR-020).
    """
    from ledgerlinc_ocr.evaluator.outcomes import (
        DocumentEvaluationOutcome,
        RunSummaryOutcome,
    )

    root = Path(root)
    pinned = contract_set_version or CONTRACT_SET_VERSION

    if document_folders is None:
        folders = list_document_folders(root)
    else:
        folders = [Path(folder) for folder in document_folders]
        if not folders:
            raise EmptyCorpusError("no prepared document folders available to evaluate")

    evaluations: list[DocumentEvaluation] = []
    per_document_outcomes: list[DocumentEvaluationOutcome] = []
    for folder in folders:
        ev = _ensure_document_evaluation(
            folder, lazy=lazy, contract_set_version=pinned, refresh=refresh
        )
        evaluations.append(ev)
        per_document_outcomes.append(
            DocumentEvaluationOutcome(
                ok=True,
                evaluation=ev,
                output_path=folder / _EVAL_DOC_FILENAME,
            )
        )

    ev_tuple = tuple(evaluations)
    document_count = len(ev_tuple)
    overall = build_overall_metrics(ev_tuple)
    consensus = build_consensus_metrics(document_count)
    by_difficulty = build_by_difficulty(ev_tuple)
    by_field = build_by_field(ev_tuple)
    documents = build_documents_list(ev_tuple)

    summary = RunSummary(
        contract_set_version=pinned,
        run_id=generate_run_id(),
        pipeline_version=None,
        policy_version=None,
        document_count=document_count,
        overall_metrics=overall,
        consensus_metrics=consensus,
        by_difficulty=by_difficulty,
        by_field=by_field,
        documents=documents,
    )

    persistable = summary.to_persistable_dict()
    validate_against_schema(
        persistable,
        load_evaluation_run_summary_schema(pinned),
        source=root / _EVAL_RUN_SUMMARY_FILENAME,
        artifact_label=_EVAL_RUN_SUMMARY_FILENAME,
    )

    json_path = root / _EVAL_RUN_SUMMARY_FILENAME
    write_json(json_path, persistable)

    from ledgerlinc_ocr.evaluator.report import render_run_summary

    md_path = root / "evaluation_run_summary.md"
    md_text = render_run_summary(summary, document_evaluations=ev_tuple)
    write_text(md_path, md_text)

    return RunSummaryOutcome(
        ok=True,
        summary=summary,
        per_document=per_document_outcomes,
        json_output_path=json_path,
        md_output_path=md_path,
    )
