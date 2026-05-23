"""argparse CLI for `python -m dartwing_ocr.validator`.

Exit codes for the original subcommands (artifact / folder / corpus / show):
  0  pass (no error-severity violations; warnings allowed)
  1  validation failed (one or more error-severity violations)
  2  usage error

Sidecar-aware exit codes added at v1.3.0 (feature 022 / US1) per
``specs/022-ocr-semantic-quality-gate/contracts/validator-cli-contract.md``:
  3  semantic_table_truth.json present but ``document_id`` mismatch
  4  semantic_table_truth.json present but row-violation
     (missing sidecar / non-unique row_id / row fails row-truth contract)
  5  semantic_table_truth.json present but JSON parse or schema-validation failure

These codes apply to BOTH the new ``validate semantic-truth <folder>`` subcommand
AND the existing ``validate folder`` / ``validate corpus`` subcommands when
they encounter sidecar-class errors. The exit-code selection rule is
lowest-non-zero: when more than one error class is present, the lowest
non-zero code among them is returned.

Note: the original codes 1 / 2 are unchanged. Pre-v1.3.0 internal-error code 3
on the original subcommands is preserved at code 3 below for parity — sidecar
exit code 3 only fires when the validator successfully runs and finds a
``document_id`` mismatch, never as a generic internal error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dartwing_ocr.validator.artifact import validate_artifact
from dartwing_ocr.validator.loader import (
    ContractSet,
    ContractSetCorruptError,
    ContractSetNotFoundError,
    InvalidArtifactNameError,
    load_contract_set,
)
from dartwing_ocr.validator.report import (
    ArtifactName,
    ValidationOutcome,
    ViolationCode,
    render_text,
)
from dartwing_ocr.validator.semantic_table_truth import (
    SemanticTruthValidationResult,
    SidecarErrorKind,
    validate_sidecar,
)

# Mapping from sidecar-validation ViolationCode → CLI exit code per
# validator-cli-contract.md. Lower codes win when multiple are present.
_SIDECAR_VIOLATION_TO_EXIT_CODE: dict[str, int] = {
    ViolationCode.SIDECAR_DOCUMENT_ID_MISMATCH: 3,
    ViolationCode.SIDECAR_ROW_VIOLATION: 4,
    ViolationCode.SIDECAR_SCHEMA_INVALID: 5,
    ViolationCode.SIDECAR_JSON_INVALID: 5,
}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m dartwing_ocr.validator",
        description=(
            "Validate stage 1 vendor-identity artifacts and folders against the "
            "frozen contract set."
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)

    vp = sub.add_parser("validate", help="Validate an artifact, folder, or corpus.")
    vsub = vp.add_subparsers(dest="subcommand", required=True)

    art = vsub.add_parser("artifact", help="Validate a single JSON artifact.")
    art.add_argument("path", type=Path)
    art.add_argument(
        "--contract",
        required=True,
        choices=[a.value for a in ArtifactName],
    )
    art.add_argument("--contract-set-version", dest="version", default=None)
    _add_output_flags(art)

    fol = vsub.add_parser("folder", help="Validate a per-document folder.")
    fol.add_argument("path", type=Path)
    fol.add_argument("--contract-set-version", dest="version", default=None)
    _add_output_flags(fol)

    cor = vsub.add_parser("corpus", help="Validate an entire corpus root.")
    cor.add_argument("path", type=Path)
    cor.add_argument("--contract-set-version", dest="version", default=None)
    cor.add_argument("--fail-fast", action="store_true")
    _add_output_flags(cor)

    # Feature 022 / US1 — validate the optional semantic_table_truth.json
    # sidecar in a per-document folder, in isolation, for fixture-author
    # workflows. See specs/022-ocr-semantic-quality-gate/contracts/
    # validator-cli-contract.md §`validate semantic-truth`.
    sem = vsub.add_parser(
        "semantic-truth",
        help="Validate the optional semantic_table_truth.json sidecar in a folder.",
    )
    sem.add_argument("path", type=Path)
    # Note: no --contract-set-version flag here. The sidecar always
    # validates against the active contract set's
    # semantic_table_truth.schema.json; there is no per-call version
    # override surface. (Sourcery review PR #46 2026-05-23: the previous
    # flag was parsed but never threaded through to validate_sidecar,
    # which always uses the active schema — removed to avoid a
    # misleading CLI option.)
    _add_output_flags(sem)

    show = sub.add_parser("show", help="Inspect contract-set metadata.")
    shsub = show.add_subparsers(dest="subcommand", required=True)
    sc = shsub.add_parser("contract-set", help="Show the loaded contract-set metadata.")
    sc.add_argument("--version", default=None)
    _add_output_flags(sc)

    return p


def _add_output_flags(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", dest="json_output", action="store_true")
    group.add_argument("--text", dest="text_output", action="store_true")


def _format(outcome: ValidationOutcome, *, json_output: bool) -> str:
    if json_output:
        return json.dumps(outcome.to_json(), indent=2, sort_keys=False)
    return render_text(outcome)


def _walk_violations(outcome: ValidationOutcome):
    """Yield every Violation in ``outcome`` and its sub-reports recursively."""
    yield from outcome.violations
    for sub in outcome.sub_reports:
        yield from _walk_violations(sub)


def _folder_or_corpus_exit_code(outcome: ValidationOutcome) -> int:
    """Exit code for ``validate folder`` / ``validate corpus``.

    Returns the lowest non-zero code among encountered sidecar-class
    failures; otherwise returns 0 on pass or 1 on any other failure
    (validator-cli-contract.md §`validate folder` and §`validate corpus`).
    """
    if outcome.passed:
        return 0
    sidecar_codes: set[int] = set()
    for v in _walk_violations(outcome):
        mapped = _SIDECAR_VIOLATION_TO_EXIT_CODE.get(v.violation_code)
        if mapped is not None:
            sidecar_codes.add(mapped)
    if sidecar_codes:
        return min(sidecar_codes)
    return 1


def _semantic_truth_exit_code(result: SemanticTruthValidationResult) -> int:
    """Exit code for ``validate semantic-truth``.

    Lowest non-zero among encountered error classes; 0 when accepted
    (validator-cli-contract.md §`validate semantic-truth`).
    """
    return result.exit_code()


def _render_semantic_truth(
    result: SemanticTruthValidationResult, *, json_output: bool
) -> str:
    if json_output:
        payload = {
            "folder": str(result.folder),
            "sidecar": str(result.sidecar_path),
            "passed": result.passed,
            "errors": [
                {
                    "kind": e.kind.value,
                    "message": e.message,
                    "row_id": e.row_id,
                    "row_index": e.row_index,
                    "field": e.field,
                }
                for e in result.errors
            ],
        }
        return json.dumps(payload, indent=2, sort_keys=False)
    if result.passed:
        return (
            f"Sidecar: {result.sidecar_path}\n"
            f"Result: PASS\n"
            f"  semantic_table_truth.json accepted for folder "
            f"'{result.folder.name}'."
        )
    lines = [
        f"Sidecar: {result.sidecar_path}",
        f"Result: FAIL ({len(result.errors)} error(s))",
        "",
    ]
    for e in result.errors:
        lines.append(f"  {e.kind.value}")
        lines.append(f"    {e.message}")
    return "\n".join(lines)


def _render_contract_set(cs: ContractSet, *, json_output: bool) -> str:
    payload = {
        "contract_set_version": cs.version,
        "version_dir": str(cs.version_dir),
        "artifact_schemas": {k.value: str(v) for k, v in cs.artifact_schemas.items()},
        "folder_schema": str(cs.folder_schema),
        "challenge_tags": sorted(cs.challenge_tags),
        "cross_artifact_rules": list(cs.cross_artifact_rules),
        "pipeline_versioned_artifacts": sorted(
            a.value for a in cs.pipeline_versioned_artifacts
        ),
        "policy_versioned_artifacts": sorted(
            a.value for a in cs.policy_versioned_artifacts
        ),
    }
    if json_output:
        return json.dumps(payload, indent=2)
    lines = [
        f"Contract set: {payload['contract_set_version']}",
        f"Directory:    {payload['version_dir']}",
        "",
        "Artifact schemas:",
    ]
    for name in ArtifactName:
        rel = payload["artifact_schemas"].get(name.value, "<missing>")
        lines.append(f"  {name.value:<30} {rel}")
    lines += [
        "",
        f"Folder schema: {payload['folder_schema']}",
        "",
        f"Challenge tags ({len(payload['challenge_tags'])}):",
    ]
    lines.extend(f"  - {t}" for t in payload["challenge_tags"])
    lines += [
        "",
        f"Cross-artifact rules ({len(payload['cross_artifact_rules'])}):",
    ]
    lines.extend(f"  - {r}" for r in payload["cross_artifact_rules"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:  # NOSONAR S3776 — validator CLI dispatcher — branches over all subcommands and their failure modes.
    argv = list(argv) if argv is not None else sys.argv[1:]
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # NOSONAR S5754 — intentional: argparse exits via SystemExit on --help / parse errors; convert to an integer return so library callers don't see an exception.
        return int(exc.code) if isinstance(exc.code, int) else 2

    json_output: bool = bool(getattr(args, "json_output", False))

    try:
        if args.command == "validate" and args.subcommand == "artifact":
            outcome = validate_artifact(
                args.path, args.contract, version=args.version
            )
            print(_format(outcome, json_output=json_output))
            return 0 if outcome.passed else 1

        if args.command == "validate" and args.subcommand == "folder":
            from dartwing_ocr.validator.folder import validate_folder
            outcome = validate_folder(args.path, version=args.version)
            print(_format(outcome, json_output=json_output))
            return _folder_or_corpus_exit_code(outcome)

        if args.command == "validate" and args.subcommand == "corpus":
            from dartwing_ocr.validator.corpus import validate_corpus
            outcome = validate_corpus(
                args.path, version=args.version, fail_fast=args.fail_fast
            )
            print(_format(outcome, json_output=json_output))
            return _folder_or_corpus_exit_code(outcome)

        if args.command == "validate" and args.subcommand == "semantic-truth":
            # Feature 022 / US1 — validate the optional sidecar in isolation
            # per validator-cli-contract.md §`validate semantic-truth`.
            if not args.path.is_dir():
                print(
                    f"usage error: folder does not exist: {args.path}",
                    file=sys.stderr,
                )
                return 2
            result = validate_sidecar(args.path)
            print(_render_semantic_truth(result, json_output=json_output))
            return _semantic_truth_exit_code(result)

        if args.command == "show" and args.subcommand == "contract-set":
            cs = load_contract_set(args.version)
            print(_render_contract_set(cs, json_output=json_output))
            return 0

        parser.error(f"unknown command: {args.command} {args.subcommand}")
        return 2

    except (ContractSetNotFoundError, ContractSetCorruptError) as exc:
        print(f"contract-set error: {exc}", file=sys.stderr)
        return 3
    except InvalidArtifactNameError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"file not found: {exc}", file=sys.stderr)
        return 2
    except NotImplementedError as exc:
        print(f"not implemented yet: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"internal error: {exc!r}", file=sys.stderr)
        return 3
