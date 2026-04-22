"""SC-009: every visible email/URL/phone/EIN in the easy-bucket corpus surfaces in the packet."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlinc_ocr.evidence_packet import assemble_from_preprocess
from ledgerlinc_ocr.evidence_packet.regex_hints import (
    EIN_RE,
    EMAIL_RE,
    URL_RE,
    US_PHONE_RE,
)

_CORPUS_ROOT = Path(__file__).resolve().parents[2] / "stage1_vendor_identity"


def _easy_folders():
    if not _CORPUS_ROOT.is_dir():
        return []
    out = []
    for folder in sorted(_CORPUS_ROOT.iterdir()):
        if not folder.is_dir():
            continue
        if not folder.name.endswith("_easy"):
            continue
        if (folder / "preprocess_output.json").is_file():
            out.append(folder)
    return out


_EASY_FOLDERS = _easy_folders()


@pytest.mark.skipif(
    not _EASY_FOLDERS, reason="no easy-bucket corpus with preprocess_output on this branch"
)
@pytest.mark.parametrize("folder", _EASY_FOLDERS, ids=lambda p: p.name)
def test_sc009_recall_on_easy_corpus(folder: Path):
    preprocess = json.loads((folder / "preprocess_output.json").read_text())
    packet = assemble_from_preprocess(preprocess)
    document_text = packet["document_text"]
    signals = packet["candidate_vendor_signals"]

    expected = {
        "emails": [m.group(0) for m in EMAIL_RE.finditer(document_text)],
        "websites": [m.group(0) for m in URL_RE.finditer(document_text)],
        "phones": [m.group(0) for m in US_PHONE_RE.finditer(document_text)],
        "tax_ids": [m.group(0) for m in EIN_RE.finditer(document_text)],
    }

    for category, expected_values in expected.items():
        actual_values = [h["value"] for h in signals[category]]
        for value in expected_values:
            assert value in actual_values, (
                f"{folder.name}: expected {category} value "
                f"{value!r} missing from packet"
            )
