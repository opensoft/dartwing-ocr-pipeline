"""Deterministic field normalization + classification per `research.md` §§1–7.

Each `normalize_*` helper returns a canonical string form; each `classify_*`
helper takes two non-null raw values and returns one of `MATCH`, `PARTIAL_MATCH`,
or `MISMATCH`. `classify_value(field_name, expected, actual)` dispatches to the
right classifier. `FR-006` exclusions (booleans, `review_reason`, tax IDs) are
enforced here by returning only `MATCH`/`MISMATCH` for those fields; `compare.py`
re-enforces the invariant via `FieldResult.__post_init__`.
"""

from __future__ import annotations

import re
from typing import Any

from ledgerlinc_ocr.evaluator.scoring import ResultLabel


_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")
_NON_DIGIT_RE = re.compile(r"\D+")
_PHONE_EXTENSION_RE = re.compile(r"\b(?:ext\.?|x|#)\s*\d+", re.IGNORECASE)
_TAX_ID_SEP_RE = re.compile(r"[\s\-\.]+")

# --- State abbreviation map (research.md §1) -----------------------------------
# 50 US states + DC + 5 US territories (PR, GU, AS, MP, VI). 2-letter → full name.
_STATE_CODE_TO_NAME: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
    "PR": "Puerto Rico", "GU": "Guam", "AS": "American Samoa",
    "MP": "Northern Mariana Islands", "VI": "US Virgin Islands",
}
_STATE_NAME_TO_CODE: dict[str, str] = {
    name.lower(): code for code, name in _STATE_CODE_TO_NAME.items()
}

# --- Street suffix / directional maps (research.md §6) -------------------------
_STREET_SUFFIX_MAP: dict[str, str] = {
    "st": "street", "street": "street",
    "rd": "road", "road": "road",
    "ave": "avenue", "av": "avenue", "avenue": "avenue",
    "blvd": "boulevard", "boulevard": "boulevard",
    "dr": "drive", "drive": "drive",
    "ln": "lane", "lane": "lane",
    "ct": "court", "court": "court",
    "pl": "place", "place": "place",
    "pkwy": "parkway", "parkway": "parkway",
    "hwy": "highway", "highway": "highway",
    "ter": "terrace", "terrace": "terrace",
    "cir": "circle", "circle": "circle",
    "sq": "square", "square": "square",
}
_DIRECTIONAL_MAP: dict[str, str] = {
    "n": "north", "north": "north",
    "s": "south", "south": "south",
    "e": "east", "east": "east",
    "w": "west", "west": "west",
    "ne": "northeast", "northeast": "northeast",
    "nw": "northwest", "northwest": "northwest",
    "se": "southeast", "southeast": "southeast",
    "sw": "southwest", "southwest": "southwest",
}

# Company legal-form suffixes to strip (research.md §7).
_COMPANY_SUFFIXES: tuple[str, ...] = (
    "incorporated", "inc",
    "limited liability company", "llc", "l.l.c",
    "corporation", "corp",
    "limited", "ltd",
    "company", "co",
    "plc",
    "lp", "llp",
)


# =============================================================================
# Low-level normalizers
# =============================================================================


def normalize_default(value: Any) -> str | None:
    """Lowercase, trim, collapse internal whitespace. Non-strings pass through."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    collapsed = _WHITESPACE_RE.sub(" ", value).strip()
    return collapsed.lower()


def _base_clean(value: str) -> str:
    """Lowercase + strip punctuation + collapse whitespace."""
    stripped = _PUNCT_RE.sub(" ", value)
    collapsed = _WHITESPACE_RE.sub(" ", stripped).strip()
    return collapsed.lower()


def _strip_company_suffix(cleaned: str) -> str:
    """Repeatedly strip trailing legal-form suffixes from a cleaned company name."""
    tokens = cleaned.split()
    changed = True
    while changed and tokens:
        changed = False
        for suf in _COMPANY_SUFFIXES:
            suf_tokens = suf.split()
            n = len(suf_tokens)
            if len(tokens) > n and tokens[-n:] == suf_tokens:
                tokens = tokens[:-n]
                changed = True
                break
    return " ".join(tokens)


def normalize_company(value: Any) -> str | None:
    """Company-name normalization per research.md §7: lowercase + punct-strip +
    whitespace-collapse + trailing legal-suffix strip."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    return _strip_company_suffix(_base_clean(value))


def normalize_phone(value: Any) -> str | None:
    """Digits only per research.md §2. Non-strings pass through."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    return _NON_DIGIT_RE.sub("", value)


def _phone_has_extension_marker(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return bool(_PHONE_EXTENSION_RE.search(value))


def normalize_website(value: Any) -> str | None:
    """Per research.md §3: lowercase → strip scheme → strip leading www. →
    strip single trailing / → strip query+fragment; preserve path segments."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    v = value.strip().lower()
    for scheme in ("https://", "http://"):
        if v.startswith(scheme):
            v = v[len(scheme):]
            break
    if v.startswith("www."):
        v = v[4:]
    for sep in ("?", "#"):
        idx = v.find(sep)
        if idx != -1:
            v = v[:idx]
    if v.endswith("/"):
        v = v[:-1]
    return v


def normalize_postal(value: Any) -> str | None:
    """Per research.md §4: trim. Classification is handled in `classify_postal`."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    return value.strip()


def normalize_tax_id(value: Any) -> str | None:
    """Per research.md §5: strip spaces / hyphens / dots; uppercase (VAT prefixes)."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    return _TAX_ID_SEP_RE.sub("", value).upper()


def normalize_email(value: Any) -> str | None:
    """Lowercase + trim."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    return value.strip().lower()


def normalize_state(value: Any) -> str | None:
    """Canonicalize to 2-letter code when recognized. Falls back to default normalize."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    v = _base_clean(value)
    if v.upper() in _STATE_CODE_TO_NAME:
        return v.upper()
    if v in _STATE_NAME_TO_CODE:
        return _STATE_NAME_TO_CODE[v]
    return v


def _apply_street_token_map(tokens: list[str]) -> list[str]:
    """Apply suffix and directional maps to each token in place."""
    out: list[str] = []
    for tok in tokens:
        if tok in _STREET_SUFFIX_MAP:
            out.append(_STREET_SUFFIX_MAP[tok])
        elif tok in _DIRECTIONAL_MAP:
            out.append(_DIRECTIONAL_MAP[tok])
        else:
            out.append(tok)
    return out


def normalize_street(value: Any) -> str | None:
    """Per research.md §6: suffix + directional map + lowercase + punct strip +
    whitespace collapse."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    cleaned = _base_clean(value)
    tokens = _apply_street_token_map(cleaned.split())
    return " ".join(tokens)


# =============================================================================
# Classifiers — return one of MATCH / PARTIAL_MATCH / MISMATCH
# =============================================================================


def _bool_equal(expected: Any, actual: Any) -> ResultLabel:
    return ResultLabel.MATCH if expected == actual else ResultLabel.MISMATCH


def classify_company(expected: Any, actual: Any) -> ResultLabel:
    """MATCH on equal-after-suffix-strip; PARTIAL_MATCH on token-subset + ≥3 char
    overlap; else MISMATCH."""
    exp_n = normalize_company(expected)
    act_n = normalize_company(actual)
    if exp_n == act_n and exp_n != "":
        return ResultLabel.MATCH
    exp_tokens = set(exp_n.split()) if isinstance(exp_n, str) else set()
    act_tokens = set(act_n.split()) if isinstance(act_n, str) else set()
    if not exp_tokens or not act_tokens:
        return ResultLabel.MISMATCH
    shared = exp_tokens & act_tokens
    if not shared:
        return ResultLabel.MISMATCH
    # Token-subset: one side's tokens ⊆ the other's.
    subset = exp_tokens <= act_tokens or act_tokens <= exp_tokens
    if not subset:
        return ResultLabel.MISMATCH
    overlap_chars = sum(len(t) for t in shared)
    if overlap_chars >= 3:
        return ResultLabel.PARTIAL_MATCH
    return ResultLabel.MISMATCH


def classify_phone(expected: Any, actual: Any) -> ResultLabel:
    """Digits-only equality = MATCH; one side is a proper prefix of the other AND
    the expected carried an explicit extension marker the actual dropped =
    PARTIAL_MATCH; else MISMATCH."""
    exp_digits = normalize_phone(expected) or ""
    act_digits = normalize_phone(actual) or ""
    if not isinstance(exp_digits, str) or not isinstance(act_digits, str):
        return ResultLabel.MISMATCH
    if exp_digits == act_digits and exp_digits != "":
        return ResultLabel.MATCH
    if not exp_digits or not act_digits:
        return ResultLabel.MISMATCH
    exp_had_ext = _phone_has_extension_marker(expected)
    act_had_ext = _phone_has_extension_marker(actual)
    shorter, longer = (
        (exp_digits, act_digits)
        if len(exp_digits) < len(act_digits)
        else (act_digits, exp_digits)
    )
    if longer.startswith(shorter) and (exp_had_ext or act_had_ext) and not (
        exp_had_ext and act_had_ext
    ):
        return ResultLabel.PARTIAL_MATCH
    return ResultLabel.MISMATCH


def classify_website(expected: Any, actual: Any) -> ResultLabel:
    exp_n = normalize_website(expected)
    act_n = normalize_website(actual)
    if exp_n == act_n and isinstance(exp_n, str) and exp_n != "":
        return ResultLabel.MATCH
    return ResultLabel.MISMATCH


def classify_postal(expected: Any, actual: Any) -> ResultLabel:
    """Exact equality = MATCH; 5-digit prefix of the other = PARTIAL_MATCH."""
    exp_n = normalize_postal(expected)
    act_n = normalize_postal(actual)
    if exp_n == act_n and isinstance(exp_n, str) and exp_n != "":
        return ResultLabel.MATCH
    if not isinstance(exp_n, str) or not isinstance(act_n, str):
        return ResultLabel.MISMATCH
    exp_digits = exp_n.replace("-", "").replace(" ", "")
    act_digits = act_n.replace("-", "").replace(" ", "")
    if exp_digits.isdigit() and act_digits.isdigit():
        five_exp = exp_digits[:5]
        five_act = act_digits[:5]
        if len(exp_digits) != len(act_digits) and five_exp == five_act and len(five_exp) == 5:
            return ResultLabel.PARTIAL_MATCH
    return ResultLabel.MISMATCH


def classify_tax_id(expected: Any, actual: Any) -> ResultLabel:
    """Never PARTIAL_MATCH per FR-006."""
    exp_n = normalize_tax_id(expected)
    act_n = normalize_tax_id(actual)
    return (
        ResultLabel.MATCH
        if isinstance(exp_n, str) and exp_n != "" and exp_n == act_n
        else ResultLabel.MISMATCH
    )


def classify_email(expected: Any, actual: Any) -> ResultLabel:
    exp_n = normalize_email(expected)
    act_n = normalize_email(actual)
    if isinstance(exp_n, str) and exp_n != "" and exp_n == act_n:
        return ResultLabel.MATCH
    return ResultLabel.MISMATCH


def classify_state(expected: Any, actual: Any) -> ResultLabel:
    exp_n = normalize_state(expected)
    act_n = normalize_state(actual)
    if isinstance(exp_n, str) and exp_n != "" and exp_n == act_n:
        return ResultLabel.MATCH
    return ResultLabel.MISMATCH


def _street_number(cleaned: str) -> str | None:
    for tok in cleaned.split():
        if tok and tok[0].isdigit():
            return tok
    return None


def classify_street(expected: Any, actual: Any) -> ResultLabel:
    """MATCH on equal-after-normalize; PARTIAL_MATCH when street numbers match
    AND token overlap ≥ 0.7; else MISMATCH."""
    exp_n = normalize_street(expected)
    act_n = normalize_street(actual)
    if isinstance(exp_n, str) and exp_n != "" and exp_n == act_n:
        return ResultLabel.MATCH
    if not isinstance(exp_n, str) or not isinstance(act_n, str):
        return ResultLabel.MISMATCH
    if exp_n == "" or act_n == "":
        return ResultLabel.MISMATCH
    exp_num = _street_number(exp_n)
    act_num = _street_number(act_n)
    if exp_num is None or act_num is None or exp_num != act_num:
        return ResultLabel.MISMATCH
    exp_tokens = set(exp_n.split())
    act_tokens = set(act_n.split())
    if not exp_tokens or not act_tokens:
        return ResultLabel.MISMATCH
    shared = exp_tokens & act_tokens
    # Overlap relative to the shorter side: captures "same street plus suffix/
    # unit/qualifier" while rejecting "different street that happens to share a
    # common word".
    overlap = len(shared) / min(len(exp_tokens), len(act_tokens))
    if overlap >= 0.7:
        return ResultLabel.PARTIAL_MATCH
    return ResultLabel.MISMATCH


def classify_default(expected: Any, actual: Any) -> ResultLabel:
    """Fallback: default normalize + string equality. MATCH or MISMATCH only."""
    if normalize_default(expected) == normalize_default(actual):
        return ResultLabel.MATCH
    return ResultLabel.MISMATCH


# --- Dispatcher ---------------------------------------------------------------

_BOOLEAN_FIELDS: frozenset[str] = frozenset(
    {"company_name.present", "company_name.inferred", "manual_review_required"}
)
_CLASSIFIERS = {
    "company_name.value": classify_company,
    "address.street_1": classify_street,
    "address.street_2": classify_street,
    "address.city": classify_default,
    "address.state": classify_state,
    "address.postal_code": classify_postal,
    "address.country": classify_default,
    "tax_ids.ein": classify_tax_id,
    "tax_ids.state_tax_id": classify_tax_id,
    "tax_ids.vat_id": classify_tax_id,
    "tax_ids.other_tax_id": classify_tax_id,
    "website": classify_website,
    "phone": classify_phone,
    "email": classify_email,
    "review_reason": classify_default,
}


def classify_value(field_name: str, expected: Any, actual: Any) -> ResultLabel:
    """Route (expected, actual) — both non-null — to the field-specific classifier.
    Boolean fields compare strictly. FR-006 exclusions are naturally enforced:
    `classify_tax_id` and `classify_default` (used for `review_reason`) return
    only MATCH/MISMATCH."""
    if isinstance(expected, bool) or isinstance(actual, bool) or field_name in _BOOLEAN_FIELDS:
        return _bool_equal(expected, actual)
    classifier = _CLASSIFIERS.get(field_name, classify_default)
    return classifier(expected, actual)


def normalized_equal(field_name: str, expected: Any, actual: Any) -> bool:
    """Legacy helper retained for any callers outside compare.py."""
    return classify_value(field_name, expected, actual) is ResultLabel.MATCH
