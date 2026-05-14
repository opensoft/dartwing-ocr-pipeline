"""Late-stage contract-set version propagation for active v1.2 artifacts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from dartwing_ocr.assembler.pipeline import Invocation as AssemblerInvocation
from dartwing_ocr.assembler.pipeline import run as assembler_run
from dartwing_ocr.extract.config import load_voter_config
from dartwing_ocr.extract.errors import InputContractDrift
from dartwing_ocr.extract.pipeline import run as extract_run
from dartwing_ocr.extract.voters.stub import StubVoter
from dartwing_ocr.router.pipeline import run as router_run
from dartwing_ocr.validator import ArtifactName, validate_artifact

_REPO_ROOT = Path(__file__).resolve().parents[2]
_US1 = _REPO_ROOT / "tests" / "fixtures" / "extract" / "us1_happy"


def _copy_us1_with_contract(tmp_path: Path, version: str) -> Path:
    folder = tmp_path / f"us1_happy_v{version.replace('.', '_')}"
    shutil.copytree(_US1, folder)
    packet_path = folder / "preprocess_output.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet["contract_set_version"] = version
    packet_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    return folder


def _run_stub_extract(folder: Path, *, contract_set_version: str | None = None) -> Path:
    config, config_path, extensions = load_voter_config(
        name_or_path=str(folder / "voter_config.yaml"),
        base_dir=Path.cwd(),
    )
    return extract_run(
        folder_path=folder,
        voter_config=config,
        voter=StubVoter(extensions=extensions, config_dir=config_path.parent),
        template_path=config_path.parent / config.prompt.template_path,
        pipeline_version="test-pipeline@0.0.0",
        contract_set_version=contract_set_version,
    )


def test_late_stages_preserve_active_v1_2_contract_set(tmp_path: Path) -> None:
    folder = _copy_us1_with_contract(tmp_path, "1.2.0")

    edge_path = _run_stub_extract(folder, contract_set_version="1.2.0")
    edge_payload = json.loads(edge_path.read_text(encoding="utf-8"))
    assert edge_payload["contract_set_version"] == "1.2.0"

    routing_path, routing = router_run(
        folder,
        pipeline_version="test-pipeline@0.0.0",
        policy_version="test-policy@0.0.0",
        contract_set_version="1.2.0",
    )
    assert routing["contract_set_version"] == "1.2.0"

    final_path = assembler_run(
        AssemblerInvocation(
            document_folder=folder,
            pipeline_version="test-pipeline@0.0.0",
            contract_set_version="1.2.0",
        )
    )
    final_payload = json.loads(final_path.read_text(encoding="utf-8"))
    assert final_payload["contract_set_version"] == "1.2.0"

    expected = {
        edge_path: ArtifactName.EDGE_EXTRACTION_OUTPUT,
        routing_path: ArtifactName.ROUTING_DECISION,
        final_path: ArtifactName.FINAL_STRUCTURED_PAYLOAD,
    }
    for path, artifact_name in expected.items():
        outcome = validate_artifact(path, artifact_name, version="1.2.0")
        assert outcome.passed, outcome.violations


def test_extract_rejects_controller_contract_mismatch(tmp_path: Path) -> None:
    folder = _copy_us1_with_contract(tmp_path, "1.0.0")

    with pytest.raises(InputContractDrift) as exc_info:
        _run_stub_extract(folder, contract_set_version="1.2.0")

    assert "requested contract_set_version='1.2.0'" in str(exc_info.value)
