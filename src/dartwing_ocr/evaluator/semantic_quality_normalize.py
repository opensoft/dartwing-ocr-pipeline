"""FR-009 / Q5 / Q32 — normalized exact-match pipeline (data-model §11).

Pipeline (order is fixed; do NOT reorder):

    1. Unicode NFKC normalization.
    2. ``str.casefold()`` — case-fold (handles Turkish I, German ß, etc.).
    3. Whitespace collapse — every Unicode whitespace run → single ASCII
       space via ``re.sub(r"\\s+", " ", text)``.
    4. Punctuation strip — drop every code point whose Unicode general
       category starts with ``P`` (``Pc``, ``Pd``, ``Pe``, ``Pf``,
       ``Pi``, ``Po``, ``Ps``) after NFKC.
    5. Final ``strip()`` to drop leading/trailing whitespace introduced
       by punctuation removal.

The function is idempotent: ``normalize(normalize(x)) == normalize(x)``
for all inputs.

**Currency-shape exception (Q16 / MI-8)**: FR-010 currency-shape checks
operate on the RAW observed OCR token text BEFORE this normalization
pipeline. Do NOT apply :func:`normalize` to currency candidates being
evaluated by ``CANONICAL_MONEY_REGEX``.

Stdlib only (``unicodedata``, ``re``). No Paddle. No network. MI-1.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

_WHITESPACE_RUN_RE: Final[re.Pattern[str]] = re.compile(r"\s+", flags=re.UNICODE)


def normalize(text: str) -> str:
    """Apply the FR-009 normalization pipeline to ``text``.

    Args:
        text: Arbitrary input text.

    Returns:
        The normalized form, suitable for "found anywhere" comparisons in
        the semantic quality gate's missing-content, row-text-coverage,
        and row-anchoring checks.
    """
    # Step 1: NFKC composition+compat fold.
    text = unicodedata.normalize("NFKC", text)
    # Step 2: case-fold (lowercase + special-language rules).
    text = text.casefold()
    # Step 3: collapse every Unicode whitespace run to a single ASCII space.
    text = _WHITESPACE_RUN_RE.sub(" ", text)
    # Step 4: strip every code point whose Unicode general category begins
    # with "P" (Pc, Pd, Pe, Pf, Pi, Po, Ps).
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("P"))
    # Step 4b: collapse whitespace runs ONCE MORE. Dropping a punctuation
    # code point between two single spaces (e.g. "a — b" → "a  b" after
    # NFKC/casefold/whitespace-collapse/punct-strip) would otherwise leave
    # a double space, breaking the idempotence invariant
    # (normalize(normalize(x)) == normalize(x), data-model §11). Re-applying
    # the collapse here is consistent with the spec's intent — every
    # whitespace run is normalized to a single ASCII space — and is
    # required to satisfy MI-2's determinism invariant.
    text = _WHITESPACE_RUN_RE.sub(" ", text)
    # Step 5: final strip — removes whitespace that may have been left
    # adjacent to dropped punctuation.
    return text.strip()
