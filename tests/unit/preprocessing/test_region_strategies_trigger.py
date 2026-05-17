"""Feature 018 (T023 / R-018.7 / I-018.5 / Clarifications Q3):
CPU-safe unit tests for the `header-first-v1` FR-007 fallback trigger
predicate.

Trigger contract (Clarifications Q3 / R-018.7):
- `trigger_fired(blocks)` returns True iff
  `not "".join(b.text for b in blocks).strip()` — the whitespace-stripped
  concatenation of all `blocks[].text` in the targeted region on page 1
  is empty.
- Inspects ONLY `blocks[].text` — NOT `raw_ocr_lines[].text`, NOT
  bounding-box presence, NOT block count (I-018.5).

All tests are CPU-safe (no Paddle import).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest

from dartwing_ocr.preprocessing.region_strategies import resolve_region_strategy


@dataclass
class _StubBlock:
    """Duck-type for the `text` attribute the trigger reads."""

    text: str


def _trigger():
    return resolve_region_strategy("header-first-v1").trigger_fired


# ---------------------------------------------------------------------------
# Empty inputs → trigger fires
# ---------------------------------------------------------------------------


def test_empty_block_list_fires_trigger() -> None:
    """Zero blocks → empty concat → trigger fires."""
    assert _trigger()([]) is True


def test_single_empty_string_block_fires_trigger() -> None:
    """One block with `text=""` → empty concat → trigger fires."""
    assert _trigger()([_StubBlock(text="")]) is True


# ---------------------------------------------------------------------------
# Whitespace-only inputs → trigger fires
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "whitespace_only",
    [
        " ",
        "  \t\n",
        "\r\n\t",
        "\u00A0",          # NBSP (Unicode non-breaking space)
        "\u2028\u2029",   # LINE / PARAGRAPH SEPARATOR
        "\u200B\u200C",   # ZWSP + ZWNJ -- NOT in str.strip() set
    ],
)
def test_whitespace_only_block_text_fires_trigger(whitespace_only: str) -> None:
    """Whitespace-only `text` after `str.strip()` is empty for standard
    Unicode whitespace categories. Note: zero-width characters (ZWSP /
    ZWNJ / ZWJ) are NOT in Python's default `str.strip()` whitespace
    set, so they would NOT fire the trigger — but they're also not
    typical OCR output. The trigger contract is "Python's default
    str.strip()" semantics per R-018.7."""
    blocks = [_StubBlock(text=whitespace_only)]
    # `str.strip()` removes Unicode whitespace categories; ZWSP is
    # NOT in those categories. The test assertion below reflects
    # str.strip() actual semantics — change here if the trigger
    # contract is later tightened to also strip zero-width chars.
    expected = not whitespace_only.strip()
    assert _trigger()(blocks) is expected


# ---------------------------------------------------------------------------
# Non-whitespace text → trigger does NOT fire
# ---------------------------------------------------------------------------


def test_single_non_whitespace_block_does_not_fire_trigger() -> None:
    """One block with non-whitespace text → trigger does not fire."""
    assert _trigger()([_StubBlock(text="Acme Corp")]) is False


def test_mixed_whitespace_and_non_whitespace_does_not_fire_trigger() -> None:
    """One whitespace-only block + one non-whitespace block → concat
    contains non-whitespace → trigger does not fire (any text in the
    targeted region prevents fallback)."""
    blocks = [
        _StubBlock(text="   "),
        _StubBlock(text="Acme"),
    ]
    assert _trigger()(blocks) is False


def test_multiple_non_whitespace_blocks_do_not_fire_trigger() -> None:
    """Multiple blocks with non-whitespace text → trigger does not fire."""
    blocks = [
        _StubBlock(text="Acme"),
        _StubBlock(text="Corp"),
        _StubBlock(text="123 Main St"),
    ]
    assert _trigger()(blocks) is False


def test_punctuation_only_blocks_do_not_fire_trigger() -> None:
    """Blocks with non-whitespace, non-letter text (punctuation, digits)
    → concat is non-empty → trigger does not fire. The trigger checks
    string emptiness after str.strip(), NOT semantic content."""
    blocks = [_StubBlock(text=".")]
    assert _trigger()(blocks) is False
    assert _trigger()([_StubBlock(text="123")]) is False
    assert _trigger()([_StubBlock(text="—")]) is False


# ---------------------------------------------------------------------------
# I-018.5: trigger inspects only `text`, NOT bbox or block_type
# ---------------------------------------------------------------------------


@dataclass
class _StubBlockWithExtraFields:
    """A block with extra attributes — trigger MUST ignore them per
    I-018.5."""

    text: str
    bbox: Optional[list] = None
    block_type: str = "text"


def test_trigger_ignores_bbox_and_block_type() -> None:
    """I-018.5: the trigger inspects ONLY `text`. Blocks with non-empty
    bbox / block_type but empty text MUST still fire the trigger."""
    blocks = [_StubBlockWithExtraFields(text="", bbox=[0, 0, 100, 100], block_type="text")]
    assert _trigger()(blocks) is True


def test_trigger_handles_block_without_text_attribute_gracefully() -> None:
    """Defensive: a block-shaped object with no `text` attribute
    contributes empty-string to the concat (via `getattr(b, "text", "")`)
    so the trigger still fires when no other blocks have text."""
    class _NoTextBlock:
        pass

    assert _trigger()([_NoTextBlock()]) is True
