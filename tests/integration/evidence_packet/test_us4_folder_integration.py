"""US4 acceptance: folder-contract integration."""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
from pathlib import Path

from jsonschema import Draft202012Validator

from ledgerlinc_ocr.evidence_packet import assemble_from_folder

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "evidence_packet"
_PACKET_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "stage1_vendor_identity"
    / "v1.2.0"
    / "evidence_packet.schema.json"
)

_SIBLING_FILES = {
    "source.pdf": b"%PDF-1.4 fake pdf bytes",
    "edge_extraction_output.json": b'{"trace": "dummy"}',
    "routing_decision.json": b'{"decision": "dummy"}',
    "final_structured_payload.json": b'{"payload": "dummy"}',
}


def _seed_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    shutil.copyfile(
        _FIXTURE_DIR / "minimal_valid.json", folder / "preprocess_output.json"
    )
    for name, data in _SIBLING_FILES.items():
        (folder / name).write_bytes(data)
    return folder


def _hash_everything(folder: Path) -> dict[str, str]:
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.iterdir())
        if p.is_file()
    }


def test_ac1_default_reads_only_preprocess_writes_nothing(tmp_path):
    folder = _seed_folder(tmp_path)
    before = _hash_everything(folder)
    assemble_from_folder(folder)
    after = _hash_everything(folder)
    assert before == after
    assert not (folder / "evidence_packet.json").exists()


def test_ac2_debug_writes_packet_validates(tmp_path, caplog):
    folder = _seed_folder(tmp_path)
    siblings_before = {
        name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
        for name in _SIBLING_FILES
    }

    with caplog.at_level(logging.DEBUG, logger="ledgerlinc_ocr"):
        assemble_from_folder(folder)

    packet_path = folder / "evidence_packet.json"
    assert packet_path.exists()

    schema = json.loads(_PACKET_SCHEMA_PATH.read_text())
    validator = Draft202012Validator(schema)
    packet = json.loads(packet_path.read_text())
    errors = sorted(validator.iter_errors(packet), key=lambda e: list(e.absolute_path))
    assert errors == [], [e.message for e in errors]

    for name, digest in siblings_before.items():
        current = hashlib.sha256((folder / name).read_bytes()).hexdigest()
        assert current == digest, name


def test_ac3_folder_validator_accepts_both_states(tmp_path, caplog):
    """Adding evidence_packet.json to a folder must NOT introduce new
    folder-contract violations. We don't require the seeded folder to pass
    outright (it is synthetic — expected.json, required artifacts, etc. are
    absent); we only assert that the error/warning footprint is unchanged
    between packet-absent and packet-present states.
    """
    folder = _seed_folder(tmp_path)

    from ledgerlinc_ocr.validator.folder import validate_folder
    from ledgerlinc_ocr.validator.loader import load_contract_set

    contract_set = load_contract_set()

    def _fingerprint(outcome):
        def _keys(vs):
            def _code(v):
                code = v.violation_code
                return code.value if hasattr(code, "value") else code

            return sorted((v.target, v.field_path, _code(v)) for v in vs)

        return {
            "errors": _keys(outcome.violations),
            "warnings": _keys(outcome.warnings),
        }

    absent_outcome = validate_folder(folder, contract_set=contract_set)
    absent_fingerprint = _fingerprint(absent_outcome)

    with caplog.at_level(logging.DEBUG, logger="ledgerlinc_ocr"):
        assemble_from_folder(folder)
    assert (folder / "evidence_packet.json").is_file()

    present_outcome = validate_folder(folder, contract_set=contract_set)
    present_fingerprint = _fingerprint(present_outcome)

    assert present_fingerprint == absent_fingerprint, (
        "folder validator treated evidence_packet.json differently:\n"
        f"  absent: {absent_fingerprint}\n"
        f"  present: {present_fingerprint}"
    )
