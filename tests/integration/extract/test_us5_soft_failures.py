"""US5 integration tests — soft failures (T072-T076, T090)."""

from __future__ import annotations

import json
from pathlib import Path

from dartwing_ocr.extract.cli import main as extract_main
from dartwing_ocr.validator import ArtifactName, validate_artifact


def _load(folder: Path) -> dict:
    return json.loads((folder / "edge_extraction_output.json").read_text(encoding="utf-8"))


def _run(folder: Path) -> int:
    return extract_main(
        ["--folder", str(folder), "--voter", "stub",
         "--voter-config", str(folder / "voter_config.yaml")]
    )


def test_ac2_json_repair_warns(us5_failure_folder) -> None:
    """US5 AC#2: fenced/prose-wrapped JSON repairs; status=partial; warnings names repair."""

    folder = us5_failure_folder("malformed_json")
    assert _run(folder) == 0
    payload = _load(folder)
    assert payload["status"] == "partial"
    repair_msgs = [w for w in payload["warnings"] if "repaired" in w.lower()]
    assert repair_msgs, f"expected a repair warning, got {payload['warnings']}"


def test_ac3_missing_subfield_defaulted(us5_failure_folder) -> None:
    """US5 AC#3: missing vat_id → defaulted to null shape; status=partial; warning names it."""

    folder = us5_failure_folder("missing_subfield")
    assert _run(folder) == 0
    payload = _load(folder)
    assert payload["status"] == "partial"

    vat = payload["vendor_candidate"]["tax_ids"]["vat_id"]
    assert vat == {"value": None, "confidence": 0.0, "evidence": []}
    assert any("vendor_candidate/tax_ids/vat_id" in w for w in payload["warnings"])


def test_ac4_blank_packet_failure_status(us5_failure_folder) -> None:
    """US5 AC#4 artifact path: blank packet + all-null model response → status=failure."""

    folder = us5_failure_folder("blank_packet")
    assert _run(folder) == 0
    payload = _load(folder)
    assert payload["status"] == "failure"

    # every value null, every evidence empty
    cn = payload["vendor_candidate"]["company_name"]
    assert cn["value"] is None
    assert cn["evidence"] == []
    for field_group in (
        payload["vendor_candidate"]["address"],
        payload["vendor_candidate"]["tax_ids"],
    ):
        for v in field_group.values():
            assert v["value"] is None
            assert v["evidence"] == []
    assert payload["invoice_header_fields"]["total_amount"]["value"] is None
    assert payload["invoice_header_fields"]["total_amount"]["evidence"] == []
    assert payload["warnings"], "failure status must carry at least one warning"


def test_ac5_warnings_are_informative(us5_failure_folder) -> None:
    """US5 AC#5: every warning from soft-failure paths is a non-empty string."""

    for name in ("malformed_json", "missing_subfield", "blank_packet"):
        folder = us5_failure_folder(name)
        assert _run(folder) == 0
        payload = _load(folder)
        for w in payload["warnings"]:
            assert isinstance(w, str) and w.strip(), (
                f"empty/non-string warning in {name}: {w!r}"
            )


def test_ac6_schema_valid_regardless_of_status(us5_failure_folder) -> None:
    """US5 AC#6: every soft-failure artifact validates against the frozen schema."""

    for name in ("malformed_json", "missing_subfield", "blank_packet"):
        folder = us5_failure_folder(name)
        assert _run(folder) == 0

        outcome = validate_artifact(
            folder / "edge_extraction_output.json",
            ArtifactName.EDGE_EXTRACTION_OUTPUT,
        )
        assert outcome.passed, (
            f"{name}: schema validation failed: "
            f"{[(v.field_path, v.violation_code) for v in outcome.violations]}"
        )


def test_partial_input_propagation(us5_partial_input_folder: Path) -> None:
    """T090 / FR-023: input-side partiality surfaces in extraction_notes or warnings."""

    rc = extract_main(
        ["--folder", str(us5_partial_input_folder), "--voter", "stub",
         "--voter-config", str(us5_partial_input_folder / "voter_config.yaml")]
    )
    assert rc == 0
    payload = _load(us5_partial_input_folder)
    assert payload["status"] in {"success", "partial"}
    blob = "\n".join(payload["extraction_notes"]) + "\n" + "\n".join(payload["warnings"])
    assert "falcon_perception" in blob or "preprocessing was partial" in blob
