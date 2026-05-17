"""Feature 020: deterministic vendor-identity evidence gate.

This module computes the FR-001 five-signal set over the page-1 header band
of ``preprocess_output.json`` content and maps it to one of three states
(``sufficient`` / ``borderline`` / ``insufficient``) via the v1 explicit
decision table (R-020.6).

The gate is a PURE FUNCTION over ``preprocess_output.json`` content:

- No network call, no subprocess, no filesystem write
- No Paddle / paddleocr / paddlepaddle import at module load (MI-4 / MI-5)
- No global mutable state; the module is stateless at module level
- No consultation of ``edge_extraction_output.json``, ``routing_decision.json``,
  or ``final_structured_payload.json`` (MI-2 / MI-3)

References:

- ``specs/020-vendor-evidence-gate/spec.md`` §FR-001, §FR-004, §FR-027
- ``specs/020-vendor-evidence-gate/research.md`` R-020.3, R-020.4, R-020.5, R-020.6
- ``specs/020-vendor-evidence-gate/data-model.md`` §1, §2, §3, §6, §7, §8
- ``specs/020-vendor-evidence-gate/contracts/evidence-gate-rule.md``
- ``specs/020-vendor-evidence-gate/contracts/module-invariants.md`` MI-1 through MI-27
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Final, Literal, Mapping

from ledgerlinc_ocr.preprocessing.identifiers import (
    EVIDENCE_GATE_ID_DEFAULT,
    EVIDENCE_GATE_ID_V1,
)

# Module-level numeric constants (R-020.5 / R-020.6 / data-model.md §7).
# All three are pinned at landing; future presets land via additive code
# change in EVIDENCE_GATES, not by mutating these constants.
Y_THRESHOLD_FRACTION: Final[float] = 0.25
DENSITY_THRESHOLD: Final[int] = 8
CONFIDENCE_THRESHOLD: Final[float] = 0.70

# Module-level regex constants (R-020.4 / data-model.md §6). Compiled once
# at module load (MI-8). All three use bounded repetition — no nested
# quantifiers, no catastrophic-backtracking risk.
BUSINESS_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(LLC|Inc|Incorporated|Ltd|Limited|GmbH|S\.A\.|S\.A\.S\.|Corp|Corporation|Co\.)\b"
)
TAX_ID_EIN_RE: Final[re.Pattern[str]] = re.compile(r"\b\d{2}-\d{7}\b")
TAX_ID_VAT_RE: Final[re.Pattern[str]] = re.compile(r"\b[A-Z]{2}[A-Z0-9]{2,12}\b")

# Stop-word set for the vendor-name-candidate heuristic (R-020.3 /
# data-model.md §8). Common invoice-header tokens that ARE uppercase /
# title-case but are NOT vendor names; case-folded comparison.
VENDOR_NAME_STOP_WORDS: Final[frozenset[str]] = frozenset(
    {
        "INVOICE",
        "BILL",
        "TAX",
        "DATE",
        "PAGE",
        "NUMBER",
        "TOTAL",
        "AMOUNT",
        "DUE",
        "PAYMENT",
        "FROM",
        "TO",
    }
)


@dataclass(frozen=True)
class FiveSignalSet:
    """The five FR-001 signals computed over the page-1 header band of one
    ``preprocess_output.json``.

    Field order matches the JSON emission order in
    ``evidence_gate_documents[i].signals`` per data-model.md §2.
    Validation rules (no NaN, no Infinity, confidence ∈ [0.0, 1.0],
    non-negative counts) enforced in ``__post_init__``.
    """

    vendor_name_candidate_count: int
    header_band_token_density: int
    ocr_detection_confidence_mean: float
    business_suffix_present: bool
    tax_id_shaped_present: bool

    def __post_init__(self) -> None:
        if self.vendor_name_candidate_count < 0:
            raise ValueError(
                f"vendor_name_candidate_count must be >= 0, got "
                f"{self.vendor_name_candidate_count!r}"
            )
        if self.header_band_token_density < 0:
            raise ValueError(
                f"header_band_token_density must be >= 0, got "
                f"{self.header_band_token_density!r}"
            )
        c = self.ocr_detection_confidence_mean
        # Reject NaN (NaN != NaN) and Infinity.
        if c != c or c in (float("inf"), float("-inf")):
            raise ValueError(
                f"ocr_detection_confidence_mean must be finite, got {c!r}"
            )
        if not (0.0 <= c <= 1.0):
            raise ValueError(
                f"ocr_detection_confidence_mean must be in [0.0, 1.0], got {c!r}"
            )

    def to_signals_dict(self) -> dict[str, Any]:
        """Serialize to the nested ``signals`` object shape emitted inside
        ``evidence_gate_documents[i]`` on the ``run_summary`` line.

        Field order is deterministic per data-model.md §2 (matches
        dataclass field order).
        """
        return {
            "vendor_name_candidate_count": self.vendor_name_candidate_count,
            "header_band_token_density": self.header_band_token_density,
            "ocr_detection_confidence_mean": self.ocr_detection_confidence_mean,
            "business_suffix_present": self.business_suffix_present,
            "tax_id_shaped_present": self.tax_id_shaped_present,
        }


GateDecision = Literal["sufficient", "borderline", "insufficient"]


@dataclass(frozen=True)
class EvidenceGateResult:
    """Output of one gate evaluation: the five signals + the decision + the
    active preset identifier (data-model.md §3).

    Re-derivability invariant (MI-7 / SC-012):
    ``result.decision == EVIDENCE_GATES[result.evidence_gate_id].decide(result.signals)``
    is enforced by ``evaluate_evidence_gate`` at construction time.
    """

    signals: FiveSignalSet
    decision: GateDecision
    evidence_gate_id: str


@dataclass(frozen=True)
class EvidenceGate:
    """Closed-vocabulary preset describing one gate-rule body (data-model.md §1).

    Registry size at landing is exactly one — ``EVIDENCE_GATES["v1"]``.
    Future presets ``"v2"``, ``"v3"``, ... add additional entries via
    additive code change per R-020.2.
    """

    evidence_gate_id: str
    y_threshold_fraction: float
    density_threshold: int
    confidence_threshold: float
    decide: Callable[[FiveSignalSet], GateDecision]


def _v1_decide(signals: FiveSignalSet) -> GateDecision:
    """The v1 explicit decision table (R-020.6 /
    contracts/evidence-gate-rule.md).

    Mapping (inclusive-on-the-high-side comparisons):

    - ``sufficient`` iff ``has_name AND has_density AND has_confidence
      AND (has_suffix OR has_tax_id)``
    - ``insufficient`` iff ``NOT has_name AND NOT has_density AND NOT
      has_confidence AND NOT has_suffix AND NOT has_tax_id`` (all five
      at negative level)
    - ``borderline`` for the residual (28 of 32 truth-table rows)
    """
    has_name = signals.vendor_name_candidate_count >= 1
    has_density = signals.header_band_token_density >= DENSITY_THRESHOLD
    has_confidence = signals.ocr_detection_confidence_mean >= CONFIDENCE_THRESHOLD
    has_suffix = signals.business_suffix_present
    has_tax_id = signals.tax_id_shaped_present

    if has_name and has_density and has_confidence and (has_suffix or has_tax_id):
        return "sufficient"
    if (
        not has_name
        and not has_density
        and not has_confidence
        and not has_suffix
        and not has_tax_id
    ):
        return "insufficient"
    return "borderline"


# Closed-vocabulary preset registry (R-020.2 / data-model.md §1).
# Size at landing: exactly one. Mutating this dict at runtime is a
# developer error (MI-25); adding a future preset requires a code change
# plus a new selection flag (R-020.2).
EVIDENCE_GATES: Final[dict[str, EvidenceGate]] = {
    EVIDENCE_GATE_ID_V1: EvidenceGate(
        evidence_gate_id=EVIDENCE_GATE_ID_V1,
        y_threshold_fraction=Y_THRESHOLD_FRACTION,
        density_threshold=DENSITY_THRESHOLD,
        confidence_threshold=CONFIDENCE_THRESHOLD,
        decide=_v1_decide,
    ),
}


# --- Signal computation helpers (R-020.3 / R-020.5) -------------------------


def _bbox_top_y(block: Mapping[str, Any]) -> float | None:
    """Return the top-y coordinate of a block's bbox.

    bbox shape (per ``preprocess_output.json`` schema): ``[x1, y1, x2, y2]``
    with top-left origin. The "top" of the block is ``y1`` (the smaller y
    in top-left convention).

    Returns ``None`` if the bbox is missing or malformed; the caller treats
    a None-y block as out-of-band (fails closed for the malformed Edge Case).
    """
    bbox = block.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
        return None
    try:
        return float(bbox[1])
    except (TypeError, ValueError):
        return None


def _nfkc(text: str) -> str:
    """Apply NFKC Unicode normalization (R-020.3 / MI-9)."""
    return unicodedata.normalize("NFKC", text)


def _band_blocks(
    preprocess_output: Mapping[str, Any], *, y_threshold_fraction: float
) -> list[Mapping[str, Any]]:
    """Return the list of ``pages[0].blocks`` whose ``bbox_top_y /
    page_height < y_threshold_fraction`` — the page-1 header band tokens
    (R-020.5).

    Fails closed on malformed input per spec §Edge Cases:

    - Missing ``pages`` key, ``pages == []``, ``pages[0]`` missing, or
      ``pages[0].height`` missing/zero → return ``[]``
    - Missing ``pages[0].blocks`` → return ``[]``
    - Blocks with malformed bbox → excluded from the result

    Tokens on ``pages[1..N]`` are NEVER considered (R-020.5 multi-page rule).
    """
    pages = preprocess_output.get("pages") if isinstance(preprocess_output, Mapping) else None
    if not isinstance(pages, (list, tuple)) or len(pages) == 0:
        return []
    page = pages[0]
    if not isinstance(page, Mapping):
        return []
    try:
        page_height = float(page.get("height", 0))
    except (TypeError, ValueError):
        return []
    if page_height <= 0:
        return []
    blocks = page.get("blocks")
    if not isinstance(blocks, (list, tuple)):
        return []
    in_band: list[Mapping[str, Any]] = []
    threshold_y = page_height * y_threshold_fraction
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        top_y = _bbox_top_y(block)
        if top_y is None:
            continue
        if top_y < threshold_y:
            in_band.append(block)
    return in_band


def _tokens_from_blocks(blocks: list[Mapping[str, Any]]) -> list[str]:
    """Whitespace-tokenize the ``text`` field of each block, after NFKC
    normalization. Returns the flat token list across all in-band blocks
    in block iteration order (R-020.3)."""
    tokens: list[str] = []
    for block in blocks:
        text = block.get("text")
        if not isinstance(text, str):
            continue
        normalized = _nfkc(text)
        tokens.extend(normalized.split())
    return tokens


def _count_vendor_name_candidates(tokens: list[str]) -> int:
    """Count tokens that match the vendor-name-candidate heuristic (R-020.3):

    - at least two characters long, AND
    - starts with an uppercase letter OR is title-case OR is all-caps, AND
    - is not a pure number, AND
    - is not in ``VENDOR_NAME_STOP_WORDS`` (case-folded).
    """
    count = 0
    for tok in tokens:
        if len(tok) < 2:
            continue
        # Strip punctuation for the case-class check; a token like
        # "Acme-Corp." should still count as a candidate. We test the
        # alphabetic-only projection for casing properties.
        alpha_only = "".join(ch for ch in tok if ch.isalpha())
        if not alpha_only:
            continue
        if tok.casefold().upper() in VENDOR_NAME_STOP_WORDS:
            continue
        # Pure-number tokens fail the "isalpha for at least one char"
        # check above already; this is belt-and-braces.
        if tok.isdigit():
            continue
        starts_upper = alpha_only[0].isupper()
        is_title = alpha_only.istitle()
        is_upper = alpha_only.isupper()
        if not (starts_upper or is_title or is_upper):
            continue
        count += 1
    return count


def _count_band_tokens(tokens: list[str]) -> int:
    """Total non-whitespace token count in the band (R-020.3). Tokens were
    produced by ``str.split()`` which already strips whitespace, so the
    length is the density."""
    return len(tokens)


def _mean_band_confidence(blocks: list[Mapping[str, Any]]) -> float:
    """Arithmetic mean of ``confidence`` across in-band blocks (R-020.3).

    Returns ``0.0`` when the band is empty OR no block has a numeric
    confidence (the negative-level fallback per data-model.md §2).
    Out-of-range confidences are clamped to ``[0.0, 1.0]`` before
    averaging — defensive against producer drift.
    """
    confidences: list[float] = []
    for block in blocks:
        c = block.get("confidence")
        if c is None:
            continue
        try:
            value = float(c)
        except (TypeError, ValueError):
            continue
        if value != value or value in (float("inf"), float("-inf")):
            continue
        # Clamp to [0.0, 1.0].
        value = max(0.0, min(1.0, value))
        confidences.append(value)
    if not confidences:
        return 0.0
    mean = statistics.mean(confidences)
    # Re-clamp the mean (defensive — mean of clamped values is itself
    # in-range, but guard against floating-point drift).
    return max(0.0, min(1.0, mean))


def _business_suffix_present(tokens: list[str]) -> bool:
    """``True`` if any token matches ``BUSINESS_SUFFIX_RE`` (R-020.4).

    Whole-token matching via ``re.search`` is appropriate because the
    pattern has ``\\b`` boundaries on both sides; the search succeeds iff
    the pattern matches anywhere in the token bounded by word boundaries.
    """
    for tok in tokens:
        if BUSINESS_SUFFIX_RE.search(tok):
            return True
    return False


def _tax_id_shaped_present(tokens: list[str]) -> bool:
    """``True`` if any token matches EIN ``XX-XXXXXXX`` OR EU VAT
    ``<country><alphanumeric>`` shape (R-020.4)."""
    for tok in tokens:
        if TAX_ID_EIN_RE.search(tok):
            return True
        if TAX_ID_VAT_RE.search(tok):
            return True
    return False


# --- Public API -------------------------------------------------------------


def compute_five_signals(
    preprocess_output: Mapping[str, Any],
    *,
    y_threshold_fraction: float = Y_THRESHOLD_FRACTION,
) -> FiveSignalSet:
    """Compute the FR-001 five-signal set for one ``preprocess_output.json``
    dict.

    The signal set is a pure deterministic function of the input dict
    (MI-1 through MI-6). Same input ⇒ same output across reruns and hosts;
    NFKC normalization + bounded-repetition regex + deterministic
    aggregation (``statistics.mean``) ensure cross-host byte-identity by
    construction.

    Empty / malformed input → all five signals at their negative level
    (spec §Edge Cases "Malformed `preprocess_output.json` reaches the gate").
    """
    blocks = _band_blocks(
        preprocess_output, y_threshold_fraction=y_threshold_fraction
    )
    tokens = _tokens_from_blocks(blocks)
    return FiveSignalSet(
        vendor_name_candidate_count=_count_vendor_name_candidates(tokens),
        header_band_token_density=_count_band_tokens(tokens),
        ocr_detection_confidence_mean=_mean_band_confidence(blocks),
        business_suffix_present=_business_suffix_present(tokens),
        tax_id_shaped_present=_tax_id_shaped_present(tokens),
    )


def evaluate_evidence_gate(
    preprocess_output: Mapping[str, Any],
    *,
    gate_id: str = EVIDENCE_GATE_ID_DEFAULT,
) -> EvidenceGateResult:
    """Run the evidence gate over one ``preprocess_output.json`` dict.

    Returns an ``EvidenceGateResult`` carrying the five signals (R-020.3),
    the gate decision drawn from the closed three-state vocabulary
    (R-020.6), and the active preset identifier (R-020.2).

    The function accepts ONLY a ``preprocess_output`` dict — never an
    extraction / routing / final-payload artifact (MI-2 / MI-3). The type
    signature enforces this at static-analysis level.

    Raises ``KeyError`` if ``gate_id`` is not in ``EVIDENCE_GATES``; at
    landing only ``"v1"`` is valid.
    """
    gate = EVIDENCE_GATES[gate_id]
    signals = compute_five_signals(
        preprocess_output, y_threshold_fraction=gate.y_threshold_fraction
    )
    decision = gate.decide(signals)
    return EvidenceGateResult(
        signals=signals, decision=decision, evidence_gate_id=gate_id
    )


def build_evidence_gate_document_record(
    *,
    document_id: str,
    result: EvidenceGateResult,
) -> dict[str, Any]:
    """Build one element of the ``run_summary.evidence_gate_documents``
    array from a per-document gate evaluation (R-020.10 / R-020.11 /
    data-model.md §4).

    The returned dict has EXACTLY three top-level keys:

    - ``document_id`` (per-document folder name relative to corpus root)
    - ``decision`` (one of ``"sufficient"`` / ``"borderline"`` /
      ``"insufficient"``)
    - ``signals`` (nested object with exactly the five FR-001 signal names)

    FR-003 PII-safety closure (Clarifications Session 2026-05-16 Q1
    Option A): only the five signal TYPES (int / int / float / bool /
    bool) appear in ``signals``. No raw token text, no matched EIN/VAT
    values, no matched suffix substring.

    No extra keys; the shape is locked so a future regression that adds
    a leaky raw-text field fails ``test_run_summary_schema_0_1_7.py``'s
    PII closure assertion.
    """
    return {
        "document_id": document_id,
        "decision": result.decision,
        "signals": result.signals.to_signals_dict(),
    }


def load_preprocess_output_for_gate(
    preprocess_output_path: Any,
) -> Mapping[str, Any] | None:
    """Load ``preprocess_output.json`` from disk for gate evaluation.

    Returns the parsed dict on success, or ``None`` when the file
    cannot be read or parsed. Callers that get ``None`` should treat
    the document as "gate did not evaluate" — distinct from "gate
    evaluated as `insufficient`" — and may either skip the per-doc
    record or emit one with the malformed-input negative-level signals
    (spec §Edge Cases).

    Accepts any path-like or string. Does NOT raise — fails closed.
    """
    import json
    from pathlib import Path

    try:
        path = Path(preprocess_output_path)
    except (TypeError, ValueError):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(obj, dict):
        return None
    return obj


__all__ = (
    "BUSINESS_SUFFIX_RE",
    "CONFIDENCE_THRESHOLD",
    "DENSITY_THRESHOLD",
    "EVIDENCE_GATES",
    "EvidenceGate",
    "EvidenceGateResult",
    "FiveSignalSet",
    "GateDecision",
    "TAX_ID_EIN_RE",
    "TAX_ID_VAT_RE",
    "VENDOR_NAME_STOP_WORDS",
    "Y_THRESHOLD_FRACTION",
    "build_evidence_gate_document_record",
    "compute_five_signals",
    "evaluate_evidence_gate",
    "load_preprocess_output_for_gate",
)
