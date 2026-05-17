"""T019: R-011 exit-code table and error→code mapping."""

from __future__ import annotations

from dartwing_ocr.extract import exit_codes
from dartwing_ocr.extract.errors import (
    FolderWriteError,
    InputContractDrift,
    MalformedResponse,
    OllamaModelUnavailable,
    OllamaUnreachable,
    UnrepairableResponse,
    VoterConfigInvalid,
)


def test_table_matches_r011() -> None:
    assert exit_codes.EXIT_OK == 0
    assert exit_codes.EXIT_UNEXPECTED == 1
    assert exit_codes.EXIT_INPUT_CONTRACT_DRIFT == 2
    assert exit_codes.EXIT_OLLAMA_UNREACHABLE == 3
    assert exit_codes.EXIT_MODEL_UNAVAILABLE == 4
    assert exit_codes.EXIT_UNREPAIRABLE_RESPONSE == 5
    assert exit_codes.EXIT_VOTER_CONFIG_INVALID == 6
    assert exit_codes.EXIT_FOLDER_WRITE == 7


def test_for_error_mapping() -> None:
    assert exit_codes.for_error(InputContractDrift("x")) == 2
    assert exit_codes.for_error(OllamaUnreachable("x")) == 3
    assert exit_codes.for_error(OllamaModelUnavailable("x")) == 4
    assert exit_codes.for_error(UnrepairableResponse("x")) == 5
    assert exit_codes.for_error(MalformedResponse("x")) == 5
    assert exit_codes.for_error(VoterConfigInvalid("x")) == 6
    assert exit_codes.for_error(FolderWriteError("x")) == 7


def test_unknown_exception_is_unexpected() -> None:
    assert exit_codes.for_error(RuntimeError("boom")) == 1
    assert exit_codes.for_error(ValueError("boom")) == 1
