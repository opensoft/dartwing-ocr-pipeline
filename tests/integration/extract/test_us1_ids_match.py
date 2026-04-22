"""US1 AC#2 — document_id, contract_set_version, pipeline_version, processed_at are present and consistent."""

from __future__ import annotations

import json
import re
from pathlib import Path

_ISO8601_UTC = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"
)


def test_ac2_ids_and_timestamps(us1_happy_folder: Path, run_extractor, load_output) -> None:
    rc = run_extractor(us1_happy_folder, us1_happy_folder / "voter_config.yaml")
    assert rc == 0

    packet = json.loads((us1_happy_folder / "preprocess_output.json").read_text(encoding="utf-8"))
    payload = load_output(us1_happy_folder)

    assert payload["document_id"] == packet["document_id"]
    assert payload["contract_set_version"] == "1.0.0"

    pv = payload["pipeline_version"]
    assert isinstance(pv, str) and pv, "pipeline_version must be a non-empty string"

    processed_at = payload["processed_at"]
    assert isinstance(processed_at, str)
    assert _ISO8601_UTC.match(processed_at), f"processed_at not ISO-8601 UTC with Z: {processed_at!r}"
