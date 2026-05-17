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

from dartwing_ocr.preprocessing.evidence_gate import (
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
    from dartwing_ocr.preprocessing.evidence_gate import (
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
    from dartwing_ocr.preprocessing.evidence_gate import (
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
    from dartwing_ocr.preprocessing.evidence_gate import (
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
    from dartwing_ocr.pipeline.timing import RunSummary

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
    from dartwing_ocr.pipeline.timing import RunSummary

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


# --- Phase 4 fixes: bbox guards, token-length, confidence text guard, ---
# --- serializer scalar safety ----------------------------------------------


def test_bbox_negative_y1_rejected_fail_closed() -> None:
    """Phase 4 #2: a block whose ``bbox[1]`` is negative is malformed
    per the producer schema (non-negative coords). The gate must
    fail-closed by excluding such blocks from the header band, not
    fail-open by treating ``y1 < 0`` as "even higher up = definitely
    in-band"."""
    doc = {
        "pages": [{
            "page_number": 1, "width": 1000, "height": 1000,
            "rotation_detected": 0,
            "blocks": [
                # Malformed: y1 < 0. Must be excluded.
                {"text": "MalformedNegative", "confidence": 0.95,
                 "bbox": [0, -50, 100, 100]},
                # Valid in-band: y1=50 < 250 threshold.
                {"text": "ValidInBand", "confidence": 0.85,
                 "bbox": [0, 50, 100, 100]},
            ],
            "raw_ocr_lines": [],
        }]
    }
    result = compute_five_signals(doc)
    # Only "ValidInBand" counted as a token; "MalformedNegative" dropped.
    assert result.header_band_token_density == 1


def test_bbox_with_more_than_four_elements_rejected() -> None:
    """Phase 4 #3: the schema pins bbox to exactly 4 elements. A bbox
    with 5+ elements (extra junk) is malformed; the gate must drop the
    block rather than silently reading bbox[1] from the first 4."""
    doc = {
        "pages": [{
            "page_number": 1, "width": 1000, "height": 1000,
            "rotation_detected": 0,
            "blocks": [
                # Malformed: 5 elements. Must be excluded.
                {"text": "FiveElementBbox", "confidence": 0.95,
                 "bbox": [0, 100, 100, 200, 999]},
                # Valid 4-element in-band.
                {"text": "ValidInBand", "confidence": 0.85,
                 "bbox": [0, 100, 100, 200]},
            ],
            "raw_ocr_lines": [],
        }]
    }
    result = compute_five_signals(doc)
    assert result.header_band_token_density == 1


def test_short_alpha_tokens_rejected_as_candidates() -> None:
    """Phase 4 #5: ``A.`` (raw len 2, alpha-only 1) and ``1A`` (raw
    len 2, alpha-only 1) previously passed the candidate check
    because the length test ran on the raw token. Now they're filtered
    because the length check runs on the alpha-only projection."""
    assert _count_vendor_name_candidates(["A.", "1A", "B,", "9C", "X"]) == 0


def test_real_two_letter_alpha_tokens_still_count() -> None:
    """Phase 4 #5: the tightened length check doesn't over-correct —
    real two-letter capitalized tokens (``Co``, ``LA``) still count
    EXCEPT when they're in the stop-word set (A5 expansion)."""
    # "Co" / "LA" / "JP" are NOT in stop words (after A5 / Phase 3 #8
    # the suffix tokens like CO are bare-uppercase). "Co" is title-case,
    # the alpha-only projection is "Co" (len 2, NOT in stop words since
    # the stop word is the upper-case "CO"). Wait: the upper().upper()
    # comparison means "Co" → "CO" → IS in stop words. So Co is rejected.
    # Try something unambiguously not in stops: "Mu" (a real Greek-style
    # vendor prefix); alpha-only "Mu" → "MU", not in stop words.
    assert _count_vendor_name_candidates(["Mu", "Pi"]) == 2


def test_empty_text_blocks_excluded_from_confidence_mean() -> None:
    """Phase 4 #6: blocks whose ``text`` is an empty or whitespace-only
    string contribute zero tokens; they must also contribute zero
    weight to the confidence mean. Otherwise a doc with only-whitespace
    blocks at high confidence falsely passes the 0.70 threshold."""
    from dartwing_ocr.preprocessing.evidence_gate import _mean_band_confidence

    blocks = [
        # Empty text — must be ignored.
        {"text": "", "confidence": 0.99, "bbox": [0, 0, 10, 10]},
        # Whitespace-only — must be ignored.
        {"text": "   \t\n  ", "confidence": 0.98, "bbox": [0, 0, 10, 10]},
        # Real text — counted.
        {"text": "Acme Inc.", "confidence": 0.80, "bbox": [0, 0, 10, 10]},
    ]
    assert _mean_band_confidence(blocks) == 0.80


def test_serializer_safe_int_rejects_garbage() -> None:
    """Phase 4 #4: ``_safe_int`` in timing.py rejects garbage
    (non-numeric strings, booleans, None, negative, NaN-via-float)
    at the run_summary serializer boundary."""
    from dartwing_ocr.pipeline.timing import _safe_int

    assert _safe_int(5) == 5
    assert _safe_int(0) == 0
    assert _safe_int(-3) == 0  # negative → default
    assert _safe_int(True) == 0  # bool → default (not silently 1)
    assert _safe_int(False) == 0
    assert _safe_int(None) == 0
    assert _safe_int("not a number") == 0
    assert _safe_int("5") == 5
    assert _safe_int(3.7) == 3  # truncating float OK


def test_serializer_safe_float_rejects_non_finite() -> None:
    """Phase 4 #4: ``_safe_float`` in timing.py clamps NaN/inf/inf
    strings to the safe default; clamps out-of-range to [0.0, 1.0]."""
    from dartwing_ocr.pipeline.timing import _safe_float

    assert _safe_float(0.5) == 0.5
    assert _safe_float(0.0) == 0.0
    assert _safe_float(1.0) == 1.0
    assert _safe_float(1.5) == 1.0  # over-range → clamped
    assert _safe_float(-0.1) == 0.0  # under-range → clamped
    assert _safe_float(float("nan")) == 0.0
    assert _safe_float(float("inf")) == 0.0
    assert _safe_float(float("-inf")) == 0.0
    assert _safe_float("nan") == 0.0  # string form → default
    assert _safe_float("inf") == 0.0
    assert _safe_float("not a number") == 0.0
    assert _safe_float(True) == 0.0  # bool → default
    assert _safe_float(None) == 0.0


def test_canonicalization_rejects_nan_inf_strings_in_signals() -> None:
    """Phase 4 #4 end-to-end: a per-doc record carrying NaN/inf strings
    in the signals dict gets coerced to safe defaults at the
    serializer boundary, NOT emitted as non-finite JSON."""
    from dartwing_ocr.pipeline.timing import RunSummary

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
                    "vendor_name_candidate_count": "garbage",
                    "header_band_token_density": -5,
                    "ocr_detection_confidence_mean": "nan",
                    "business_suffix_present": False,
                    "tax_id_shaped_present": False,
                },
            },
        ],
    )
    d = rs.to_dict()
    signals = d["evidence_gate_documents"][0]["signals"]
    assert signals["vendor_name_candidate_count"] == 0
    assert signals["header_band_token_density"] == 0
    assert signals["ocr_detection_confidence_mean"] == 0.0


# --- Phase 5 fixes: safe_bool + OverflowError + state_counts coercion -----


def test_safe_int_handles_float_infinity() -> None:
    """Phase 5: ``_safe_int`` no longer raises ``OverflowError`` when
    asked to coerce ``float('inf')`` / ``float('-inf')`` — both fall
    back to the safe default."""
    from dartwing_ocr.pipeline.timing import _safe_int

    assert _safe_int(float("inf")) == 0
    assert _safe_int(float("-inf")) == 0
    assert _safe_int(float("nan")) == 0


def test_safe_bool_rejects_non_bool_inputs() -> None:
    """Phase 5: ``_safe_bool`` accepts only actual booleans; any other
    type (string, int, float, list, dict, None) → default. This
    closes the ``bool("false") == True`` hole."""
    from dartwing_ocr.pipeline.timing import _safe_bool

    assert _safe_bool(True) is True
    assert _safe_bool(False) is False
    assert _safe_bool("false") is False  # KEY case
    assert _safe_bool("True") is False  # KEY case
    assert _safe_bool("nonsense") is False
    assert _safe_bool(1) is False  # int → default
    assert _safe_bool(0) is False
    assert _safe_bool(None) is False
    assert _safe_bool([]) is False


def test_canonicalization_uses_safe_bool_for_signal_booleans() -> None:
    """Phase 5: a per-doc record carrying string values in the boolean
    signal slots gets coerced to ``False`` at the serializer boundary,
    not ``True`` (which raw ``bool(...)`` would produce for non-empty
    strings)."""
    from dartwing_ocr.pipeline.timing import RunSummary

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
                    "business_suffix_present": "false",  # string, not bool
                    "tax_id_shaped_present": "True",  # string, not bool
                },
            },
        ],
    )
    d = rs.to_dict()
    signals = d["evidence_gate_documents"][0]["signals"]
    assert signals["business_suffix_present"] is False
    assert signals["tax_id_shaped_present"] is False


def test_state_counts_serializer_uses_safe_int() -> None:
    """Phase 5 / Phase 6: the ``evidence_gate_state_counts`` serializer
    is now derived from the canonicalized ``evidence_gate_documents``
    list, not the in-process accumulator. A buggy accumulator carrying
    garbage is therefore ignored — state_counts always reflects the
    canonical per-doc records (an even stronger guarantee than the
    Phase 5 ``_safe_int`` coercion of accumulator values)."""
    from dartwing_ocr.pipeline.timing import RunSummary

    rs = RunSummary(
        stack_preset="cpu", resolved_profiles={}, execution_slice={},
        on_failure="abort", documents_total=0, documents_succeeded=0,
        documents_failed=0,
        evidence_gate_state_counts={
            "sufficient": float("inf"),  # type: ignore[dict-item]
            "borderline": "garbage",  # type: ignore[dict-item]
            "insufficient": -3,
        },
    )
    d = rs.to_dict()
    state_counts = d["evidence_gate_state_counts"]
    # Empty documents list ⇒ all-zero state counts regardless of
    # accumulator content.
    assert state_counts == {"sufficient": 0, "borderline": 0, "insufficient": 0}


# --- Phase 6 fixes: bool-in-float, bbox guards, regex tightening,
# --- post_init dispatch, canonicalizer re-derivation, exception path
# --- emits insufficient, etc. ----------------------------------------------


def test_bbox_with_bool_coord_rejected(tmp_path) -> None:
    """Phase 6: `float(True) == 1.0` would silently coerce a JSON `true`
    in a bbox slot into a numeric coord. The guard now rejects any
    bool in any bbox position — schema says coords are numeric."""
    doc = {
        "pages": [{
            "page_number": 1, "width": 1000, "height": 1000,
            "rotation_detected": 0,
            "blocks": [
                {"text": "BoolBbox", "confidence": 0.9,
                 "bbox": [0, True, 10, 200]},
                {"text": "ValidInBand", "confidence": 0.9,
                 "bbox": [0, 100, 10, 200]},
            ],
            "raw_ocr_lines": [],
        }]
    }
    result = compute_five_signals(doc)
    assert result.header_band_token_density == 1


def test_inverted_bbox_rejected() -> None:
    """Phase 6: producer contract is `y1 <= y2`. An inverted bbox
    (`y1=100, y2=50`) violates the contract and must be excluded."""
    doc = {
        "pages": [{
            "page_number": 1, "width": 1000, "height": 1000,
            "rotation_detected": 0,
            "blocks": [
                # Inverted bbox: y1=100, y2=50.
                {"text": "InvertedBbox", "confidence": 0.9,
                 "bbox": [0, 100, 10, 50]},
                # Valid bbox.
                {"text": "Valid", "confidence": 0.9,
                 "bbox": [0, 100, 10, 200]},
            ],
            "raw_ocr_lines": [],
        }]
    }
    result = compute_five_signals(doc)
    assert result.header_band_token_density == 1


def test_page_height_infinity_rejected() -> None:
    """Phase 6: a non-finite `page_height` would make `threshold_y`
    infinite, classifying every finite-y block as in-band (fail-OPEN).
    The guard now rejects NaN/inf page heights."""
    doc = {
        "pages": [{
            "page_number": 1, "width": 1000, "height": float("inf"),
            "rotation_detected": 0,
            "blocks": [
                {"text": "SomeText", "confidence": 0.9,
                 "bbox": [0, 100, 10, 200]},
            ],
            "raw_ocr_lines": [],
        }]
    }
    result = compute_five_signals(doc)
    # Fail-closed: malformed page → no in-band tokens.
    assert result.header_band_token_density == 0


def test_page_height_bool_rejected() -> None:
    """Phase 6: `height = true` would coerce to 1.0 via float()."""
    doc = {
        "pages": [{
            "page_number": 1, "width": 1000, "height": True,
            "rotation_detected": 0,
            "blocks": [
                {"text": "Token", "confidence": 0.9,
                 "bbox": [0, 0, 10, 1]},
            ],
            "raw_ocr_lines": [],
        }]
    }
    result = compute_five_signals(doc)
    assert result.header_band_token_density == 0


def test_confidence_bool_rejected() -> None:
    """Phase 6: `confidence = true` would coerce to 1.0 via float() and
    inflate the mean. JSON booleans are not valid confidence values."""
    from dartwing_ocr.preprocessing.evidence_gate import _mean_band_confidence

    blocks = [
        {"text": "Bool", "confidence": True, "bbox": [0, 0, 10, 10]},
        {"text": "Real", "confidence": 0.80, "bbox": [0, 0, 10, 10]},
    ]
    # The bool block is excluded; mean is just the real block's 0.80.
    assert _mean_band_confidence(blocks) == 0.80


def test_vat_shaped_token_not_counted_as_vendor_name() -> None:
    """Phase 6: ``GB123456789`` is a VAT-shaped token, captured by
    ``tax_id_shaped_present``. It must NOT also count as a
    ``vendor_name_candidate`` — double-counts the same evidence."""
    assert _count_vendor_name_candidates(
        ["GB123456789", "DE12345", "Acme", "Widget"]
    ) == 2  # Acme + Widget; not the two VATs


def test_ein_shaped_token_not_counted_as_vendor_name() -> None:
    """Phase 6: a bare EIN like ``12-3456789`` must not count as a
    vendor name candidate either."""
    assert _count_vendor_name_candidates(["12-3456789", "Acme"]) == 1


@pytest.mark.parametrize(
    "token",
    [
        "12-3456789-extra",  # trailing junk after the 7-digit run
        "12-3456789-1234",
        "extra-12-3456789",  # leading junk
        "112-3456789",  # extra leading digit
        "12-34567890",  # extra trailing digit
    ],
)
def test_ein_regex_rejects_trailing_junk(token: str) -> None:
    """Phase 6: ``TAX_ID_EIN_RE`` now uses ``(?<![\\w-])`` / ``(?![\\w-])``
    instead of ``\\b`` so tokens with trailing/leading word chars or
    hyphens don't partial-match the EIN shape."""
    from dartwing_ocr.preprocessing.evidence_gate import TAX_ID_EIN_RE

    assert not TAX_ID_EIN_RE.search(token), (
        f"{token!r} falsely matched TAX_ID_EIN_RE — trailing-junk regression"
    )


def test_ein_regex_still_matches_canonical() -> None:
    """Phase 6: canonical EIN forms still match (regression doesn't
    over-correct)."""
    from dartwing_ocr.preprocessing.evidence_gate import TAX_ID_EIN_RE

    assert TAX_ID_EIN_RE.search("12-3456789")
    assert TAX_ID_EIN_RE.search("EIN: 12-3456789")
    assert TAX_ID_EIN_RE.search("(12-3456789)")
    assert TAX_ID_EIN_RE.search("12-3456789.")


def test_evidence_gate_result_dispatch_through_decide_for_gate() -> None:
    """Phase 6: ``EvidenceGateResult.__post_init__`` now dispatches
    through ``decide_for_gate(evidence_gate_id, signals)`` rather than
    calling ``_v1_decide`` directly. This keeps the validation in lock-
    step with the dispatch table — when v2 lands, adding a branch to
    ``decide_for_gate`` is enough."""
    from dartwing_ocr.preprocessing.evidence_gate import (
        EvidenceGateResult,
        FiveSignalSet,
    )

    # Unknown gate_id should raise ValueError (mapped from KeyError).
    s = FiveSignalSet(0, 0, 0.0, False, False)
    with pytest.raises(ValueError, match="evidence_gate_id"):
        EvidenceGateResult(signals=s, decision="insufficient", evidence_gate_id="v2")


def test_canonicalizer_rederives_decision_from_signals() -> None:
    """Phase 6: the canonicalizer re-derives ``decision`` from
    canonical signals rather than just clamping the decision string.
    A caller-supplied ``decision="sufficient"`` with all-negative
    signals is overridden to the derived value (``"insufficient"``)."""
    from dartwing_ocr.pipeline.timing import RunSummary

    rs = RunSummary(
        stack_preset="cpu", resolved_profiles={}, execution_slice={},
        on_failure="abort", documents_total=1, documents_succeeded=1,
        documents_failed=0,
        evidence_gate_documents=[
            {
                "document_id": "inv_001_easy",
                # Mismatched: caller says sufficient, but signals are
                # all-negative.
                "decision": "sufficient",
                "signals": {
                    "vendor_name_candidate_count": 0,
                    "header_band_token_density": 0,
                    "ocr_detection_confidence_mean": 0.0,
                    "business_suffix_present": False,
                    "tax_id_shaped_present": False,
                },
            },
        ],
    )
    d = rs.to_dict()
    # Decision overridden to the derived value.
    assert d["evidence_gate_documents"][0]["decision"] == "insufficient"
    # state_counts derived from canonicalized records (MI-18 at wire).
    assert d["evidence_gate_state_counts"] == {
        "sufficient": 0, "borderline": 0, "insufficient": 1,
    }


def test_serializer_clamps_unknown_evidence_gate_id_to_v1() -> None:
    """Phase 6: a buggy caller cannot leak ``evidence_gate_id="v99"``
    onto the wire format. The serializer clamps unknown IDs to the
    default ``"v1"``."""
    from dartwing_ocr.pipeline.timing import RunSummary

    rs = RunSummary(
        stack_preset="cpu", resolved_profiles={}, execution_slice={},
        on_failure="abort", documents_total=0, documents_succeeded=0,
        documents_failed=0,
        evidence_gate_id="v99",
    )
    d = rs.to_dict()
    assert d["evidence_gate_id"] == "v1"
