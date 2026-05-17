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

from dartwing_ocr.preprocessing.identifiers import (
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
# before the suffix; `(?![\w-])` at the end requires "not followed by
# a word character OR a hyphen". The trailing-`\b` version silently
# failed to match suffixes ending in `.` (e.g., `Co.` / `S.A.` /
# `S.A.S.`) when they sat at end-of-string — `\b` requires a
# word/non-word transition and both `.` and end-of-string are
# non-word, so no boundary fires. The hyphen exclusion (vs. plain
# `(?!\w)`) prevents hyphenated compounds like `Inc-related` or
# `Incorporated-by-reference` from falsely matching the suffix.
# S.A.S. is listed BEFORE S.A. so the longer alternative wins.
BUSINESS_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(LLC|Incorporated|Inc|Limited|Ltd|GmbH|S\.A\.S\.|S\.A\.|Corporation|Corp|Co\.)(?![\w-])"
)
# `TAX_ID_EIN_RE` uses `(?<![\w-])` / `(?![\w-])` instead of `\b`. The
# `\b` form treats the `-` after the 7-digit run as a word/non-word
# transition and fires, so tokens like `12-3456789-extra` match the
# first 9 chars. The lookaround form rejects both word chars AND
# hyphens on either side, requiring whitespace / start / end / non-`-`
# punctuation boundaries (Phase 6).
TAX_ID_EIN_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w-])\d{2}-\d{7}(?![\w-])"
)
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
#
# A5 expansion (post-review): the set covers three classes —
#   1. Invoice-header labels (`INVOICE`, `BILL`, `TAX`, `DATE`, `PAGE`,
#      `NUMBER`, `TOTAL`, `AMOUNT`, `DUE`, `PAYMENT`, `FROM`, `TO`)
#   2. Tax-ID label tokens (`EIN`, `VAT`) — these are label markers, not
#      vendor names; their presence is captured elsewhere via the
#      tax-id-shaped regex on the value tokens
#   3. Business-entity suffix tokens (`LLC`, `INC`, `INCORPORATED`,
#      `LTD`, `LIMITED`, `GMBH`, `CORP`, `CORPORATION`, `CO`) — suffixes
#      ARE business-vendor indicators (captured by `business_suffix_present`)
#      but they are NOT vendor NAMES; including them in the candidate
#      count double-counts the same evidence
VENDOR_NAME_STOP_WORDS: Final[frozenset[str]] = frozenset(
    {
        # Invoice-header labels
        "INVOICE", "BILL", "TAX", "DATE", "PAGE", "NUMBER", "TOTAL",
        "AMOUNT", "DUE", "PAYMENT", "FROM", "TO",
        # Tax-ID label tokens
        "EIN", "VAT",
        # Business-entity suffixes (also captured by business_suffix_present).
        # `SA` and `SAS` are the alpha-only projections of `S.A.` and
        # `S.A.S.` from BUSINESS_SUFFIX_RE — the stop-word check
        # compares against the punctuation-stripped form, so the dotted
        # and dotless forms must both be in the set for consistency.
        "LLC", "INC", "INCORPORATED", "LTD", "LIMITED", "GMBH", "CORP",
        "CORPORATION", "CO", "SA", "SAS",
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
        # A2 strict type check: `bool` is a subclass of `int` in Python,
        # so `True < 0` is False and a bare `isinstance(..., int)` check
        # accepts booleans. The count fields are integer counts, never
        # booleans — reject `True`/`False` explicitly so a misrouted
        # boolean cannot be silently serialized into the int field.
        if type(self.vendor_name_candidate_count) is not int:
            raise TypeError(
                f"vendor_name_candidate_count must be int (not bool), got "
                f"{type(self.vendor_name_candidate_count).__name__}"
            )
        if self.vendor_name_candidate_count < 0:
            raise ValueError(
                f"vendor_name_candidate_count must be >= 0, got "
                f"{self.vendor_name_candidate_count!r}"
            )
        if type(self.header_band_token_density) is not int:
            raise TypeError(
                f"header_band_token_density must be int (not bool), got "
                f"{type(self.header_band_token_density).__name__}"
            )
        if self.header_band_token_density < 0:
            raise ValueError(
                f"header_band_token_density must be >= 0, got "
                f"{self.header_band_token_density!r}"
            )
        c = self.ocr_detection_confidence_mean
        if type(c) is not float:
            raise TypeError(
                f"ocr_detection_confidence_mean must be float (not bool/int), "
                f"got {type(c).__name__}"
            )
        if math.isnan(c) or math.isinf(c):
            raise ValueError(
                f"ocr_detection_confidence_mean must be finite, got {c!r}"
            )
        if not (0.0 <= c <= 1.0):
            raise ValueError(
                f"ocr_detection_confidence_mean must be in [0.0, 1.0], got {c!r}"
            )
        if type(self.business_suffix_present) is not bool:
            raise TypeError(
                f"business_suffix_present must be bool, got "
                f"{type(self.business_suffix_present).__name__}"
            )
        if type(self.tax_id_shaped_present) is not bool:
            raise TypeError(
                f"tax_id_shaped_present must be bool, got "
                f"{type(self.tax_id_shaped_present).__name__}"
            )


GateDecision = Literal["sufficient", "borderline", "insufficient"]
_CLOSED_DECISION_VOCABULARY: Final[frozenset[str]] = frozenset(
    {"sufficient", "borderline", "insufficient"}
)


@dataclass(frozen=True)
class EvidenceGateResult:
    """Output of one gate evaluation: the five signals + the decision + the
    active preset identifier (data-model.md §3).

    Validation invariants (enforced in ``__post_init__``):

    - ``decision`` is in the closed three-state vocabulary (MI-26).
    - ``evidence_gate_id`` is in the closed gate-ID vocabulary
      (currently only ``"v1"`` per MI-25).
    - ``decision`` re-derives from ``signals`` via the gate's
      decision function: ``decision == decide_for_gate(evidence_gate_id,
      signals)`` (MI-7 / SC-002 / SC-012). This catches direct
      construction with mismatched (decision, signals, gate_id) tuples
      — important because the dataclass is a public export and a
      caller using it without going through ``evaluate_evidence_gate``
      could otherwise build an invalid result.
    """

    signals: FiveSignalSet
    decision: GateDecision
    evidence_gate_id: str

    def __post_init__(self) -> None:
        if self.decision not in _CLOSED_DECISION_VOCABULARY:
            raise ValueError(
                f"decision must be one of "
                f"{sorted(_CLOSED_DECISION_VOCABULARY)!r}, got "
                f"{self.decision!r}"
            )
        # Phase 6: dispatch through `decide_for_gate` instead of calling
        # `_v1_decide` directly. When v2 lands, adding a branch to
        # `decide_for_gate` is enough — without this dispatch, a future
        # v2 result would be silently validated against the v1 table.
        # `decide_for_gate` itself enforces the gate-id closed
        # vocabulary (raises KeyError on unknown ids), so the explicit
        # `evidence_gate_id != "v1"` check is redundant.
        try:
            rederived = decide_for_gate(self.evidence_gate_id, self.signals)
        except KeyError as e:
            raise ValueError(
                f"evidence_gate_id must be a known gate id, got "
                f"{self.evidence_gate_id!r}"
            ) from e
        if self.decision != rederived:
            raise ValueError(
                f"decision {self.decision!r} does not re-derive from "
                f"signals via {self.evidence_gate_id!r}'s decision "
                f"function (re-derived: {rederived!r}); the "
                f"(decision, signals, evidence_gate_id) tuple must "
                f"satisfy MI-7 / SC-012"
            )


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

    Top-left origin: ``bbox == [x1, y1, x2, y2]`` with ``y1 <= y2`` and
    non-negative coords; the "top" of the block is ``y1``. Returns
    ``None`` (fail-closed) on any malformed bbox:

    - not a list/tuple
    - length != exactly 4 (schema pins bbox to 4 elements)
    - any element is a ``bool`` (``float(True) == 1.0`` would silently
      coerce a boolean coord into a numeric one — Phase 6)
    - ``y1`` not convertible to float
    - ``y1`` is NaN, infinity, or negative
    - ``y2 < y1`` (inverted bbox violates producer's ``y1 <= y2`` contract — Phase 6)
    """
    bbox = block.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    # Phase 6: bool is a subclass of int, and float(True) == 1.0 — a
    # bool in any bbox slot must not silently coerce to a numeric coord.
    if any(isinstance(c, bool) for c in bbox):
        return None
    try:
        y1 = float(bbox[1])
        y2 = float(bbox[3])
    except (TypeError, ValueError):
        return None
    if math.isnan(y1) or math.isinf(y1) or y1 < 0:
        return None
    if math.isnan(y2) or math.isinf(y2) or y2 < y1:
        return None
    return y1


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
    # Phase 6: reject booleans (float(True) == 1.0 would silently treat
    # `height = true` as a 1-pt page → threshold_y = 0.25), and reject
    # NaN/infinity (a non-finite height makes threshold_y infinite and
    # classifies every finite-y block as in-band — fail-open).
    raw_height = page.get("height", 0)
    if isinstance(raw_height, bool):
        return []
    try:
        page_height = float(raw_height)
    except (TypeError, ValueError):
        return []
    if math.isnan(page_height) or math.isinf(page_height) or page_height <= 0:
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
        # Phase 6: tax-ID-shaped tokens (EIN / VAT) are captured by
        # `tax_id_shaped_present`; do NOT double-count them as
        # vendor-name candidates. The prior filter accepted tokens like
        # `GB123456789` because `alpha_only == "GB"` passed the
        # uppercase + non-stop-word checks — but `GB123456789` is a
        # VAT shape, not a vendor name.
        if TAX_ID_VAT_RE.search(tok) or TAX_ID_EIN_RE.search(tok):
            continue
        alpha_only = "".join(ch for ch in tok if ch.isalpha())
        # Phase 4 hardening (post-review): the length check now runs on
        # the alpha-only projection, not the raw token. The prior order
        # accepted tokens like ``A.`` and ``1A`` because their RAW
        # length is 2 even though they have only ONE alphabetic
        # character — too short to be a plausible vendor-name
        # candidate.
        if len(alpha_only) < 2:
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
    """Arithmetic mean of ``confidence`` across in-band blocks that
    contributed tokens (R-020.3).

    Returns ``0.0`` when the band is empty OR no contributing block has
    a numeric confidence. Out-of-range confidences are clamped to
    ``[0.0, 1.0]`` before averaging — defensive against producer drift.

    A4 (post-review): blocks whose ``text`` field is missing or
    non-string contribute zero tokens to ``_tokens_from_blocks`` but
    previously still contributed to the confidence mean. That allowed a
    document with only non-text blocks at high confidence to evaluate
    above the 0.70 threshold despite having NO textual evidence. The
    mean now considers only blocks whose ``text`` is a string — keeping
    the confidence signal aligned with the token signal.

    Phase 4 hardening (post-review): also reject blocks whose ``text``
    is an empty or whitespace-only string. Such blocks split into zero
    tokens but previously still contributed confidence weight — same
    bug as the non-string case, just on the empty-string boundary.
    """
    confidences: list[float] = []
    for block in blocks:
        text = block.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        c = block.get("confidence")
        if c is None:
            continue
        # Phase 6: reject booleans — `float(True) == 1.0` would treat a
        # malformed `confidence: true` as max confidence and inflate the
        # mean. JSON booleans are not valid confidence values.
        if isinstance(c, bool):
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

    The catch clause covers four failure modes:
    - ``OSError`` — file missing, permission denied, IO error
    - ``json.JSONDecodeError`` — file content is not valid JSON
    - ``UnicodeDecodeError`` — file content is not valid UTF-8 (A3
      post-review: previously leaked through and contradicted the
      "never raises" contract)
    - ``ValueError`` — pypy and CPython have raised this on extremely
      malformed paths; defensive
    """
    try:
        path = Path(preprocess_output_path)
    except (TypeError, ValueError):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
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

    On ANY failure (unreadable / non-dict / corrupt input, or
    unexpected exception from the gate itself): emits an
    ``insufficient`` record with all-negative-level signals and logs a
    warning. The PII-safe warning carries only ``document_id`` — no
    file content, no exception payload (FR-003).

    Phase 6 strengthening (post-review): the prior version emitted
    ``insufficient`` on load failure but SKIPPED on internal exception.
    Per Copilot's review, this violated the always-one-record-per-
    successful-document contract — a gate bug could silently drop a
    document from ``evidence_gate_documents`` while it still counted
    in ``documents_succeeded``. The new behavior keeps MI-18 strong:
    ``sum(state_counts) == documents_succeeded`` holds across ALL
    failure modes.

    Used identically by ``pipeline/corpus_run.py`` and
    ``preprocessing/cli.py`` to avoid drift between the two call sites.
    """
    def _emit_insufficient_record(reason: str) -> None:
        _logger.warning(
            "evidence_gate: %s for document_id=%r; emitting insufficient record",
            reason,
            document_id,
        )
        insufficient_signals = FiveSignalSet(
            vendor_name_candidate_count=0,
            header_band_token_density=0,
            ocr_detection_confidence_mean=0.0,
            business_suffix_present=False,
            tax_id_shaped_present=False,
        )
        record = build_evidence_gate_document_record(
            document_id=document_id,
            result=EvidenceGateResult(
                signals=insufficient_signals,
                decision="insufficient",
                evidence_gate_id=EVIDENCE_GATE_ID_V1,
            ),
        )
        state_counts["insufficient"] += 1
        documents.append(record)

    try:
        gate_input = load_preprocess_output_for_gate(
            Path(document_folder) / "preprocess_output.json"
        )
        if gate_input is None:
            _emit_insufficient_record(
                "preprocess_output.json missing, unreadable, or not a JSON object"
            )
            return
        result = evaluate_evidence_gate(gate_input)
        state_counts[result.decision] += 1
        documents.append(
            build_evidence_gate_document_record(
                document_id=document_id, result=result
            )
        )
    except Exception:
        _emit_insufficient_record("evaluation raised an unexpected exception")


def should_suppress_fallback(
    *,
    preprocess_strategy_id: str | None,
    fr_005_trigger_would_fire: bool,
    opt_in_active: bool,
    candidate_gate_decision: GateDecision | str,
) -> bool:
    """Return True iff the OCR-only fallback should be suppressed (MI-13)."""
    return (
        preprocess_strategy_id == "ocr-only-v1"
        and fr_005_trigger_would_fire
        and opt_in_active
        and candidate_gate_decision == "sufficient"
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
    "should_suppress_fallback",
)
