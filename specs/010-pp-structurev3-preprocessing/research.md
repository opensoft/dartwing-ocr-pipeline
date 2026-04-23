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
- Module-level `_ENGINE` caching mirrors current V2 `_OCR_ENGINE` / `_STRUCTURE_ENGINE` caching. One construction per process, not per call.

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
- **Image preprocessing**: rasterization stays at 300 DPI via `pypdfium2`, deterministic. No change from 003.
- **Output ordering**: `pages` is iterated in page-number order; `blocks` and `raw_ocr_lines` within each page follow the sort above; `warnings` follow FR-020 (page-ascending, vocabulary-lexical within a page). `tables` follow block order within their page.

The Phase 2 implementation MUST add a determinism smoke as part of the integration test suite: run `inv_001_easy` twice, sha256 both `preprocess_output.json`, assert match.

**Rationale**: SC-003 (byte-identical reruns) is a hard gate. Every axis above has been a source of flakiness in the past; pinning them upfront beats chasing an intermittent CI diff.

**Alternatives considered**:
- Trust V3's default ordering and skip the post-sort — rejected; V3 does not document stable list order, and reading-order is semantically our responsibility anyway.
- Allow `cpu_threads=auto` for speed — rejected; determinism outweighs speed on a 20-doc corpus.

## R-006: Corpus regeneration sweep — halt-on-fail

**Decision**: The FR-010 regeneration sweep is implemented as a **shell loop** around the existing `ledgerlinc-preprocess` CLI, not a new Python orchestrator. The loop halts immediately on the first non-zero exit code, so an FR-016 engine-init failure on document K of N leaves `inv_001..inv_{K-1}` regenerated and `inv_K..inv_N` un-touched — but the sweep will be re-run from the top after the env is fixed, and git will discard the partial progress (no commit happens until the sweep succeeds end-to-end).

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
- Skip-and-continue on failure — explicitly rejected by Clarifications (mixed-engine baseline risk).

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

Aggregate warnings that don't fit the `page N: [<token>]` format (e.g., the existing `"ingestion_sources.paddleocr_vl: failure (all pages failed)"` line appended in `pipeline.py:145` and the `"page N: OCR failed: <ExceptionClass>: <message>"` / `"page N: layout extraction failed: ..."` per-page engine-runtime-error lines) are **not** rewritten into the bracketed vocabulary in this slice — they remain free-form and sort to the end (or after their page's categorized warnings). This keeps the vocabulary scoped to the four categories FR-020 names without requiring AMENDMENTS for adjacent existing warnings.

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

## Baseline timings

> This section is populated during Phase 2 implementation, per SC-005. The table below is the target shape; values will be filled in when the corpus regeneration sweep runs end-to-end.

| Invoice | Pages | First-run wall-clock | Second-run wall-clock | CPU | RAM | OS | paddleocr version | notes |
|---------|-------|---------------------|-----------------------|-----|-----|----|-|-|
| `inv_001_easy` | 1 | _tbd_ | _tbd_ | _tbd_ | _tbd_ | _tbd_ | 3.5.0 | baseline single-invoice reference (SC-005) |

"First-run" means first CLI invocation after model-weight warm-up has completed (so weights are on disk but the engine is fresh). "Second-run" means the same invocation repeated, with the engine already lazy-initialized — useful as a rough determinism + warm-cache sanity.

The table MUST stay in this file (not in `quickstart.md`, not in the landing commit body) per Clarifications Q4.
