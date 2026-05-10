# Research: DPI Reduction And Region-First Vendor Identity Preprocess

**Feature**: 018-dpi-region-first-preprocess
**Date**: 2026-05-10

This document resolves the implementation-level decisions the spec deferred to `/speckit.plan` (Assumptions section: activation flag names, exact CPU-default identifier strings, reduced-DPI numeric value, region-first heuristic and band proportion, fixed corpus subset, rasterization rounding tolerance), the `[Gap]`-marked items from the five release-gate checklists this layer is responsible for, plus the internal architecture choices the implementation has to make (preset registry shape, error-class extension vs. addition, schema_version bump, `phase_timings.rasterization` accounting under fallback, coordinate translation for header-band cropping, single-engine reuse on fallback). One decision per section, in the standard `Decision / Rationale / Alternatives considered` format.

## R-018.1: Activation mechanism for both new switches

**Decision**: Add two CLI flags to BOTH the existing `python -m ledgerlinc_ocr.preprocessing` entry point and `python -m ledgerlinc_ocr.pipeline` (corpus mode):

- `--raster-profile <id>` (string; default `cpu-default` on the CPU profile, default `legacy` on the GPU profile)
- `--region-strategy <id>` (string; default `cpu-default` on the CPU profile, default `full-page` on the GPU profile)

Each flag has an env-var fallback:

- `LEDGERLINC_RASTER_PROFILE=<id>` (CLI flag wins when both are set)
- `LEDGERLINC_REGION_STRATEGY=<id>` (CLI flag wins when both are set)

**Env-var literal-value handling**: identical to feature 017 R-017.1 — the env-var value is passed verbatim to `resolve_raster_profile` / `resolve_region_strategy`; no `.strip()`, no case normalization, no whitespace trimming. A trailing newline, surrounding whitespace, or a mixed-case value (e.g., `Reduced-V1`) results in `UnknownPresetError` → exit code 16. Identifier values are case-sensitive lowercase by codebase convention; a forgiving normalization here would mask typos.

Both flags are **off-by-default** in the sense that the empty / unset case selects the active profile's default identifier. They are **orthogonal** to `--preprocess-profile`, `--gpu-warmup`, `--module-set`, and `--det-rec-variant` (an operator may combine `--preprocess-profile=ppstructurev3@gpu --gpu-warmup --module-set=reduced-v1 --det-rec-variant=ppocrv5-mobile --raster-profile=reduced-v1 --region-strategy=header-first-v1` in a single invocation).

When either flag is set on `ppstructurev3@cpu` or any stub adapter, the CLI emits a single stderr warning containing the literal `--raster-profile ignored:` (or `--region-strategy ignored:`) and proceeds with the active profile's default — warn-and-proceed, not silent-ignore and not rejection (FR-014, mirroring feature 016 FR-010 / feature 017 FR-013). Selecting an unknown identifier value (e.g., `--raster-profile reduced-v99` or `--region-strategy header-first-v99`) fails fast with exit code 16 and a clear stderr message naming the valid values for that axis (R-018.12).

**Rationale**:
- The CLI-flag-with-env-var-fallback shape matches feature 014's `--preprocess-profile`, feature 016's `--gpu-warmup`, and feature 017's `--module-set` / `--det-rec-variant` precedents on the same entry points; operators discover the flags in `--help` next to the existing knobs.
- Two separate flags (rather than a single combined string like `--gpu-preprocessing legacy:full-page`) is the natural shape for two separate top-level run_summary fields agreed under /speckit.clarify (FR-008: `raster_profile_id` + `region_strategy_id`).
- "CLI wins over env var" is the standard precedence and matches feature 016 R-016.1 / feature 017 R-017.1.
- Strings (not enums) keep the identifier extensible without contract churn — matches the human-readable-not-hash requirement in FR-008.

**Alternatives considered**:
- **Single combined flag** (`--gpu-preprocessing legacy:full-page`). Rejected: contradicts FR-008 (two separate top-level fields). Combined string requires parse-on-read everywhere it's grepped.
- **Profile suffix** (`ppstructurev3@gpu+reduced-v1+header-first-v1`). Rejected: violates the orthogonality assumption with `--preprocess-profile` and would multiply the profile namespace combinatorially with feature 017's two axes already in flight.
- **Env vars only**. Rejected: discoverability is poor (`--help` does not show env vars) and would break the feature 014 / 016 / 017 flag-based precedent.
- **Per-page region coordinates** (`--region-bbox 0,0,612,250`). Rejected: contradicts FR-004 (closed-vocabulary preset names only; no free-form region coordinates on the runtime path).
- **Free-form numeric DPI** (`--dpi 200`). Rejected: contradicts FR-001 (closed-vocabulary preset names only; no free-form numeric DPI knob on the runtime path). The numeric DPI value lives behind the preset name in `raster_profiles.py`.

## R-018.2: Closed `raster_profile_id` vocabulary at landing

**Decision**: Exactly four valid values at landing time:

| Value | Profile | DPI | Meaning |
|---|---|---|---|
| `legacy` | `ppstructurev3@gpu` only | 300 (read from `preprocessing/version.py:DPI`) | The rasterization DPI active on `main` at landing time of feature 017 (DPI = 300, set in feature 014's `version.py`). Default `raster_profile_id` value emitted on a no-flag GPU run; unchanged from feature 017's GPU defaults. |
| `reduced-v1` | `ppstructurev3@gpu` only | 200 | Reduced DPI value chosen per R-018.3. |
| `cpu-default` | `ppstructurev3@cpu` (CPU singleton) | 300 | Identity preset — preset resolution does not mutate the CPU rasterizer's DPI; the CPU lane continues to use the module-level `DPI = 300` constant. The `cpu-default` value exists only to populate the run_summary identifier surface on every run (FR-011). |
| `stub-default` | stub adapter | 300 (irrelevant; no rasterization) | Stub-adapter identity preset; emits `raster_profile_id="stub-default"` on the run_summary. |

Resolving any other string raises `UnknownPresetError(preset_axis="raster_profile", ...)` → exit code 16 (R-018.12).

Adding a future preset (e.g., `reduced-v2` at 150 DPI if R-018.3 sensitivity work later supports it) is a code change to `preprocessing/raster_profiles.py` plus a new entry in this table — not a runtime numeric knob (per FR-001).

**Rationale**:
- Symmetric with feature 017's `module_set_id` registry: two GPU values (legacy + one reduced) plus two identity values (CPU + stub).
- The `legacy` DPI is read from the existing `preprocessing/version.py:DPI` constant (300) so that "legacy" never drifts from whatever feature 014 originally pinned. This avoids a duplicate-source-of-truth bug if `DPI` ever changes.
- Distinct strings for CPU vs stub make absence-as-regression-signal (FR-011) actually informative, mirroring feature 017 R-017.2.

**Alternatives considered**:
- **Three values** (`legacy`, `reduced-v1`, `default`). Rejected: a single `default` for both CPU and stub erases the CPU-vs-stub distinction useful for diagnosing test-infrastructure problems. (Same reasoning as feature 017 R-017.2.)
- **Two reduced presets at landing** (`reduced-v1` at 200, `reduced-v2` at 150). Rejected: the spec mandates "at least one" reduced preset (FR-001) but the four-corner benchmark (FR-005) exercises only one cell per axis. Adding a second reduced preset doubles benchmark cost without buying decision value at landing — `reduced-v2` can be added later as a pure code change without contract churn.

## R-018.3: `reduced-v1` DPI value

**Decision**: `reduced-v1` rasterizes at **200 DPI**.

**Rationale**:
- 200 DPI is the conventional "high-quality OCR" setting for receipts/invoices in the broader document-AI literature; legacy 300 DPI was originally chosen for general document understanding (tables, formulas, fine print on scientific PDFs), not for vendor-identity-only OCR which is dominated by header text typically printed at 8-pt or larger.
- A 200 / 300 ratio rasterizes ~44% fewer pixels per page (200²/300² ≈ 0.44) ⇒ ~56% rasterization-time savings as a first-order estimate. Per-page inference cost on PaddleOCR scales with input image area, so per-page inference time should also drop materially. The actual measured savings land in `quickstart.md` Appendix A after the FR-005 four-corner benchmark.
- 200 DPI keeps a comfortable margin above the ~150 DPI floor where PaddleOCR detection recall on small text starts to degrade in our experience (verified informally on the same fixed 5-doc subset before plan time).
- A single reduced value is enough to demonstrate the surface and serve as the FR-005 benchmark cell. If the team later wants `reduced-v2` at 150 DPI, that is a code change plus a new table entry (per FR-001) and a follow-up benchmark; this feature does not require it.

**Alternatives considered**:
- **150 DPI**. Rejected as the *first* reduced preset for safety: 150 is closer to the floor where PaddleOCR detection starts to miss small text, and a regression on the FR-016 quality gate would block landing the surface itself. Better to land 200 DPI and then iterate to 150 in a follow-up if quality numbers from 200 are clean.
- **240 DPI** (a smaller reduction). Rejected: the predicted latency win (~36% rasterization savings at 240² vs. 300²) is modest enough that the four-corner benchmark might struggle to distinguish it from noise. 200 DPI is a clearer signal for "did the win materialize?".

## R-018.4: Closed `region_strategy_id` vocabulary at landing

**Decision**: Exactly four valid values at landing time:

| Value | Profile | Behavior | Meaning |
|---|---|---|---|
| `full-page` | `ppstructurev3@gpu` only | Identity strategy | Process every PDF page edge-to-edge (the strategy active on `main` at landing time of feature 017). Default `region_strategy_id` value emitted on a no-flag GPU run. |
| `header-first-v1` | `ppstructurev3@gpu` only | Region-first targeting per R-018.5 | Process page 1's top-30%-of-height band only; pages 2..N appear in `preprocess_output.json.pages[]` as empty records (R-018.6). On no-evidence trigger, fall back to full-page on that document (R-018.7). |
| `cpu-default` | `ppstructurev3@cpu` (CPU singleton) | Identity (full-page semantics on CPU) | The CPU lane continues to process every PDF page edge-to-edge; the `cpu-default` value exists only to populate the run_summary identifier surface on every run (FR-011). |
| `stub-default` | stub adapter | Identity | Stub-adapter identity preset; emits `region_strategy_id="stub-default"` on the run_summary. |

Resolving any other string raises `UnknownPresetError(preset_axis="region_strategy", ...)` → exit code 16 (R-018.12).

**Rationale**:
- Symmetric with R-018.2 and feature 017 R-017.2 / R-017.4 (two GPU presets + two identity presets).
- The CPU lane explicitly does NOT inherit the `header-first-v1` behavior; CPU users may set `--region-strategy=header-first-v1` and observe the warn-and-proceed line per FR-014. CPU runs are not a primary optimization target for this feature.

**Alternatives considered**:
- **Add `header-only-v1`** (process header band on page 1 with no fallback — fail-fast on empty). Rejected at /speckit.clarify Q1 in favor of fall-back-to-full-page semantics.
- **Add `header-on-every-page-v1`** (uniform narrow band on every page). Rejected at /speckit.clarify Q2 in favor of page-1-only with empty page records for pages 2..N.

## R-018.5: `header-first-v1` heuristic and band proportion

**Decision**: The `header-first-v1` preset's page-targeting rule is:

```python
def page_targeting(pdf_doc, page_index: int) -> Optional[BBox]:
    if page_index != 0:
        return None  # pages 2..N: skip → empty page record (R-018.6)
    page = pdf_doc.get_page(page_index)
    width_pt, height_pt = page.get_size()
    band_height_pt = height_pt * 0.30  # top 30% of page height
    return BBox(
        x0_pt=0.0,
        y0_pt=0.0,
        x1_pt=width_pt,
        y1_pt=band_height_pt,
    )  # PDF coordinate system: origin top-left, y increases downward
```

Band proportion is **30% of page height**, hard-coded in `preprocessing/region_strategies.py`. The proportion is a deterministic constant — it is NOT exposed on the runtime path (FR-004) and NOT computed from page content (FR-006).

**Rationale**:
- Vendor identity on US/EU invoice templates is overwhelmingly in the top portion of page 1 (logo + business name + address block typically occupy the top 15–25% of the printed area). A 30% band is a comfortable margin that catches the common cases without requiring per-document tuning.
- A constant proportion (rather than absolute mm/in / page-size-aware) keeps determinism trivial: same input PDF ⇒ same band ⇒ same crop ⇒ same OCR output (FR-006).
- Origin top-left + y-increases-downward matches `pypdfium2`'s coordinate convention (which the feature already uses for page geometry). The crop coordinate translation back to full-page bbox space (R-018.15) is an additive offset of `(0, 0)` for the top-left band, simplifying the bbox math.
- 30% leaves a substantial margin: even on a US-Letter portrait page (792 pt tall), 30% is 237.6 pt — comfortably more than the typical 150–200 pt header zone of an invoice. If a fixture's vendor identity sits below 237.6 pt the FR-007 trigger fires and the document falls back to full-page (R-018.7) — graceful degradation, not silent failure.

**Alternatives considered**:
- **20% band**. Rejected: tight on tall pages (US-Legal, A3) where the full header zone may exceed 20% of height. Risks higher fallback rate without proportional latency win on the no-fallback documents.
- **40% band**. Rejected: erodes the latency win materially (40% of pixel area is less than 50% savings) without a clear benefit on the typical fixtures.
- **Fixed pt height** (e.g., top 240 pt). Rejected: page-size-dependent; on landscape A3 (842 pt tall), 240 pt is only 28% of the page; on US-Letter portrait (792 pt), it's 30%. The constant-proportion rule produces the same fraction of page height across all page sizes.
- **Adaptive band** (use layout heuristics to detect the header zone). Rejected: would violate FR-006 ("MUST NOT depend on extraction or vendor-identity model output") if the heuristic touches predict output. Constant-proportion is strictly deterministic.

## R-018.6: Empty page record schema details for skipped pages 2..N

**Decision**: When `header-first-v1` skips page `i` (i.e., `i > 0`), the orchestrator emits the following page record into `preprocess_output.json.pages[i]`:

```python
{
    "page_number": i + 1,
    "width": int(round(width_pt * DPI / 72.0)),     # derived from PDF geometry; uses the resolved RasterProfile.dpi (legacy=300 or reduced-v1=200), not the legacy-only constant
    "height": int(round(height_pt * DPI / 72.0)),
    "rotation_detected": rotation_from_pdf,         # 0 unless the PDF page declares /Rotate per pypdfium2
    "blocks": [],
    "raw_ocr_lines": [],
}
```

`width` and `height` are derived from the PDF page geometry via `pypdfium2` (no rasterization required — `width_pt` / `height_pt` come from `page.get_size()`, which reads the PDF's MediaBox without paging in the rendered image). This satisfies the schema's `width >= 1` / `height >= 1` constraint without paying any rasterization cost. `rotation_detected` is read from the PDF page rotation field (one of `[0, 90, 180, 270]` per the schema enum); when the PDF declares no rotation, `0` is emitted.

**Rationale**:
- The schema (`contracts/stage1_vendor_identity/v1.2.0/preprocess_output.schema.json`) requires `page_number`, `width`, `height`, `rotation_detected`, `blocks`, `raw_ocr_lines` for every page object (lines 62–68 of the schema). Empty `blocks: []` and `raw_ocr_lines: []` are explicitly permitted by the per-page object definition.
- Deriving `width` / `height` from PDF geometry (not from a rendered image) means pages 2..N do zero rasterization work and zero inference work — capturing essentially all of the region-first latency win per Clarifications Q2.
- Using the resolved RasterProfile's DPI (not the module-level `DPI = 300` constant) ensures that a `reduced-v1 × header-first-v1` run produces page-2 geometry consistent with the actual rasterization that page 1 used. (If we used 300 DPI for the empty page geometry while page 1 was rendered at 200, downstream consumers comparing `pages[0].width` to `pages[1].width` would see a confusing mismatch.)

**Alternatives considered**:
- **Omit pages 2..N entirely** (`pages.length == 1`). Rejected at /speckit.clarify Q2 in favor of preserving `pages.length == page_count`.
- **Render pages 2..N at 1 DPI** to produce trivially small images. Rejected: still pays the PDF-render+disk-I/O cost without buying any benefit; deriving from `page.get_size()` is strictly cheaper.
- **Use the legacy DPI (300) for empty page geometry regardless of resolved profile**. Rejected: as noted above, would create a `pages[0].width` vs `pages[1].width` inconsistency on `reduced-v1` runs.

## R-018.7: FR-007 fallback trigger evaluation and action

**Decision**: After region-first preprocessing of page 1's targeted band completes, the orchestrator in `preprocessing/pipeline.py` performs:

```python
def trigger_fired(targeted_blocks: list[Block]) -> bool:
    """Clarifications Q3: whitespace-stripped concat of blocks[].text empty."""
    return not "".join(b.text for b in targeted_blocks).strip()

if region_strategy.name == "header-first-v1":
    targeted_blocks = engine.predict(crop_image)  # crop = page 1 header band
    if region_strategy.trigger_fired(targeted_blocks):
        # Discard partial output entirely; re-preprocess as full-page on the SAME engine instance.
        run_summary.region_strategy_fallback_count += 1
        document_output = run_full_page(engine, pdf_path)  # rasterize all pages, predict each
    else:
        translated_blocks = translate_bboxes(targeted_blocks, crop_offset=(0, 0))
        document_output = build_output(
            page_1_blocks=translated_blocks,
            pages_2_to_N=[empty_page_record(pdf_doc, i) for i in range(1, page_count)],
        )
```

"Whitespace-stripped" uses Python's default `str.strip()` (Unicode whitespace categories — spaces, tabs, newlines, NBSPs, etc.). The trigger check inspects only `blocks[].text` — not `raw_ocr_lines[].text`, not bounding-box presence, not block count. Per /speckit.clarify Q3, the trigger is a pure string-emptiness check on the targeted region's blocks.

On a triggered fallback the partial region-first output is **fully discarded**: the `pages[0]` populated by the page-1 region-first attempt is replaced by `pages[0]` from the full-page strategy; `pages[1..N]` are populated by the full-page strategy (not empty records); the document's `phase_timings.rasterization` / `phase_timings.per_page_inference` accumulate the wall-clock cost of BOTH attempts (R-018.10); the run-level `region_strategy_fallback_count` increments by exactly 1.

**Rationale**:
- Clarifications Q3 fixed the trigger condition explicitly; this decision just maps it into pseudocode for `pipeline.py` so the planner does not have to re-derive it.
- "Discard partial output" (rather than "merge page 1 region-first with full-page pages 2..N") avoids ambiguous output shapes — the document's `pages[]` is either fully region-first (page 1 populated, pages 2..N empty) or fully full-page (all pages populated), never mixed. This makes the per-document attribution rule from Clarifications Q4 ("fallen-back document has full-length populated `pages[]`") unambiguous.
- Reusing the same engine instance for the fallback predict (R-018.9) preserves feature 015 FR-001 (PPStructureV3 constructed exactly once per process).
- Per-document fallback granularity (not per-page) matches Clarifications Q1.

**Alternatives considered**:
- **Per-page fallback** (fall back only the page that triggered, keep other pages region-first). Rejected at /speckit.clarify Q1 in favor of per-document. Per-page fallback would break the Clarifications Q4 attribution rule (`pages[]` shape would no longer cleanly indicate "fell back vs. clean").
- **Merge partial outputs** (keep page 1 region-first; emit pages 2..N from full-page). Rejected: produces a `pages[]` shape that doesn't match either the clean-region-first pattern or the clean-full-page pattern, complicating attribution and downstream debugging.
- **Trigger on confidence threshold** rather than empty-text. Rejected at /speckit.clarify Q3 — introduces a magic number; less stable across documents; the empty-text check is simpler and already catches the real-world failure mode.

## R-018.8: `region_strategy_fallback_count` accounting on `run_summary`

**Decision**: `region_strategy_fallback_count` on the `kind: "run_summary"` line is the **count of documents in this run that triggered the FR-007 fallback exactly once each**. Specifically:

- For a single-document run (single-doc CLI path), the value is `0` or `1`.
- For a corpus run (warm-corpus CLI path), the value is the number of documents in `--documents-file` for which `header-first-v1` triggered the fallback (one increment per document, not per page).
- For runs where `region_strategy_id != "header-first-v1"` (i.e., `full-page`, `cpu-default`, `stub-default`), the value is always `0` (always-emit per Clarifications Q4 / FR-009).
- For runs that ran `header-first-v1` cleanly on every document (no triggers), the value is `0` — `0` does NOT mean "the field was missing"; absence of the field is itself a regression signal per FR-011.
- The counter is reproducible: two runs of the same `(raster_profile_id, region_strategy_id)` × same corpus subset produce the same `region_strategy_fallback_count` value (Determinism checklist CHK026), because the trigger (R-018.7) is deterministic on per-document content and the per-document content is read from a pinned source PDF.
- **Duplicate-document semantics**: if the same source document appears twice in a corpus run (e.g., `--documents-file` lists `inv_001_easy` twice), the unit is "document occurrence" not "distinct document" — the counter increments once per occurrence that triggered the fallback (so the same fallback-forcing document listed twice would contribute `+2` to the counter). The corpus is not expected to contain duplicates in normal operation; this rule exists to make the counter's behavior unambiguous at the edge.

**Rationale**:
- Clarifications Q4 fixed the field shape (single integer, always emitted). This decision pins the *unit*: documents-fallen-back, not pages-fallen-back, not corpus-aggregate-percentage.
- Documents-fallen-back is the natural unit because the fallback granularity itself is per-document (R-018.7 / Clarifications Q1). Switching to a different unit at the counter level would create an off-by-K mismatch between "one document fell back" and "the counter incremented by N".
- The "always emit even when zero" rule is the carry-forward of feature 011/014/015/016/017's pattern — every additive run_summary field is always emitted; absence is the regression signal.

**Alternatives considered**:
- **Page-granular counter** (`region_strategy_fallback_pages_count`). Rejected: per Clarifications Q1, fallback is per-document, not per-page. A page-granular counter would imply a per-page fallback semantic that the spec rejected.
- **Percentage instead of count** (`region_strategy_fallback_rate: float`). Rejected: less informative for single-doc runs (0 / 1 is awkward to express as a percent) and changes the field type from int to float without buying anything.
- **Object** (`{count: int, documents: [doc_id, ...]}`). Rejected at /speckit.clarify Q4 in favor of the single-integer shape. Per-doc attribution is recoverable from `pages[]` shape.

## R-018.9: Engine reuse on fallback (preserve feature 015 FR-001)

**Decision**: The fallback path in `preprocessing/pipeline.py` (R-018.7) MUST reuse the **same** PPStructureV3 engine instance that was constructed at preflight time (per feature 015 FR-001 — engine constructed exactly once per process). The fallback predict on full pages 1..N goes through `engine.predict(rendered_page_image)` exactly the way a normal full-page run would; no second engine is constructed.

**Rationale**:
- Feature 015 FR-001 / FR-006 (single engine per process; single device per process) is non-negotiable. Constructing a second engine on the fallback path would violate it and double the engine_init / GPU-bind cost per fallen-back document.
- The PPStructureV3 engine is stateless across `predict` calls (verified informally during feature 015 work — calls to `engine.predict(page_a)` followed by `engine.predict(page_b)` produce the same outputs for `page_b` regardless of whether `page_a` came first). Reusing the engine for the fallback predict is safe.

**Alternatives considered**:
- **Construct a second engine in fallback mode**. Rejected as above.
- **Cache the page-1 crop and re-predict the same crop after fallback**. Rejected: meaningless — the fallback is precisely the case where the crop predict yielded no text, so re-predicting the same crop yields the same nothing.

## R-018.10: `phase_timings.rasterization` accounting on fallen-back documents

**Decision**: For a document that triggers the FR-007 fallback, the document's `phase_timings.rasterization` reports the **combined wall-clock time** of (a) the page-1 header-band rasterization that triggered fallback PLUS (b) the full-page rasterization of pages 1..N performed by the fallback path. Same combination rule for `phase_timings.per_page_inference`. No new field is added to break out the two phases — the existing `phase_timings.rasterization` key is honest about total work done.

**Rationale**:
- "Honest cost reporting" — the wall clock spent rasterizing for that document IS the sum of both attempts. Hiding the page-1 attempt's cost would make the FR-005 four-corner benchmark for `header-first-v1` look artificially good vs. `full-page` on documents that fell back, which is exactly the wrong signal for the FR-016 promotion gate.
- Contract-wise, the existing `phase_timings.rasterization` semantic is "total wall-clock seconds spent rasterizing for this document" — combined cost is the natural reading. No field shape change required (FR-022).
- For benchmark interpretation, readers comparing `(reduced-v1, header-first-v1)` to `(reduced-v1, full-page)` can detect "header-first paid more on this document" by comparing per-document `phase_timings.rasterization` against the per-document `region_strategy_fallback_count` contribution (recoverable from `pages[]` shape per Clarifications Q4). The benchmark narrative in `quickstart.md` Appendix A will note this explicitly.

**Alternatives considered**:
- **Final-only** (report the full-page rasterization time only on fallen-back documents). Rejected: hides the cost of the failed attempt; makes header-first look strictly cheaper than full-page on those documents, which is dishonest.
- **Region-first attempt only** (report only the failed crop time). Rejected: hides the full-page work that actually produced the document's output.
- **Add a new sub-key** (`phase_timings.rasterization_fallback`). Rejected: violates FR-010 / FR-022 (`phase_timings.*` shape is frozen). The combined-cost reading already gives readers the information they need (combined with `region_strategy_fallback_count` for context).

## R-018.11: Quality-gate metric extraction (carry-forward from feature 017 R-017.10)

**Decision**: The FR-016 two-metric quality gate consumes exactly the same two numbers feature 017 R-017.10 specified, on the same fixed 5-doc subset (R-018.13):

1. **Aggregate vendor-identity field score** — read from `evaluation_run_summary.json` at the corpus root, key `aggregate.vendor_identity_field_score` (the per-corpus aggregate produced by the existing evaluator). Decimal in `[0.0, 1.0]`.
2. **Per-document pass count** — count of documents where the per-document `evaluation_document.json.pass_status == "pass"` (per `docs/stage1-vendor-identity/scoring.md`'s pass criterion). Integer in `[0, 5]` for the 5-doc subset.

The candidate `(raster_profile_id, region_strategy_id)` pair passes the gate iff `candidate_metric_1 >= legacy_metric_1` AND `candidate_metric_2 >= legacy_metric_2` on the same subset. Equality counts as parity (per FR-016 "≥").

**Rationale**:
- Identical to feature 017 R-017.10 — reuses the exact metrics so the gate is comparable across features. The spec FR-016 explicitly mirrors feature 017 FR-015.
- Both metrics come from existing evaluator outputs; no new metric is introduced (FR-016 / SC-009).

**Alternatives considered**:
- See feature 017 R-017.10 (alternatives evaluated and rejected there carry over unchanged).

## R-018.12: Unknown-preset fail-fast wiring (extend, don't add)

**Decision**: Extend the existing `UnknownPresetError.preset_axis: Literal["module_set", "det_rec_variant"]` field to `Literal["module_set", "det_rec_variant", "raster_profile", "region_strategy"]`. Reuse the existing `UNKNOWN_PRESET = 16` exit code. No new exception class; no new exit code. The existing CLI catch sites in `preprocessing/cli.py` and `pipeline/cli.py` already route `UnknownPresetError` uniformly to exit 16 with the standard `error: unknown <preset_axis>: <preset_value!r> — valid values are: <…>` stderr message; widening the `preset_axis` type does not require any caller change.

**Rationale**:
- Feature 017 R-017.9 / data-model.md `UnknownPresetError` Stability stance explicitly anticipated this: *"`preset_axis` is a closed two-element string literal type at the type level. Adding a third axis is a feature-level decision, not an implementation choice."* Adding two more axes here is exactly that feature-level decision.
- The operator-visible behavior is identical to feature 017 (exit code 16, same stderr format, no `run_summary` emitted on fail-fast). Reusing the exit code is simpler than adding `UNKNOWN_RASTER_PROFILE = 17` / `UNKNOWN_REGION_STRATEGY = 18` (which would force every CLI catch site to grow new branches without changing what operators do in response).
- Minimal blast radius: a single line change in `preprocessing/errors.py` (the `Literal[…]` widening) plus the two new `resolve_*` functions in `raster_profiles.py` / `region_strategies.py` raising `UnknownPresetError(preset_axis="raster_profile", ...)` / `(..., "region_strategy", ...)`.

**Alternatives considered**:
- **New exception class** (`UnknownAxisError`). Rejected: breaks the uniform CLI-boundary catch, forces caller changes, adds maintenance burden for no operator-visible benefit.
- **New exit codes** (17 + 18 for the two new axes). Rejected: operators already learn to treat exit code 16 as "you passed a bad preset name on some axis"; differentiating by code adds noise without enabling different operator response.

## R-018.13: Fixed corpus subset for the FR-005 four-corner benchmark

**Decision**: The four-corner benchmark uses the **exact same fixed 5-document subset** feature 017 R-017.11 pinned: `inv_001_easy`, `inv_002_easy`, plus the three mid-difficulty / challenging documents named in feature 017's research artifact. The exact list is read from `specs/017-ppstructurev3-module-reduction/research.md` R-017.11 at landing time and copied verbatim into this feature's `tasks.md` benchmark task description.

**Rationale**:
- Spec Assumptions §3 says: *"Where possible, the subset matches feature 017's so cross-feature comparison is meaningful."* This decision honors that.
- Comparable subsets across features 017 and 018 lets the team see at a glance which feature's optimization was responsible for which timing change (vs. having to re-run feature 017's benchmark on a new subset).
- Five documents is large enough to detect the kinds of effects this feature targets (header-band fallback rates, DPI-related per-page-inference savings) and small enough that the four-corner matrix runs in tractable wall-clock time on a workstation.

**Alternatives considered**:
- **Whole 20-document corpus**. Rejected: 4× the runtime per benchmark cell (× 4 cells = 16×) without proportional decision value.
- **A different 5-doc subset chosen for this feature**. Rejected: breaks cross-feature comparability without buying anything specific to feature 018.

## R-018.14: SCHEMA_VERSION codebase-level patch bump

**Decision**: `RunSummary.SCHEMA_VERSION` patches **0.1.4 → 0.1.5** in `pipeline/timing.py` for the three additive top-level fields introduced by this feature (`raster_profile_id`, `region_strategy_id`, `region_strategy_fallback_count`). This is the codebase-level run_summary observability schema, not a stage 1 artifact contract — see Constitution II PASS row in plan.md for the QG#2 inapplicability argument.

The bump is automatic on every run regardless of preset selection (CPU runs, stub-adapter runs, GPU runs all report `schema_version: "0.1.5"` after this feature lands). This is the same always-emit pattern features 014/015/016/017 used.

**Rationale**:
- Patch bump (third digit) signals "additive only, no existing fields renamed/removed/retyped" — consistent with feature 014 (0.1.0 → 0.1.1), feature 015 (0.1.1 → 0.1.2), feature 016 (0.1.2 → 0.1.3), feature 017 (0.1.3 → 0.1.4).
- Bumping signals to readers / downstream consumers / log analyzers that the run_summary's content surface widened. The current readers in this repository (the harness, the evaluator) consume only existing fields and ignore unknown new ones; a future reader checking `schema_version` exactly knows when each field was added.

**Alternatives considered**:
- **Minor bump 0.1.4 → 0.2.0**. Rejected: would imply a non-additive change. Run_summary fields are strictly additive in this feature — no rename, no removal, no retyping.
- **No bump** (keep 0.1.4). Rejected: undermines the schema_version's only purpose (signaling field-set evolution).

## R-018.15: Coordinate translation for header-band crop (preserve FR-002)

**Decision**: PaddleOCR returns block / line bboxes in the coordinate system of the input image it was given. For the `header-first-v1` preset, the input image is the header-band crop, so PaddleOCR's bboxes are in crop-relative coordinates. Before placing those bboxes into `preprocess_output.json.pages[0].blocks[].bbox` and `pages[0].raw_ocr_lines[].bbox`, the orchestrator in `preprocessing/pipeline.py` MUST translate them back to **full-page coordinates** by adding the crop's top-left offset:

```python
def translate_bbox(crop_relative_bbox: BBox, crop_offset_px: Tuple[int, int]) -> BBox:
    """Crop is taken from page top-left → offset = (0, 0) for header-first-v1.
    For a future preset that crops a different region, offset = (crop_x0_px, crop_y0_px).
    """
    dx, dy = crop_offset_px
    return BBox(
        x0=crop_relative_bbox.x0 + dx,
        y0=crop_relative_bbox.y0 + dy,
        x1=crop_relative_bbox.x1 + dx,
        y1=crop_relative_bbox.y1 + dy,
    )
```

For `header-first-v1` specifically, the crop offset is `(0, 0)` (header band starts at the page top-left), so the translation is the identity. The translation function is still present as a guard rail for future presets that might crop a non-top-left region.

**Rounding tolerance for FR-002**: The bbox coordinates in `preprocess_output.json` are integers (per the schema's bbox def, lines 116–122 of `preprocess_output.schema.json` — `minItems: 4, maxItems: 4` of integer pixels). For a `(reduced-v1, full-page)` run vs. a `(legacy, full-page)` run on the same fixture, bbox values may differ by **±1 pixel per coordinate** (due to rasterization rounding from a different source DPI). Beyond that, no other field of `preprocess_output.json` differs in shape (no field added, removed, renamed, retyped — FR-002).

**Rationale**:
- FR-002 requires that `preprocess_output.json` field shape and coordinate system stay identical to the legacy run on the same fixture. The translation back to full-page coordinates is the implementation step that makes this true for the header-first preset; without it, page-1 bboxes would silently use crop-relative coordinates and downstream bbox-based logic would break.
- The ±1 pixel tolerance is the natural floor of integer rasterization at different DPIs — `round(value_pt * 200 / 72)` and `round(value_pt * 300 / 72)` differ by at most 1 in the final integer for any given `value_pt`. Naming it explicitly resolves the FR-002 deferral.

**Alternatives considered**:
- **Crop the page image but keep PaddleOCR's bbox returns in crop-relative space** (rely on a downstream `region_offset` field to translate later). Rejected: violates FR-020 (no new `preprocess_output.json` field) and pushes complexity downstream where it doesn't belong.
- **Tighter tolerance (0 px)**. Rejected: literally impossible to achieve at different DPIs; integer rasterization rounds differently at 200 vs. 300 DPI.
- **Looser tolerance (±5 px)**. Rejected: hides real bugs in coordinate translation behind benchmark noise. ±1 is the genuinely correct floor.

## R-018.16: Audit narrative location (Appendix B in this feature)

**Decision**: The FR-016 quality-gate evidence (per-cell numbers from the four-corner benchmark) lands in this feature's `quickstart.md` **Appendix A** (benchmark numbers), and the FR-017 quality-gate decision narrative (which `(raster_profile_id, region_strategy_id)` was promoted, if any, and the gate evaluation pass/fail) lands in `research.md` **Appendix B**. Neither lands in `docs/stage1-vendor-identity/` — the runtime topology and stage 1 contracts are unchanged, so no operator-facing docs page is added (Constitution Quality Gate #3 inapplicability).

**Rationale**:
- Mirrors feature 017's split (research.md Appendix B for narrative; quickstart.md Appendix A for raw numbers).
- Keeps the `docs/stage1-vendor-identity/` surface stable — that directory describes the contract and runtime, not per-feature benchmark results.

**Alternatives considered**:
- **Add a new `docs/stage1-vendor-identity/dpi-region-first-benchmark.md`**. Rejected: per-feature benchmark results don't belong in the contract-and-runtime docs surface; future readers looking for `docs/stage1-vendor-identity/*` material expect contract-stable references, not feature-018-specific benchmarks.
- **Put both in `tasks.md`**. Rejected: `tasks.md` is the implementation work breakdown; the benchmark numbers and decision narrative are research outputs, not tasks.

## Appendix A: Header-band-proportion sensitivity (filled if relevant)

If the FR-005 four-corner benchmark surfaces evidence that 30% (R-018.5) is the wrong default — e.g., the `header-first-v1 × reduced-v1` cell shows a fallback rate above 1/5 on the fixed subset, or page-2 vendor-identity content is materially undercounted — record the alternative band proportion considered and the supporting per-document evidence here. Otherwise this appendix stays empty: 30% is the landing value.

## Appendix B: Quality-gate evidence (filled at landing)

| Cell | `raster_profile_id` | `region_strategy_id` | aggregate field score | per-document pass count | Verdict (vs. legacy × full-page) |
|---|---|---|---|---|---|
| Legacy baseline | `legacy` | `full-page` | _filled at landing_ | _filled at landing_ | — |
| Reduced DPI | `reduced-v1` | `full-page` | _filled at landing_ | _filled at landing_ | _pass / fail / deferred per FR-025_ |
| Region-first | `legacy` | `header-first-v1` | _filled at landing_ | _filled at landing_ | _pass / fail / deferred per FR-025_ |
| Combined | `reduced-v1` | `header-first-v1` | _filled at landing_ | _filled at landing_ | _pass / fail / deferred per FR-025_ |

Promotion decision (recorded at landing per FR-017): either name the promoted `(raster_profile_id, region_strategy_id)` pair OR record "no promotion at landing — legacy stays GPU default; both new presets stay opt-in only".
