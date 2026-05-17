"""argparse CLI for `python -m dartwing_ocr.validator`.

Exit codes:
  0  pass (no error-severity violations; warnings allowed)
  1  validation failed (one or more error-severity violations)
  2  usage error
  3  internal error
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
    render_text,
)


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
            return 0 if outcome.passed else 1

        if args.command == "validate" and args.subcommand == "corpus":
            from dartwing_ocr.validator.corpus import validate_corpus
            outcome = validate_corpus(
                args.path, version=args.version, fail_fast=args.fail_fast
            )
            print(_format(outcome, json_output=json_output))
            return 0 if outcome.passed else 1

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
