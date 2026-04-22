"""US5 integration tests — hard failures (T067-T071, T089)."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import yaml

from ledgerlinc_ocr.extract.cli import main as extract_main

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIX_ROOT = _REPO_ROOT / "tests" / "fixtures" / "extract"


def _no_artifact(folder: Path) -> None:
    assert not (folder / "edge_extraction_output.json").exists(), (
        f"artifact should NOT be written on hard failure; found one in {folder}"
    )


def test_ac1_ollama_unreachable(
    us1_happy_folder: Path, tmp_path: Path, monkeypatch, caplog
) -> None:
    """US5 AC#1 (Ollama path): unreachable host → exit 3, no artifact."""

    # Point at a closed port. Rewrite the us1_happy config to an Ollama provider.
    cfg_path = us1_happy_folder / "voter_config.yaml"
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    raw["model_runtime"]["provider"] = "ollama"
    raw.pop("x_fixture_path", None)
    cfg_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")

    with caplog.at_level("ERROR"):
        rc = extract_main(
            ["--folder", str(us1_happy_folder), "--voter", "stub",
             "--voter-config", str(cfg_path)]
        )
    assert rc == 3
    _no_artifact(us1_happy_folder)
    msg = caplog.text.lower()
    assert "unreachable" in msg or "could not connect" in msg


def test_ac1_contract_drift(us5_failure_folder, caplog) -> None:
    """US5 AC#1 (input path): contract_set_version drift → exit 2, no artifact."""

    folder = us5_failure_folder("drift_folder")
    with caplog.at_level("ERROR"):
        rc = extract_main(
            ["--folder", str(folder), "--voter", "stub",
             "--voter-config", str(folder / "voter_config.yaml")]
        )
    assert rc == 2
    _no_artifact(folder)
    assert "contract_set_version" in caplog.text


def test_ac1_schema_invalid_input(us5_failure_folder) -> None:
    """US5 AC#1 (input path): schema-invalid packet → exit 2, no artifact."""

    folder = us5_failure_folder("schema_invalid_folder")
    rc = extract_main(
        ["--folder", str(folder), "--voter", "stub",
         "--voter-config", str(folder / "voter_config.yaml")]
    )
    assert rc == 2
    _no_artifact(folder)


def test_config_invalid(tmp_path: Path, us1_happy_folder: Path) -> None:
    """Broken YAML at --voter-config → exit 6, no artifact."""

    broken = tmp_path / "broken.yaml"
    broken.write_text("voter_id: [not-a-string,\n", encoding="utf-8")

    rc = extract_main(
        ["--folder", str(us1_happy_folder), "--voter", "stub",
         "--voter-config", str(broken)]
    )
    assert rc == 6
    _no_artifact(us1_happy_folder)


def test_ac4_unrepairable_response(us5_failure_folder) -> None:
    """US5 AC#4: unrepairable voter body → exit 5, no artifact."""

    folder = us5_failure_folder("unrepairable")
    rc = extract_main(
        ["--folder", str(folder), "--voter", "stub",
         "--voter-config", str(folder / "voter_config.yaml")]
    )
    assert rc == 5
    _no_artifact(folder)


def test_empty_response(us5_failure_folder) -> None:
    """Empty voter body → exit 5, no artifact (UnrepairableResponse)."""

    folder = us5_failure_folder("empty_response")
    rc = extract_main(
        ["--folder", str(folder), "--voter", "stub",
         "--voter-config", str(folder / "voter_config.yaml")]
    )
    assert rc == 5
    _no_artifact(folder)


def test_ac1_model_unavailable(
    us1_happy_folder: Path, monkeypatch, caplog
) -> None:
    """T089 / analysis C1: Ollama returns `model not found` → exit 4, no artifact."""

    # Switch the config to Ollama provider with a fake model tag.
    cfg_path = us1_happy_folder / "voter_config.yaml"
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    raw["model_runtime"]["provider"] = "ollama"
    raw["ollama"]["model_tag"] = "fake-model:edge"
    raw.pop("x_fixture_path", None)
    cfg_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:65535")

    # Patch httpx.Client.post to return the "model not found" payload.
    class _FakeResponse:
        status_code = 404

        def json(self):
            return {
                "error": "model 'fake-model:edge' not found, try pulling it first"
            }

        text = '{"error":"model not found"}'

    def _fake_post(self, url, json=None, **kwargs):  # noqa: A002
        return _FakeResponse()

    with caplog.at_level("ERROR"), patch.object(httpx.Client, "post", _fake_post):
        rc = extract_main(
            ["--folder", str(us1_happy_folder), "--voter", "stub",
             "--voter-config", str(cfg_path)]
        )

    assert rc == 4
    _no_artifact(us1_happy_folder)
    assert "fake-model:edge" in caplog.text
    msg = caplog.text.lower()
    assert "unavailable" in msg or "not found" in msg
