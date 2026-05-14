"""End-to-end extractor orchestration.

Load preprocess_output.json → validate → render prompt → call voter →
parse → reconcile → assemble & write. No retries, no fallbacks.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ledgerlinc_ocr.contract_versions import (
    ContractVersionError,
    require_matching_contract_version,
    require_stage1_contract_version,
)
from ledgerlinc_ocr.validator import (
    ArtifactName,
    validate_artifact,
)

from .artifact import assemble_and_write
from .config import VoterConfig
from .errors import InputContractDrift, VoterConfigInvalid
from .parse import parse_model_response
from .prompt import render_prompt
from .reconcile import reconcile
from .version import build_pipeline_version
from .voters.base import VoterAdapter

_INPUT_NAME = "preprocess_output.json"


def _load_packet(folder: Path) -> dict[str, Any]:
    path = folder / _INPUT_NAME
    if not path.exists():
        raise InputContractDrift(
            f"input packet missing: {path}",
            detail={"path": str(path)},
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InputContractDrift(
            f"input packet is not valid JSON: {path}",
            detail={"path": str(path), "error": str(exc)},
        ) from exc


def _validate_packet(folder: Path, *, contract_set_version: str) -> None:
    outcome = validate_artifact(
        folder / _INPUT_NAME,
        ArtifactName.PREPROCESS_OUTPUT,
        version=contract_set_version,
    )
    if not outcome.passed:
        raise InputContractDrift(
            f"{_INPUT_NAME} failed schema validation",
            detail={
                "errors": [
                    {
                        "field_path": v.field_path,
                        "violation_code": v.violation_code,
                        "reason": v.reason,
                    }
                    for v in outcome.violations
                ],
            },
        )


def run(
    folder_path: str | Path,
    voter_config: VoterConfig,
    voter: VoterAdapter,
    template_path: Path,
    *,
    pipeline_version: str | None = None,
    contract_set_version: str | None = None,
) -> Path:
    """Extract one document. Returns the path to the written artifact.

    ``pipeline_version`` is optional: when None, ``build_pipeline_version()``
    supplies the package default. Callers (notably the 011 controller's
    extract adapter) pass ``--pipeline-version`` through here so the
    written artifact stamps the user-supplied value, matching how the
    other stage modules honor pipeline-version overrides.

    ``contract_set_version`` is optional for standalone stage runs. When
    supplied by the pipeline controller, it must match the upstream
    preprocess artifact; the extractor does not silently retarget an existing
    packet to a different contract set.
    """

    folder = Path(folder_path)
    if not folder.is_dir():
        raise InputContractDrift(
            f"folder does not exist or is not a directory: {folder}",
            detail={"path": str(folder)},
        )

    if voter_config.voter_role != "primary_extractor":
        raise VoterConfigInvalid(
            f"stage 1 requires voter_role='primary_extractor'; got "
            f"{voter_config.voter_role!r} (reserved for future ensemble work)",
            detail={"voter_role": voter_config.voter_role},
        )

    packet = _load_packet(folder)
    try:
        packet_contract_set_version = require_stage1_contract_version(
            packet.get("contract_set_version"),
            artifact_label=_INPUT_NAME,
        )
        packet_contract_set_version = require_matching_contract_version(
            found=packet_contract_set_version,
            expected=contract_set_version,
            artifact_label=_INPUT_NAME,
        )
    except ContractVersionError as exc:
        raise InputContractDrift(
            str(exc),
            detail={
                "path": str(folder / _INPUT_NAME),
                "found": packet.get("contract_set_version"),
                "expected": contract_set_version,
            },
        ) from exc

    _validate_packet(folder, contract_set_version=packet_contract_set_version)

    now = datetime.now(UTC)
    if pipeline_version is None:
        pipeline_version = build_pipeline_version()

    rendered = render_prompt(packet, template_path, voter_config)
    raw = voter.call(rendered, voter_config)
    parsed, repair_trail = parse_model_response(raw.body)

    artifact = reconcile(
        packet=packet,
        parsed=parsed,
        config=voter_config,
        now=now,
        pipeline_version=pipeline_version,
        contract_set_version=packet_contract_set_version,
        repair_trail=repair_trail,
    )

    return assemble_and_write(artifact, folder)
