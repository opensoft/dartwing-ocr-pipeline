# Feature Specification: PDF Preprocessing (Stage 1)

**Feature Branch**: `003-pdf-preprocessing`
**Created**: 2026-04-13
**Status**: Draft
**Input**: User description: "PDF Preprocessing — Create the stage 1 PDF preprocessing slice for the Dartwing OCR pipeline. Accept a single input PDF, rasterize each page into images suitable for OCR, perform deterministic page-level preprocessing and structure capture, and emit a schema-aligned `preprocess_output.json`."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Produce a Schema-Valid Preprocessing Artifact for One PDF (Priority: P1)

A pipeline operator (or downstream extraction workstream) runs the stage 1 pipeline against a single invoice PDF from the test corpus. The preprocessing step transforms that PDF into a deterministic, schema-aligned `preprocess_output.json` that downstream work (evidence-packet assembly, extraction, routing) can consume without further OCR or layout work.

**Why this priority**: Without a schema-valid `preprocess_output.json`, every downstream stage 1 workstream is blocked. This is the MVP slice that unblocks parallel work on extraction, routing, and evaluation. It is also the layer that gives stage 1 its evidence-first, schema-first foundation.

**Independent Test**: Run preprocessing against a single easy-difficulty invoice PDF from `tests/stage1_vendor_identity/inv_XXX_easy/source.pdf`. Verify the command writes `preprocess_output.json` into that document's folder and that the validator (`python -m dartwing_ocr.validator validate artifact preprocess_output`) accepts the artifact. No other stage 1 artifact is required for this test to pass.

**Acceptance Scenarios**:

1. **Given** a readable single-page invoice PDF in a per-document folder, **When** preprocessing runs on that document, **Then** a `preprocess_output.json` file is written next to `source.pdf` that validates against the frozen contract `contracts/stage1_vendor_identity/v1.0.0/preprocess_output.schema.json`, contains `source_type: "pdf"`, matches the `document_id` derived from the folder name per FR-002 (e.g., folder `inv_001_easy/` → `document_id "inv_001"`), and reports `page_count == 1` with one fully populated `pages[0]` entry.
2. **Given** the same readable single-page PDF is preprocessed twice with identical configuration and pipeline version, **When** the two output files are compared, **Then** their contents are byte-identical: ordering of blocks, `raw_ocr_lines`, `reading_order` values, `block_id`s (`p{page}_b{n}`), `line_id`s (`p{page}_l{n}`), bbox values, and `document_text` are all deterministic and stable, including ID numbering remaining page-scoped such that failures on other pages do not renumber this page's blocks or lines.
3. **Given** a PDF whose text is legibly recognized end-to-end, **When** preprocessing completes, **Then** `ingestion_sources.paddleocr_vl.enabled == true` and `.status == "success"`, while `falcon_ocr` and `falcon_perception` both report `enabled == false` and `status == "not_implemented"`.
4. **Given** a PDF with no structural issues, **When** preprocessing completes, **Then** `quality` is fully populated (`scan_quality`, `skew_detected`, `noise_level`) and `warnings` is an empty list.
5. **Given** a preprocessed document, **When** a downstream consumer reads `document_text`, **Then** the string contains page text joined in reading order, consistent with the per-page `blocks` ordering used to build it.

---

### User Story 2 - Handle Multi-Page PDFs Deterministically (Priority: P2)

A pipeline operator processes an invoice PDF that has more than one page (e.g., a remittance cover page followed by the invoice body). Preprocessing must rasterize every page, produce per-page blocks and OCR lines with page-scoped identifiers, and assemble a single multi-page `preprocess_output.json`.

**Why this priority**: Stage 1 scope is PDF-only and real invoices in the corpus include multi-page documents (cover pages, continuation sheets). Downstream extraction must be able to cite evidence across pages using stable identifiers.

**Independent Test**: Run preprocessing against a known multi-page PDF. Verify `page_count` matches the source PDF page count, that `pages` contains exactly that many entries in order, that identifiers are unique and follow the `p{N}_b{n}` / `p{N}_l{n}` convention, and that `document_text` concatenates all pages in document order.

**Acceptance Scenarios**:

1. **Given** an N-page PDF where every page is readable, **When** preprocessing runs, **Then** `page_count == N`, `pages` has N entries ordered by `page_number` ascending starting at 1, and every block and line identifier is unique across the document and carries its page prefix.
2. **Given** an N-page PDF, **When** preprocessing completes, **Then** each page's `reading_order` values are contiguous integers starting at 1 within that page and no two blocks on the same page share a `reading_order`.
3. **Given** pages that differ in dimensions or rotation, **When** preprocessing runs, **Then** each page records its own `width`, `height`, and `rotation_detected` (one of 0/90/180/270) independently; a page's own rasterized image is used for its OCR and layout output.
4. **Given** a multi-page PDF, **When** `document_text` is produced, **Then** it is the concatenation of per-page text in `page_number` order using the deterministic `"\n\n"` page separator pinned in FR-010.

---

### User Story 3 - Degrade Gracefully on Unreadable Pages and Partial Failures (Priority: P2)

A pipeline operator processes an invoice PDF that has a blank page, a badly scanned page, or one page that triggers a rasterization or OCR failure. Preprocessing must not crash the run; it must record the failure as a warning, continue with the remaining pages, and still emit a schema-valid `preprocess_output.json` whenever at least one page was processed successfully.

**Why this priority**: Real corpora include poor scans, blank pages, and occasional rasterization failures. A partial result is more valuable to downstream extraction than a failed run, provided the failure is visible in the artifact rather than hidden.

**Independent Test**: Run preprocessing against a PDF deliberately seeded with one unreadable page (e.g., corrupted image stream or blank). Verify the run exits successfully, `preprocess_output.json` is written, the failing page is represented with an empty `blocks`/`raw_ocr_lines` list (or equivalent minimal record), and `warnings` contains a human-readable description citing the affected `page_number`.

**Acceptance Scenarios**:

1. **Given** a PDF with one unreadable page among otherwise readable pages, **When** preprocessing runs, **Then** the run completes without raising to the caller, the output artifact validates against the schema, the unreadable page appears in `pages` with empty `blocks` and empty `raw_ocr_lines` and the page record still contains `width`, `height`, and `rotation_detected` populated per FR-005a, and `warnings` includes an entry naming the page and cause.
2. **Given** a blank page (a page whose PaddleOCR-VL run succeeds but produces zero blocks and zero OCR lines), **When** preprocessing runs, **Then** the blank page is represented with empty `blocks` and `raw_ocr_lines`, `scan_quality` and other document-level quality signals are not downgraded to `poor` purely because of blankness, and **no warning is emitted**. Blankness itself is not treated as an anomaly; warnings are emitted only when a page actually failed at rasterization, OCR, or layout (see AC#1 and AC#4), never when a page succeeded with zero content. Determining "expected" content is therefore not required — an empty successful run is always the silent path.
3. **Given** a malformed PDF that cannot be opened at all, **When** preprocessing runs, **Then** the pipeline surfaces a clear error (non-zero exit, explicit error message) without writing an invalid `preprocess_output.json`; no partial artifact that would fail schema validation is persisted.
4. **Given** preprocessing failed on a page at a single step (layout extraction OR OCR) while the other step succeeded, **When** the artifact is produced, **Then** the successful step's output is retained (e.g., `raw_ocr_lines` populated when layout failed, OR `blocks` populated when OCR failed with the block `text` field set to empty strings per FR-020), the failed step's output is an empty array, and `warnings` records which step failed and on which page. Rasterization failure is covered separately by AC#1 and FR-005a.
5. **Given** the PaddleOCR-VL source fails entirely, **When** preprocessing runs, **Then** `ingestion_sources.paddleocr_vl.status == "failure"`, `enabled` reflects whether it was supposed to run, the artifact still validates, and `warnings` includes the failure.

---

### User Story 4 - Capture Tables and Layout Structure When Available (Priority: P3)

When a page contains tabular structure (e.g., a line-item grid on an invoice), preprocessing should capture it structurally in the `tables` array and as table-typed blocks, so that later workstreams can reference the structure without re-running layout analysis. This is structural capture only — no line-item field extraction.

**Why this priority**: Tables appear on most invoices and are needed by later workstreams, but vendor-identity extraction (the stage 1 focus) does not strictly require table contents. Including structural capture now avoids re-running layout later while staying inside schema scope.

**Independent Test**: Run preprocessing against a PDF containing a recognizable table. Verify `tables` is non-empty, that at least one block has `block_type == "table"` with a bbox that reasonably aligns with the table, and that no business-level line-item fields (descriptions, quantities, prices) are interpreted or added to any other artifact.

**Acceptance Scenarios**:

1. **Given** a PDF page containing a table, **When** preprocessing runs, **Then** the corresponding page has at least one block of `block_type == "table"` covering the table region, and `tables` contains a structural record for that table.
2. **Given** a PDF with no tabular structure, **When** preprocessing runs, **Then** `tables` is an empty array and no block is forced to `block_type == "table"`.
3. **Given** a captured table, **When** downstream code inspects the artifact, **Then** the table record contains only structural information (page reference, bbox, and optionally a deterministic grid representation) and does not contain business-field interpretation such as "line_item_description" or "unit_price".

---

### Edge Cases

- A PDF file with zero pages (or whose page count cannot be determined) is treated as malformed per User Story 3, AC #3.
- A page whose detected rotation is not one of `{0, 90, 180, 270}` is snapped to the nearest allowed value and a warning is recorded; the schema does not admit arbitrary rotations.
- A PDF that is actually an image wrapper (single raster page) is still accepted as PDF input and rasterized normally.
- A PDF embedding a searchable text layer is still rasterized; text is obtained from OCR over the rasterized image so that `confidence` values and bbox coordinates are comparable across the corpus. The embedded text layer is not used as a shortcut.
- A document larger than typical invoice size (many pages, very large dimensions) still produces a single `preprocess_output.json`; page images are kept next to the artifact only if the implementation chooses to persist them (see Assumptions).
- An encrypted or password-protected PDF is treated as malformed per User Story 3, AC #3: the pipeline surfaces a clear error (non-zero exit, explicit error message citing encryption) without writing an artifact. Decryption is out of scope.
- A PDF whose `source.pdf` filename differs from expectation still works; `source_file` records what was actually read and `document_id` derives from the folder name, not the filename.
- Re-running preprocessing on a folder that already contains `preprocess_output.json` overwrites the prior artifact atomically (temp-file + rename per FR-019); no merging of prior state occurs.

## Clarifications

### Session 2026-04-20

- Q: What fixed DPI should be used for PDF rasterization? → A: 300 DPI (standard OCR resolution)
- Q: How should encrypted/password-protected PDFs be handled? → A: Treat as malformed — reject with clear error, no artifact written
- Q: How should quality signal thresholds (FR-013) be specified? → A: Pin the input metrics now (avg OCR line confidence, low-confidence line percentage, skew angle estimate); defer exact threshold values to planning for corpus calibration

## Requirements *(mandatory)*

### Functional Requirements

#### Input and invocation

- **FR-001**: The system MUST accept exactly one PDF document per invocation, addressed via the stage 1 CLI contract already established for one-document processing. Input that is not a PDF MUST be rejected with a clear error before any rasterization is attempted. Batch invocation (multiple documents per call, corpus-wide sweeps, or directory-walking behavior) is out of scope for this slice; multi-document runs are the responsibility of the test harness layer calling this CLI once per document.
- **FR-002**: The system MUST derive `document_id` from the per-document folder basename by extracting the leading `inv_XXX` slice (three decimal digits) and discarding any `_<difficulty>` suffix. For example, a folder named `inv_001_easy/` yields `document_id = "inv_001"`. The derived value MUST match the frozen contract pattern `^inv_\d{3}$` defined in `contracts/stage1_vendor_identity/v1.0.0/folder.schema.json`. The `<difficulty>` suffix is corpus-layout metadata consumed by the test harness and MUST NOT appear in `document_id`. Deriving from the folder name (not the source filename) keeps the artifact self-consistent when the corpus is moved or renamed at the filename level.
- **FR-003**: The system MUST record the relative source filename in `source_file` and MUST set `source_type` to the literal value `"pdf"`.

#### Rasterization and page metadata

- **FR-004**: The system MUST rasterize every page of the input PDF into an image representation suitable for OCR and layout analysis at a fixed resolution of 300 DPI. This resolution is a project-wide constant (not a per-invocation flag) chosen for standard OCR quality and PaddleOCR compatibility; changing it constitutes a pipeline-version bump.
- **FR-005**: The system MUST record per-page `width` and `height` in pixels of the rasterized image after any rotation normalization has been applied (FR-006), not PDF point dimensions and not the pre-rotation raster dimensions. When a page is snapped from 90° or 270° rotation to 0°, the recorded `width` and `height` are the dimensions of the upright post-rotation image. All bboxes on that page MUST be expressed in this same post-rotation coordinate space, so `bbox[0] + bbox[2]` never exceeds `width` and `bbox[1] + bbox[3]` never exceeds `height`.
- **FR-005a**: If rasterization itself fails for a page (the image cannot be produced), that page's `width`, `height`, and `rotation_detected` MUST still be populated as best-effort fallbacks derived from the PDF's declared page metadata: `width` and `height` computed from the PDF point dimensions scaled to 300 DPI (i.e. `round(point_dim × 300 / 72)`), and `rotation_detected` set to `0`. When even the PDF metadata is unreadable for that page, `width` and `height` MUST be `0` and `rotation_detected` MUST be `0`. `blocks` and `raw_ocr_lines` MUST be empty arrays. The page record MUST remain schema-valid so the document-level artifact still validates.
- **FR-006**: The system MUST record per-page `rotation_detected` as one of `{0, 90, 180, 270}`. If the OCR/layout stack detects a different rotation, preprocessing MUST normalize to the nearest allowed value and MUST emit a warning when such normalization occurs. The warning string MUST be formatted as `"page {page_number}: rotation {original_angle}° normalized to {snapped_angle}°"`, where `{original_angle}` is the raw detected value (integer or one decimal) and `{snapped_angle}` is the chosen value from `{0, 90, 180, 270}`. The exact format is part of the determinism contract and is covered by FR-012.
- **FR-007**: The system MAY persist per-page image files alongside `preprocess_output.json` for debugging. Downstream correctness MUST NOT depend on those image files being present; the JSON artifact is the contract.

#### Deterministic layout and OCR output

- **FR-008**: For each page, the system MUST emit `blocks` with `block_id` matching `^p\d+_b\d+$`, `block_type` from the closed vocabulary `{text, title, table, figure, header, footer}`, an integer `bbox` of exactly four non-negative integers in the page's coordinate space, a `reading_order` integer unique and contiguous starting from 1 within each page, a `text` string (may be empty), and a `confidence` in [0.0, 1.0]. The `reading_order` sequence MUST include every block on the page regardless of `block_type` — `figure`, `table`, `header`, and `footer` blocks participate in the same single sequence as `text` and `title` blocks. Non-text blocks (`figure`, `table`) are assigned a `reading_order` position based on their bbox top-y (then left-x, then the layout-engine detection index — the zero-based order in which the engine produced each block — as final tiebreak), matching the rule used for `raw_ocr_lines` sorting (FR-009). `block_id` numeric suffixes are assigned after this sort (i.e. `p{page}_b{n}` = the n-th block in that sort order, starting at 1), so `block_id` itself cannot be used as the tie-break. Non-text blocks MAY have an empty `text` string but MUST still occupy a unique `reading_order` slot so downstream consumers can cite spatial evidence deterministically.
- **FR-009**: For each page, the system MUST emit `raw_ocr_lines` with `line_id` matching `^p\d+_l\d+$`, an integer `bbox` of exactly four non-negative integers in the page's post-rotation coordinate space (same frame as block bboxes per FR-005), a `text` string (may be empty), and a `confidence` in `[0.0, 1.0]` matching the range used for blocks. Within each page, `raw_ocr_lines` MUST be sorted by `bbox[1]` (top-y) ascending, then `bbox[0]` (left-x) ascending, with the OCR detection index (the zero-based order in which the OCR engine produced each line) as the final tie-break. Detection index is stable across reruns for the same input bytes and is known before `line_id` is minted, avoiding any circular self-reference. Line identifiers MUST be unique within a page and stable across reruns of the same input; `line_id` numeric suffixes are assigned after this sort (i.e. `p{page}_l{n}` = the n-th line in that sort order, starting at 1), so `line_id` itself cannot be used as the tie-break.
- **FR-009a**: `block_id` and `line_id` numeric suffixes are page-scoped in the strict sense: the suffix sequence on page X depends only on the successful processing of page X itself. A partial or total failure on any other page MUST NOT shift, skip, or renumber IDs on page X. Concretely: if pages 1 and 3 succeed and page 2 fails with empty `blocks`/`raw_ocr_lines`, then page 3's `block_id`s still begin at `p3_b1` and its `line_id`s at `p3_l1` — the page-2 failure does not alter page-3 numbering. This is part of the determinism contract (FR-012).
- **FR-010**: The system MUST emit `document_text` as a single string built deterministically as follows: (1) per-page text is the concatenation of each page's `blocks[].text` in `reading_order` ascending, joined by the intra-page separator `"\n"`; (2) `document_text` is the concatenation of per-page text in `page_number` ascending, joined by the inter-page separator `"\n\n"`. Both separators are string constants defined in code; changing either MUST be treated as a pipeline-version bump per FR-004.
- **FR-011**: The system MUST emit `tables` as an array of structural table records when tables are detected. Each record MUST contain only structural information (page reference, bbox, optionally a grid) and MUST NOT contain business-field interpretation. When no tables are detected, `tables` MUST be `[]`.
- **FR-011a**: Each entry in `tables[]` MUST be a JSON object with exactly these keys: `page_number` (1-based integer matching a `pages[].page_number`), `block_id` (string matching `^p\d+_b\d+$`, referencing a `blocks[]` entry on that page with `block_type == "table"`), `bbox` (four non-negative integers mirroring the referenced block's bbox), `rows` (non-negative integer; `0` if unknown), `columns` (non-negative integer; `0` if unknown), and optionally `cells` (array of `{row, column, bbox, text}` objects; omitted entirely if the table recognizer produced no grid). No other keys are permitted; in particular, no business-field keys (FR-024). This convention is part of the deterministic pipeline version — changing the `tables[*]` object shape is a `pipeline_version` bump per FR-018.
- **FR-012**: The system MUST produce deterministic, repeatable output for identical inputs and identical configuration: given the same PDF bytes, same pipeline version, and same ingestion-source configuration, two preprocessing runs MUST produce byte-identical `preprocess_output.json` contents.

#### Quality signals and warnings

- **FR-013**: The system MUST emit `quality` with `scan_quality` in `{good, fair, poor}`, `skew_detected` as a boolean, and `noise_level` in `{low, medium, high}`. These signals MUST be derived from deterministic rules (thresholds on measurable page-level metrics), not from model judgment. The required input metrics are: (1) average OCR line confidence across all pages, (2) percentage of OCR lines below a low-confidence cutoff, and (3) estimated skew angle. Exact threshold values for each quality tier will be calibrated against the stage 1 corpus during planning/implementation.
- **FR-014**: The system MUST emit `warnings` as an array of human-readable strings describing any recoverable anomaly encountered during preprocessing (rotation normalization, unreadable page, layout-extraction failure, ingestion-source failure, etc.). The array MUST be empty when no anomalies occurred.

#### Ingestion sources and Trijunction readiness

- **FR-015**: The system MUST emit `ingestion_sources` with exactly three keys — `paddleocr_vl`, `falcon_ocr`, `falcon_perception` — each containing `enabled` and `status`, where `status` is one of `{success, failure, not_implemented}`. For stage 1, `paddleocr_vl` is the only source expected to run; the other two MUST report `enabled: false` and `status: "not_implemented"` unless the slice explicitly wires them up.
- **FR-015a**: For stage 1, `ingestion_sources.paddleocr_vl.status` is derived deterministically from per-page outcomes: `"success"` if at least one page produced a non-empty `blocks` or `raw_ocr_lines` array via PaddleOCR-VL; `"failure"` if every page failed at the PaddleOCR-VL step; otherwise `"success"` with per-page anomalies recorded only in `warnings`. Individual per-page failures MUST NOT downgrade `paddleocr_vl.status` to `"failure"` unless all pages failed. The same rule applies to any later-wired ingestion source (`falcon_ocr`, `falcon_perception`).
- **FR-016**: The system MUST be structured so that `falcon_ocr` and `falcon_perception` can be added later by populating their ingestion-source status and contributing blocks/lines into the existing per-page arrays, without changing the `preprocess_output` contract.

#### Artifact placement and contract compliance

- **FR-017**: The system MUST write `preprocess_output.json` into the same per-document folder as `source.pdf` (i.e., `tests/stage1_vendor_identity/inv_XXX_<difficulty>/preprocess_output.json`). No other artifact is written by this slice. This explicitly includes, but is not limited to, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`, `evaluation_document.json`, `evaluation_run_summary.json`, and any per-voter artifacts under a `votes/` subfolder. Evaluation artifacts belong to the test harness (a separate concern per `docs/stage1-vendor-identity/prd-test-harness.md`) and are produced by the harness running against `preprocess_output.json`, never by the preprocessing slice itself.
- **FR-018**: The system MUST set `contract_set_version` to the currently frozen contract-set version (`1.0.0`) and `pipeline_version` to a value identifying the stage 1 pipeline build that produced the artifact. The `pipeline_version` string MUST encode every input whose change could break byte-identity under FR-012, including at minimum: the preprocessing code commit SHA (or semantic version), the PaddleOCR-VL package version, the PaddleOCR-VL model weights identifier/hash, and the raster resolution constant (300 DPI). Changing any of these MUST produce a different `pipeline_version` value. Consumers can therefore use `pipeline_version` alone to decide whether two `preprocess_output.json` files are comparable under the byte-identity guarantee.
- **FR-019**: Every emitted `preprocess_output.json` MUST validate against `contracts/stage1_vendor_identity/v1.0.0/preprocess_output.schema.json` using the repository's validator. An invocation that cannot produce a schema-valid artifact MUST fail loudly and MUST NOT persist a partial artifact. Writing `preprocess_output.json` MUST be atomic: the system MUST write to a sibling temp file in the same per-document folder (e.g. `preprocess_output.json.tmp-{pid}`) and then rename that file to `preprocess_output.json`. On crash or interruption, the folder MUST contain either the previous artifact or the new artifact — never a partially-written `preprocess_output.json`. Lingering `*.tmp-*` files from a crashed run MAY exist and are not part of the contract; implementations MAY clean them up opportunistically.
- **FR-020**: The system MUST use `null` only in places where the schema permits it. Missing OCR text MUST be represented as an empty string (per the block/line schema), not as `null`. No schema-prohibited keys (e.g., business vendor fields) may appear anywhere in the artifact.

#### Scope boundaries (explicit exclusions)

- **FR-021**: The system MUST NOT perform any business-field extraction. The following is the explicit, non-exhaustive exclusion set for this slice: vendor-identity fields (`company_name`, `address`, `tax_ids`, `website`, `phone`, `email`), invoice-header fields (`invoice_number`, `invoice_date`, `total_amount`), and any line-item fields. The provenance markers used by later slices (`present`, `inferred`, `manual_review_required`) are likewise out of scope here — preprocessing emits raw evidence (blocks, lines, tables, quality, warnings) and never emits field-level provenance. All of the above concerns belong to later slices.
- **FR-022**: The system MUST NOT invoke any model for voting, consensus, routing, or final payload assembly, and MUST NOT produce `edge_extraction_output.json`, `routing_decision.json`, or `final_structured_payload.json`.
- **FR-023**: The system MUST NOT call any cloud service during preprocessing, and MUST NOT call the host Ollama inference service (`OLLAMA_BASE_URL`, the native-Linux ROCm Ollama, or any container-local Ollama). All OCR/layout work for stage 1 runs locally in-process via the PaddleOCR-VL source and, when wired, the Falcon sources — none of which are Ollama-served models. Ollama is reserved for the later extraction/voting slices (Model A/B/C); preprocessing is the lower, model-free layer of the pipeline. See `docs/stage1-vendor-identity/ollama-runtime.md` for the distinction between preprocessing (no Ollama) and later slices (Ollama-dependent), and note that the "edge path only" assumption applies to model calls in later slices — preprocessing does not involve any model path at all.
- **FR-024**: The system MUST NOT interpret tabular content beyond structural capture (bboxes, grid cells). Line-item parsing (descriptions, quantities, unit prices, line totals) is out of scope.
- **FR-025**: The CLI surface for this slice MUST NOT introduce invocation-time flags that toggle ingestion sources on or off (e.g., no `--no-paddleocr`, `--enable-falcon-ocr`, or equivalent). For stage 1, ingestion-source enablement is fixed: `paddleocr_vl.enabled = true`, `falcon_ocr.enabled = false`, `falcon_perception.enabled = false`. These values are emitted into `ingestion_sources` per FR-015 and are part of the deterministic pipeline version, not a user-controlled parameter. Wiring a new ingestion source on is a code change plus a pipeline-version bump, not a CLI flag.

### Key Entities

- **Preprocessing Invocation**: A single run that reads one PDF and produces one `preprocess_output.json`. Attributes: source PDF path, resolved per-document folder, pipeline version, contract-set version, chosen ingestion-source configuration.
- **Page Record**: One entry in `pages`. Attributes: `page_number` (1-based), rasterized `width` and `height`, `rotation_detected`, ordered `blocks`, ordered `raw_ocr_lines`. Serves as the coordinate frame for all bboxes on that page.
- **Block**: A layout-level region on one page. Attributes: `block_id` (page-scoped), `block_type` (closed vocabulary), `bbox`, `reading_order` (page-scoped integer), `text`, `confidence`. Referenced by downstream extraction via `block_id`.
- **OCR Line**: A low-level OCR text line on one page. Attributes: `line_id` (page-scoped), `bbox`, `text`, `confidence`. Serves as fine-grained evidence for later voters.
- **Table Record**: A structural description of a detected table at the document level. Attributes: page reference, bbox, optional grid structure. Contains no business-field interpretation.
- **Quality Signals**: Deterministic, rule-derived descriptors of the document as a whole: `scan_quality`, `skew_detected`, `noise_level`.
- **Ingestion Source Status**: A fixed three-element record (`paddleocr_vl`, `falcon_ocr`, `falcon_perception`) declaring which sources were configured and whether each one succeeded, failed, or is not implemented for this run.
- **Warning Entry**: A human-readable string describing a recoverable anomaly (rotation normalization, unreadable page, layout failure, ingestion-source failure).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every invoice in the 20-document stage 1 corpus, a single preprocessing invocation produces a `preprocess_output.json` that validates against the frozen contract on the first run, with 0 schema validation errors across the corpus.
- **SC-002**: Rerunning preprocessing against the same PDF produces byte-identical `preprocess_output.json` output in 100% of cases across the corpus, confirming determinism.
- **SC-003**: For the 5 "easy" corpus documents, every detected OCR line on the page containing the vendor name is addressable by a stable `line_id` (reruns return the same identifier for the same detection), enabling downstream extraction to cite evidence reliably.
- **SC-004**: Preprocessing completes successfully (exit code 0, valid artifact written) for at least 90% of the stage 1 corpus, including the 5 "hard" and 5 "missing_name" documents, without any manual intervention.
- **SC-005**: When a page is deliberately corrupted, the run still exits successfully, the artifact still validates, and `warnings` contains at least one entry naming the affected `page_number` in 100% of seeded-failure cases.
- **SC-006**: When the input is a malformed PDF that cannot be opened, the run exits non-zero with an explicit error and does not persist any `preprocess_output.json`, in 100% of seeded-failure cases.
- **SC-007**: Downstream extraction work (next slice) can begin consuming `preprocess_output.json` without requesting any change to the `preprocess_output` contract, confirming compatibility with both current routing and future Trijunction evidence assembly.
- **SC-008**: A documented one-command invocation processes one PDF end-to-end through preprocessing in a developer's devcontainer without requiring cloud access or GPU acceleration.

## Assumptions

- The stage 1 one-document CLI contract already established in the pipeline (i.e., an entry point that accepts a single document and writes artifacts next to the source PDF) is the surface through which this slice is invoked. The CLI's exact flag names are not redefined here; they are inherited.
- The per-document folder layout documented in `docs/stage1-vendor-identity/dataset-layout.md` (each document lives in its own `inv_XXX_<difficulty>/` folder with `source.pdf` at the top) is the canonical input/output location.
- `contract_set_version` is `1.0.0` and frozen; this slice is a consumer of the frozen contract, not an amender of it. Any needed contract change would follow `contracts/stage1_vendor_identity/AMENDMENTS.md` and is out of scope.
- PaddleOCR-VL (or an equivalent deterministic OCR+layout source) is the single active ingestion source for stage 1. Falcon OCR and Falcon Perception are declared in `ingestion_sources` for Trijunction readiness but are `not_implemented` here.
- Rasterization resolution is fixed at 300 DPI, chosen for standard OCR quality and PaddleOCR compatibility. Changing it is a pipeline-version bump, not a runtime toggle.
- OCR-engine version drift across developer machines is mitigated by `pipeline_version` encoding the PaddleOCR-VL package and model-weights identifier. Two runs that produce different `pipeline_version` values are not required to be byte-identical — they are different pipelines. The devcontainer pins the PaddleOCR-VL version so that routine contributor setups converge on the same `pipeline_version`; a contributor on a mismatched environment will see a different `pipeline_version` rather than silently drifted output.
- All preprocessing work runs locally in the lightweight devcontainer (no cloud, no managed GPU requirement, no Ollama). Host Ollama is a later-slice dependency only — see FR-023 and `docs/stage1-vendor-identity/ollama-runtime.md`.
- Per-page image files, if written at all, are treated as debug outputs and are not part of the contract; their presence or absence does not affect downstream correctness.
- The evaluation harness, routing logic, extraction, and final payload assembly are owned by other slices and are not produced or modified by this work.
- The repository's validator (`src/dartwing_ocr/validator/`) is consumed by this slice but not modified. Any validator change (new checks, bug fixes, CLI additions) is a separate concern tracked under its own slice; this work may depend on the validator behaving per its current module-API contract but MUST NOT edit its code.
- The JSON examples shown in `docs/stage1-vendor-identity/schemas.md` are illustrative, not normative. When an example in `schemas.md` appears to conflict with the JSON Schema file at `contracts/stage1_vendor_identity/v1.0.0/preprocess_output.schema.json`, the JSON Schema file wins. Only fields marked required in the schema are required in the artifact; fields that appear only in an example (e.g., illustrative extra keys) do not imply a requirement on this slice.
