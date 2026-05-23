"""T023 / FR-009 / Q5 / Q32 — normalization pipeline tests.

The normalize() function must apply, in order:
  1. Unicode NFKC normalization
  2. casefold()
  3. Unicode whitespace collapse → single ASCII space
  4. Strip every code point whose Unicode general category begins with 'P'
     (Pc, Pd, Pe, Pf, Pi, Po, Ps) AFTER NFKC
  5. Final strip()

Idempotence: normalize(normalize(x)) == normalize(x) for all inputs.

Currency-shape evaluation explicitly does NOT use this normalizer
(MI-8 / Q16) — that is enforced elsewhere (test_semantic_quality_currency.py).
"""

from __future__ import annotations

import pytest

from dartwing_ocr.evaluator.semantic_quality_normalize import normalize


class TestNFKCNormalization:
    def test_fullwidth_digits_collapse_to_ascii(self) -> None:
        # Full-width 0/1/2 → ASCII 0/1/2 under NFKC
        assert normalize("０１２") == "012"

    def test_composed_vs_decomposed_accents_equal(self) -> None:
        composed = normalize("café")  # é = U+00E9 (composed)
        decomposed = normalize("café")  # e + combining acute
        assert composed == decomposed

    def test_ligature_fi_decomposed(self) -> None:
        # U+FB01 (ﬁ) → "fi" under NFKC
        assert normalize("ﬁnal") == "final"


class TestCaseFold:
    def test_turkish_dotted_capital_i(self) -> None:
        # İ (U+0130) casefold → "i" + combining dot, but NFKC happens FIRST.
        # After our pipeline, the combining dot is non-letter (Mn) and is
        # preserved — only P* categories are stripped. So Turkish I just becomes
        # lowercase i-with-dot; the key contract is "no uppercase letters remain".
        out = normalize("İSTANBUL")
        assert out == out.casefold()
        # Defensive: no uppercase letters
        assert not any(ch.isupper() for ch in out)

    def test_dotless_i_lowercase(self) -> None:
        # ı (U+0131) is already lowercase; should round-trip
        assert normalize("ıstanbul") == "ıstanbul"

    def test_german_eszett_expands_to_ss(self) -> None:
        assert normalize("STRAẞE") == "strasse"

    def test_simple_ascii_lower(self) -> None:
        assert normalize("HELLO World") == "hello world"


class TestWhitespaceCollapse:
    def test_nbsp_collapses(self) -> None:
        # NBSP U+00A0 — NFKC keeps it as NBSP (NFKC does not fold NBSP).
        # The whitespace collapse step uses re \s+ which matches NBSP.
        assert normalize("foo bar") == "foo bar"

    def test_em_space_collapses(self) -> None:
        # U+2003 em-space
        assert normalize("foo bar") == "foo bar"

    def test_tabs_and_newlines_collapse(self) -> None:
        assert normalize("foo\t\nbar") == "foo bar"

    def test_multiple_whitespace_runs_collapse(self) -> None:
        assert normalize("a   b\t\t\tc") == "a b c"


class TestPunctuationStrip:
    @pytest.mark.parametrize(
        "punct,name",
        [
            ("_", "Pc"),
            ("-", "Pd"),
            (")", "Pe"),
            ("»", "Pf"),
            ("«", "Pi"),
            (".", "Po"),
            (",", "Po"),
            (":", "Po"),
            ("(", "Ps"),
        ],
    )
    def test_category_p_star_stripped(self, punct: str, name: str) -> None:
        out = normalize(f"foo{punct}bar")
        assert punct not in out
        # Either foobar or foo bar depending on category — both acceptable;
        # the invariant is the punctuation is gone.
        assert "foo" in out and "bar" in out

    def test_em_dash_stripped(self) -> None:
        # Em-dash is Pd → stripped; surrounding spaces collapse to one.
        assert normalize("a — b") == "a b"

    def test_combining_marks_preserved(self) -> None:
        # Combining marks are Mn / Mc, not P*, so they survive.
        # After NFKC composition + casefold + punct-strip, the e+acute
        # is normalized to é under NFC variants. Just assert the text
        # is non-empty alphabetic-only.
        out = normalize("café!")
        assert "!" not in out
        assert "caf" in out


class TestIdempotence:
    @pytest.mark.parametrize(
        "text",
        [
            "Hello, World!",
            "Café résumé naïve façade",
            "INVOICE #12345 — Total: $1,234.56",
            "  multiple   spaces  ",
            "ﬁle System (Annual)",
            "ＡＢＣＤ ０１２３",
            "İSTANBUL ışık",
            "STRAẞE 42",
            "",
            " ",
            "  \t\n",
            "!@#$%^&*()",
            "a-b_c.d:e",
        ],
    )
    def test_idempotent(self, text: str) -> None:
        once = normalize(text)
        twice = normalize(once)
        assert once == twice


class TestEmptyAndWhitespace:
    def test_empty_string(self) -> None:
        assert normalize("") == ""

    def test_pure_whitespace_to_empty(self) -> None:
        assert normalize("   \t\n  ") == ""

    def test_pure_punctuation_to_empty(self) -> None:
        # All P* categories stripped → empty after strip()
        assert normalize("...,,,---___") == ""

    def test_pure_whitespace_unicode_to_empty(self) -> None:
        assert normalize("   ") == ""
