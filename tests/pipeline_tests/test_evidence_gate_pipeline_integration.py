"""Feature 020 review cleanup (B3): real integration test for the
``evidence_gate`` wiring layer.

The existing ``test_evidence_gate_corpus_run.py`` is a UNIT test that
synthesizes ``RunSummary`` objects in-process; it does NOT exercise the
on-disk-file → ``evaluate_and_record`` → accumulator path that both
``pipeline/corpus_run.py`` and ``preprocessing/cli.py`` actually run in
production. A wiring regression that drops a call to
``evaluate_and_record`` or mis-builds the per-document record would not
be caught by that unit test.

This file fills that gap: it writes real ``preprocess_output.json``
fixtures to a ``tmp_path`` directory, invokes the production helper, and
asserts the accumulators populate correctly.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from ledgerlinc_ocr.preprocessing.evidence_gate import evaluate_and_record


def _write_preprocess_output(folder: Path, content: dict[str, Any]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "preprocess_output.json").write_text(json.dumps(content))


def _vendor_doc() -> dict[str, Any]:
    """Produces signals that classify as borderline under v1."""
    return {
        "pages": [
            {
                "page_number": 1, "width": 1000, "height": 1000,
                "rotation_detected": 0,
                "blocks": [
                    {"text": "Acme Widget Inc.", "confidence": 0.85,
                     "bbox": [0, 100, 100, 200]},
                ],
                "raw_ocr_lines": [],
            }
        ]
    }


def _strong_doc() -> dict[str, Any]:
    """Produces signals that classify as sufficient under v1: ≥1 vendor
    candidate AND ≥8 header tokens AND ≥0.70 confidence AND a business
    suffix."""
    text = " ".join(["Acme", "Widget", "Inc.", "Headquartered", "in",
                     "Springfield", "Suite", "100", "Telephone"])
    return {
        "pages": [
            {
                "page_number": 1, "width": 1000, "height": 1000,
                "rotation_detected": 0,
                "blocks": [
                    {"text": text, "confidence": 0.88,
                     "bbox": [0, 100, 100, 200]},
                ],
                "raw_ocr_lines": [],
            }
        ]
    }


def _empty_doc() -> dict[str, Any]:
    """No content in the header band — classifies as insufficient."""
    return {
        "pages": [
            {
                "page_number": 1, "width": 1000, "height": 1000,
                "rotation_detected": 0,
                "blocks": [],
                "raw_ocr_lines": [],
            }
        ]
    }


def test_evaluate_and_record_writes_record_for_valid_doc(
    tmp_path: Path,
) -> None:
    """Real file on disk → real record in accumulator. This is the
    production wiring path."""
    folder = tmp_path / "inv_001_easy"
    _write_preprocess_output(folder, _strong_doc())

    state_counts = {"sufficient": 0, "borderline": 0, "insufficient": 0}
    documents: list[dict[str, Any]] = []

    evaluate_and_record(
        document_folder=folder,
        document_id="inv_001_easy",
        state_counts=state_counts,
        documents=documents,
    )

    assert sum(state_counts.values()) == 1
    assert len(documents) == 1
    record = documents[0]
    assert record["document_id"] == "inv_001_easy"
    assert record["decision"] in {"sufficient", "borderline", "insufficient"}
    assert set(record["signals"].keys()) == {
        "vendor_name_candidate_count",
        "header_band_token_density",
        "ocr_detection_confidence_mean",
        "business_suffix_present",
        "tax_id_shaped_present",
    }


def test_evaluate_and_record_aggregates_across_multiple_docs(
    tmp_path: Path,
) -> None:
    """Multi-doc invocation: state_counts sums to documents.len, MI-18
    aggregate-vs-per-doc invariant holds."""
    state_counts = {"sufficient": 0, "borderline": 0, "insufficient": 0}
    documents: list[dict[str, Any]] = []

    for i, (doc_id, content) in enumerate([
        ("inv_001_easy", _strong_doc()),
        ("inv_002_easy", _vendor_doc()),
        ("inv_003_easy", _vendor_doc()),
        ("inv_004_hard", _empty_doc()),
    ]):
        folder = tmp_path / doc_id
        _write_preprocess_output(folder, content)
        evaluate_and_record(
            document_folder=folder,
            document_id=doc_id,
            state_counts=state_counts,
            documents=documents,
        )

    assert len(documents) == 4
    assert sum(state_counts.values()) == 4
    # MI-18: state_counts[s] equals count of documents with decision==s.
    for s in ("sufficient", "borderline", "insufficient"):
        expected = sum(1 for r in documents if r["decision"] == s)
        assert state_counts[s] == expected


def test_evaluate_and_record_missing_file_emits_insufficient(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A6 (post-review): missing ``preprocess_output.json`` → emit an
    ``insufficient`` record + log a warning. Keeps MI-18 invariant
    strong (state_counts always sums to documents_succeeded)."""
    folder = tmp_path / "inv_005_easy"
    folder.mkdir()
    # File intentionally NOT written.

    state_counts = {"sufficient": 0, "borderline": 0, "insufficient": 0}
    documents: list[dict[str, Any]] = []

    with caplog.at_level(
        logging.WARNING, logger="ledgerlinc_ocr.preprocessing.evidence_gate"
    ):
        evaluate_and_record(
            document_folder=folder,
            document_id="inv_005_easy",
            state_counts=state_counts,
            documents=documents,
        )

    assert state_counts == {"sufficient": 0, "borderline": 0, "insufficient": 1}
    assert len(documents) == 1
    record = documents[0]
    assert record["document_id"] == "inv_005_easy"
    assert record["decision"] == "insufficient"
    # All signals at negative level.
    assert record["signals"]["vendor_name_candidate_count"] == 0
    assert record["signals"]["header_band_token_density"] == 0
    assert record["signals"]["ocr_detection_confidence_mean"] == 0.0
    assert record["signals"]["business_suffix_present"] is False
    assert record["signals"]["tax_id_shaped_present"] is False
    # Warning logged, document_id present, no exception content.
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "inv_005_easy" in warnings[0].getMessage()


def test_evaluate_and_record_malformed_json_emits_insufficient(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A6 (post-review): corrupt JSON → load fails closed to None →
    helper emits an ``insufficient`` record + log warning. Same as
    missing-file case."""
    folder = tmp_path / "inv_006_easy"
    folder.mkdir()
    (folder / "preprocess_output.json").write_text("{not valid json")

    state_counts = {"sufficient": 0, "borderline": 0, "insufficient": 0}
    documents: list[dict[str, Any]] = []

    with caplog.at_level(
        logging.WARNING, logger="ledgerlinc_ocr.preprocessing.evidence_gate"
    ):
        evaluate_and_record(
            document_folder=folder,
            document_id="inv_006_easy",
            state_counts=state_counts,
            documents=documents,
        )

    assert state_counts == {"sufficient": 0, "borderline": 0, "insufficient": 1}
    assert len(documents) == 1
    assert documents[0]["decision"] == "insufficient"


def test_evaluate_and_record_non_dict_json_emits_insufficient(
    tmp_path: Path,
) -> None:
    """A6: parsed JSON that is not a dict (e.g., top-level list, string,
    number) → load returns None → insufficient record emitted."""
    folder = tmp_path / "inv_006a_easy"
    folder.mkdir()
    (folder / "preprocess_output.json").write_text('["list", "at", "top"]')

    state_counts = {"sufficient": 0, "borderline": 0, "insufficient": 0}
    documents: list[dict[str, Any]] = []

    evaluate_and_record(
        document_folder=folder,
        document_id="inv_006a_easy",
        state_counts=state_counts,
        documents=documents,
    )

    assert state_counts["insufficient"] == 1
    assert len(documents) == 1
    assert documents[0]["decision"] == "insufficient"


def test_evaluate_and_record_non_utf8_emits_insufficient(
    tmp_path: Path,
) -> None:
    """A3: non-UTF-8 file content does not crash the helper; A6:
    falls through to the insufficient-record emission."""
    folder = tmp_path / "inv_006b_easy"
    folder.mkdir()
    # Latin-1 encoded bytes that are NOT valid UTF-8.
    (folder / "preprocess_output.json").write_bytes(b'\xff\xfe\xfd')

    state_counts = {"sufficient": 0, "borderline": 0, "insufficient": 0}
    documents: list[dict[str, Any]] = []

    evaluate_and_record(
        document_folder=folder,
        document_id="inv_006b_easy",
        state_counts=state_counts,
        documents=documents,
    )

    assert state_counts["insufficient"] == 1
    assert len(documents) == 1


def test_evaluate_and_record_logs_warning_on_internal_exception(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the gate raises an unexpected exception (e.g., a bug in
    ``evaluate_evidence_gate``), the helper MUST log a warning and
    return without aborting — and the warning MUST NOT contain
    exception content (PII safety per FR-003)."""
    folder = tmp_path / "inv_007_easy"
    _write_preprocess_output(folder, _vendor_doc())

    # Inject a fault by patching the module-level reference the helper
    # uses. The object form (vs. string form) ensures the new binding
    # lands in the same module __dict__ that ``evaluate_and_record``
    # reads from at call time.
    import ledgerlinc_ocr.preprocessing.evidence_gate as eg_module

    def _explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("secret OCR text that must not leak")

    monkeypatch.setattr(eg_module, "evaluate_evidence_gate", _explode)

    state_counts = {"sufficient": 0, "borderline": 0, "insufficient": 0}
    documents: list[dict[str, Any]] = []

    with caplog.at_level(
        logging.WARNING, logger="ledgerlinc_ocr.preprocessing.evidence_gate"
    ):
        eg_module.evaluate_and_record(
            document_folder=folder,
            document_id="inv_007_easy",
            state_counts=state_counts,
            documents=documents,
        )

    # No record, no counter increment.
    assert documents == []
    assert sum(state_counts.values()) == 0
    # Exactly one warning recorded.
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    msg = warnings[0].getMessage()
    # PII safety: the exception message MUST NOT leak into the log line.
    assert "secret OCR text" not in msg, (
        "exception content leaked into log — PII safety violation"
    )
    # The document_id IS in the log line (corpus-internal, safe).
    assert "inv_007_easy" in msg
