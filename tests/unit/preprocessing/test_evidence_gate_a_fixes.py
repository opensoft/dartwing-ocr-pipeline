"""Feature 020 / Copilot Phase 2 review (A-fixes): regression tests
for the six correctness bugs surfaced during the second review pass.

A1 — BUSINESS_SUFFIX_RE excludes hyphen lookahead (tests live in
     ``test_evidence_gate_regex_negatives.py``).
A2 — FiveSignalSet rejects bool values for int count fields.
A3 — load_preprocess_output_for_gate catches UnicodeDecodeError.
A4 — _mean_band_confidence skips blocks with non-string text.
A5 — VENDOR_NAME_STOP_WORDS expanded with suffix + tax-label tokens.
A6 — load failure emits insufficient record (in
     ``test_evidence_gate_pipeline_integration.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlinc_ocr.preprocessing.evidence_gate import (
    VENDOR_NAME_STOP_WORDS,
    FiveSignalSet,
    _count_vendor_name_candidates,
    _mean_band_confidence,
    compute_five_signals,
    load_preprocess_output_for_gate,
)


# --- A2: bool values rejected for int fields --------------------------------


@pytest.mark.parametrize(
    "field_name,bad_value",
    [
        ("vendor_name_candidate_count", True),
        ("vendor_name_candidate_count", False),
        ("header_band_token_density", True),
        ("header_band_token_density", False),
    ],
)
def test_post_init_rejects_bool_in_int_fields(
    field_name: str, bad_value: bool,
) -> None:
    """A2: int count fields must reject bool values — `bool` is a
    subclass of `int` so `isinstance(True, int)` is True, but the
    serialized JSON would emit ``true`` instead of ``1``, breaking the
    FR-003 typed-shape closure."""
    base_kwargs = dict(
        vendor_name_candidate_count=0,
        header_band_token_density=0,
        ocr_detection_confidence_mean=0.0,
        business_suffix_present=False,
        tax_id_shaped_present=False,
    )
    base_kwargs[field_name] = bad_value
    with pytest.raises(TypeError, match=f"{field_name}.*bool"):
        FiveSignalSet(**base_kwargs)  # type: ignore[arg-type]


def test_post_init_rejects_int_in_confidence_field() -> None:
    """A2 extension: the float confidence field rejects bool/int."""
    with pytest.raises(TypeError, match="ocr_detection_confidence_mean.*float"):
        FiveSignalSet(
            vendor_name_candidate_count=0,
            header_band_token_density=0,
            ocr_detection_confidence_mean=1,  # type: ignore[arg-type]
            business_suffix_present=False,
            tax_id_shaped_present=False,
        )


def test_post_init_rejects_int_for_bool_fields() -> None:
    """A2: the two bool fields reject int/None too (defensive)."""
    with pytest.raises(TypeError, match="business_suffix_present.*bool"):
        FiveSignalSet(
            vendor_name_candidate_count=0,
            header_band_token_density=0,
            ocr_detection_confidence_mean=0.0,
            business_suffix_present=1,  # type: ignore[arg-type]
            tax_id_shaped_present=False,
        )


# --- A3: load_preprocess_output_for_gate catches UnicodeDecodeError ---------


def test_load_returns_none_on_non_utf8_file(tmp_path: Path) -> None:
    """A3: a file with non-UTF-8 bytes must not raise UnicodeDecodeError;
    the loader returns None per its 'never raises' contract."""
    p = tmp_path / "preprocess_output.json"
    # Bytes that are NOT valid UTF-8.
    p.write_bytes(b'\xff\xfe\xfd\xfc some non-utf8 content')
    result = load_preprocess_output_for_gate(p)
    assert result is None


def test_load_returns_none_on_unparseable_json(tmp_path: Path) -> None:
    """Regression that exercises the JSON-decode failure path
    (already covered, included here so the A3 test family is
    self-contained)."""
    p = tmp_path / "preprocess_output.json"
    p.write_text('{"missing": "close-brace"')
    assert load_preprocess_output_for_gate(p) is None


def test_load_returns_none_on_non_dict_top_level(tmp_path: Path) -> None:
    """A6 supporting: parsed JSON with list/string/number at top level
    is not a usable preprocess output dict; loader returns None."""
    for content in ('["list", "at", "top"]', '"a string"', "42", "true"):
        p = tmp_path / "preprocess_output.json"
        p.write_text(content)
        assert load_preprocess_output_for_gate(p) is None


# --- A4: confidence mean ignores blocks with non-string text ----------------


def test_mean_confidence_ignores_non_string_text_blocks() -> None:
    """A4: a block whose ``text`` field is non-string contributes 0
    tokens — so it must also contribute 0 weight to the confidence
    mean. Otherwise a doc with only non-text blocks at high confidence
    falsely passes the confidence threshold."""
    blocks = [
        {"text": None, "confidence": 0.95, "bbox": [0, 0, 10, 10]},
        {"text": 42, "confidence": 0.98, "bbox": [0, 0, 10, 10]},
        {"text": ["x"], "confidence": 0.99, "bbox": [0, 0, 10, 10]},
    ]
    assert _mean_band_confidence(blocks) == 0.0  # noqa: SIM300 — RHS clearer


def test_mean_confidence_uses_only_text_blocks() -> None:
    """A4: text + non-text blocks → mean computed over text blocks only."""
    blocks = [
        # Real text block — contributes
        {"text": "Acme Inc.", "confidence": 0.80, "bbox": [0, 0, 10, 10]},
        # Non-text — must be ignored
        {"text": 42, "confidence": 0.99, "bbox": [0, 0, 10, 10]},
    ]
    assert _mean_band_confidence(blocks) == 0.80


# --- A5: expanded VENDOR_NAME_STOP_WORDS ------------------------------------


@pytest.mark.parametrize(
    "label_token",
    [
        # Tax-ID labels
        "EIN", "EIN:", "VAT", "VAT:",
        # Business suffix tokens (also captured by business_suffix_present;
        # excluded from candidate count to avoid double-counting)
        "LLC", "INC", "Inc", "Inc.", "Incorporated", "INCORPORATED",
        "LTD", "Ltd", "Ltd.", "Limited", "LIMITED",
        "GMBH", "GmbH",
        "CORP", "Corp", "Corp.", "Corporation", "CORPORATION",
        "CO", "Co.",
    ],
)
def test_label_tokens_are_not_vendor_candidates(label_token: str) -> None:
    """A5: tax-ID label tokens (EIN, VAT) and business-entity suffix
    tokens (LLC, Inc., Ltd., GmbH, Corp., Co.) MUST NOT count as
    vendor-name candidates. They are evidence indicators captured by
    other signals (`business_suffix_present`, `tax_id_shaped_present`)
    — including them here would double-count the same evidence and
    over-inflate `vendor_name_candidate_count`."""
    assert _count_vendor_name_candidates([label_token]) == 0, (
        f"label token {label_token!r} falsely counted as a vendor candidate"
    )


def test_stop_word_set_membership() -> None:
    """A5: the documented stop-word entries are in the set."""
    for w in (
        "INVOICE", "BILL", "TAX", "DATE", "PAGE", "NUMBER", "TOTAL",
        "AMOUNT", "DUE", "PAYMENT", "FROM", "TO",
        "EIN", "VAT",
        "LLC", "INC", "INCORPORATED", "LTD", "LIMITED", "GMBH", "CORP",
        "CORPORATION", "CO",
    ):
        assert w in VENDOR_NAME_STOP_WORDS, (
            f"expected {w!r} in VENDOR_NAME_STOP_WORDS"
        )


def test_real_vendor_name_with_suffix_now_counts_name_only() -> None:
    """A5 end-to-end: ``Acme Widget Inc.`` produces 2 vendor candidates
    (the prior 3-count over-inflated by including the suffix)."""
    doc = {
        "pages": [
            {
                "page_number": 1, "width": 1000, "height": 1000,
                "rotation_detected": 0,
                "blocks": [
                    {"text": "Acme Widget Inc.", "confidence": 0.9,
                     "bbox": [0, 100, 100, 200]},
                ],
                "raw_ocr_lines": [],
            }
        ]
    }
    result = compute_five_signals(doc)
    assert result.vendor_name_candidate_count == 2  # Acme + Widget; not Inc
    # business_suffix_present captures the Inc. as evidence.
    assert result.business_suffix_present is True


# --- Phase 3 fixes: SA/SAS in stop words; EvidenceGateResult validation ----


@pytest.mark.parametrize("token", ["S.A.", "S.A.S.", "SA", "SAS"])
def test_dotted_and_dotless_french_spanish_suffixes_filtered(token: str) -> None:
    """Phase 3 #8: ``S.A.`` and ``S.A.S.`` are in BUSINESS_SUFFIX_RE.
    Their punctuation-stripped projections (``SA``, ``SAS``) are what
    the vendor-name stop-word check actually compares against — the
    dotted and dotless forms must both be filtered for consistency
    with the A5 intent."""
    assert _count_vendor_name_candidates([token]) == 0


def test_evidence_gate_result_rejects_invalid_decision() -> None:
    """Phase 3 #6: EvidenceGateResult.__post_init__ rejects a decision
    string outside the closed three-state vocabulary."""
    from ledgerlinc_ocr.preprocessing.evidence_gate import (
        EvidenceGateResult,
        FiveSignalSet,
    )
    signals = FiveSignalSet(0, 0, 0.0, False, False)
    with pytest.raises(ValueError, match="decision must be one of"):
        EvidenceGateResult(
            signals=signals, decision="maybe", evidence_gate_id="v1",  # type: ignore[arg-type]
        )


def test_evidence_gate_result_rejects_unknown_gate_id() -> None:
    """Phase 3 #6: EvidenceGateResult.__post_init__ rejects an
    evidence_gate_id outside the closed vocabulary."""
    from ledgerlinc_ocr.preprocessing.evidence_gate import (
        EvidenceGateResult,
        FiveSignalSet,
    )
    signals = FiveSignalSet(0, 0, 0.0, False, False)
    with pytest.raises(ValueError, match="evidence_gate_id must be"):
        EvidenceGateResult(
            signals=signals, decision="insufficient", evidence_gate_id="v2",
        )


def test_evidence_gate_result_rejects_mismatched_decision_signals() -> None:
    """Phase 3 #6: EvidenceGateResult.__post_init__ enforces the
    re-derivability invariant (MI-7 / SC-012). A caller cannot
    construct an EvidenceGateResult where the decision contradicts
    what the gate's decision function would produce from the signals.
    """
    from ledgerlinc_ocr.preprocessing.evidence_gate import (
        EvidenceGateResult,
        FiveSignalSet,
    )
    # All-negative signals → canonical decision is "insufficient".
    insufficient_signals = FiveSignalSet(0, 0, 0.0, False, False)
    # Building with "sufficient" violates re-derivability.
    with pytest.raises(ValueError, match="does not re-derive"):
        EvidenceGateResult(
            signals=insufficient_signals,
            decision="sufficient",
            evidence_gate_id="v1",
        )


def test_canonicalization_drops_extra_keys_from_records() -> None:
    """Phase 3 #7: RunSummary.to_dict() canonicalizes
    evidence_gate_documents records, dropping extra keys (incl.
    potential PII leaks). Defense-in-depth for FR-003."""
    from ledgerlinc_ocr.pipeline.timing import RunSummary

    rs = RunSummary(
        stack_preset="cpu", resolved_profiles={}, execution_slice={},
        on_failure="abort", documents_total=1, documents_succeeded=1,
        documents_failed=0,
        evidence_gate_state_counts={"sufficient": 0, "borderline": 0, "insufficient": 1},
        evidence_gate_documents=[
            {
                "document_id": "inv_001_easy",
                "decision": "insufficient",
                "signals": {
                    "vendor_name_candidate_count": 0,
                    "header_band_token_density": 0,
                    "ocr_detection_confidence_mean": 0.0,
                    "business_suffix_present": False,
                    "tax_id_shaped_present": False,
                    # Extra PII leak attempt:
                    "matched_tax_id_value": "12-3456789",
                    "vendor_name_candidates": ["Acme", "Widget"],
                },
                # Extra top-level field attempt:
                "extracted_text": "secret invoice content",
            },
        ],
    )
    d = rs.to_dict()
    record = d["evidence_gate_documents"][0]
    # Top-level keys: exactly three, no extras.
    assert set(record.keys()) == {"document_id", "decision", "signals"}
    # Nested signals: exactly five FR-001 names, no extras.
    assert set(record["signals"].keys()) == {
        "vendor_name_candidate_count",
        "header_band_token_density",
        "ocr_detection_confidence_mean",
        "business_suffix_present",
        "tax_id_shaped_present",
    }
    # The PII leak attempts were dropped.
    assert "matched_tax_id_value" not in record["signals"]
    assert "extracted_text" not in record


def test_canonicalization_clamps_unknown_decision_to_insufficient() -> None:
    """Phase 3 #7: a caller-supplied record with an out-of-vocabulary
    decision gets clamped to ``insufficient`` at the serializer
    boundary (last-line-of-defense for the closed vocabulary)."""
    from ledgerlinc_ocr.pipeline.timing import RunSummary

    rs = RunSummary(
        stack_preset="cpu", resolved_profiles={}, execution_slice={},
        on_failure="abort", documents_total=1, documents_succeeded=1,
        documents_failed=0,
        evidence_gate_state_counts={"sufficient": 0, "borderline": 0, "insufficient": 1},
        evidence_gate_documents=[
            {
                "document_id": "inv_001_easy",
                "decision": "maybe",
                "signals": {},
            },
        ],
    )
    d = rs.to_dict()
    assert d["evidence_gate_documents"][0]["decision"] == "insufficient"
