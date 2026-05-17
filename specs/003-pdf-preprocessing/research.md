# Phase 0 Research: PDF Preprocessing

This document resolves the unknowns surfaced in `plan.md`'s Technical Context
and pins down the technology choices for the stage 1 PDF preprocessing slice.
Every decision below is scoped to what stage 1 actually needs — PDF-in,
`preprocess_output.json`-out, deterministic, CPU-only, inside the devcontainer.

---

## Decision 1 — PDF rasterization library

**Decision**: `pypdfium2` (PDFium bindings via `ctypes`), pinned `>=4.30,<5`.

**Rationale**:
- Pure Python wheels for Linux x86_64; no system poppler / cairo dependency,
  which keeps the lightweight devcontainer lightweight.
- PDFium's rasterization is **deterministic** for a given (file, page, DPI,
  rotation) tuple, which is non-negotiable for FR-012 / SC-002 (byte-identical
  reruns).
- Renders directly to a `Pillow` `Image` (or raw buffer) at an arbitrary DPI
  — we fix it at 300 (FR-004).
- Surfaces encryption as a clear exception type, which lets us honor the
  "encrypted → malformed" clarification (Edge Case, User Story 3 AC #3) without
  probe-hacking.
- Actively maintained; 4.x line is current as of 2026-Q1.

**Alternatives considered**:
- `pdf2image` (wraps poppler `pdftoppm`): requires poppler in the container;
  adds OS dependency; subprocess roundtrip per page is slower; external binary
  upgrades can shift output, risking determinism regressions.
- `PyMuPDF` (`fitz`): fast, great quality, but is AGPL unless a commercial
  license is acquired. Dartwing has not cleared that licensing path — rejecting
  now rather than retrofitting later.
- `pdfplumber` / `pdfminer.six`: text-extraction oriented, not rasterization.
  Out of scope.
- PaddleOCR's built-in PDF loader: convenient but opaque about DPI control and
  rotation handling; we want explicit control over rasterization so the
  coordinate space matches the image PaddleOCR sees.

---

## Decision 2 — OCR + layout + table engine

**Decision**: `PaddleOCR` + `PP-StructureV2` running in CPU mode, pinned to the
project's existing `paddleocr>=2.8,<3` line with `paddlepaddle>=3.0,<4` (CPU
build).

**Rationale**:
- Constitution + architecture doc name `PaddleOCR-VL-1.5` as the Trijunction
  ingestion source. Using the same family (layout + text + tables in one call)
  keeps stage 1 aligned with the target architecture in shape (FR-016 — Falcon
  sources can be added later without changing the contract).
- PaddleOCR is already a transitive dependency of the prototype
  (`requirements.txt`), so developers already have a working pin.
- CPU inference is viable for one invoice at a time on the devcontainer; stage
  1 has no latency gate.
- PP-StructureV2 produces the closed-vocabulary block types we need:
  `{text, title, table, figure, header, footer}` (FR-008).
- Table-structure output ("HTML/grid" per detected table) maps directly onto
  our `tables[]` structural records (FR-011).

**Determinism configuration** (required for FR-012 / SC-002):
- `paddle.seed(0)` at worker init.
- `use_gpu=False`, `use_mp=False` (no multiprocessing; multiprocessing reorders
  page-level returns).
- Single-threaded inference: `cpu_threads=1`.
- Rotation classifier on (`use_angle_cls=True`) — produces the one of
  `{0,90,180,270}` snap we need for `rotation_detected`. If it returns anything
  else, we snap to the nearest allowed value and emit a warning (FR-006).
- Sort detection results by `(bbox.y, bbox.x)` in our code, never relying on
  PaddleOCR's native order, because minor model-build differences across
  environments can reorder equal-score detections.

**Alternatives considered**:
- `tesseract` + `pdfplumber` for layout: simpler but does not produce layout
  blocks or table structure in a consistent schema; does not match the
  Trijunction architecture in shape.
- `docTR`: Torch-based; architecturally different; not aligned with the
  `PaddleOCR-VL` named source in the architecture doc. Dropped to keep
  stage 1 shape close to target.
- `EasyOCR`: text-only, no layout; would force us to glue a separate layout
  analyzer, which is strictly more complexity for no gain.
- Falcon OCR / Falcon Perception: architecturally expected (Trijunction), but
  stage 1 explicitly ships them as `not_implemented` (FR-015). Out of scope
  for this slice.

---

## Decision 3 — Rasterization DPI

**Decision**: Fixed 300 DPI, project-wide constant — not a CLI flag.

**Rationale**:
- Standard OCR resolution. PaddleOCR-VL was trained on images near this
  density. Below 200 DPI character recall falls off; above 400 DPI adds time
  and memory without measurable recall gain on invoice-sized pages.
- Pinned by clarification (`spec.md` — Clarifications 2026-04-20 Q1).
- Making it a constant instead of a flag is deliberate: any change is a
  pipeline-version bump (FR-004), not a per-run toggle, so bboxes across the
  corpus stay comparable for evaluation.

**Alternatives considered**: 200 DPI (rejected — weak on small-font footers),
400 DPI (rejected — CPU-time regression on multi-page docs, no accuracy win).

---

## Decision 4 — `document_text` join strategy

**Decision**: Join blocks page-by-page in `reading_order`, pages in
`page_number` order, using `"\n"` between blocks within a page and `"\n\n"`
between pages.

**Rationale**:
- Deterministic and documented (FR-010).
- Double-newline page separator lets downstream consumers detect page
  boundaries without extra metadata while keeping the string human-readable.
- Using `reading_order` (not raw detection order) guarantees the text reflects
  the layout analyzer's reading order, which is what we want evidence to cite.

**Alternatives considered**:
- Form-feed (`\f`) page separator: technically correct, but trips JSON viewers
  and diff tools; hurts debuggability for no functional gain.
- Concatenating `raw_ocr_lines` instead of `blocks`: rejected — lines are
  fine-grained evidence, blocks are the reading-order unit. Mixing them
  muddies the contract.

---

## Decision 5 — Identifier minting

**Decision**:
- Block IDs: `p{page_number}_b{n}` where `n` increments per page starting at 1.
- Line IDs:  `p{page_number}_l{n}` where `n` increments per page starting at 1.
- `reading_order` per block = `n` (blocks are renumbered in final reading order
  before IDs are assigned).

**Rationale**:
- Page-scoped minting keeps IDs stable even if other pages change (e.g., one
  page seeded as unreadable in User Story 3).
- `reading_order == block index` collapses two moving parts into one; no
  arithmetic, no drift.
- Matches the schema's regex constraints directly (`^p\d+_b\d+$`,
  `^p\d+_l\d+$`).

**Alternatives considered**:
- Hash-based IDs (e.g., `p1_b_<hash>`): rejected — unstable under OCR text
  jitter; violates byte-identical rerun guarantee.
- Document-scoped IDs (`b001`, `b002`): rejected — schema regex requires
  page prefix, and page-scoping is safer under partial failures.

---

## Decision 6 — Quality signal thresholds (calibrated)

**Decision**: Derive all three signals from the three pinned input metrics
(`spec.md` FR-013):

- `avg_line_confidence` = mean of `confidence` across all `raw_ocr_lines` over
  all pages.
- `low_confidence_ratio` = fraction of lines with `confidence < 0.60`.
- `max_skew_deg` = max absolute detected skew angle per page (before rotation
  snapping).

**Final thresholds** (calibrated against the populated 20-document corpus in
GitHub issue #1):

| Signal          | Value  | Condition                                           |
|-----------------|--------|-----------------------------------------------------|
| `scan_quality`  | good   | `avg_line_confidence ≥ 0.85` AND `low_confidence_ratio ≤ 0.10` |
|                 | fair   | `avg_line_confidence ≥ 0.70` AND `low_confidence_ratio ≤ 0.25` |
|                 | poor   | otherwise                                           |
| `skew_detected` | true   | `max_skew_deg ≥ 2.0°`                               |
| `noise_level`   | low    | `low_confidence_ratio ≤ 0.10`                       |
|                 | medium | `low_confidence_ratio ≤ 0.30`                       |
|                 | high   | otherwise                                           |

**Rationale**:
- Pure rules on measurable inputs — satisfies FR-013 ("not model judgment").
- The populated corpus artifacts classified 20/20 documents as `good` and
  20/20 as `low` noise. The lowest average line confidence was 0.8970
  (`inv_011_hard`), and the highest low-confidence ratio was 0.0737
  (`inv_011_hard`), still below the `good` / `low` boundary. The provisional
  constants therefore did not misfire and were kept unchanged.
- Because no threshold constant changed, `src/dartwing_ocr/preprocessing/version.py`
  `SEMVER` was not bumped.
- All three signals are derivable from what PaddleOCR already returns (line
  confidences + detected rotation/skew). No new dependency.

**Alternatives considered**:
- Blur / contrast metrics on raw images: stronger, but adds OpenCV and adds a
  second coordinate space to reason about. Reserving for a future slice.
- Model-based quality scoring: forbidden by Principle III.

---

## Decision 7 — Partial-failure handling

**Decision**: Per-page try/except boundary. On page-level failure:
- The page entry is still emitted with `blocks = []` and `raw_ocr_lines = []`
  (empty but schema-valid; `width`/`height`/`rotation_detected` carry the
  rasterization values, or 1×1/0 fallbacks if rasterization itself failed).
- A warning string `"page {N}: {stage} failed: {short_reason}"` is appended to
  `warnings[]`.
- `ingestion_sources.paddleocr_vl.status = "failure"` only if *all* pages
  failed layout/OCR; otherwise it stays `"success"`, with per-page failures
  surfaced via `warnings`.

Document-level failure (cannot open the PDF at all, or PDF is encrypted, or
`page_count == 0`) is non-recoverable: raise, exit non-zero, do not write any
artifact (User Story 3 AC #3).

**Rationale**:
- Maps directly onto the acceptance scenarios for User Story 3.
- Keeps the schema-valid invariant (FR-019 / SC-001): every persisted artifact
  validates; malformed inputs never produce partial artifacts.

---

## Decision 8 — Pipeline version string

**Decision**: `pipeline_version` is a **structured, determinism-encoding
string**, not a single literal. The format is:

```
stage1-preprocess-{semver}+paddleocr{pkg_ver}.{weights_hash7}.dpi{dpi}
```

- `{semver}` — semantic version of this slice's code (e.g. `v0.1.0`); bumped
  on any commit that changes preprocessing behavior. Implementations MAY also
  append the short commit SHA (`+sha.abc1234`) when running from a dirty or
  non-tagged tree.
- `{pkg_ver}` — installed PaddleOCR-VL package version reported by
  `importlib.metadata.version("paddleocr")` at runtime.
- `{weights_hash7}` — first 7 hex chars of a stable hash over the PaddleOCR-VL
  model-weights blobs actually loaded at runtime. Computed once at process
  startup from the weight files PaddleOCR resolves (detection model +
  recognition model + layout model + angle classifier).
- `{dpi}` — rasterization DPI constant (`300` today; bumping it changes this
  token, which is the FR-004 version-bump signal).

**Example** (ship default):
`stage1-preprocess-v0.1.0+paddleocr2.8.1.9f3c4a7.dpi300`

**Rationale**:
- Satisfies the tightened FR-018: every input whose change could break
  byte-identity (FR-012) is encoded in the version string. Consumers can
  diff `pipeline_version` alone to decide whether two artifacts are
  comparable under the byte-identity guarantee.
- Distinct from `contract_set_version = "1.0.0"`. The contract is frozen; the
  pipeline build that produced the artifact is not.
- Still mirrors the `stage1-edge-v0.1`-style convention from
  `docs/stage1-vendor-identity/schemas.md` in the `stage1-preprocess-`
  prefix, so later slices can use `stage1-extract-`, `stage1-route-`, etc.,
  without coupling.
- Weights-hash inclusion turns "OCR version drift" from a silent byte-identity
  bug into a visible version delta (research.md Decision 9 → spec Assumptions).
- Bumping DPI, changing document-text join strategy, changing ID minting, or
  changing threshold rules all change `{semver}`. Swapping OCR engine build
  within the same minor changes `{pkg_ver}` or `{weights_hash7}`.

**Alternatives considered**:
- Literal static string (`stage1-preprocess-v0.1`): rejected — hides OCR-engine
  drift; two contributors on different PaddleOCR builds would publish
  artifacts carrying the same `pipeline_version` but different bytes,
  violating FR-018's "consumers can use `pipeline_version` alone" promise.
- Full 64-char SHA for weights: rejected — unreadable at a glance in review;
  7 chars is the git-short-SHA convention and is collision-resistant at the
  corpus scale stage 1 operates at.

---

## Decision 9 — CLI invocation surface

**Decision**: `python -m dartwing_ocr.preprocessing --document-folder tests/stage1_vendor_identity/inv_001_easy`.

Flags:
- `--document-folder PATH` (required): the per-document folder containing
  `source.pdf`. `document_id` is derived from the folder basename (FR-002).
- `--source-file NAME` (optional, default `source.pdf`): override the PDF
  filename inside that folder.
- `--write-page-images` (optional, off by default): emit debug `page_{N}.png`
  files alongside the artifact (FR-007).
- `--pipeline-version STRING` (optional, default = Decision 8): override for
  experiments; the default is the ship value.

Exit codes:
- `0` on success (artifact written and validated).
- `2` on malformed input (encrypted PDF, zero pages, non-PDF file, unreadable
  bytes). No artifact written.
- `3` on internal/unexpected errors (validator rejected an assembled artifact —
  should never happen if contracts and code agree).

**Rationale**:
- Matches the one-document CLI contract already assumed in the spec
  (Assumption: "stage 1 one-document CLI contract already established").
- `--document-folder` instead of `--input` aligns with the per-document folder
  layout from `docs/stage1-vendor-identity/dataset-layout.md` — input,
  expected, and all generated artifacts live in the same folder.

---

## Summary of resolved unknowns

| Unknown (from Technical Context) | Resolved by          |
|----------------------------------|----------------------|
| PDF raster library choice        | Decision 1           |
| OCR + layout engine choice       | Decision 2 (superseded by Decision 10) |
| DPI pinned value                 | Decision 3 (confirms clarification) |
| `document_text` join rule        | Decision 4           |
| Identifier minting scheme        | Decision 5           |
| Quality threshold specification  | Decision 6           |
| Partial-failure boundary         | Decision 7           |
| Pipeline version string          | Decision 8           |
| CLI shape                        | Decision 9           |
| OCR + layout engine migration    | Decision 10          |

No NEEDS CLARIFICATION markers remain in the plan after this research pass.

---

## Decision 10 — Engine migration: PaddleOCR 2.10 → 3.5 (2026-04)

**Decision**: Supersede Decision 2's `paddleocr>=2.8,<3` + `PP-StructureV2` pin with `paddleocr>=3.5,<4` + `PPStructureV3` + `paddlex[ocr]>=3.5,<4`. `paddlepaddle>=3.0,<4` is retained.

**Rationale**:
- Decision 2's PP-StructureV2 (PubLayNet-trained `picodet_lcnet_x1_0_fgd_layout_infer`) returns zero regions on invoice-style documents because PubLayNet's five academic-paper classes don't match invoice layouts. Running against `tests/stage1_vendor_identity/inv_001_easy/source.pdf` silently produced an empty `blocks` array and an empty `document_text` — breaking every downstream stage. See `docs/stage1-vendor-identity/prd-ppstructurev3-migration.md` for the root-cause analysis.
- `PPStructureV3` with PP-DocBlockLayout + PP-DocLayout_plus-L detects invoice regions correctly and produces populated blocks on the same corpus.
- `PP-OCRv5`, which runs as V3's built-in OCR pass, replaces the standalone PP-OCRv4 call — retiring the separate `run_ocr_lines` code path (FR-007).
- `enable_mkldnn=False` is required on V3 construction both as a workaround for the paddle 3.3.1 PIR/oneDNN `ConvertPirAttribute2RuntimeAttribute` bug on `PP-DocBlockLayout` AND as a determinism axis.

**Details + fallback pivot cost**: see `specs/010-pp-structurev3-preprocessing/research.md` — research R-001 through R-010. The PaddleOCR 2.10 + CDLA layout fallback remains a documented contingency only (FR-017); no 2.10 code path ships under 010.

**Alternatives considered**:
- Stay on Decision 2 and accept the silent-empty output — rejected; violates the constitution's evidence-first rule.
- Switch V2 to the CDLA detector (`picodet_lcnet_x1_0_fgd_layout_cdla_infer`) via `layout_model_dir` + `layout_dict_path` — works, but bundles a Chinese OCR model. Kept as the documented fallback only.
