"""Byte-identical JSON serialization for newly written semantic outputs (Q34 / MI-16 / R-022.3).

Implements the conventions pinned by Clarifications Q34 / FR-014 / MI-16 so
two evaluator runs on identical inputs produce byte-identical output files
(SC-007 / MI-2):

* Sorted keys at every nesting level (``sort_keys=True``).
* UTF-8 encoding (``ensure_ascii=False`` so non-ASCII characters survive
  intact instead of being escaped).
* LF line endings (no CRLF).
* A single trailing newline at EOF; no trailing whitespace on any line.
* Derived ratios and confidence values (e.g.
  ``semantic_table_quality_pass_rate``, ``body_confidence_mean``,
  ``body_confidence_min``) emitted as **JSON numbers** (NOT strings) with
  6 decimal places using ``decimal.ROUND_HALF_EVEN``. This is the post-fix F3
  pinning: even when ``body_line_count == 0`` both confidence fields emit
  as ``0.0`` (never ``null``).
* Integer counts pass through as JSON integers via the standard encoder.

Callers pass ordinary Python objects with ``decimal.Decimal`` instances for
any value that must round at the boundary. The encoder converts each
``Decimal`` to a 6-dp ``float`` so it serializes as a JSON number rather
than a string. The Decimal-based approach avoids the ``parse_float=Decimal``
round-trip that would convert every float in an input document to Decimal
and break backward-compat reads of pre-feature artifacts (per R-022.3).
"""

from __future__ import annotations

import json
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any, Final

SUPPORTING_EVIDENCE_FLOAT_PRECISION: Final[int] = 6
"""Decimal places for derived ratios and confidence values (data-model §10)."""

_QUANTIZE_TARGET: Final[Decimal] = Decimal(10) ** -SUPPORTING_EVIDENCE_FLOAT_PRECISION


def round_half_even(value: Decimal | float | int) -> float:
    """Round ``value`` to 6 decimal places with ROUND_HALF_EVEN.

    Returns a ``float`` so the standard JSON encoder serializes it as a JSON
    number. Integer inputs round-trip unchanged (``0.0``). The Decimal path
    is the authoritative one — callers that care about banker's rounding
    should pass a ``Decimal`` to avoid float-precision artifacts.

    Args:
        value: A ``Decimal``, ``float``, or ``int`` to round.

    Returns:
        A ``float`` with exactly 6 decimal places of precision (post-round).
    """
    if isinstance(value, Decimal):
        quantized = value.quantize(_QUANTIZE_TARGET, rounding=ROUND_HALF_EVEN)
    else:
        quantized = Decimal(repr(value)).quantize(
            _QUANTIZE_TARGET, rounding=ROUND_HALF_EVEN
        )
    return float(quantized)


class _StableJSONEncoder(json.JSONEncoder):
    """JSON encoder that converts ``Decimal`` values to 6-dp ``float`` JSON numbers.

    Subclassing ``json.JSONEncoder`` and overriding ``default`` is the
    standard-library-only way to emit a Decimal as a JSON number (not a
    string). Without this hook, ``json.dumps`` raises ``TypeError`` on
    ``Decimal`` instances.
    """

    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return round_half_even(o)
        return super().default(o)


def dump_stable(obj: Any, path: Path) -> None:
    """Write ``obj`` to ``path`` using the Q34 stable JSON conventions.

    Sorted keys at every nesting level; UTF-8 encoding; LF line endings;
    exactly one trailing newline at EOF; no trailing whitespace; Decimal
    values rounded to 6 dp with ROUND_HALF_EVEN and emitted as JSON numbers.

    The function performs a single ``write_text`` call so the file is created
    or replaced atomically from the caller's perspective; partial-write
    interruption windows match Python's ``Path.write_text`` semantics.

    Args:
        obj: A JSON-serializable Python object. ``Decimal`` instances at any
            nesting level are rounded by :class:`_StableJSONEncoder`.
        path: Destination filesystem path. Parent directory must already
            exist (the writer does not ``mkdir``).
    """
    serialized = json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
        cls=_StableJSONEncoder,
    )
    path.write_text(serialized + "\n", encoding="utf-8", newline="\n")
