# Research: PPStructureV3 Preprocessing Migration

**Feature**: 010-pp-structurev3-preprocessing
**Phase**: 0 (research — resolves all NEEDS CLARIFICATION from the plan before Phase 1 design)
**Primary source**: `docs/stage1-vendor-identity/prd-ppstructurev3-migration.md` (authoritative)
**Cross-references**: `specs/010-pp-structurev3-preprocessing/spec.md`, `specs/003-pdf-preprocessing/research.md`

## Table of contents

- [R-001: PPStructureV3 construction + oneDNN workaround](#r-001-ppstructurev3-construction--onednn-workaround)
- [R-002: V3 output shape + line extraction](#r-002-v3-output-shape--line-extraction)
- [R-003: V3 label vocabulary + block_type mapping](#r-003-v3-label-vocabulary--block_type-mapping)
- [R-004: Retiring `run_ocr_lines()`](#r-004-retiring-run_ocr_lines)
- [R-005: Determinism audit on V3](#r-005-determinism-audit-on-v3)
- [R-006: Corpus regeneration sweep — halt-on-fail](#r-006-corpus-regeneration-sweep--halt-on-fail)
- [R-007: `pipeline_version` format and engine SHA](#r-007-pipeline_version-format-and-engine-sha)
- [R-008: FR-016 hard-fail error format](#r-008-fr-016-hard-fail-error-format)
- [R-009: Warning category vocabulary + ordering](#r-009-warning-category-vocabulary--ordering)
- [R-010: FR-017 fallback — PaddleOCR 2.10 + CDLA (doc-only)](#r-010-fr-017-fallback--paddleocr-210--cdla-doc-only)
- [R-011: Page-at-a-time raster streaming](#r-011-page-at-a-time-raster-streaming)
- [R-012: PP-OCRv5 default recognition threshold](#r-012-pp-ocrv5-default-recognition-threshold)
- [R-013: Confidence value semantics under V3](#r-013-confidence-value-semantics-under-v3)
- [R-014: `tables[]` projection boundary under V3](#r-014-tables-projection-boundary-under-v3)
- [R-015: Debug PNG emission policy](#r-015-debug-png-emission-policy)
- [Baseline timings](#baseline-timings)

---

## R-001: PPStructureV3 construction + oneDNN workaround

**Decision**: Construct the engine once per process with:

```python
from paddleocr import PPStructureV3

_ENGINE = PPStructureV3(
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    use_formula_recognition=False,
    use_seal_recognition=False,
    use_chart_recognition=False,
    cpu_threads=1,
    enable_mkldnn=False,
    device="cpu",
    lang="en",
)
```

**Rationale**:
- All preview / auxiliary modules (orientation, dewarping, formula, seal, chart) stay off per FR-005 and the PRD scope line. Turning any of them on would drag in additional weights and non-deterministic behavior we don't need for vendor identity.
- `enable_mkldnn=False` is the PRD-documented workaround for the paddle 3.3.1 PIR/oneDNN `ConvertPirAttribute2RuntimeAttribute` bug on `PP-DocBlockLayout`. Without it, layout inference crashes or silently miscomputes attention shapes on some invoices. Trade: slower inference on x86; acceptable at stage 1 CPU-only corpus-size workloads (SC-005 records the cost, does not gate on it).
- `cpu_threads=1`, `device="cpu"` — matches 003's determinism discipline. Multi-threaded CPU kernels have produced non-byte-identical floats on reruns in the past.
- Module-level `_ENGINE` caching mirrors current V2 `_OCR_ENGINE` / `_STRUCTURE_ENGINE` caching. One construction per process, not per call. The engine stays resident while pages stream through it one by one.

**Alternatives considered**:
- GPU path via `device="gpu"` — out of scope (FR-005). WSL Docker Desktop can't see the AMD GPU; production-Linux ROCm is a future story.
- Leaving `enable_mkldnn=True` and hoping the bug doesn't fire — rejected; the probe on `inv_001_easy` reproduced the crash deterministically on paddle 3.3.1.
- Pinning paddle < 3.3.1 to avoid the bug entirely — rejected; older paddle drops V3 features the probe validated.

**Upstream tracking**: PaddlePaddle issue describing the `ConvertPirAttribute2RuntimeAttribute` crash on `PP-DocBlockLayout`. Workaround removal is gated on an upstream fix; `enable_mkldnn=True` will be restored once the fix is released and we bump the paddle lockfile pin. Captured here for SC-007.

## R-002: V3 output shape + line extraction

**Decision**: `PPStructureV3()(image_array)` returns a `StructureChatOCRPipelineResult`-style object per page (or a list of such for multi-image input). Two fields matter for us:

- `layout_det_res.boxes` — list of layout regions. Each region has `label` (string), `coordinate` (4-point or 4-tuple bbox), and `score`. This is the source of `pages[*].blocks`.
- `overall_ocr_res.rec_texts` + `overall_ocr_res.rec_boxes` + `overall_ocr_res.rec_scores` (and the parallel `text_det_res.polys` if needed for bbox shape) — line-level OCR output. This is the source of `pages[*].raw_ocr_lines`.

For the table branch, V3 exposes `table_res_list` with an HTML fragment per detected table; the existing `_parse_table_dims()` regex logic in `src/ledgerlinc_ocr/preprocessing/ocr.py:109-132` is reused unchanged.

The richer `parsing_res_list` (which holds Markdown-style block content V3 generates) is **discarded** at the persistence boundary — capturing it would require an AMENDMENTS entry to widen the `preprocess_output` contract, which is explicitly out of scope (see spec assumption §"Frozen contract" and FR-001).

**Rationale**:
- Single engine call produces both layout and OCR — retiring `run_ocr_lines()` removes a redundant PP-OCRv4 pass against the same image.
- Using V3's built-in OCR (PP-OCRv5) keeps `blocks[*].text` and `raw_ocr_lines[*].text` consistent with each other — they came from the same recognizer on the same image. Today's V2 path uses PP-OCRv4 for lines and PP-OCRv3 (via PPStructure internals) for block text, producing two text streams to reconcile.

**Alternatives considered**:
- Continue calling `PaddleOCR` separately for lines and `PPStructureV3` for layout — rejected; wastes inference budget, breaks text consistency.
- Emit V3's `parsing_res_list` into `preprocess_output.json` somewhere — rejected; no schema slot, and the extractor doesn't need it yet.

## R-003: V3 label vocabulary + block_type mapping

**Decision**: Extend `PPSTRUCTURE_LABEL_TO_BLOCK_TYPE` in `src/ledgerlinc_ocr/preprocessing/ocr.py:15-26` with the V3-specific labels observed on `inv_001_easy` and the documented PP-DocLayout_plus-L class set:

```python
PPSTRUCTURE_LABEL_TO_BLOCK_TYPE = {
    # V2 labels (retained for parity)
    "text": "text",
    "title": "title",
    "table": "table",
    "figure": "figure",
    "image": "figure",
    "header": "header",
    "footer": "footer",
    "reference": "text",
    "equation": "text",
    "list": "text",
    # V3 additions
    "paragraph_title": "title",        # PP-DocLayout_plus-L section headings
    "doc_title": "title",              # PP-DocLayout_plus-L document title
    "abstract": "text",
    "content": "text",
    "figure_title": "text",            # caption — downstream treats as text, not figure
    "formula_number": "text",
    "chart_title": "text",
    "table_title": "text",
    "seal": "text",                    # we don't do seal recognition, but V3 may still emit the layout label
}
```

Any label not in this map falls back to `"text"` and emits the FR-006 `[unknown_layout_label]` warning.

**Rationale**:
- The closed enum `{text, title, table, figure, header, footer}` is frozen in the v1.0.0 contract. We cannot add new `block_type` values without an AMENDMENTS entry. Every new V3 label MUST map onto the existing set.
- `paragraph_title` and `doc_title` both collapse to `"title"` — downstream consumers don't distinguish document-level from section-level titles today. If the extractor later needs to, that's a separate slice + AMENDMENTS.
- `figure_title` → `"text"` (not `"figure"`) — it's a caption string, not the figure itself. Matches the 003-era `"reference"` → `"text"` convention.
- `seal` → `"text"` defensively: we don't enable seal recognition (FR-005), but the layout detector may still classify a seal region. Capturing it as `"text"` avoids an `[unknown_layout_label]` warning for something benign.

**Alternatives considered**:
- Skip layout regions with unknown labels — rejected; discarding evidence violates the evidence-first rule. Fallback + warning is the constitution-compliant path.
- Add `"note"` or `"unknown"` to `block_type` — rejected; requires AMENDMENTS, out of scope.

## R-004: Retiring `run_ocr_lines()`

**Decision**: Collapse `ocr.run_ocr_lines()` and `ocr.run_layout()` into a single `ocr.run_page()` that invokes `PPStructureV3` once and returns `(lines, blocks, tables, warnings)`. The new function does the bbox/text/confidence extraction from both `layout_det_res` and `overall_ocr_res` in one pass.

Pseudocode shape:

```python
def run_page(image, page_number, width, height):
    engine = _get_engine()  # cached
    try:
        result = engine.predict(np_img)  # or engine(np_img); exact method resolved at impl time
    except Exception as exc:
        return [], [], [], [build_warning(page_number, "layout_extraction_failed", f"{type(exc).__name__}: {exc}")]
    lines = _extract_lines(result.overall_ocr_res, page_number, width, height)
    blocks, tables, label_warnings = _extract_blocks(result.layout_det_res, result.table_res_list, page_number, width, height)
    return lines, blocks, tables, label_warnings
```

`pipeline.py` then has a single call site per page and applies FR-003 / FR-018 / FR-019 checks based on `len(lines)` + `len(blocks)` + the block-type distribution on the page.

**Rationale**:
- Single engine call: half the inference time; single source of truth for OCR text.
- Warnings assembled centrally in the new `warnings.py` module (see R-009) rather than scattered across `run_ocr_lines` / `run_layout` / `pipeline`.

**Alternatives considered**:
- Keep two separate V3 calls (one for layout only via `layout_det_model`, one for OCR via a separate text-recognizer path) — rejected; the PRD explicitly calls out running PP-OCRv5 once via V3's built-in pass.
- Keep `run_ocr_lines` as a thin wrapper that extracts only `overall_ocr_res` — rejected; still needs to call the full pipeline, just hides the call behind a misleading name. Clean collapse is simpler.

## R-005: Determinism audit on V3

**Decision**: V3's determinism posture is the same as V2's with these flags, but we pin each axis explicitly:

- **Threading**: `cpu_threads=1`, `use_mp=False` (or V3 equivalent) — no parallel kernel paths.
- **oneDNN**: `enable_mkldnn=False` — eliminates the PIR bug AND eliminates oneDNN's pool-sized-dependent scratch memory layouts that can perturb floats between runs.
- **Paddle seed**: `paddle.seed(0)` called once at engine-lazy-init — carried over from V2's `_lazy_paddle()`.
- **Sort after extraction**: the existing `(bbox.y0, bbox.x0, det_idx)` stable sort on both lines and blocks stays, because V3 does not guarantee list-order stability across reruns. `reading_order` is assigned `1..N` from the sorted sequence.
- **Image preprocessing**: rasterization stays at 300 DPI via `pypdfium2`, deterministic, but page images are streamed one at a time instead of being retained for the whole document lifetime.
- **Output ordering**: `pages` is iterated in page-number order; `blocks` and `raw_ocr_lines` within each page follow the sort above; `warnings` follow FR-020 (page-ascending, vocabulary-lexical within a page). `tables` follow block order within their page.

The Phase 2 implementation MUST add a determinism smoke as part of the integration test suite: run `inv_001_easy` twice, sha256 both `preprocess_output.json`, assert match.

**Rationale**: SC-003 (byte-identical reruns) is a hard gate. Every axis above has been a source of flakiness in the past; pinning them upfront beats chasing an intermittent CI diff.

**Alternatives considered**:
- Trust V3's default ordering and skip the post-sort — rejected; V3 does not document stable list order, and reading-order is semantically our responsibility anyway.
- Allow `cpu_threads=auto` for speed — rejected; determinism outweighs speed on a 20-doc corpus.

## R-006: Corpus regeneration sweep — halt-on-fail

**Decision**: The FR-010 regeneration sweep is implemented as a **shell loop** around the existing `ledgerlinc-preprocess` CLI, not a new Python orchestrator. The loop halts immediately on ANY non-zero exit code — `1` (unexpected), `2` (input_rejected, includes encrypted / malformed PDFs), or `3` (internal_error, includes FR-016 engine-init). This broad halt scope was formalized in Session 2026-04-23 (spec clarification Q23): baseline integrity is the target, and any non-zero exit means a document's artifact failed to land. A failure on document K of N leaves `inv_001..inv_{K-1}` regenerated and `inv_K..inv_N` un-touched — but the sweep will be re-run from the top after the root cause is fixed, and git will discard the partial progress (no commit happens until the sweep succeeds end-to-end).

Reference invocation (quickstart pins the exact form):

```bash
set -e
for folder in tests/stage1_vendor_identity/inv_{001,002,...,020}_*; do
    ledgerlinc-preprocess --document-folder "$folder"
done
```

**Rationale**:
- Halting on first failure is mandated by the spec Clarifications session: "Halt immediately — no partial baselines committed, the sweep is re-run after the env is fixed."
- Shell loop beats a new Python orchestrator because the orchestrator wouldn't add value — there's no state to coordinate, and the CLI already reports structured status.
- Git-level discard of partial progress is natural: regeneration goes into one commit; if the commit doesn't happen, no baselines land.

**Alternatives considered**:
- Python orchestrator that catches `EngineInitError` and stops — rejected; duplicates CLI exit-code logic for no extra signal.
- Skip-and-continue on failure — explicitly rejected by Clarifications (mixed-engine or mixed-completion baseline risk).
- Halt only on FR-016 engine-init (`3`) and skip-and-continue on input-rejection (`2`) or unexpected (`1`) — rejected per Session 2026-04-23 Q23. Any non-zero means a document is missing from the baseline set; proceeding would commit a partial corpus that the downstream evaluator would score incorrectly.

## R-007: `pipeline_version` format and engine SHA

**Decision**: FR-008 dictates bumping both the preprocessing semver and the engine segment. Target shape: `stage1-preprocess-v0.2.0+paddleocr3.5.0.<sha7>.dpi300`.

Implementation in `src/ledgerlinc_ocr/preprocessing/version.py`:

- `SEMVER = "v0.2.0"` (was `"v0.1.0"`).
- `paddleocr_version` still comes from `importlib.metadata.version("paddleocr")` → `"3.5.0"`.
- The 7-char `<sha>` segment: currently hardcoded to `"0000000"` (`build_pipeline_version` default `weights_hash7`). Keep it at `"0000000"` for this slice rather than actually hashing weight files, because weight locations vary by platform and we haven't committed to a canonical weight-cache path. A future slice can swap in a real `hash_weights(...)` call once the weight-caching story is firmer. The hash-function itself (`hash_weights`) stays in `version.py` for that future use.

**Rationale**:
- The `v0.1.0 → v0.2.0` bump communicates "material behavior change" to downstream consumers: silent-fail → loud-fail, blocks-absent → blocks-present. This is exactly the signal a consumer gating on `pipeline_version` needs.
- Keeping `<sha7>` at `0000000` is a tolerated compromise. The PRD cites the same placeholder; swapping it for a real hash is strictly additive and can be done later without another AMENDMENTS entry.

**Alternatives considered**:
- Jump to `v1.0.0` — rejected per Clarifications; `v1.0.0` implies "first production-ready preprocessing", which is stronger than "silent→loud fix." We're still pre-1.0.
- Only bump the engine segment (keep `v0.1.0`) — rejected per Clarifications; behavior change justifies the preprocessing bump.
- Compute `<sha7>` now over the downloaded `~/.paddlex/official_models/**` tree — rejected; first-run download varies in timing and path by OS/devcontainer, and the hash would flap between environments. Defer to a future slice that owns weight caching.

## R-008: FR-016 hard-fail error format

**Decision**: On any exception raised during `PPStructureV3(...)` construction (or during the lazy `_get_engine()` lookup before the first page is processed), `src/ledgerlinc_ocr/preprocessing/pipeline.py` propagates the exception as `EngineInitError`. `src/ledgerlinc_ocr/preprocessing/cli.py` catches it and emits a structured JSON error on stderr with exit code `EXIT_INTERNAL_ERROR` (3). No `preprocess_output.json` is written.

Error payload:

```json
{
    "status": "error",
    "kind": "engine_init_failed",
    "cause_class": "<exception class name>",
    "cause_module": "<module path>",
    "message": "<str(exception)>",
    "missing_weight": "<model artifact name, only if cause is a weight-download failure>",
    "weight_hoster_url": "<upstream URL, only if cause is a weight-download failure>"
}
```

Detection for the "weight-download" sub-case:
- `paddlex`/`paddleocr` raise distinct exception subclasses when a weight file can't be fetched (`HTTPError`, `ConnectionError`, `FileNotFoundError` from within `paddlex.utils.download`). We classify by checking (a) the exception's module path contains `paddlex` or `paddleocr`, AND (b) the exception message matches a loose pattern like `model|weight|download|fetch`. If either check fails, we treat it as a generic engine-init failure and omit the weight fields.

**Rationale**:
- Structured JSON on stderr matches the CLI's existing error envelope — downstream tooling can parse it.
- Including `cause_class` + `cause_module` makes the failure mode unambiguous without needing a full traceback.
- The `missing_weight` + `weight_hoster_url` fields satisfy FR-016's requirement to name the hoster when the cause is weight-related, and are absent otherwise.

**Alternatives considered**:
- Emit a non-JSON error string — rejected; breaks CLI envelope consistency.
- Always include a full `traceback` field — rejected; bloats stderr; developers who need it can rerun with `PYTHONFAULTHANDLER=1` or a debug mode in a future slice.

## R-009: Warning category vocabulary + ordering

**Decision**: A new module `src/ledgerlinc_ocr/preprocessing/warnings.py` centralizes the closed warning vocabulary and the FR-020 ordering rules. Vocabulary (in lexical order):

```python
WARNING_CATEGORIES = [
    "silent_empty_layout",     # FR-003  — downgrades status to "failure"
    "silent_empty_ocr",        # FR-019  — downgrades status to "failure"
    "suspicious_single_block", # FR-018  — does NOT downgrade
    "unknown_layout_label",    # FR-006  — does NOT downgrade
]
STATUS_DOWNGRADING = {"silent_empty_layout", "silent_empty_ocr"}
```

The helper signature:

```python
def build_warning(page_number: int, category_token: str, detail: str) -> str:
    return f"page {page_number}: [{category_token}] {detail}"
```

Sort key for the final `warnings` array:

```python
def warning_sort_key(w: str) -> tuple[int, int]:
    # Parse "page N: [<token>] ..." to (N, vocab_index). Non-parseable (e.g., aggregate
    # "ingestion_sources.paddleocr_vl: failure (all pages failed)") sort last.
    ...
```

Aggregate warnings that don't fit the `page N: [<token>]` format (e.g., the existing `"ingestion_sources.paddleocr_vl: failure (all pages failed)"` line appended in `pipeline.py:145` and the `"page N: OCR failed: <ExceptionClass>: <message>"` / `"page N: layout extraction failed: ..."` per-page engine-runtime-error lines) are **not** rewritten into the bracketed vocabulary in this slice — they remain free-form. Ordering per spec FR-020 rule 4: page-scoped non-categorized (e.g., `"page N: OCR failed: ..."`, `"page N: layout extraction failed: ..."`, rasterization-failed, rotation-normalization) sort AFTER categorized warnings *within that page* in emission order; aggregate / non-page-scoped (e.g., `"ingestion_sources.paddleocr_vl: failure (all pages failed)"`) sort LAST in the document. This keeps the vocabulary scoped to the four categories FR-020 names without requiring AMENDMENTS for adjacent existing warnings.

**Rationale**:
- Centralizing the vocabulary in one module prevents future contributors from inventing a `[foo]` token that isn't in the list.
- Sort-to-end for non-parseable warnings is defensible and keeps the artifact byte-stable.
- Not rebadging existing runtime-error warnings keeps the change surface small; FR-020 only pins the four categories it names, and extending the vocabulary later is explicitly an AMENDMENTS move.

**Alternatives considered**:
- Fold rasterization / OCR-failure / layout-extraction-failed warnings into the bracketed vocabulary too — rejected; requires extending FR-020's closed vocabulary, which Clarifications Q8 scoped to exactly four tokens. Future slice.
- Inline `f"page {n}: [token] ..."` construction at each call site — rejected; easy to mistype the token or format.

## R-010: FR-017 fallback — PaddleOCR 2.10 + CDLA (doc-only)

**Decision**: No 2.10 code ships. This section captures the trigger criteria and pivot cost so the team can invoke the fallback as a future slice without re-discovering the context.

**Trigger criteria** (any one is sufficient):

1. **V3 cannot initialize on corpus** — `PPStructureV3()` construction raises (FR-016 hard-fail) on more than one devcontainer environment even after the `enable_mkldnn=False` workaround is applied.
2. **V3 regresses on > 1 corpus document** — after regeneration, `document_text` no longer contains the `expected.json` vendor-identity token for more than one document that today (under V2 with the `inv_001`-style probe — i.e., one that produces a non-empty `document_text`) would satisfy SC-001's case-insensitive substring check.
3. **V3 weights hoster unreachable for > 1 week** — PP-DocBlockLayout / PP-OCRv5 server det/rec cannot be downloaded from `paddlepaddle.bj.bcebos.com` or `paddlex` hosters, breaking first-run warm-up.

**Pivot cost** (engineering effort to swap in the fallback):

| Axis | Effort |
|------|--------|
| Dependency pin change: revert `paddleocr` to `>=2.8,<3`, remove `paddlex[ocr]`, keep `paddlepaddle>=3.0,<4`. | ~1 PR-hour. |
| Swap `src/ledgerlinc_ocr/preprocessing/ocr.py`: restore `PaddleOCR` + `PPStructure` construction, point `layout_model_dir` at `picodet_lcnet_x1_0_fgd_layout_cdla_infer`, restore `run_ocr_lines()` as a separate call. | ~1 PR-day. |
| Restore separate PP-OCRv4 line pass in `pipeline.py`. | ~1 PR-hour (mostly reverting this slice's collapse). |
| Re-regenerate the `inv_001..inv_020` baseline under the fallback engine, commit with FR-010-style per-doc shift summaries. | ~1 PR-day. |
| Update docs: `architecture.md`, `ollama-runtime.md`, preprocessing quickstart back to the 2.10-era language. | ~2 PR-hours. |
| Total realistic: **2–3 engineering days** to pivot the pipeline off V3 and onto 2.10 + CDLA, excluding review cycles. |

**Rationale**: Recording the criteria and cost here (not code) matches Clarifications Q2 ("Doc-only — fallback decision and trigger criteria recorded in `research.md`; no 2.10 code path ships in this slice") and FR-017. It gives the team a concrete off-ramp without paying the carrying cost of dual-engine code.

**Alternatives considered**:
- Keep a hidden `--engine=legacy` flag that runs 2.10 + CDLA — rejected; doubles the test matrix and violates FR-017's "no 2.10 code path ... in this slice."
- Rely on git-revert of this feature as the fallback — rejected; too coarse, loses FR-003 / FR-018 / FR-019 / FR-020 defensive improvements that are engine-agnostic.

## R-011: Page-at-a-time raster streaming

**Decision**: Refactor preprocessing so rasterization and inference stream one page at a time through the existing page-local `ocr.run_page(...)` boundary. `rasterize.py` should expose a page iterator/generator instead of returning a fully materialized list of `PageRaster | PageRasterFailure`, and `pipeline.py` should consume that iterator directly. Once a page's `raw_ocr_lines`, `blocks`, `tables`, and warnings have been copied into artifact-owned Python data structures, the page image becomes eligible for release before the next page is rasterized.

No previous-page or next-page header/footer context is fed into OCR/layout. The current V3 path already performs recognition per page, and the page image is the only model input needed for stage 1 preprocessing.

**Rationale**:
- The current `010` implementation keeps every rasterized `PIL.Image` in memory until the whole document finishes because `rasterize_pdf(...)` returns a list and `pipeline.run(...)` iterates it later. With PPStructureV3's larger CPU-only model bundle, that turns moderate multi-page fixtures into workstation-level OOMs under WSL.
- Streaming page images removes the unnecessary `N-page raster list` memory multiplier without changing OCR semantics, because `ocr.run_page(...)` is already page-local.
- Avoiding adjacent-page context keeps the preprocessing boundary clean. Cross-page normalization such as repeated-header suppression or multi-page table stitching belongs in a later post-processing layer, not in OCR/layout evidence capture.

**Alternatives considered**:
- Keep whole-document rasterization and rely on larger machines or swap — rejected; the three-page integration fixture already proves the current memory behavior is not robust enough for this slice.
- Reduce raster DPI to cut memory — rejected; 300 DPI is already part of the deterministic preprocessing contract and changing it would confound the migration with an OCR-quality regression.
- Feed previous/next page header/footer snippets into OCR/layout — rejected; that adds cross-page inference complexity without helping glyph recognition on the current page.
- Solve this only with a future GPU lane — rejected; `010` is explicitly CPU-only and needs a fix that works on the current development/runtime path.

## R-012: PP-OCRv5 default recognition threshold

**Decision**: Use the PP-OCRv5 recognition model's default confidence threshold without override. No `text_rec_score_thresh` / `drop_score` parameter is passed to `PPStructureV3(...)`, and no post-filter is applied in `ocr._extract_lines()` beyond what the engine itself returns. Record the exact default value (as emitted by `paddleocr==3.5.0` under `enable_mkldnn=False`, `cpu_threads=1`) in this section during Phase 2 probe work.

**Probe-derived default**: _pending — environment-blocked as of 2026-04-23_. The probe below must run in a devcontainer with the pinned dep set installed (`paddleocr==3.5.0`, `paddlex[ocr]==3.5.1`, `paddlepaddle==3.3.1`, after `~/.paddlex/official_models/` is warm). Capture by inspecting `PPStructureV3`'s constructed pipeline object — typically `pipeline.text_rec_score_thresh` or equivalent `drop_score` attribute on the underlying `TextRecognizer`. Reference values from PP-OCRv5 release notes are often `0.0` (no threshold) or `0.5` (default cutoff); the actual pinned value is recorded here once the probe runs.

**Probe procedure** (T050):

```python
# Run from the repo root with the venv active.
from ledgerlinc_ocr.preprocessing.ocr import _get_engine
engine = _get_engine()  # applies the 010 flags from ocr.py
# Walk candidate attributes; record the first one that returns a float.
for attr in ("text_rec_score_thresh", "drop_score", "rec_score_thresh"):
    if hasattr(engine, attr):
        print(attr, getattr(engine, attr)); break
# Fall back to the underlying TextRecognizer if the top-level attribute is absent.
rec = getattr(engine, "text_recognizer", None) or getattr(engine, "_text_recognizer", None)
for attr in ("text_rec_score_thresh", "drop_score", "rec_score_thresh", "score_thresh"):
    if rec is not None and hasattr(rec, attr):
        print("recognizer.", attr, getattr(rec, attr)); break
```

Fill this section with: `paddleocr` version, `paddlex` version, resolved attribute name, the float value, and the probe date. A future engine bump that moves the default surfaces during FR-010 baseline regeneration review.

**Rationale**:
- **Evidence-first alignment**: tying the filter to engine defaults means `len(raw_ocr_lines)` — the trigger input for FR-003 (`lines>0 AND blocks==0`) and FR-019 (`blocks>0 AND lines==0` on text blocks) — reflects whatever PP-OCRv5 considers a confident recognition. Overriding the threshold would introduce a second axis of "what counts as a line" that has to be justified against the evidence-first rule and maintained across engine bumps.
- **Determinism is preserved via engine pinning**: the lockfile pins `paddleocr==3.5.0` exactly (see Technical Context), so the default doesn't drift between runs on a given dev machine. FR-004 byte-identical reruns still hold.
- **Future engine bumps surface automatically**: if a future `paddleocr` release changes the default, the FR-010 corpus regeneration sweep will produce diffs, and the review cadence catches the shift before it lands in a committed baseline.

**Alternatives considered**:
- Pin a project-specific threshold (e.g., `0.5`) to guarantee stability across engine bumps — rejected per Clarifications Q16. Adds a maintenance surface (where to document, who updates it, how to rationalize) without clear evidence that the engine default is wrong for invoice OCR.
- No threshold at all (persist every detection including low-confidence noise) — rejected. Would bloat `raw_ocr_lines` with noise, potentially firing FR-003 less often than it should on pages where recognition is genuinely weak.
- Defer recording the default until corpus regression surfaces a problem — rejected. The value is discoverable now and recording it upfront is the cheapest way to make FR-010 diffs interpretable later.

**Implementation note**: extract the default at engine-lazy-init time (right after `_ENGINE = PPStructureV3(...)`). Do not hard-code the value; introspect it so that a dependency bump changes the recorded value naturally. If the default is not easily introspectable, print it via a one-off probe script and paste the output into this section alongside the probe date.

## R-013: Confidence value semantics under V3

**Decision**: Persist `confidence` values verbatim from PPStructureV3 output, as floats, on every block and every OCR line. No clamping to `[0.0, 1.0]`, no renormalization, no sigmoid/min-max remapping. When V3 emits no confidence for a given block or line (e.g., a layout region whose `score` is missing, a recognized line without a `rec_scores` entry), `confidence` is persisted as `null` — never `0.0`, never an empty value, consistent with the constitution's "missing fields use null, never zero / empty string" rule.

Implementation points:

- **Blocks**: `confidence = layout_det_res.boxes[i].score` if present and `isinstance(score, (int, float))`, else `None`. No float coercion beyond `float(score)` for JSON stability.
- **OCR lines**: `confidence = overall_ocr_res.rec_scores[det_i]` if the index exists and the value is numeric, else `None`. Parallel-array length mismatch (e.g., `rec_texts` longer than `rec_scores`) MUST NOT silently drop the line; the line persists with `confidence = null` and a note is captured in research if it ever fires in practice.

The current V2 path applied `max(0.0, min(1.0, float(...)))` clamping on OCR-line confidences (see `data-model.md:60` pre-010). That clamp is **removed** under 010 per Clarifications Q18. V2 confidences already fell inside `[0.0, 1.0]` in practice, so the observable diff on the `inv_001..inv_020` baselines from this change alone is zero; the rule matters mainly as a posture statement and as insurance against a future engine emitting out-of-range values that would otherwise be silently clamped.

**Rationale**:
- **Evidence-first discipline**: downstream consumers (evidence packet, extractor, evaluator) decide what to do with confidence signals. Preprocessing is the wrong layer to impose a canonicalization rule, since a clamp or remap would bake in an assumption about what confidence means under a specific engine version.
- **FR-004 determinism preserved**: verbatim persistence with explicit `null` handling is deterministic. The only flake axis is the engine-native float emission, which is already pinned via `cpu_threads=1` + `enable_mkldnn=False` + `paddle.seed(0)` per R-005.
- **Engine-bump visibility**: a future engine that changes confidence semantics (e.g., emitting `logit` scores instead of `[0, 1]` probabilities) will produce a visible diff during FR-010 baseline regeneration review, instead of being silently renormalized into the old range.

**Alternatives considered**:
- Clamp to `[0.0, 1.0]`; missing → `null` (Option B from Clarifications Q18) — rejected. Clamping hides out-of-range values without alerting to them; if a future engine emits logit-scale scores, we'd rather see the outlier and adjust than silently lose the signal.
- Normalize to `[0.0, 1.0]` via documented mapping — rejected. Adds hidden semantics that downstream consumers would have to reverse-engineer.
- Drop `confidence` entirely and write `null` on every block and line — rejected. Discards engine-side information that the extractor already consumes as a signal.

**Schema compatibility note**: the frozen `preprocess_output.schema.json` at `contract_set_version = "1.0.0"` accepts both `number` and `null` for `confidence` fields on blocks and lines. No AMENDMENTS entry is required to persist `null`; spot-check the schema before implementation to confirm the `oneOf [number, null]` / `"type": ["number", "null"]` shape is in place, and add a contract-test fixture covering a block/line with `confidence = null` as part of Phase 2.

## R-014: `tables[]` projection boundary under V3

**Decision**: Populate the artifact's `tables[]` field from PPStructureV3's `table_res_list`, projected into the frozen v1.0.0 schema shape **as of 010's landing commit** (strict-current-shape, formalized in Session 2026-04-23 spec clarification Q24). Discard richer HTML / cell-level structure the engine emits beyond the schema at the persistence boundary. Future AMENDMENTS entries that widen the schema (e.g., adding an optional `cell_confidence` field) DO NOT auto-populate through this projection — a matching preprocessing code change is required before the new field begins to appear in emitted artifacts. This prevents a silent drift where the schema accepts more fields than preprocessing emits. The existing `_parse_table_dims(html) → (rows, columns)` regex logic in `src/ledgerlinc_ocr/preprocessing/ocr.py:113-132` is reused unchanged — the regex treats HTML as opaque and is engine-version-agnostic.

Projection table:

| V3 `table_res_list[i]` field | Artifact `tables[j]` field | Notes |
|------------------------------|----------------------------|-------|
| `html` (full `<table>…</table>` string) | used only via `_parse_table_dims()` to compute `rows` / `columns`; the raw HTML is NOT persisted | richer HTML discarded |
| `cell_bbox` (list of per-cell 4-tuple or 4-point polys) | `cells[]` — each projected to the v1.0.0 cell shape (bbox + text fields defined by the schema) | cell ordering preserved as-emitted; if the schema does not carry per-cell text, text content is NOT persisted even though V3 provides it |
| any V3-only per-cell metadata (e.g., spans, cell type) | **DISCARDED** | requires AMENDMENTS to widen the contract |
| `table_score` / per-cell scores | `confidence` at table level iff the v1.0.0 schema carries it; verbatim per R-013; otherwise discarded | |

Ordering: `tables[]` follows block order within each page (the same sort key as `blocks[]` per R-005). Two runs on the same PDF therefore produce byte-identical `tables[]` ordering.

**Rationale**:
- **Parity with V2 baseline shape**: V2's `PPStructure` table branch populated `tables[]` using the same regex + bbox projection. Leaving `tables[]` empty under V3 would be a silent regression on a schema-visible field that downstream consumers may read.
- **Evidence-first alignment with Assumptions**: the existing spec Assumptions line — "Richer per-block content produced by the new engine (e.g., Markdown-style block content) is discarded at the persistence boundary until a future AMENDMENTS entry permits capturing it" — is extended in FR-021 to explicitly cover table-level richer content. Same rule, same reasoning, now pinned for the top-level `tables[]` array rather than just per-block content.
- **Frozen contract preserved**: no schema edits, no AMENDMENTS entry. Richer V3 content remains available in-memory for future slices once the contract widens.

**Alternatives considered**:
- Leave `tables[]` empty in every artifact this slice produces (Option B from Clarifications Q17) — rejected. Creates a silent shape regression that downstream consumers (evidence packet especially) would have to special-case.
- Populate only when V3 emits a non-empty HTML payload (Option C) — rejected. Adds a conditional branch without changing the end state in practice (V3 either emits a table or it doesn't); simpler to always project.
- Project AND emit a warning when richer content is discarded (Option D) — rejected. Would produce warnings on every table on every document, which is noise rather than signal. A future AMENDMENTS entry is the right place to unlock the richer content, not a permanent warning.

**Implementation note**: the projection logic lives in `ocr._extract_blocks()` (or a sibling helper such as `ocr._extract_tables()`). Do not leak V3-specific `TableRes` objects into `artifact.py`; convert at the `ocr` module boundary.

## R-015: Debug PNG emission policy

**Decision**: Debug `page_*.png` emission stays opt-in via the existing `--write-page-images` CLI flag inherited from 003. No new flag is introduced. When the flag is absent, preprocessing writes no PNGs. When the flag is present, each rasterized page produces `<document-folder>/page_{N}.png` alongside the artifact. PNGs are never committed to the corpus and are NOT subject to FR-004 byte-identical determinism — they are a developer investigation tool, not an artifact downstream consumers read.

Project policy:

- `.gitignore` already excludes `page_*.png` at the corpus root (inherited from 003); verify during Phase 2 and tighten if missing.
- FR-004 language scopes determinism to `preprocess_output.json` explicitly. Do not assert sha256 equality on PNGs in the determinism smoke test (step 4 of the quickstart).
- PNG rendering under PPStructureV3's page-at-a-time streaming (R-011) writes the PNG immediately after rasterization, before the image is released. No in-memory retention of the full document's PNG set.

**Rationale**:
- **Corpus commit hygiene**: committing PNGs under FR-010 regeneration would balloon the feature commit with ~20 MB of binary churn on every engine bump (PP-OCRv5 glyph shifts don't change rasterization, but a future DPI / rasterizer bump would). Keeping PNGs out of the corpus keeps the regeneration diff scoped to JSON.
- **FR-004 scope clarity**: pinning determinism to the JSON artifact matches what downstream consumers actually read. PaddleOCR's rendering of internal annotations (if we ever wire up `--write-page-images` to include layout overlays) is not a contract surface.
- **Zero implementation cost**: `--write-page-images` already exists in the 003 CLI contract (see `contracts/cli-contract.md`). Clarifications Q19 formalizes its semantics rather than introducing a new code path.

**Alternatives considered**:
- Always emit PNGs alongside the JSON, commit to corpus, subject to FR-004 determinism (Option B from Clarifications Q19) — rejected. Adds ~20 MB of binary corpus churn without a downstream consumer that reads the PNGs.
- Opt-in flag but committed per developer discretion (Option C) — rejected. Creates inconsistent corpus state depending on who ran the regeneration; determinism story becomes "sometimes deterministic."
- Remove the feature entirely in this slice (Option D) — rejected. The flag is useful for local debugging of layout-vs-OCR disagreements (e.g., diagnosing when FR-018 fires); no reason to kill it.

**Implementation note**: nothing to change in `cli.py` for this clarification. Spot-check during Phase 2 that the flag is still wired to `rasterize.py` / `pipeline.py` and that `.gitignore` excludes `page_*.png`.

## Baseline timings

> This section is populated during Phase 2 implementation, per SC-005. The table below is the target shape; values will be filled in when the corpus regeneration sweep runs end-to-end.

| Invoice | Pages | First-run wall-clock | Second-run wall-clock | CPU | RAM | OS | paddleocr version | notes |
|---------|-------|---------------------|-----------------------|-----|-----|----|-|-|
| `inv_001_easy` | 1 | _tbd_ | _tbd_ | _tbd_ | _tbd_ | _tbd_ | 3.5.0 | baseline single-invoice reference (SC-005) |

"First-run" means first CLI invocation after model-weight warm-up has completed (so weights are on disk but the engine is fresh). "Second-run" means the same invocation repeated, with the engine already lazy-initialized — useful as a rough determinism + warm-cache sanity.

The table MUST stay in this file (not in `quickstart.md`, not in the landing commit body) per Clarifications Q4.
