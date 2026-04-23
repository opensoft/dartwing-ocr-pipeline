"""T022 / US1 AC#7: the router writes ONLY routing_decision.json.

Stage a folder with peer artifacts + a ``votes/`` dir, run the CLI, confirm
every non-output file's content hash + mtime are untouched, and that no
file is created outside the folder.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

RESERVED_NAMES = (
    "final_structured_payload.json",
    "evaluation_document.json",
)


def _fingerprint(path: Path) -> tuple[float, str]:
    return (
        os.path.getmtime(path),
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def test_router_leaves_peers_and_votes_untouched(
    tmp_path: Path, stage_fixture, run_cli
):
    folder = stage_fixture(tmp_path, "clean_explicit_name_full_identity.json")

    peers = {
        "preprocess_output.json": b'{"preprocess": "placeholder"}',
        "expected.json": b'{"expected": "placeholder"}',
        "notes.md": b"notes\n",
        "source.pdf": b"%PDF-1.4\n%placeholder\n",
    }
    for name, content in peers.items():
        (folder / name).write_bytes(content)
    (folder / "votes").mkdir()
    (folder / "votes" / "voter_a.json").write_bytes(b'{"voter": "a"}')

    peer_fingerprints = {
        name: _fingerprint(folder / name) for name in peers
    }
    votes_fp = _fingerprint(folder / "votes" / "voter_a.json")

    result = run_cli(folder)
    assert result.returncode == 0, result.stderr

    expected_names = set(peers) | {
        "edge_extraction_output.json",
        "routing_decision.json",
        "votes",
    }
    assert {p.name for p in folder.iterdir()} == expected_names

    for name in peers:
        assert _fingerprint(folder / name) == peer_fingerprints[name], name

    assert _fingerprint(folder / "votes" / "voter_a.json") == votes_fp

    for reserved in RESERVED_NAMES:
        assert not (folder / reserved).exists(), reserved
