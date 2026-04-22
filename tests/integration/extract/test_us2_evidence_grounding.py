"""US2 integration tests (T041-T045) — evidence grounding end-to-end."""

from __future__ import annotations

import json
import re
from pathlib import Path

_EVIDENCE_ID = re.compile(r"^p\d+_[bl]\d+$")


def _all_evidence_fields(payload: dict):
    vc = payload["vendor_candidate"]
    yield "vendor_candidate/company_name", vc["company_name"]
    for k, v in vc["address"].items():
        yield f"vendor_candidate/address/{k}", v
    for k, v in vc["tax_ids"].items():
        yield f"vendor_candidate/tax_ids/{k}", v
    for k in ("website", "phone", "email"):
        yield f"vendor_candidate/{k}", vc[k]
    hf = payload["invoice_header_fields"]
    for k in ("invoice_number", "invoice_date"):
        yield f"invoice_header_fields/{k}", hf[k]
    yield "invoice_header_fields/total_amount", hf["total_amount"]


def _evidence_index(packet: dict) -> set[str]:
    ids: set[str] = set()
    for page in packet["pages"]:
        for block in page.get("blocks", []):
            ids.add(block["block_id"])
        for line in page.get("raw_ocr_lines", []):
            ids.add(line["line_id"])
    return ids


def test_ac1_every_evidence_resolves(us2_evidence_folder: Path, run_extractor, load_output) -> None:
    rc = run_extractor(us2_evidence_folder, us2_evidence_folder / "voter_config.yaml")
    assert rc == 0

    payload = load_output(us2_evidence_folder)
    packet = json.loads((us2_evidence_folder / "preprocess_output.json").read_text(encoding="utf-8"))
    index = _evidence_index(packet)

    for path, field in _all_evidence_fields(payload):
        for eid in field["evidence"]:
            assert _EVIDENCE_ID.match(eid), f"{path} bad id {eid!r}"
            assert eid in index, f"{path} id {eid!r} not in input packet's evidence_index"


def test_ac2_bogus_ids_filtered_and_warned(us2_evidence_folder: Path, run_extractor, load_output) -> None:
    rc = run_extractor(us2_evidence_folder, us2_evidence_folder / "voter_config.yaml")
    assert rc == 0

    payload = load_output(us2_evidence_folder)
    warnings_blob = "\n".join(payload["warnings"])

    # Pattern-malformed IDs
    assert "postal_code" in warnings_blob and "p1_x5" in warnings_blob
    assert "country" in warnings_blob and "b0" in warnings_blob
    assert "phone" in warnings_blob and "page1_line9" in warnings_blob

    # Pattern-valid but unresolved IDs
    assert "city" in warnings_blob and "p1_l99" in warnings_blob
    assert "state" in warnings_blob and "p2_b1" in warnings_blob
    assert "invoice_number" in warnings_blob and "p1_b99" in warnings_blob

    # Bogus IDs stripped; surviving fields keep only valid ones.
    vc = payload["vendor_candidate"]
    assert vc["address"]["city"]["evidence"] == []
    assert vc["address"]["state"]["evidence"] == []
    assert vc["address"]["postal_code"]["evidence"] == []
    assert vc["address"]["country"]["evidence"] == []
    assert vc["phone"]["evidence"] == []
    assert payload["invoice_header_fields"]["invoice_number"]["evidence"] == []


def test_ac3_empty_evidence_downgrades_confidence(
    us2_evidence_folder: Path, run_extractor, load_output
) -> None:
    rc = run_extractor(us2_evidence_folder, us2_evidence_folder / "voter_config.yaml")
    assert rc == 0

    payload = load_output(us2_evidence_folder)
    cap = 0.30  # voter_config.yaml's ungrounded_confidence_cap

    for path, field in _all_evidence_fields(payload):
        if not field["evidence"]:
            assert field["confidence"] <= cap, (
                f"{path} ungrounded but confidence={field['confidence']!r} > cap"
            )
            # Value is preserved even when evidence is dropped.
            # (No assertion here — some fields legitimately have value=None.)

    # The model values for the ungrounded fields are preserved.
    vc = payload["vendor_candidate"]
    assert vc["address"]["city"]["value"] == "Springfield"
    assert vc["address"]["state"]["value"] == "IL"
    assert vc["phone"]["value"] == "(555) 123-4567"
    assert payload["invoice_header_fields"]["invoice_number"]["value"] == "INV-2026-0420"


def test_ac4_empty_company_name_evidence_forces_override(
    us2_evidence_folder: Path, run_extractor, load_output, tmp_path: Path
) -> None:
    # US2 fixture's company_name has valid evidence. We need a variant where
    # company_name.evidence is entirely bogus so reconciliation strips it.
    import shutil

    dest = tmp_path / "us2_evidence_noname"
    shutil.copytree(us2_evidence_folder, dest)

    response_path = dest / "voter_response_bogus_evidence.json"
    resp = json.loads(response_path.read_text(encoding="utf-8"))
    resp["vendor_candidate"]["company_name"]["evidence"] = ["p9_b9", "xyz"]
    # Even though the model claims the name (value) is populated, we verify the
    # override ignores any `present` claim by injecting one.
    resp["vendor_candidate"]["company_name"]["present"] = True
    response_path.write_text(json.dumps(resp), encoding="utf-8")

    rc = run_extractor(dest, dest / "voter_config.yaml")
    assert rc == 0

    payload = json.loads((dest / "edge_extraction_output.json").read_text(encoding="utf-8"))
    cn = payload["vendor_candidate"]["company_name"]
    assert cn["evidence"] == []
    assert cn["present"] is False
    assert cn["inferred"] is True


def test_ac5_reconciliation_discoverable(
    us2_evidence_folder: Path, run_extractor, load_output
) -> None:
    rc = run_extractor(us2_evidence_folder, us2_evidence_folder / "voter_config.yaml")
    assert rc == 0

    payload = load_output(us2_evidence_folder)
    # Every evidence-drop was recorded in warnings; the only other reconciliation
    # adjustment on this fixture is the cap, which does not itself emit a note —
    # but any field with ungrounded confidence post-cap is discoverable because
    # its evidence==[] says so. Assert there's at least one warning per dropped
    # field.
    warnings = payload["warnings"]
    assert len(warnings) >= 6  # 3 malformed + 3 unresolved, at minimum

    # No reconciliation adjustment fires silently — either status != "success",
    # warnings non-empty, or extraction_notes non-empty.
    assert payload["status"] != "success"
    assert warnings or payload["extraction_notes"]
