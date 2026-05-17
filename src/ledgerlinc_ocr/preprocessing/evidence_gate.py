"""Feature 020: deterministic vendor-identity evidence gate.

Computes the FR-001 five-signal set over the page-1 header band of
``preprocess_output.json`` content and maps it to one of three states
(``sufficient`` / ``borderline`` / ``insufficient``) via the v1 explicit
decision table (R-020.6).

Pure stdlib + ``re`` only at module load (MI-4 / MI-5). No Paddle, no
network, no filesystem write, no consultation of other artifacts (MI-2 /
MI-3). Stateless at module level.

References: ``specs/020-vendor-evidence-gate/`` spec.md, research.md,
data-model.md, contracts/evidence-gate-rule.md, contracts/module-invariants.md.
"""

from __future__ import annotations

import json
import logging
import math
import re
import statistics
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final, Literal, Mapping

_logger = logging.getLogger(__name__)

from ledgerlinc_ocr.preprocessing.identifiers import (
    EVIDENCE_GATE_ID_DEFAULT,
    EVIDENCE_GATE_ID_V1,
)

# Module-level numeric constants (R-020.5 / R-020.6 / data-model.md §7).
Y_THRESHOLD_FRACTION: Final[float] = 0.25
DENSITY_THRESHOLD: Final[int] = 8
CONFIDENCE_THRESHOLD: Final[float] = 0.70

# Module-level regex constants (R-020.4 / data-model.md §6). All use
# bounded repetition — no nested quantifiers, no catastrophic-backtracking
# risk.
#
# BUSINESS_SUFFIX_RE: `\b` at the start anchors to a token boundary
# before the suffix; `(?!\w)` at the end requires "not followed by a
# word character" instead of the trailing `\b` that the original PR
# used. The trailing-`\b` version silently failed to match suffixes
# ending in `.` (e.g., `Co.` / `S.A.` / `S.A.S.`) when they sat at
# end-of-string — `\b` requires a word/non-word transition and both
# `.` and end-of-string are non-word, so no boundary fires.
# S.A.S. is listed BEFORE S.A. so the longer alternative wins.
BUSINESS_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(LLC|Incorporated|Inc|Limited|Ltd|GmbH|S\.A\.S\.|S\.A\.|Corporation|Corp|Co\.)(?!\w)"
)
TAX_ID_EIN_RE: Final[re.Pattern[str]] = re.compile(r"\b\d{2}-\d{7}\b")
# A 2-letter country prefix followed by 2..12 alphanumerics that MUST
# include at least one digit. The leading lookahead rejects all-letter
# tokens like INVOICE / PAYMENT / NUMBER / BALANCE / RECEIPT — common
# invoice header words — that the prior `[A-Z]{2}[A-Z0-9]{2,12}` shape
# misclassified as VAT-shaped (B2).
TAX_ID_VAT_RE: Final[re.Pattern[str]] = re.compile(
    r"\b[A-Z]{2}(?=[A-Z0-9]{2,12}\b)[A-Z0-9]*\d[A-Z0-9]*\b"
)

# Stop-word set for the vendor-name-candidate heuristic (R-020.3 /
# data-model.md §8). Bare uppercase invoice-header words; compared
# against the alphabetic-only projection of each token after upper-casing
# (B1: punctuation is stripped before the lookup, so `INVOICE:` and
# `Payment.` are filtered the same as their bare forms).
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
        if math.isnan(c) or math.isinf(c):
            raise ValueError(
                f"ocr_detection_confidence_mean must be finite, got {c!r}"
            )
        if not (0.0 <= c <= 1.0):
            raise ValueError(
                f"ocr_detection_confidence_mean must be in [0.0, 1.0], got {c!r}"
            )


GateDecision = Literal["sufficient", "borderline", "insufficient"]


@dataclass(frozen=True)
class EvidenceGateResult:
    """Output of one gate evaluation: the five signals + the decision + the
    active preset identifier (data-model.md §3)."""

    signals: FiveSignalSet
    decision: GateDecision
    evidence_gate_id: str


def _v1_decide(signals: FiveSignalSet) -> GateDecision:
    """The v1 explicit decision table (R-020.6 /
    contracts/evidence-gate-rule.md). Inclusive-on-the-high-side thresholds.

    - ``sufficient`` iff ``has_name AND has_density AND has_confidence
      AND (has_suffix OR has_tax_id)``
    - ``insufficient`` iff all five at negative level
    - ``borderline`` for the residual (28 of 32 truth-table rows)
    """
    has_name = signals.vendor_name_candidate_count >= 1
    has_density = signals.header_band_token_density >= DENSITY_THRESHOLD
    has_confidence = signals.ocr_detection_confidence_mean >= CONFIDENCE_THRESHOLD
    has_suffix = signals.business_suffix_present
    has_tax_id = signals.tax_id_shaped_present

    if has_name and has_density and has_confidence and (has_suffix or has_tax_id):
        return "sufficient"
    if not (has_name or has_density or has_confidence or has_suffix or has_tax_id):
        return "insufficient"
    return "borderline"


# --- Signal computation helpers (R-020.3 / R-020.5) -------------------------


def _bbox_top_y(block: Mapping[str, Any]) -> float | None:
    """Return the top-y coordinate of a block's bbox.

    Top-left origin: ``bbox == [x1, y1, x2, y2]`` with ``y1 <= y2``; the
    "top" of the block is ``y1``. Returns ``None`` on malformed bbox.
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
    """Return ``pages[0].blocks`` whose ``bbox_top_y / page_height <
    y_threshold_fraction`` — the page-1 header band tokens (R-020.5).

    Fails closed on malformed input per spec §Edge Cases:

    - Missing ``pages`` / ``pages == []`` / missing or zero ``height`` → ``[]``
    - Missing ``pages[0].blocks`` → ``[]``
    - Blocks with malformed bbox → excluded

    Tokens on ``pages[1..N]`` are NEVER considered (R-020.5 multi-page rule).
    """
    pages = (
        preprocess_output.get("pages") if isinstance(preprocess_output, Mapping) else None
    )
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
    threshold_y = page_height * y_threshold_fraction
    in_band: list[Mapping[str, Any]] = []
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
    """NFKC-normalize each block's ``text`` and whitespace-split. Returns
    the flat token list in block iteration order (R-020.3)."""
    tokens: list[str] = []
    for block in blocks:
        text = block.get("text")
        if not isinstance(text, str):
            continue
        tokens.extend(_nfkc(text).split())
    return tokens


def _count_vendor_name_candidates(tokens: list[str]) -> int:
    """Count tokens that match the vendor-name-candidate heuristic (R-020.3):

    - at least two characters long, AND
    - starts with an uppercase letter OR is title-case OR is all-caps, AND
    - is not a pure number, AND
    - is not in ``VENDOR_NAME_STOP_WORDS`` (compared against the
      alphabetic-only upper-cased projection — punctuation stripped).
    """
    count = 0
    for tok in tokens:
        if len(tok) < 2:
            continue
        alpha_only = "".join(ch for ch in tok if ch.isalpha())
        if not alpha_only:
            continue
        # B1: compare the punctuation-stripped projection against the
        # bare-word stop-word set. The prior code used
        # ``tok.casefold().upper()`` which left punctuation attached and
        # silently passed tokens like ``INVOICE:`` / ``Payment.`` /
        # ``Number,`` straight through the filter.
        if alpha_only.upper() in VENDOR_NAME_STOP_WORDS:
            continue
        if tok.isdigit():
            continue
        if not (
            alpha_only[0].isupper() or alpha_only.istitle() or alpha_only.isupper()
        ):
            continue
        count += 1
    return count


def _count_band_tokens(tokens: list[str]) -> int:
    """Total token count in the band (R-020.3)."""
    return len(tokens)


def _mean_band_confidence(blocks: list[Mapping[str, Any]]) -> float:
    """Arithmetic mean of ``confidence`` across in-band blocks (R-020.3).

    Returns ``0.0`` when the band is empty OR no block has a numeric
    confidence. Out-of-range confidences are clamped to ``[0.0, 1.0]``
    before averaging — defensive against producer drift.
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
        if math.isnan(value) or math.isinf(value):
            continue
        confidences.append(max(0.0, min(1.0, value)))
    if not confidences:
        return 0.0
    return max(0.0, min(1.0, statistics.mean(confidences)))


def _business_suffix_present(tokens: list[str]) -> bool:
    """``True`` if any token matches ``BUSINESS_SUFFIX_RE`` (R-020.4)."""
    return any(BUSINESS_SUFFIX_RE.search(tok) for tok in tokens)


def _tax_id_shaped_present(tokens: list[str]) -> bool:
    """``True`` if any token matches EIN ``XX-XXXXXXX`` OR EU VAT shape
    (2-letter country prefix + 2..12 alphanumerics with at least one digit
    — see ``TAX_ID_VAT_RE``; R-020.4 / B2)."""
    return any(
        TAX_ID_EIN_RE.search(tok) or TAX_ID_VAT_RE.search(tok) for tok in tokens
    )


# --- Public API -------------------------------------------------------------


def compute_five_signals(
    preprocess_output: Mapping[str, Any],
    *,
    y_threshold_fraction: float = Y_THRESHOLD_FRACTION,
) -> FiveSignalSet:
    """Compute the FR-001 five-signal set for one ``preprocess_output.json``
    dict. Pure deterministic function (MI-1..MI-6); empty/malformed input
    drops to negative-level signals per spec §Edge Cases.
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

    At landing only ``"v1"`` is a valid ``gate_id``. Future presets land
    as additive code change (R-020.2): a new ``_v2_decide`` function plus
    an additional branch here.

    Accepts ONLY a ``preprocess_output`` dict — never an extraction /
    routing / final-payload artifact (MI-2 / MI-3).
    """
    if gate_id != EVIDENCE_GATE_ID_V1:
        raise KeyError(
            f"unknown evidence gate id: {gate_id!r}; valid ids: "
            f"{EVIDENCE_GATE_ID_V1!r}"
        )
    signals = compute_five_signals(
        preprocess_output, y_threshold_fraction=Y_THRESHOLD_FRACTION
    )
    return EvidenceGateResult(
        signals=signals,
        decision=_v1_decide(signals),
        evidence_gate_id=gate_id,
    )


def decide_for_gate(gate_id: str, signals: FiveSignalSet) -> GateDecision:
    """Dispatch ``signals`` to the named gate's decision function.

    Re-derivability hook (MI-7 / SC-012): given an ``EvidenceGateResult``,
    ``decide_for_gate(result.evidence_gate_id, result.signals)`` MUST
    return ``result.decision``. Used by the rederivability test suite.
    """
    if gate_id != EVIDENCE_GATE_ID_V1:
        raise KeyError(
            f"unknown evidence gate id: {gate_id!r}; valid ids: "
            f"{EVIDENCE_GATE_ID_V1!r}"
        )
    return _v1_decide(signals)


def build_evidence_gate_document_record(
    *,
    document_id: str,
    result: EvidenceGateResult,
) -> dict[str, Any]:
    """Build one element of ``run_summary.evidence_gate_documents`` from a
    per-document gate evaluation (R-020.10 / R-020.11 / data-model.md §4).

    Returned dict has EXACTLY three top-level keys: ``document_id``,
    ``decision``, ``signals``. The nested ``signals`` dict has exactly the
    five FR-001 signal names. FR-003 PII-safety closure: only int / float
    / bool primitives appear in ``signals`` — no raw token text, no
    matched EIN/VAT values, no matched suffix substring.
    """
    return {
        "document_id": document_id,
        "decision": result.decision,
        "signals": asdict(result.signals),
    }


def load_preprocess_output_for_gate(
    preprocess_output_path: Any,
) -> Mapping[str, Any] | None:
    """Load ``preprocess_output.json`` from disk for gate evaluation.

    Returns the parsed dict on success or ``None`` when the file cannot
    be read or parsed. Never raises — fails closed.
    """
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


def evaluate_and_record(
    *,
    document_folder: Any,
    document_id: str,
    state_counts: dict[str, int],
    documents: list[dict[str, Any]],
) -> None:
    """Evaluate the gate on ``<document_folder>/preprocess_output.json`` and
    update the run-level accumulators.

    On success: increments ``state_counts[result.decision]`` and appends one
    record to ``documents``.

    On unreadable / malformed input: silently skips — no record, no
    counter increment. Operators detect this as ``sum(state_counts) <
    documents_succeeded``.

    On unexpected exception from the gate itself: logs a warning (no
    exception content surfaced — PII-safe per FR-003) and continues; the
    gate is observability and a bug here MUST NOT abort the run.

    Used identically by ``pipeline/corpus_run.py`` and
    ``preprocessing/cli.py`` to avoid drift between the two call sites
    (H3 review cleanup).
    """
    try:
        gate_input = load_preprocess_output_for_gate(
            Path(document_folder) / "preprocess_output.json"
        )
        if gate_input is None:
            return
        result = evaluate_evidence_gate(gate_input)
        state_counts[result.decision] += 1
        documents.append(
            build_evidence_gate_document_record(
                document_id=document_id, result=result
            )
        )
    except Exception:
        # PII-safety: surface ONLY the document_id, not the exception
        # content (which could carry OCR text from a buggy code path).
        _logger.warning(
            "evidence_gate evaluation failed for document_id=%r; "
            "skipping record (gate is observability — failure does not "
            "abort the run)",
            document_id,
        )


__all__ = (
    "EVIDENCE_GATE_ID_V1",
    "EvidenceGateResult",
    "FiveSignalSet",
    "GateDecision",
    "build_evidence_gate_document_record",
    "compute_five_signals",
    "decide_for_gate",
    "evaluate_and_record",
    "evaluate_evidence_gate",
    "load_preprocess_output_for_gate",
)
