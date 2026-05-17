"""Closed warning-category vocabulary and FR-020 ordering helpers.

This module owns the four bracketed warning categories emitted by preprocessing
(FR-003, FR-006, FR-018, FR-019) and the sort key that renders the final
`warnings` array byte-stable across reruns per FR-020 / research R-009.
"""

from __future__ import annotations

import re

# FR-020 closed vocabulary, held in lexical order so this list is also the
# within-page sort order for categorized warnings.
WARNING_CATEGORIES: list[str] = [
    "silent_empty_layout",     # FR-003 — downgrades ingestion_sources.paddleocr_vl.status
    "silent_empty_ocr",        # FR-019 — downgrades ingestion_sources.paddleocr_vl.status
    "suspicious_single_block", # FR-018 — does NOT downgrade
    "unknown_layout_label",    # FR-006 — does NOT downgrade
]

# Subset of WARNING_CATEGORIES whose presence downgrades
# `ingestion_sources.paddleocr_vl.status` to "failure" (data-model §IngestionSource).
STATUS_DOWNGRADING: frozenset[str] = frozenset({
    "silent_empty_layout",
    "silent_empty_ocr",
})

_CATEGORY_INDEX: dict[str, int] = {tok: i for i, tok in enumerate(WARNING_CATEGORIES)}

# "page N: [<token>] <detail>" — group 1 is the 1-based page number (N),
# group 2 is the category token.
_CATEGORIZED_RE = re.compile(r"^page (\d+): \[([a-z_]+)\] ")

# "page N: <free-form>" without a bracketed token — page-scoped but non-categorized
# (e.g., "page 2: OCR failed: ...", "page 3: rasterization failed: ...").
_PAGE_FREEFORM_RE = re.compile(r"^page (\d+): ")

# Sort-key constants: categorized warnings sort first (0), page-scoped free-form
# (non-categorized) warnings sort after all categorized on their page (1),
# aggregate / non-page-scoped warnings sort last in the document (2).
_BUCKET_CATEGORIZED = 0
_BUCKET_PAGE_FREEFORM = 1
_BUCKET_AGGREGATE = 2

# Large sentinel for the page-index axis of aggregate warnings so they sort
# after every page-scoped one regardless of the corpus's page count.
_AGGREGATE_PAGE_SENTINEL = 1_000_000


def build_warning(page_number: int, category_token: str, detail: str) -> str:
    """Render an FR-020-compliant categorized warning string.

    Raises ValueError if the category token is not in WARNING_CATEGORIES, so
    a typo at the call site fails loudly instead of producing a warning that
    the sort key would later push into the "page free-form" bucket.
    """
    if category_token not in _CATEGORY_INDEX:
        raise ValueError(
            f"unknown warning category {category_token!r}; "
            f"allowed: {WARNING_CATEGORIES}"
        )
    return f"page {page_number}: [{category_token}] {detail}"


def warning_sort_key(warning: str) -> tuple[int, int, int]:
    """Return a stable 3-tuple sort key for FR-020 ordering.

    Tuple shape is `(page_number, bucket, category_index)`:
    - `page_number`: 1-based page for page-scoped warnings; the aggregate
      sentinel for warnings without a `page N:` prefix.
    - `bucket`: 0 = categorized, 1 = page-scoped free-form, 2 = aggregate.
    - `category_index`: lexical-order index inside WARNING_CATEGORIES for
      categorized warnings; 0 for non-categorized (ties broken by
      `sorted`'s stable sort, which preserves insertion order — FR-020 step 3).
    """
    m = _CATEGORIZED_RE.match(warning)
    if m is not None:
        page_num = int(m.group(1))
        token = m.group(2)
        idx = _CATEGORY_INDEX.get(token, len(WARNING_CATEGORIES))
        return (page_num, _BUCKET_CATEGORIZED, idx)

    m = _PAGE_FREEFORM_RE.match(warning)
    if m is not None:
        return (int(m.group(1)), _BUCKET_PAGE_FREEFORM, 0)

    return (_AGGREGATE_PAGE_SENTINEL, _BUCKET_AGGREGATE, 0)


def sort_warnings(warnings: list[str]) -> list[str]:
    """Return a new list sorted per FR-020. Input is not mutated."""
    return sorted(warnings, key=warning_sort_key)
