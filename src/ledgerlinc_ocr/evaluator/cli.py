"""CLI entry point — argparse surface for `evaluate document` and `evaluate corpus`.

Exit codes (contracts/module-api.md §CLI contract):
- 0: clean completion (even when the document fails its gates — FR-023)
- 2: usage error (argparse default)
- 3: hard error (EvaluatorError, FileNotFoundError, schema violation, etc.)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from ledgerlinc_ocr.evaluator.exceptions import EvaluatorError
from ledgerlinc_ocr.evaluator.scoring import CONTRACT_SET_VERSION, ResultLabel


EXIT_OK = 0
EXIT_USAGE = 2
EXIT_HARD_ERROR = 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ledgerlinc_ocr.evaluator",
        description="Stage 1 vendor-identity evaluator & reporting.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    evaluate = subparsers.add_parser(
        "evaluate",
        help="Run evaluation over a single document or a corpus.",
    )
    evaluate_sub = evaluate.add_subparsers(
        dest="target", required=True, metavar="TARGET"
    )

    doc = evaluate_sub.add_parser(
        "document",
        help="Evaluate a single per-document folder.",
    )
    doc.add_argument("folder", type=Path, help="Per-document folder path")
    doc.add_argument(
        "--contract-set-version",
        default=CONTRACT_SET_VERSION,
        help=f"Contract set version (default: {CONTRACT_SET_VERSION})",
    )
    _add_pipeline_preparation_arguments(doc, corpus=False)
    format_group = doc.add_mutually_exclusive_group()
    format_group.add_argument(
        "--text",
        dest="output_format",
        action="store_const",
        const="text",
        help="Emit a short human-readable summary on stdout (default).",
    )
    format_group.add_argument(
        "--json",
        dest="output_format",
        action="store_const",
        const="json",
        help="Emit the DocumentEvaluationOutcome as JSON on stdout.",
    )
    doc.set_defaults(output_format="text", handler=_handle_document)

    corpus = evaluate_sub.add_parser(
        "corpus",
        help="Evaluate a corpus root (discovers per-document folders).",
    )
    corpus.add_argument("root", type=Path, help="Corpus root directory")
    corpus.add_argument(
        "--contract-set-version",
        default=CONTRACT_SET_VERSION,
        help=f"Contract set version (default: {CONTRACT_SET_VERSION})",
    )
    _add_pipeline_preparation_arguments(corpus, corpus=True)
    corpus.add_argument(
        "--no-lazy",
        action="store_true",
        help=(
            "Strict mode: require every per-document folder to already contain a "
            "valid evaluation_document.json; hard-fail otherwise. Note: without "
            "--refresh, any schema-valid evaluation_document.json on disk is "
            "trusted as-is, even if evaluator code or weights have changed since "
            "it was produced."
        ),
    )
    corpus.add_argument(
        "--refresh",
        action="store_true",
        help=(
            "Re-evaluate every document from scratch; ignore any existing "
            "evaluation_document.json. Use this after evaluator code or weights "
            "change, otherwise stale cached results are silently reused."
        ),
    )
    corpus.set_defaults(handler=_handle_corpus)

    return parser


def _add_pipeline_preparation_arguments(
    parser: argparse.ArgumentParser, *, corpus: bool
) -> None:
    group = parser.add_argument_group("pipeline preparation")
    group.add_argument(
        "--run-pipeline",
        action="store_true",
        help="Run the stage 1 pipeline before evaluation.",
    )
    group.add_argument(
        "--pipeline-overwrite",
        action="store_true",
        help="Pass --overwrite to the pipeline preparation step.",
    )
    if corpus:
        group.add_argument(
            "--pipeline-on-failure",
            choices=("continue", "fail-fast"),
            default="continue",
            help="Warm corpus pipeline failure policy (default: continue).",
        )
    group.add_argument(
        "--stack-preset",
        default=None,
        help=(
            "Pipeline stack preset to run before evaluation. If omitted with "
            "--run-pipeline and no explicit stage profiles, all stages use stub."
        ),
    )
    group.add_argument(
        "--preprocess-profile",
        default=None,
        help="Pipeline preprocessing profile passed through to the controller.",
    )
    group.add_argument(
        "--extract-profile",
        default=None,
        help="Pipeline extraction profile passed through to the controller.",
    )
    group.add_argument(
        "--routing-profile",
        default=None,
        help="Pipeline routing profile passed through to the controller.",
    )
    group.add_argument(
        "--final-payload-profile",
        default=None,
        help="Pipeline final-payload profile passed through to the controller.",
    )
    group.add_argument(
        "--start-at",
        default=None,
        help="First pipeline stage to run before evaluation.",
    )
    group.add_argument(
        "--stop-after",
        default=None,
        help="Last pipeline stage to run before evaluation.",
    )
    group.add_argument(
        "--ollama-url",
        default=None,
        help="GPU Ollama endpoint forwarded to pipeline preparation.",
    )
    group.add_argument(
        "--ollama-cpu-url",
        default=None,
        help="CPU Ollama endpoint forwarded to pipeline preparation.",
    )
    group.add_argument(
        "--ollama-jetson-url",
        default=None,
        help="Jetson Ollama endpoint forwarded to pipeline preparation.",
    )
    group.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Pipeline per-stage timeout in seconds.",
    )


def _handle_document(args: argparse.Namespace) -> int:
    from ledgerlinc_ocr.evaluator.document import evaluate_document

    if args.run_pipeline:
        prep_code = _prepare_document_for_evaluation(args)
        if prep_code != EXIT_OK:
            return prep_code

    outcome = evaluate_document(
        args.folder, contract_set_version=args.contract_set_version
    )
    if args.output_format == "json":
        print(
            json.dumps(
                {
                    "ok": outcome.ok,
                    "output_path": str(outcome.output_path)
                    if outcome.output_path
                    else None,
                    "document_id": outcome.evaluation.document_id
                    if outcome.evaluation
                    else None,
                    "difficulty": outcome.evaluation.difficulty
                    if outcome.evaluation
                    else None,
                    "document_pass_fail": {
                        "vendor_identity_passed": outcome.evaluation.document_pass_fail.vendor_identity_passed,
                        "review_routing_passed": outcome.evaluation.document_pass_fail.review_routing_passed,
                        "overall_passed": outcome.evaluation.document_pass_fail.overall_passed,
                    }
                    if outcome.evaluation
                    else None,
                    "comparison_summary": {
                        "applicable_field_count": outcome.evaluation.comparison_summary.applicable_field_count,
                        "matched_field_count": outcome.evaluation.comparison_summary.matched_field_count,
                        "mismatched_field_count": outcome.evaluation.comparison_summary.mismatched_field_count,
                        "missing_prediction_count": outcome.evaluation.comparison_summary.missing_prediction_count,
                        "unexpected_prediction_count": outcome.evaluation.comparison_summary.unexpected_prediction_count,
                        "field_accuracy": outcome.evaluation.comparison_summary.field_accuracy,
                    }
                    if outcome.evaluation
                    else None,
                    "errors": outcome.errors,
                    "warnings": outcome.warnings,
                },
                indent=2,
            )
        )
    else:
        ev = outcome.evaluation
        assert ev is not None
        pf = ev.document_pass_fail
        cs = ev.comparison_summary
        print(f"document_id:      {ev.document_id}")
        print(f"difficulty:       {ev.difficulty}")
        print(f"field_accuracy:   {cs.field_accuracy:.6f}")
        print(f"document_score:   {ev.document_score:.6f}")
        print(f"vendor_identity:  {'PASS' if pf.vendor_identity_passed else 'FAIL'}")
        print(f"review_routing:   {'PASS' if pf.review_routing_passed else 'FAIL'}")
        print(f"overall:          {'PASS' if pf.overall_passed else 'FAIL'}")
        failing = [
            fr
            for fr in ev.field_results
            if fr.result not in (ResultLabel.MATCH, ResultLabel.NOT_APPLICABLE)
        ]
        if failing:
            print(f"failing fields ({len(failing)}):")
            for fr in failing[:10]:
                print(f"  - {fr.field_name}: {fr.result.value}")
        print(f"written:          {outcome.output_path}")
    return EXIT_OK


def _handle_corpus(args: argparse.Namespace) -> int:
    from ledgerlinc_ocr.evaluator.corpus import evaluate_corpus

    document_folders = None
    if args.run_pipeline:
        prep_code, document_folders = _prepare_corpus_for_evaluation(args)
        if prep_code != EXIT_OK:
            return prep_code

    outcome = evaluate_corpus(
        args.root,
        contract_set_version=args.contract_set_version,
        lazy=not args.no_lazy,
        refresh=args.refresh,
        document_folders=document_folders,
    )
    assert outcome.md_output_path is not None
    # The rendered Markdown already ends with a single trailing newline;
    # use sys.stdout.write so the stream bytes match the on-disk file exactly.
    md_text = outcome.md_output_path.read_text(encoding="utf-8")
    sys.stdout.write(md_text)
    return EXIT_OK


def _pipeline_request(
    *,
    target: str,
    path: Path,
    args: argparse.Namespace,
) -> "PipelinePreparationRequest":
    from ledgerlinc_ocr.evaluator.pipeline_invocation import (
        PipelinePreparationRequest,
    )

    return PipelinePreparationRequest(
        target=target,
        path=path,
        contract_set_version=args.contract_set_version,
        overwrite=args.pipeline_overwrite,
        stack_preset=args.stack_preset,
        preprocess_profile=args.preprocess_profile,
        extract_profile=args.extract_profile,
        routing_profile=args.routing_profile,
        final_payload_profile=args.final_payload_profile,
        start_at=args.start_at,
        stop_after=args.stop_after,
        ollama_url=args.ollama_url,
        ollama_cpu_url=args.ollama_cpu_url,
        ollama_jetson_url=args.ollama_jetson_url,
        timeout=args.timeout,
        on_failure=getattr(args, "pipeline_on_failure", None),
    )


def _prepare_document_for_evaluation(args: argparse.Namespace) -> int:
    from ledgerlinc_ocr.evaluator.pipeline_invocation import (
        format_preparation_error,
        run_document_preparation,
    )

    request = _pipeline_request(target="document", path=args.folder, args=args)
    outcome = run_document_preparation(request)
    if outcome.ok:
        return EXIT_OK
    print(format_preparation_error(outcome), file=sys.stderr)
    return EXIT_HARD_ERROR


def _prepare_corpus_for_evaluation(
    args: argparse.Namespace,
) -> tuple[int, tuple[Path, ...] | None]:
    from ledgerlinc_ocr.evaluator.corpus import list_document_folders
    from ledgerlinc_ocr.evaluator.pipeline_invocation import (
        format_corpus_preparation_report,
        format_preparation_error,
        run_corpus_preparation,
    )

    folders = tuple(list_document_folders(args.root))
    request = _pipeline_request(target="corpus", path=args.root, args=args)
    outcome = run_corpus_preparation(request, folders)
    report = format_corpus_preparation_report(outcome)
    if report:
        print(report, file=sys.stderr)
    if args.pipeline_on_failure == "fail-fast" and not outcome.ok:
        print(format_preparation_error(outcome), file=sys.stderr)
        return EXIT_HARD_ERROR, None
    if not outcome.prepared_folders:
        print(
            "pipeline preparation produced no evaluatable document folders",
            file=sys.stderr,
        )
        return EXIT_HARD_ERROR, None
    return EXIT_OK, outcome.prepared_folders


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except EvaluatorError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_HARD_ERROR
    except FileNotFoundError as exc:
        print(f"file not found: {exc.filename or exc}", file=sys.stderr)
        return EXIT_HARD_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
