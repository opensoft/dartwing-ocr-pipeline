# Phase 1 Data Model: PDF Preprocessing

This document describes the entities this slice works with. The **persisted**
JSON shape is authoritatively defined in
`contracts/stage1_vendor_identity/v1.0.0/preprocess_output.schema.json` and is
**not** redefined here — this slice consumes the frozen contract as-is (FR-018,
FR-019). What this file captures is the in-memory model and the rules that
produce the persisted shape.

---

## Entity: `PreprocessingInvocation`

One run of the CLI against one PDF.

| Field                | Type          | Source                                  | Notes |
|----------------------|---------------|-----------------------------------------|-------|
| `document_folder`    | `Path`        | CLI arg                                 | Must exist and contain `source_file`. |
| `source_file_name`   | `str`         | CLI arg (default `"source.pdf"`)        | Recorded in artifact as `source_file`. |
| `document_id`        | `str`         | derived from `document_folder.name`     | FR-002. |
| `pipeline_version`   | `str`         | CLI arg override OR `"stage1-preprocess-v0.1"` | FR-018. |
| `contract_set_version` | `str`       | constant `"1.0.0"`                      | Frozen (FR-018). |
| `ingestion_config`   | `IngestionConfig` | hard-coded for stage 1              | `paddleocr_vl=enabled`, `falcon_*=not_implemented`. |

**Lifecycle**: constructed from CLI args → drives `Pipeline.run()` → emits one
`PreprocessOutput` dict → validator call → disk write.

---

## Entity: `PageRecord`

One entry in `pages[]`.

| Field              | Type     | Rules |
|--------------------|----------|-------|
| `page_number`      | `int`    | 1-based, assigned in PDF order. |
| `width`            | `int`    | Pixels of the **rasterized** image (300 DPI), after rotation normalization. FR-005. |
| `height`           | `int`    | Pixels of the rasterized image, post-rotation. |
| `rotation_detected` | `int`   | One of `{0, 90, 180, 270}`. If PaddleOCR reports a different angle, snap to nearest and record a warning. FR-006. |
| `blocks`           | `list[Block]`        | Sorted by `reading_order` ascending. |
| `raw_ocr_lines`    | `list[OcrLine]`      | Sorted by deterministic `(bbox.y, bbox.x, line_id)` key. |

**State transitions**:
- `rasterized` (has width/height) → `ocred` (has raw_ocr_lines) → `laid_out`
  (has blocks with reading_order) → `emitted`.
- On partial failure (Decision 7 in research.md):
  - rasterization failed → `width=1, height=1, rotation_detected=0, blocks=[], raw_ocr_lines=[]`, warning recorded.
  - OCR failed, layout succeeded → `raw_ocr_lines=[]`, `blocks` kept if layout produced any.
  - Layout failed, OCR succeeded → `blocks=[]`, `raw_ocr_lines` kept.

---

## Entity: `Block`

A layout-level region on one page.

| Field         | Type     | Rules |
|---------------|----------|-------|
| `block_id`    | `str`    | `f"p{page_number}_b{n}"`, `n` = `reading_order`. Matches `^p\d+_b\d+$`. |
| `block_type`  | `str`    | One of `{text, title, table, figure, header, footer}`. Map PP-Structure labels accordingly. |
| `bbox`        | `list[int]` | `[x0, y0, x1, y1]`, integer pixels, all `≥ 0`. In the **rasterized page's** coordinate space. |
| `reading_order` | `int`  | Unique per page, contiguous starting at 1. |
| `text`        | `str`    | May be empty (e.g., a figure with no recognized text). FR-020 — empty string, not `null`. |
| `confidence`  | `float`  | `[0.0, 1.0]`. For table/figure blocks with no text, use `0.0` deterministically. |

**Block-type mapping** (PP-Structure → schema):

| PP-Structure label | Schema `block_type` |
|--------------------|---------------------|
| `text`             | `text`              |
| `title`            | `title`             |
| `table`            | `table`             |
| `figure` / `image` | `figure`            |
| `header`           | `header`            |
| `footer`           | `footer`            |
| anything else      | `text` (fallback, warning recorded) |

---

## Entity: `OcrLine`

A single OCR-detected text line.

| Field         | Type     | Rules |
|---------------|----------|-------|
| `line_id`     | `str`    | `f"p{page_number}_l{n}"`, `n` increments per page starting at 1 in sorted order. Matches `^p\d+_l\d+$`. |
| `bbox`        | `list[int]` | `[x0, y0, x1, y1]`, integer pixels, `≥ 0`. |
| `text`        | `str`    | OCR text; empty string allowed (FR-020). |
| `confidence`  | `float`  | `[0.0, 1.0]`. |

**Ordering rule**: within a page, lines are sorted by `(y0, x0)` with a
tie-break on the deterministic PaddleOCR detection index, then renumbered.

---

## Entity: `TableRecord`

One entry in top-level `tables[]`.

| Field          | Type         | Rules |
|----------------|--------------|-------|
| `page_number`  | `int`        | 1-based page reference. |
| `block_id`     | `str`        | The `Block.block_id` of the `block_type == "table"` that represents this table. |
| `bbox`         | `list[int]`  | Mirror of the block's bbox. |
| `rows`         | `int`        | Detected row count (0 if unknown). |
| `columns`      | `int`        | Detected column count (0 if unknown). |
| `cells`        | `list[Cell]` | Optional structural grid (`[{row, col, bbox, text}]`). Omitted if PP-Structure's table recognizer did not produce a grid. |

> The frozen `preprocess_output.schema.json` declares
> `tables: array of object` with no per-property constraints (i.e. anything
> under `tables[*]` is accepted). The fields above are this slice's **internal
> convention** for what goes into those objects. They are stable and
> deterministic, but the schema does not enforce them — so changing them later
> is not a contract change, only a pipeline-version change.

**FR-024 guard**: `TableRecord` MUST NOT contain keys like
`line_item_description`, `unit_price`, `quantity`, etc. Structural only.

---

## Entity: `QualitySignals`

| Field            | Type   | Rules |
|------------------|--------|-------|
| `scan_quality`   | `str`  | One of `{good, fair, poor}`. Derived from rules in research.md Decision 6. |
| `skew_detected`  | `bool` | `True` iff any page's pre-snap skew angle `≥ 2.0°`. |
| `noise_level`    | `str`  | One of `{low, medium, high}`. Derived from `low_confidence_ratio`. |

Internal (non-persisted) supporting metrics:
- `avg_line_confidence: float`
- `low_confidence_ratio: float`
- `max_skew_deg: float`

---

## Entity: `IngestionSourceStatus`

| Field      | Type   | Rules |
|------------|--------|-------|
| `enabled`  | `bool` | For stage 1: `paddleocr_vl=True`, `falcon_ocr=False`, `falcon_perception=False`. |
| `status`   | `str`  | One of `{success, failure, not_implemented}`. |

The top-level `ingestion_sources` is a fixed three-key dict; keys are never
added or removed by this slice (FR-015).

---

## Entity: `Warning` (just a string)

Per FR-014, `warnings[]` is an array of human-readable strings with `minLength
≥ 1`. Convention (unenforced by schema but used by this slice):

- `"page {N}: rotation snapped from {deg}° to {allowed}° ({reason})"`
- `"page {N}: rasterization failed: {short_reason}"`
- `"page {N}: OCR failed: {short_reason}"`
- `"page {N}: layout extraction failed: {short_reason}"`
- `"ingestion_sources.paddleocr_vl: {status} ({short_reason})"`
- `"block type '{raw}' mapped to 'text' fallback on page {N}"`

---

## Derived / Computed Fields

### `page_count`
`len(pages)`. Set after all pages are emitted. Integer `≥ 1` (if `0`, the
invocation has already failed per User Story 3 AC #3 and no artifact is
written).

### `document_text`
Computed after all pages are assembled:

```python
"\n\n".join(
    "\n".join(block.text for block in page.blocks)
    for page in sorted(pages, key=lambda p: p.page_number)
)
```

Deterministic, reading-order preserving (research.md Decision 4).

---

## Validation Order (Inside `Pipeline.run()`)

1. **Input validation** (before rasterization): folder exists, `source.pdf`
   exists, file is a PDF (magic-byte check), not encrypted, `page_count > 0`.
   Any failure → raise, non-zero exit, no artifact.
2. **Per-page processing**: rasterize → OCR → layout → table capture. Failures
   at each step produce empty arrays + a warning (Decision 7).
3. **Artifact assembly**: build the dict with all required keys in schema
   order.
4. **Contract validation**: call the existing `ledgerlinc_ocr.validator`
   against `preprocess_output.schema.json`. If it rejects, this is an internal
   bug — raise, non-zero exit (code 3), no artifact written (FR-019).
5. **Atomic write**: write to `preprocess_output.json.tmp`, `fsync`, `rename`
   → `preprocess_output.json`. Guarantees no partial artifact on crash.

---

## What this slice does NOT model

Per FR-021/022/024, the following are **not** part of this data model and MUST
NOT appear in any emitted artifact:

- Any vendor-identity fields (`company_name`, `address`, `tax_ids`, `website`,
  `phone`, `email`).
- Line-item fields (`description`, `quantity`, `unit_price`, `line_total`).
- Routing/review fields (`manual_review_required`, `review_reason`, `decision`).
- Voter metadata, consensus fields, or confidence scores tied to business
  fields.

These belong to downstream slices. A schema-validation failure on any of these
keys appearing would be the validator's responsibility, but this slice should
never produce them in the first place.
