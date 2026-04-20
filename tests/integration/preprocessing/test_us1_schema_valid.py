import re
from pathlib import Path


def test_ac1_schema_valid_single_page(us1_artifact):
    a = us1_artifact
    assert a["source_type"] == "pdf"
    assert a["contract_set_version"] == "1.0.0"
    assert a["document_id"] == "inv_001"
    assert re.match(r"^inv_\d{3}$", a["document_id"])
    assert a["source_file"] == "source.pdf"
    assert a["page_count"] == 1
    assert len(a["pages"]) == 1

    page = a["pages"][0]
    assert page["page_number"] == 1
    assert page["width"] >= 1
    assert page["height"] >= 1
    assert page["rotation_detected"] in (0, 90, 180, 270)
    assert isinstance(page["blocks"], list)
    assert isinstance(page["raw_ocr_lines"], list)


def test_ac1_artifact_passes_repo_validator(tmp_path, us1_workdir):
    """The written artifact must validate via the in-repo validator CLI API."""
    from ledgerlinc_ocr.preprocessing import pipeline
    from ledgerlinc_ocr.validator.artifact import validate_artifact

    out = pipeline.run(pipeline.Invocation(document_folder=us1_workdir))
    outcome = validate_artifact(out, contract="preprocess_output")
    assert outcome.passed, outcome.violations
