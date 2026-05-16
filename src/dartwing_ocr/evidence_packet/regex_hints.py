"""Deterministic regex hints over document_text.

Four fixed, compiled patterns — no runtime composition. Order of emission
is ascending document_text_offset. Duplicates are preserved (no dedup).
Spec FR-008 + research Decision 3.
"""
from __future__ import annotations

import re

EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+\-])"
    r"[A-Za-z0-9._%+\-]+"
    r"@"
    r"[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)*"
    r"\.[A-Za-z]{2,}"
    r"(?![A-Za-z0-9.\-])"
)

URL_RE = re.compile(
    r"https?://"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,}"
    r"(?:[:/?#][^\s<>\"']*)?"
)

US_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(?:\(\d{3}\)\s?|\d{3}[-.\s])"
    r"\d{3}[-.\s]\d{4}"
    r"(?!\d)"
)

EIN_RE = re.compile(
    r"(?<!\d)"
    r"\d{2}-\d{7}"
    r"(?!\d)"
)


_Hit = tuple[str, int, int]


def find_hints(document_text: str) -> dict[str, list[_Hit]]:
    def _scan(regex: re.Pattern[str]) -> list[_Hit]:
        return [(m.group(0), m.start(), m.end()) for m in regex.finditer(document_text)]

    return {
        "emails": _scan(EMAIL_RE),
        "websites": _scan(URL_RE),
        "phones": _scan(US_PHONE_RE),
        "tax_ids": _scan(EIN_RE),
    }
