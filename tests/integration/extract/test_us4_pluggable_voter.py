"""US4 integration tests (T057-T061) — pluggable voter shape."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from dartwing_ocr.extract.config import VoterConfig, load_voter_config
from dartwing_ocr.extract.errors import VoterConfigInvalid

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GEMMA_CONFIG = (
    _REPO_ROOT / "src" / "dartwing_ocr" / "extract" / "voters" / "configs" / "gemma-edge.yaml"
)


def _patch_gemma_to_stub(src: Path, dest_folder: Path, fixture_name: str) -> Path:
    """Copy the packaged gemma-edge.yaml into `dest_folder`, rewrite `provider`
    to "stub" and inject `x_fixture_path`, plus flip `prompt.template_path` to
    the local stub_noop.md. Returns the rewritten config path.
    """

    raw = yaml.safe_load(src.read_text(encoding="utf-8"))
    raw["model_runtime"]["provider"] = "stub"
    raw["prompt"]["template_path"] = "stub_noop.md"
    raw["x_fixture_path"] = fixture_name
    out = dest_folder / "voter_config.yaml"
    out.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return out


def test_ac1_stage_1_gemma_runtime_fields(us1_happy_folder: Path, run_extractor, load_output) -> None:
    """US4 AC#1: gemma-edge.yaml's model_runtime fields plumb into the artifact."""
    gemma_stub_config = _patch_gemma_to_stub(
        _GEMMA_CONFIG, us1_happy_folder, "voter_response_clean.json"
    )

    rc = run_extractor(us1_happy_folder, gemma_stub_config)
    assert rc == 0

    runtime = load_output(us1_happy_folder)["model_runtime"]
    # Every required field non-empty; matches the (patched) config.
    for key in ("provider", "model_name", "model_version", "runtime"):
        assert runtime[key], f"model_runtime.{key} empty"

    assert runtime["model_name"] == "gemma-4-e4b"
    assert runtime["model_version"] == "2026-04-14-rocm"
    assert runtime["runtime"] == "ollama-rocm-linux-host"


def test_ac2_vote_metadata_pinned_values(us1_happy_folder: Path, run_extractor, load_output) -> None:
    rc = run_extractor(us1_happy_folder, us1_happy_folder / "voter_config.yaml")
    assert rc == 0

    vm = load_output(us1_happy_folder)["vote_metadata"]
    assert vm["voter_id"] and isinstance(vm["voter_id"], str)
    assert vm["voter_role"] == "primary_extractor"
    assert vm["consensus_mode"] == "single_voter_baseline"


def test_ac3_swap_voter_no_code_change(
    us1_happy_folder: Path, us4_qwen_sim_folder: Path, run_extractor, load_output
) -> None:
    """US4 AC#3: two runs against two different voter configs produce identically-shaped
    artifacts differing only in model_runtime and vote_metadata.voter_id."""
    rc1 = run_extractor(us1_happy_folder, us1_happy_folder / "voter_config.yaml")
    assert rc1 == 0
    a = load_output(us1_happy_folder)

    rc2 = run_extractor(us4_qwen_sim_folder, us4_qwen_sim_folder / "voter_config.yaml")
    assert rc2 == 0
    b = load_output(us4_qwen_sim_folder)

    # Identical top-level keys and sub-structure.
    def _structure(obj):
        if isinstance(obj, dict):
            return {k: _structure(v) for k, v in sorted(obj.items())}
        if isinstance(obj, list):
            return "[]" if not obj else [_structure(obj[0])]
        return type(obj).__name__

    # Differing only in document_id + pipeline_version + processed_at + runtime/metadata
    # + values that differ per voter. Structure (types + keys) must match byte-equally.
    assert json.dumps(_structure(a), sort_keys=True) == json.dumps(_structure(b), sort_keys=True)

    # Differences where expected
    assert a["model_runtime"] != b["model_runtime"]
    assert a["vote_metadata"]["voter_id"] != b["vote_metadata"]["voter_id"]


def test_ac4_artifact_filename_stable(us1_happy_folder: Path, run_extractor) -> None:
    # Run once
    rc1 = run_extractor(us1_happy_folder, us1_happy_folder / "voter_config.yaml")
    assert rc1 == 0
    first_mtime = (us1_happy_folder / "edge_extraction_output.json").stat().st_mtime_ns

    # Run again with a different config (simulating a second voter) → same filename, overwrites.
    gemma_stub_config = _patch_gemma_to_stub(
        _GEMMA_CONFIG, us1_happy_folder, "voter_response_clean.json"
    )
    rc2 = run_extractor(us1_happy_folder, gemma_stub_config)
    assert rc2 == 0

    final_path = us1_happy_folder / "edge_extraction_output.json"
    assert final_path.is_file()
    # No votes/ subdirectory.
    assert not (us1_happy_folder / "votes").exists()
    # Only one edge_extraction_output.json, no sidecars.
    outputs = list(us1_happy_folder.glob("edge_extraction_output*.json"))
    assert outputs == [final_path], f"unexpected artifact sidecars: {outputs}"
    # File was actually re-written (mtime moved forward or stayed; mainly: still exists).
    assert final_path.stat().st_mtime_ns >= first_mtime


def test_ac5_voter_role_enum_coverage(tmp_path: Path) -> None:
    """US4 AC#5: pydantic accepts `voter_role: secondary_extractor`, but the
    pipeline runtime refuses it at stage 1."""
    # Build a stub config with voter_role=secondary_extractor.
    src = _REPO_ROOT / "tests" / "fixtures" / "extract" / "us1_happy"
    dest = tmp_path / "us4_secondary"
    shutil.copytree(src, dest)

    cfg_path = dest / "voter_config.yaml"
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    raw["voter_role"] = "secondary_extractor"
    cfg_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    # Schema-level: pydantic accepts it.
    config, _, _ = load_voter_config(str(cfg_path), base_dir=Path.cwd())
    assert isinstance(config, VoterConfig)
    assert config.voter_role == "secondary_extractor"

    # Runtime-level: pipeline raises VoterConfigInvalid.
    from dartwing_ocr.extract import pipeline as pipeline_mod
    from dartwing_ocr.extract.voters.stub import StubVoter

    voter = StubVoter(extensions={"x_fixture_path": "voter_response_clean.json"}, config_dir=dest)

    with pytest.raises(VoterConfigInvalid):
        pipeline_mod.run(
            folder_path=dest,
            voter_config=config,
            voter=voter,
            template_path=dest / "stub_noop.md",
        )
