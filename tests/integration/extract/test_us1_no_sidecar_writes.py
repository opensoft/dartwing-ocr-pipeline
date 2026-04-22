"""US1 AC#6 — extractor writes exactly one artifact file and no sidecar/tmp files linger."""

from __future__ import annotations

from pathlib import Path


def test_ac6_folder_write_boundaries(us1_happy_folder: Path, run_extractor) -> None:
    before = {p.name for p in us1_happy_folder.iterdir()}

    rc = run_extractor(us1_happy_folder, us1_happy_folder / "voter_config.yaml")
    assert rc == 0

    after = {p.name for p in us1_happy_folder.iterdir()}
    new_files = after - before

    assert new_files == {"edge_extraction_output.json"}, (
        f"extractor introduced unexpected files: {sorted(new_files)}"
    )
    # No leftover tmp files.
    for name in after:
        assert ".tmp-" not in name, f"leftover tmp file: {name}"
        assert not name.endswith(".tmp"), f"leftover tmp file: {name}"
