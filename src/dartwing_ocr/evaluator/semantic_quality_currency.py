"""FR-010 / Q10 / Q16 / Q35 — currency-shape primitives.

Module-level compiled constant:

    CANONICAL_MONEY_REGEX = r"^\$?\d{1,3}(,\d{3})*\.\d{2}$"

Applied to the RAW observed OCR token text BEFORE FR-009 normalization
(Q16 / MI-8). Accepts ``$21.00``, ``21.00``, ``$1,234.56``; rejects
colon-for-decimal (``$21:00``), truncated values (``$22:``), and
ungrouped 4+ digit values (``1234.56`` / ``$1234.56`` — the ``\d{1,3}``
quantifier caps the leading digit run at 3 before the optional comma
group; data-model §9 line 257 originally claimed the inverse but
contradicts the regex literal — clarified per Copilot review on PR #45
2026-05-23).

``locate_currency_token`` implements per-field digit-sequence matching
(Q35 / MI-9): scan raw tokens in serialization order and return the
first not-yet-matched token whose digit-only representation equals the
expected field's digit sequence. Prevents misclassifying quantity tokens
as currency tokens for a paired amount field.

Pure stdlib (``re``). No Paddle. No network. MI-1.
"""

from __future__ import annotations

import re
from typing import Final

CANONICAL_MONEY_REGEX: Final[re.Pattern[str]] = re.compile(
    r"^\$?\d{1,3}(,\d{3})*\.\d{2}$"
)
"""Anchored canonical money regex (Q10 / FR-010).

Accepts:
- ``21.00`` / ``$21.00``
- ``1,234.56`` / ``$1,234.56``

Rejects:
- ``$21:00`` (colon-for-decimal)
- ``$22:`` (truncated)
- ``21.0`` (one cents digit)
- ``$1,23.00`` (malformed comma grouping)
- ``1234.56`` / ``$1234.56`` (ungrouped 4+ digit values — the
  ``\d{1,3}`` quantifier caps the leading digit run at 3 before the
  optional comma group; data-model §9 line 257 originally claimed
  ungrouped values were accepted, contradicting the regex literal —
  the regex is authoritative)
"""


def _digit_sequence(text: str) -> str:
    """Return the digit-only projection of ``text``.

    Drops every non-ASCII-digit character — currency symbols, commas,
    decimal points, colons, whitespace, etc. — leaving only ``0-9``.
    """
    return "".join(ch for ch in text if ch.isdigit())


def locate_currency_token(
    span_raw_tokens: list[str] | tuple[str, ...],
    expected_digit_seq: str,
    already_matched_indices: set[int],
) -> tuple[int, str] | None:
    """Locate the first unmatched raw token whose digit sequence equals
    ``expected_digit_seq`` (Q35 / MI-9).

    Args:
        span_raw_tokens: Raw OCR tokens within the row's anchored span,
            in serialization order (Q24).
        expected_digit_seq: The expected currency field's digit sequence
            (e.g. ``"2100"`` for an expected value of ``"21.00"``).
        already_matched_indices: Token indices within ``span_raw_tokens``
            that have already been claimed by a prior currency match for
            this row. The locator skips them so that an ``unit_price``
            and ``amount`` with the same digit sequence do not both
            collide on the same token.

    Returns:
        ``(token_index, raw_token)`` of the first match, or ``None`` if
        no unmatched token has the requested digit sequence.
    """
    if not expected_digit_seq:
        return None
    for idx, raw in enumerate(span_raw_tokens):
        if idx in already_matched_indices:
            continue
        if _digit_sequence(raw) == expected_digit_seq:
            return (idx, raw)
    return None
