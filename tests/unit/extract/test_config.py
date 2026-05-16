"""T018: voter-config loader happy path + pydantic rejections."""

from __future__ import annotations

import textwrap

import pytest

from ledgerlinc_ocr.extract.config import load_voter_config
from ledgerlinc_ocr.extract.errors import VoterConfigInvalid


def test_packaged_stub_loads_cleanly() -> None:
    config, path, extensions = load_voter_config("stub")
    assert config.voter_id == "stub@test"
    assert config.voter_role == "primary_extractor"
    assert config.consensus_mode == "single_voter_baseline"
    assert config.model_runtime.provider == "stub"
    assert config.reconciliation.ungrounded_confidence_cap == pytest.approx(0.30)
    assert path.name == "stub.yaml"
    assert extensions == {}


def test_packaged_gemma_edge_e2b_loads_cleanly() -> None:
    config, path, extensions = load_voter_config("gemma-edge-e2b")
    assert config.voter_id == "gemma-4-e2b-edge@2026-04-test"
    assert config.model_runtime.provider == "host_ollama"
    assert config.model_runtime.model_name == "gemma-4-e2b"
    assert config.ollama.model_tag == "gemma4:e2b"
    assert config.prompt.template_path == "prompts/gemma_edge_extractor.md"
    assert path.name == "gemma-edge-e2b.yaml"
    assert extensions == {}


def _write(tmp_path, body: str):
    p = tmp_path / "voter.yaml"
    p.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return p


_BASE = """\
voter_id: "v"
voter_role: "primary_extractor"
consensus_mode: "single_voter_baseline"
model_runtime:
  provider: "p"
  model_name: "m"
  model_version: "v"
  runtime: "r"
ollama:
  model_tag: "t"
sampling: {}
prompt:
  template_path: "prompts/x.md"
reconciliation: {}
"""


def test_unknown_top_level_key_rejected(tmp_path) -> None:
    p = _write(tmp_path, _BASE + "bogus: true\n")
    with pytest.raises(VoterConfigInvalid):
        load_voter_config(str(p))


def test_invalid_voter_role_rejected(tmp_path) -> None:
    body = _BASE.replace('voter_role: "primary_extractor"', 'voter_role: "admin"')
    p = _write(tmp_path, body)
    with pytest.raises(VoterConfigInvalid):
        load_voter_config(str(p))


def test_invalid_consensus_mode_rejected(tmp_path) -> None:
    body = _BASE.replace(
        'consensus_mode: "single_voter_baseline"',
        'consensus_mode: "three_voter"',
    )
    p = _write(tmp_path, body)
    with pytest.raises(VoterConfigInvalid):
        load_voter_config(str(p))


def test_negative_timeout_rejected(tmp_path) -> None:
    body = _BASE.replace(
        'ollama:\n  model_tag: "t"',
        'ollama:\n  model_tag: "t"\n  timeout_seconds: -1.0',
    )
    p = _write(tmp_path, body)
    with pytest.raises(VoterConfigInvalid):
        load_voter_config(str(p))


def test_ungrounded_cap_above_one_rejected(tmp_path) -> None:
    body = _BASE.replace(
        "reconciliation: {}",
        "reconciliation:\n  ungrounded_confidence_cap: 1.5",
    )
    p = _write(tmp_path, body)
    with pytest.raises(VoterConfigInvalid):
        load_voter_config(str(p))


def test_malformed_yaml_rejected(tmp_path) -> None:
    p = tmp_path / "voter.yaml"
    p.write_text("voter_id: [unclosed\n", encoding="utf-8")
    with pytest.raises(VoterConfigInvalid):
        load_voter_config(str(p))


def test_extension_keys_preserved_out_of_strict_model(tmp_path) -> None:
    body = _BASE + 'x_fixture_path: "./voter_response.json"\n'
    p = _write(tmp_path, body)
    config, _, extensions = load_voter_config(str(p))
    assert extensions == {"x_fixture_path": "./voter_response.json"}
    assert config.voter_id == "v"
