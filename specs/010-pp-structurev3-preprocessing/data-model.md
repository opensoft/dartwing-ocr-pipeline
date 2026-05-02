# Data Model: PPStructureV3 Preprocessing Migration

**Feature**: 010-pp-structurev3-preprocessing
**Phase**: 1 (design)
**Scope note**: This slice does **not** change the persisted JSON contract. `contracts/stage1_vendor_identity/v1.0.0/preprocess_output.schema.json` stays at `contract_set_version = "1.0.0"`. What follows is the in-flight data model: what V3 emits, the transformation pipeline that maps V3 output onto the existing artifact fields, and the new internal entities (warning categories, engine-init error) that govern the migration's runtime behavior.

Artifact-level entities already documented in `contracts/stage1_vendor_identity/v1.0.0/preprocess_output.schema.json` and `specs/003-pdf-preprocessing/data-model.md` are not re-documented here; only deltas are called out.

## Entity overview

| Entity | Scope | Persisted? | Changed by this slice? |
|--------|-------|-----------|------------------------|
| `PreprocessOutput` | artifact | yes | values only — no shape change |
| `Page` | artifact | yes | values only — no shape change |
| `LayoutBlock` | artifact | yes | values only — no shape change; new `block_type` mappings for V3 labels |
| `RawOcrLine` | artifact | yes | values only — OCR source shifts from PP-OCRv4 standalone → PP-OCRv5 via V3 |
| `Table` | artifact | yes | values only — V3 emits HTML via a different code path; dims extraction unchanged |
| `IngestionSource.paddleocr_vl` | artifact | yes | `status` may downgrade to `"failure"` based on silent-empty page detection — NEW trigger |
| `Warning` (string in `warnings[]`) | artifact | yes | new category-tokenized prefix format for four categories |
| `PipelineVersion` (string) | artifact | yes | bumped prefix + engine segment |
| `DebugPageImage` (PNG on disk) | developer-only output | no (never committed) | opt-in via `--write-page-images`; outside FR-004 determinism (FR-022) |
| `PageRasterFrame` | in-flight | no | NEW — single rasterized page yielded and released under the FR-005a streaming lifecycle |
| `V3RawResult` | in-flight | no | NEW — container around `PPStructureV3` per-page output |
| `WarningCategory` | in-flight | no | NEW — closed enum + downgrading semantics |
| `EngineInitError` | in-flight | no | NEW — exception type for FR-016 hard-fail |

## Persisted entities (deltas only)

### `LayoutBlock`

No schema change. `block_type` is constrained to the frozen enum `{text, title, table, figure, header, footer}`. `confidence` on each block is populated from `layout_det_res.boxes[*].score` (R-013 / FR-004) when the value is numeric, finite, and inside `[0.0, 1.0]`; missing or schema-unusable values persist as `null`. New V3 layout labels are mapped to existing values via `PPSTRUCTURE_LABEL_TO_BLOCK_TYPE` per R-003:

| V3 label (from `layout_det_res.boxes[*].label`) | Mapped `block_type` | Rationale |
|------------------------------------------------|---------------------|-----------|
| `paragraph_title` | `title` | PP-DocLayout_plus-L section heading |
| `doc_title` | `title` | PP-DocLayout_plus-L document title |
| `abstract` | `text` | no semantic slot; collapses to text |
| `content` | `text` | body content |
| `figure_title` | `text` | caption, not the figure itself |
| `formula_number` | `text` | numeric annotation, collapsed |
| `chart_title` | `text` | caption, collapsed |
| `table_title` | `text` | caption, collapsed |
| `seal` | `text` | seal-recognition is off, but layout may still label regions |
| *any unlisted label* | `text` (fallback) + `[unknown_layout_label]` warning (FR-006) | defensible default; surfaces unknowns to humans |

V2 labels (`text`, `title`, `table`, `figure`, `image`, `header`, `footer`, `reference`, `equation`, `list`) retain their current mapping from `src/ledgerlinc_ocr/preprocessing/ocr.py:15-26`, so existing V2-era integration tests do not need semantic updates — only OCR-text updates.

`text` content on a block comes from concatenating the OCR lines that fall inside the block's bbox, joined with a single space. This matches V2 behavior; V3's richer `parsing_res_list` Markdown is discarded at the persistence boundary.

`reading_order` is assigned by stable sort on `(bbox.y0, bbox.x0, det_idx)` — unchanged from V2. `reading_order` values are `1..N` per page, dense and without gaps.

### `RawOcrLine`

No schema change. Source shifts from a separate `PaddleOCR(...)` call (PP-OCRv4) to V3's `overall_ocr_res.rec_texts` / `.rec_boxes` / `.rec_scores` (PP-OCRv5). Per-line entry is assembled from parallel arrays:

```
line_i = {
    "line_id":   f"p{page_number}_l{i+1}",            # after sort (see below)
    "bbox":      _clip_bbox(_bbox_from_points(overall_ocr_res.rec_boxes[det_i]), width, height),
    "text":      overall_ocr_res.rec_texts[det_i],
    "confidence": _persist_confidence(overall_ocr_res.rec_scores, det_i),  # bounded float or null per FR-004 / R-013
}
```

`_persist_confidence(scores, i)` returns `float(scores[i])` when the index exists and the value is numeric, finite, and inside the schema's `[0.0, 1.0]` confidence range; otherwise it returns `None`. **No clamping** to `[0.0, 1.0]` (V2's clamp is retired under 010 per Clarifications Q18 / FR-004); invalid values become `null` rather than fabricated in-range numbers. **No filter is applied in this function for low-confidence lines** — recognition-threshold filtering happens inside PP-OCRv5 using the engine's default (R-012 / FR-007), and `raw_ocr_lines[*]` is whatever the engine returns after that.

`line_id` is minted AFTER the `(bbox.y0, bbox.x0, det_idx)` stable sort. Identifier scheme (`p{page}_l{n}`) is unchanged from 003.

### `Table`

No schema change. V3 exposes per-table HTML fragments via `table_res_list`. `_parse_table_dims(html) → (rows, columns)` in `src/ledgerlinc_ocr/preprocessing/ocr.py:113-132` is reused verbatim — the regex logic treats the HTML as opaque and is engine-version-agnostic. `cells` list construction is retained; V3's cell_bbox shape is a superset of V2's for our purposes (length-4 lists per cell).

Projection boundary (FR-021 / R-014): `tables[]` is populated from V3's `table_res_list`, projected into the v1.0.0 schema shape **as of 010's landing commit** (strict-current-shape, Session 2026-04-23 Q24). Richer V3 content beyond the schema (raw HTML string, per-cell metadata, per-cell scores) is discarded at the persistence boundary in `ocr._extract_blocks()` / `ocr._extract_tables()`. `_parse_table_dims()` reads the HTML only to derive `rows`/`columns`; the HTML string itself is NOT persisted. Future AMENDMENTS entries that widen the schema (e.g., add optional `cell_confidence`) require a matching preprocessing code change before the new field is emitted — silent auto-pickup of schema additions is prohibited. `tables[]` ordering follows block order within each page (same sort key as `blocks[]`), preserving FR-004 byte-identical reruns.

### `IngestionSource.paddleocr_vl`

No schema change. Allowed `status` values remain `"success" | "failure" | "not_implemented"`.

New downgrade trigger: `status` is `"failure"` if ANY of these conditions fires, otherwise `"success"` (per existing `pages_with_paddleocr_output >= 1` rule):

- **Existing**: `pages_with_paddleocr_output < 1` (every page failed to produce either blocks or lines — the aggregate all-pages-empty case from 003).
- **NEW (FR-003)**: any page has `len(raw_ocr_lines) > 0 AND len(blocks) == 0`.
- **NEW (FR-019)**: any page has `len(blocks) > 0 AND len(raw_ocr_lines) == 0 AND at least one block with block_type ∈ {text, title, header, footer}`.

Signal flows into `ingestion_sources.py` via a new `silent_empty_page_detected: bool` parameter (or equivalent field). Suspicious-single-block (FR-018) and unknown-label (FR-006) do NOT downgrade.

### `Warning`

Warnings remain flat strings in `preprocess_output.warnings[]`. Four new categories land in this slice, all with the pinned prefix format `"page N: [<category_token>] <detail>"` (FR-020).

| Category token | Trigger (FR) | Detail template | Downgrades status? |
|----------------|--------------|-----------------|--------------------|
| `silent_empty_layout` | FR-003 | `"OCR produced K lines but layout returned zero blocks"` | yes |
| `silent_empty_ocr` | FR-019 | `"OCR returned zero lines despite K text-type blocks"` | yes |
| `suspicious_single_block` | FR-018 | `"single block covers K OCR lines"` | no |
| `unknown_layout_label` | FR-006 | `"label=<label_string>"` | no |

Ordering within `warnings[]` (FR-020):
1. Page-ascending by page number (aggregate / non-page-scoped warnings sort after all page-scoped ones).
2. Within a page, categorized warnings sort in **vocabulary lexical order** (`silent_empty_layout`, `silent_empty_ocr`, `suspicious_single_block`, `unknown_layout_label`).
3. Non-categorized warnings retain today's ordering (appended in emission order) and sort AFTER the categorized ones. Two sub-cases per spec FR-020 rule 4:
   - **Page-scoped non-categorized** (engine-runtime-error messages like `"page N: OCR failed: <ExceptionClass>: <message>"`, `"page N: layout extraction failed: ..."`, per-page rasterization-failed, rotation-normalization) — sort AFTER categorized warnings *within that page*, in emission order.
   - **Aggregate / non-page-scoped** (e.g., `"ingestion_sources.paddleocr_vl: failure (all pages failed)"`) — sort LAST in the document, after every page-scoped warning (categorized or non-categorized), in emission order.

### `PipelineVersion` (string)

No schema change. Target value string: `"stage1-preprocess-v0.2.0+paddleocr3.5.0.0000000.dpi300"`.

Encoding (`src/ledgerlinc_ocr/preprocessing/version.py`):
- `SLICE_PREFIX = "stage1-preprocess"` (unchanged)
- `SEMVER = "v0.2.0"` (was `"v0.1.0"`)
- `paddleocr_version` from `importlib.metadata.version("paddleocr")` → `"3.5.0"`
- `weights_hash7 = "0000000"` (placeholder; real hashing deferred per R-007)
- `DPI = 300` (unchanged)

## In-flight entities (NEW)

### `PageRasterFrame`

Single rasterized PDF page yielded by `src/ledgerlinc_ocr/preprocessing/rasterize.py` into the `pipeline.py` per-page loop. Not persisted; lives only long enough for that page's OCR/layout work to complete.

| Field | Type | Notes |
|-------|------|-------|
| `page_number` | `int` | 1-based page ordinal; preserves document order |
| `width` / `height` | `int` | page dimensions after rasterization; copied into artifact-owned bbox clipping logic |
| `image` | `PIL.Image.Image` | current page raster only; eligible for release after page-owned lines/blocks/tables/warnings have been copied |
| `failure` | `PageRasterFailure \| None` | per-page rasterization failure sentinel; preserved under the streaming API exactly as under the list-based API |

Lifecycle guarantee (FR-005a / R-011): only one `PageRasterFrame.image` needs to remain resident at a time. `pipeline.py` consumes the iterator in page order, copies page-owned artifact data out, and then allows the page image to be released before requesting the next raster. No previous-page or next-page header/footer context is threaded through this entity.

### `V3RawResult`

Container around a single `PPStructureV3` per-page return. Not persisted; lives for the duration of `ocr.run_page()`. Fields (named as they appear in the upstream API surface):

| Field | Type | Source of artifact content |
|-------|------|----------------------------|
| `layout_det_res.boxes` | list of `{label: str, coordinate: list[4] \| list[[2],[2],[2],[2]], score: float}` | `pages[*].blocks` |
| `overall_ocr_res.rec_texts` | list of `str` | `pages[*].raw_ocr_lines[*].text` |
| `overall_ocr_res.rec_boxes` | list of bbox (4-point poly or 4-tuple) | `pages[*].raw_ocr_lines[*].bbox` |
| `overall_ocr_res.rec_scores` | list of `float` | `pages[*].raw_ocr_lines[*].confidence` |
| `table_res_list` | list of `{html: str, cell_bbox: list[list[4]]}` | `tables[*]` |
| `parsing_res_list` | list of `{block_label, block_content, ...}` | **DISCARDED** (no schema slot; see R-002) |

Extraction logic in `ocr._extract_lines()` and `ocr._extract_blocks()` reads only the first four axes. `parsing_res_list` is present in memory but not persisted.

### `WarningCategory`

Closed enum in `src/ledgerlinc_ocr/preprocessing/warnings.py`:

```python
WARNING_CATEGORIES = [
    "silent_empty_layout",
    "silent_empty_ocr",
    "suspicious_single_block",
    "unknown_layout_label",
]
STATUS_DOWNGRADING = {"silent_empty_layout", "silent_empty_ocr"}
```

Consumers:
- `pipeline.py` — emits warnings from the four categories via `build_warning(page, token, detail)`.
- `ingestion_sources.py` — reads `any(cat in STATUS_DOWNGRADING for cat in detected_categories)` to compute the `silent_empty_page_detected` signal.

Extension policy: a fifth category requires an AMENDMENTS entry (FR-020) AND an update to SC-002's grep list. Not extensible ad-hoc.

### `EngineInitError`

New exception type in `src/ledgerlinc_ocr/preprocessing/errors.py`:

```python
class EngineInitError(PreprocessingError):
    """FR-016: raised when PPStructureV3 cannot be constructed or the lazy engine lookup fails.

    Carries structured cause information so the CLI layer can emit the FR-016 error
    envelope without re-parsing the exception string.
    """
    exit_code = EXIT_INTERNAL_ERROR

    def __init__(
        self,
        message: str,
        cause_class: str,
        cause_module: str,
        missing_weight: str | None = None,
        weight_hoster_url: str | None = None,
    ):
        super().__init__(message)
        self.cause_class = cause_class
        self.cause_module = cause_module
        self.missing_weight = missing_weight
        self.weight_hoster_url = weight_hoster_url
```

Construction sites:
- `ocr._get_engine()` — wraps the `PPStructureV3(...)` call in a try/except; any exception is classified (weight-related vs. generic) and re-raised as `EngineInitError` with structured fields.

Consumer:
- `cli.py main()` — adds a new except branch that emits the FR-016 JSON envelope on stderr with exit code `EXIT_INTERNAL_ERROR` (3). No artifact is ever written.

## Validation rules (migration-specific)

These rules are enforced by code (deterministic, not model-inferred) and map 1:1 to FRs:

| Rule | Enforcement site | FR |
|------|------------------|-----|
| `len(raw_ocr_lines) > 0 AND len(blocks) == 0` ⇒ emit `[silent_empty_layout]`, downgrade status | `pipeline.py` per-page loop | FR-003 |
| `len(blocks) > 0 AND len(raw_ocr_lines) == 0 AND ≥1 text-type block` ⇒ emit `[silent_empty_ocr]`, downgrade status | `pipeline.py` per-page loop | FR-019 |
| `len(raw_ocr_lines) >= 2 AND len(blocks) == 1` ⇒ emit `[suspicious_single_block]` | `pipeline.py` per-page loop | FR-018 |
| V3 label not in `PPSTRUCTURE_LABEL_TO_BLOCK_TYPE` ⇒ map to `"text"` + emit `[unknown_layout_label]` | `ocr._extract_blocks()` | FR-006 |
| `PPStructureV3(...)` raises during init ⇒ `EngineInitError`, non-zero exit, no artifact | `ocr._get_engine()` → `cli.main()` | FR-016 |
| Label-fallback warnings do NOT downgrade status | `ingestion_sources.build_ingestion_sources()` ignores `unknown_layout_label` / `suspicious_single_block` | FR-006, FR-018 |
| Two runs on same PDF + deps ⇒ byte-identical output | covered by R-005 (threading, oneDNN, seed, post-sort, FR-020 warning ordering) | FR-004, SC-003 |
| Every page with `len(raw_ocr_lines) > 0` has `≥1` block (or fires FR-003) | covered by FR-002 + FR-003 being formal inverses | FR-002 |
| `confidence` on blocks and lines persisted as an in-range engine float or `null` for missing / non-finite / out-of-range values | `ocr._extract_lines()` + `ocr._extract_blocks()` | FR-004, R-013 |
| OCR recognition threshold at PP-OCRv5 engine default; no project override | `ocr._get_engine()` (no `text_rec_score_thresh` / `drop_score` override) | FR-007, R-012 |
| `tables[]` populated from V3 `table_res_list`, projected into v1.0.0 shape; richer content discarded | `ocr._extract_blocks()` / `ocr._extract_tables()` | FR-021, R-014 |
| Debug `page_*.png` emission gated on `--write-page-images`; not covered by FR-004 | `cli.py` → `rasterize.py` / `pipeline.py` | FR-022, R-015 |

## State transitions

`ingestion_sources.paddleocr_vl.status` computed at artifact-assembly time from two flags:

```
all_pages_empty = (pages_with_paddleocr_output < 1)
silent_empty_detected = any(page fired FR-003 OR FR-019 for pages in this document)

status = "failure" if (all_pages_empty OR silent_empty_detected) else "success"
```

There is no `"degraded"` middle state (the frozen enum is `{success, failure, not_implemented}`; `"not_implemented"` is only used for Falcon sources). A single page hitting FR-003 or FR-019 downgrades the whole document per Clarifications Q6 (spec Assumptions).
