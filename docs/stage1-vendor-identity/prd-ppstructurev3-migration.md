# PRD: PPStructureV3 Preprocessing Migration

## Purpose

This PRD defines the product requirements for migrating the stage 1 PDF preprocessing layer from PaddleOCR 2.10 (PPStructure + PP-OCRv4) to PaddleOCR 3.5 (PPStructureV3 + PP-OCRv5).

It is specifically about the trijunction-ingestion layer in `src/ledgerlinc_ocr/preprocessing/`. It does not change the extraction, consensus, routing, or evaluator layers — those layers consume `preprocess_output.json` and are unaffected as long as the artifact contract stays intact.

This PRD owns the **full-structure** preprocessing profile. A separate
follow-up feature may add a lightweight `edge-ocr` profile, but that profile
must plug into the same repository, profile-selection mechanism, and artifact
contract discipline described in `prd-stage-runtime-profiles.md`.

## Problem Statement

The default PPStructure layout detector bundled with PaddleOCR 2.10 for `lang='en'` is `picodet_lcnet_x1_0_fgd_layout_infer`, trained on **PubLayNet**. PubLayNet has five classes — Text, Title, List, Table, Figure — drawn from academic paper layouts. When this detector is run on a real invoice (e.g. `tests/stage1_vendor_identity/inv_001_easy/source.pdf`), it returns zero regions. OCR lines are still produced, but every page's `blocks` array is empty and `document_text` collapses to `""`.

The failure is silent:

- `PPStructure.__call__` returns `[]` without raising.
- `run_layout()` in `src/ledgerlinc_ocr/preprocessing/ocr.py` only appends a warning in the `except` branch, so an empty result produces no warning.
- `ingestion_sources.paddleocr_vl.status` reports `"success"`.
- The resulting `preprocess_output.json` looks schema-valid to downstream consumers even though the layout evidence is missing.

This is a blocker for moving the full pipeline off stubs. The evidence packet, extractor prompt, and router all rely on `blocks` and `document_text` being meaningful. Shipping vendor-identity results on top of zero-block inputs would produce confident-looking outputs with no grounding in layout evidence, which directly violates the constitution's evidence-first rule.

A probe on inv_001 confirmed the root cause and narrowed fixes:

- V2 with PubLayNet (current): 0 regions
- V2 with the CDLA detector (via `lang='ch'`): 8 regions — works, but the accompanying OCR model is Chinese
- V3 (`PPStructureV3` with `enable_mkldnn=False`): 7 layout regions + 6-entry `parsing_res_list` containing block content strings

## Goal

Replace the stage 1 preprocessing engine with PPStructureV3 so layout detection behaves correctly on invoice-style documents, surface a warning when the layout detector still returns zero regions on pages that have OCR lines, and keep the existing `preprocess_output.json` artifact contract intact for downstream consumers.

The delivered profile from this migration is the canonical full-evidence
profile for corpus baselines. It is optimized for layout/table grounding and
contract fidelity, not for the fastest possible first-pass OCR scan.

## Users and Stakeholders

Primary users:

- Internal developers building the extraction, evidence, and evaluator layers — they consume `preprocess_output.json` and need populated `blocks` and `document_text`.
- Corpus-labeling operators — their debug flow assumes layout blocks exist.

Stakeholders:

- LedgerLinc OCR/model pipeline engineering
- Devcontainer / infra owners — disk footprint and download budget change

## Scope

Included:

- Replace `PPStructure` + `PaddleOCR` usage in `src/ledgerlinc_ocr/preprocessing/ocr.py` with `PPStructureV3`.
- Retire the separate `run_ocr_lines()` call in favor of V3's built-in OCR pass (`overall_ocr_res.rec_texts`), since V3 already runs PP-OCRv5 during structure inference — running PP-OCRv4 separately on the same image is wasteful and produces two different text recognitions to reconcile.
- Apply `enable_mkldnn=False` to V3 construction as a workaround for the paddle 3.3.1 PIR/oneDNN `ConvertPirAttribute2RuntimeAttribute` bug on `PP-DocBlockLayout`. Document the workaround so it can be removed once upstream ships a fix.
- Extend `PPSTRUCTURE_LABEL_TO_BLOCK_TYPE` with V3 label names (`paragraph_title`, `doc_title`, and any additional V3 classes that appear in practice). Unknown labels continue to fall back to `text` with a warning, as today.
- Add a defensive warning in the preprocessing pipeline: when a page has `raw_ocr_lines > 0` and `blocks == 0`, emit a warning and downgrade `ingestion_sources.paddleocr_vl.status` away from `"success"`. This is the silent-empty-defect fix and must land regardless of which layout engine we run.
- Update `pyproject.toml` and `requirements.txt` pins: `paddleocr>=3.5,<4`, add `paddlex[ocr]>=3.5,<4`. Keep `paddlepaddle>=3.0,<4`.
- Regenerate the `preprocess_output.json` baseline for every `inv_XXX_<difficulty>/` document in `tests/stage1_vendor_identity/`, because OCR text and confidences will shift under PP-OCRv5. Record the V3 baseline as the new expected output.
- Update affected documentation: `docs/stage1-vendor-identity/architecture.md`, `docs/stage1-vendor-identity/ollama-runtime.md` (if it references PaddleOCR versions), `specs/003-pdf-preprocessing/research.md` (add a V3 migration decision entry), and the preprocessing quickstart.
- Update `pipeline_version` string in `preprocess_output.json` to reflect the new engine (current format: `stage1-preprocess-v0.1.0+paddleocr2.10.0.0000000.dpi300`).
- Keep the implementation shape compatible with future preprocessing profiles by isolating engine-specific logic behind preprocessing-owned call sites. This PRD does not require implementing the profile abstraction, but it must not make a later `edge-ocr` profile require a second repository.

Explicitly out of scope:

- The ~500 MB of additional model weights (PP-DocBlockLayout, PP-DocLayout_plus-L, PP-OCRv5 server det/rec, SLANeXt_wired, SLANet_plus, RT-DETR-L cell detectors) will download on first run, as today. No devcontainer-side model prefetch is in scope for this slice.
- Changes to the `preprocess_output.json` schema itself. Block types, quality, ingestion_sources, tables, and document_text stay as defined in `contracts/stage1_vendor_identity/v1.0.0/`. If V3 produces block content we'd like to capture (e.g. Markdown-style `block_content`), that requires an AMENDMENTS entry and is deferred.
- Turning on V3's doc-orientation, dewarping, textline-orientation, formula, seal, or chart modules. All stay off in this slice to keep inference deterministic and cheap.
- Implementing the lightweight `edge-ocr@jetson` preprocessing profile. That is
  a follow-up profile feature targeting the Jetson Nano Super GPU lane, not a
  CPU-only scanner.
- Splitting preprocessing engines into separate repositories.
- Evaluator or extractor changes.
- GPU / ROCm inference path for the PPStructureV3 full-structure profile.
  CPU-only, matching today. The separate lightweight edge profile is specified
  as `edge-ocr@jetson` in the runtime-profile PRD.

## Constraints

- The v1.0.0 `preprocess_output.json` contract remains frozen as a historical snapshot. New outputs for this migration must validate against the active `contracts/stage1_vendor_identity/v1.2.0/preprocess_output.schema.json` and emit `contract_set_version = "1.2.0"`.
- Determinism. V3 must run CPU-only, single-threaded (`cpu_threads=1`, `use_mp=False` equivalents), and produce byte-stable output for a given input. If V3's ordering is non-deterministic, the migration adds a sort/normalization step.
- No new cloud or network dependencies beyond the existing model weight downloads from `paddlepaddle.bj.bcebos.com` / `paddlex` model hosters.
- Warnings are surfaced in the artifact's `warnings` array, not swallowed into stdout. This matches existing preprocessing behavior.

## Success Criteria

Functional:

1. On `inv_001_easy/source.pdf`, `preprocess_output.json` has `pages[0].blocks` with `len >= 3` and `document_text` non-empty and containing at least one of the expected vendor-identity tokens (e.g. `"DESERT DIECUTTING"`).
2. Across the full stage 1 corpus (`tests/stage1_vendor_identity/inv_001..inv_020`), zero pages produce the silent `lines>0, blocks==0` condition. Any page that does hits the defensive warning and downgraded `ingestion_sources` status.
3. The regenerated baselines round-trip: running preprocessing twice on the same PDF produces byte-identical `preprocess_output.json`.
4. `python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity` passes.
5. Existing pipeline and contract tests pass. Preprocessing integration tests either pass unchanged or are updated with clear justification (OCR text shifts under PP-OCRv5).

Non-functional:

6. First-run preprocessing time on a single invoice in the devcontainer is documented (baseline) so we have a number to defend on future regressions.
7. The `enable_mkldnn=False` workaround is captured in `research.md` with a pointer to the upstream paddle issue, so it can be removed when paddle fixes the PIR/oneDNN attribute converter.

## Risks and Mitigations

- **Paddle 3.3.1 PIR/oneDNN bug on PP-DocBlockLayout.** Confirmed during the probe. Mitigation: `enable_mkldnn=False`. Risk: slower inference. Acceptable for stage 1 CPU-only corpus-size workloads.
- **Output quality regression on specific invoices.** PP-OCRv5 may transcribe certain fonts/layouts worse than PP-OCRv4 on a given sample. Mitigation: regenerate the corpus baseline and review any delta against the human-labeled `expected.json`.
- **Disk footprint.** Additional ~500 MB of model weights land in `~/.paddlex/official_models/`. Mitigation: document in `ollama-runtime.md` / preprocessing quickstart so devs don't get surprised.
- **Process-per-document runtime looks worse than production-style warm runtime.** The full PPStructureV3 stack is expensive to construct even when model files are cached. Mitigation: record cold single-document timing for this migration, then use the runtime-profile follow-up to add warm corpus/worker execution that initializes the selected preprocessing profile once per process.
- **Full-stack profile confused with lightweight edge scanning.** PPStructureV3 is the full-structure profile, not the future lightweight Jetson scanner. Mitigation: profile names and `pipeline_version` must distinguish full-structure and edge-OCR outputs.
- **Version drift.** `paddleocr>=3.5,<4` is broader than the current `<3`. Patch bumps inside 3.x could re-trigger the oneDNN bug or change default models. Mitigation: pin `paddleocr==3.5.0` and `paddlex[ocr]==3.5.1` exactly in `requirements.txt`; keep the looser bound in `pyproject.toml` for libraries that depend on us.
- **Silent regressions in the extractor.** The extractor consumes `document_text` and `blocks`. A change in block ordering or block-text concatenation could surface as field-level regressions in `edge_extraction_output.json`. Mitigation: once V3 is in, run the full pipeline end-to-end on the corpus and diff vendor-identity outcomes against the evaluator summary.

## Fallback

If PPStructureV3 cannot be stabilized on this paddle version (e.g. the oneDNN workaround itself regresses or new bugs appear mid-migration), the fallback is to keep PaddleOCR 2.10 and swap the layout detector to the CDLA model (`picodet_lcnet_x1_0_fgd_layout_cdla_infer`) via `layout_model_dir` + `layout_dict_path`, keeping English OCR in `run_ocr_lines`. That still fixes the silent-empty defect and the layout-on-invoices problem, at the cost of losing the richer `parsing_res_list` content V3 provides. This fallback is recorded as a research decision in spec 008 regardless, so we can pivot without restarting.
