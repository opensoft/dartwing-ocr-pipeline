"""T069: self-consistency checks between contract_set.json, report.py, and the
human-facing documentation layer."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ledgerlinc_ocr.validator import load_contract_set
from ledgerlinc_ocr.validator.report import ViolationCode

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATASET_LAYOUT_PATH = (
    _REPO_ROOT / "docs" / "stage1-vendor-identity" / "dataset-layout.md"
)


def _known_violation_codes() -> set[str]:
    return {
        v
        for k, v in vars(ViolationCode).items()
        if not k.startswith("_") and isinstance(v, str)
    }


def test_cross_artifact_rules_are_real_violation_codes() -> None:
    cs = load_contract_set("1.0.0")
    known = _known_violation_codes()
    for rule in cs.cross_artifact_rules:
        assert rule in known, f"{rule} referenced in contract_set.json is not a known ViolationCode"


def test_every_registered_schema_file_exists_and_is_non_empty() -> None:
    cs = load_contract_set("1.0.0")
    for name, path in cs.artifact_schemas.items():
        assert path.is_file(), f"schema file missing for {name}: {path}"
        content = path.read_text(encoding="utf-8").strip()
        assert content and content != "{}", f"schema file is empty/placeholder for {name}: {path}"


def test_folder_schema_file_exists_and_is_non_empty() -> None:
    cs = load_contract_set("1.0.0")
    content = cs.folder_schema.read_text(encoding="utf-8").strip()
    assert content and content != "{}"


def test_challenge_tags_all_appear_in_dataset_layout() -> None:
    cs = load_contract_set("1.0.0")
    doc_text = _DATASET_LAYOUT_PATH.read_text(encoding="utf-8")
    for tag in cs.challenge_tags:
        assert re.search(rf"\b{re.escape(tag)}\b", doc_text), (
            f"challenge_tag {tag!r} listed in contract_set.json is not "
            f"documented in {_DATASET_LAYOUT_PATH}"
        )


def test_contract_set_version_matches_directory_name() -> None:
    cs = load_contract_set("1.0.0")
    assert cs.version_dir.name == f"v{cs.version}"


def test_amendments_md_has_v1_0_0_entry() -> None:
    amendments_path = (
        _REPO_ROOT / "contracts" / "stage1_vendor_identity" / "AMENDMENTS.md"
    )
    assert amendments_path.is_file()
    text = amendments_path.read_text(encoding="utf-8")
    assert "v1.0.0" in text
    assert "Amendment Checklist" in text
