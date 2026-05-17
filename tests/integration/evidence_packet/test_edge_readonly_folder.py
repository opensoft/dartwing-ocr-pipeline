"""Edge case: DEBUG against a read-only folder surfaces exit 5 without losing the packet."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from dartwing_ocr.evidence_packet import assemble_from_preprocess

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="chmod-based read-only check is POSIX-only"
)

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "evidence_packet"


def test_debug_readonly_folder_exit_5(tmp_path):
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    fixture = json.loads((_FIXTURE_DIR / "minimal_valid.json").read_text())
    (folder / "preprocess_output.json").write_text(
        json.dumps(fixture), encoding="utf-8"
    )

    # Make folder read-only so write_atomic's rename/replace fails.
    os.chmod(folder, 0o500)
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "dartwing_ocr.evidence_packet",
                str(folder),
                "-v",
            ],
            capture_output=True,
            text=True,
        )
    finally:
        # Restore write permission so pytest can clean up tmp_path.
        os.chmod(folder, 0o700)

    if result.returncode == 0:
        pytest.skip("filesystem allows writes despite chmod 0o500 (e.g. root/overlayfs)")

    assert result.returncode == 5, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["status"] == "error"
    assert payload["kind"] == "persistence_failed"

    # The library-level pure path still returns a valid packet — persistence
    # failure is not an assembly failure.
    packet = assemble_from_preprocess(fixture)
    assert packet["contract_set_version"] == "1.2.0"
