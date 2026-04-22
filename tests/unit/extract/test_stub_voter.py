"""T020: StubVoter reads fixture body; missing fixture is a config error."""

from __future__ import annotations

import pytest

from ledgerlinc_ocr.extract.errors import VoterConfigInvalid
from ledgerlinc_ocr.extract.voters.stub import StubVoter


def test_reads_fixture_body(tmp_path) -> None:
    fixture = tmp_path / "voter_response.json"
    fixture.write_text('{"ok": true}\n', encoding="utf-8")

    voter = StubVoter(fixture_path=fixture)
    response = voter.call("ignored-prompt", config=None)

    assert response.body == '{"ok": true}\n'
    assert response.duration_ms == 0
    assert response.done is True
    assert response.model_echo is None


def test_missing_fixture_raises_voter_config_invalid(tmp_path) -> None:
    missing = tmp_path / "nope.json"
    voter = StubVoter(fixture_path=missing)

    with pytest.raises(VoterConfigInvalid) as exc_info:
        voter.call("ignored", config=None)

    assert str(missing) in exc_info.value.detail["path"]


def test_extensions_carry_fixture_path(tmp_path) -> None:
    fixture = tmp_path / "voter_response.json"
    fixture.write_text("x", encoding="utf-8")

    voter = StubVoter(extensions={"x_fixture_path": str(fixture)})
    assert voter.call("", config=None).body == "x"


def test_missing_extension_key_errors() -> None:
    with pytest.raises(VoterConfigInvalid):
        StubVoter(extensions={})
