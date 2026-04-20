"""T042: CLI never writes off-limits names (votes/, consensus_output.json)."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from ledgerlinc_ocr.pipeline.cli import main
from ledgerlinc_ocr.pipeline.runner import RESERVED_ARTIFACT_NAMES


def test_off_limits_preexisting_files_untouched(
    tmp_document_folder: Callable[..., Path],
):
    folder = tmp_document_folder(1, "easy")
    consensus = folder / "consensus_output.json"
    votes = folder / "votes"
    consensus.write_text('{"reserved":"for-voting-feature"}', encoding="utf-8")
    votes.mkdir()
    (votes / "voter1.json").write_text('{"v":1}', encoding="utf-8")

    expected_consensus = consensus.read_bytes()
    expected_voter = (votes / "voter1.json").read_bytes()

    code = main(["run", "--document-folder", str(folder)])
    assert code == 0

    assert consensus.read_bytes() == expected_consensus
    assert (votes / "voter1.json").read_bytes() == expected_voter
    for name in RESERVED_ARTIFACT_NAMES:
        assert (folder / name).is_file()
