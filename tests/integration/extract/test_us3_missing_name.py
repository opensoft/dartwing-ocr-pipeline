"""US3 integration tests (T050-T054) — missing-name invariants enforced at the extractor."""

from __future__ import annotations

from pathlib import Path


def test_ac1_grounded_name_positive_path(
    us3_grounded_name_folder: Path, run_extractor, load_output
) -> None:
    rc = run_extractor(us3_grounded_name_folder, us3_grounded_name_folder / "voter_config.yaml")
    assert rc == 0

    cn = load_output(us3_grounded_name_folder)["vendor_candidate"]["company_name"]
    assert cn["value"] == "Acme Widget Co."
    assert cn["evidence"] != []
    assert cn["present"] is True
    assert cn["inferred"] is False


def test_ac2_guess_present_false_inferred_true(
    us3_missing_name_folder: Path, run_extractor, load_output
) -> None:
    rc = run_extractor(us3_missing_name_folder, us3_missing_name_folder / "voter_config.yaml")
    assert rc == 0

    cn = load_output(us3_missing_name_folder)["vendor_candidate"]["company_name"]
    # Model claimed present=true with a guessed value; extractor overrides.
    assert cn["value"] == "Acme Co"
    assert cn["evidence"] == []
    assert cn["present"] is False
    assert cn["inferred"] is True


def test_ac3_override_recorded_in_notes(
    us3_missing_name_folder: Path, run_extractor, load_output
) -> None:
    rc = run_extractor(us3_missing_name_folder, us3_missing_name_folder / "voter_config.yaml")
    assert rc == 0

    payload = load_output(us3_missing_name_folder)
    blob = "\n".join(payload["extraction_notes"]) + "\n" + "\n".join(payload["warnings"])
    assert "company_name" in blob


def test_ac4_downstream_can_read_provenance(
    us3_missing_name_folder: Path, run_extractor, load_output
) -> None:
    """AC#4: the artifact alone carries enough to derive manual_review_required
    without re-reading preprocess_output.json."""
    rc = run_extractor(us3_missing_name_folder, us3_missing_name_folder / "voter_config.yaml")
    assert rc == 0

    payload = load_output(us3_missing_name_folder)
    cn = payload["vendor_candidate"]["company_name"]

    manual_review_required = (not cn["present"]) and cn["inferred"]
    assert manual_review_required is True


def test_ac5_invariant_pair_across_fixtures(
    us3_missing_name_folder: Path,
    us3_grounded_name_folder: Path,
    run_extractor,
    load_output,
) -> None:
    for folder in (us3_missing_name_folder, us3_grounded_name_folder):
        rc = run_extractor(folder, folder / "voter_config.yaml")
        assert rc == 0

        cn = load_output(folder)["vendor_candidate"]["company_name"]
        assert cn["present"] != cn["inferred"], f"XOR invariant violated for {folder}"
        assert not (cn["present"] and cn["inferred"])
        assert not (not cn["present"] and not cn["inferred"])
