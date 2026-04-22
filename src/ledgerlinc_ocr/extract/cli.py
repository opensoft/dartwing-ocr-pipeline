"""`ledgerlinc-extract` command-line entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import pipeline as pipeline_mod
from .config import VoterConfig, load_voter_config
from .errors import ExtractionError, VoterConfigInvalid
from .exit_codes import EXIT_OK, EXIT_UNEXPECTED, for_error
from .voters.base import VoterAdapter
from .voters.ollama import OllamaVoter
from .voters.stub import StubVoter

_LOG = logging.getLogger("ledgerlinc_ocr.extract")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ledgerlinc-extract",
        description="Run the stage 1 single-voter edge extractor against one per-document folder.",
    )
    parser.add_argument(
        "--folder",
        required=True,
        type=Path,
        help="Per-document folder containing preprocess_output.json",
    )
    parser.add_argument(
        "--voter",
        required=True,
        help="Voter name (e.g., 'gemma-edge', 'stub') resolved against the packaged configs.",
    )
    parser.add_argument(
        "--voter-config",
        type=Path,
        default=None,
        help="Optional path override; wins over --voter name lookup.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args(argv)


def _select_voter(
    config: VoterConfig,
    config_path: Path,
    extensions: dict,
) -> VoterAdapter:
    provider = config.model_runtime.provider
    if provider == "stub":
        return StubVoter(
            extensions=extensions,
            config_dir=config_path.parent,
        )
    if provider in ("ollama", "host_ollama"):
        return OllamaVoter()
    raise VoterConfigInvalid(
        f"unknown voter provider {provider!r}; "
        f"expected 'stub', 'ollama', or 'host_ollama'",
        detail={"provider": provider, "config_path": str(config_path)},
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        name_or_path = (
            str(args.voter_config) if args.voter_config is not None else args.voter
        )
        base_dir = Path.cwd()
        config, config_path, extensions = load_voter_config(
            name_or_path=name_or_path,
            base_dir=base_dir,
        )

        voter = _select_voter(config, config_path, extensions)
        template_path = config_path.parent / config.prompt.template_path

        written = pipeline_mod.run(
            folder_path=args.folder,
            voter_config=config,
            voter=voter,
            template_path=template_path,
        )
    except ExtractionError as exc:
        _LOG.error("%s", exc.message)
        return for_error(exc)
    except Exception as exc:  # pragma: no cover — safety net for unexpected failures
        _LOG.exception("unexpected extractor failure: %s", exc)
        return EXIT_UNEXPECTED

    _LOG.info("wrote %s", written)
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
