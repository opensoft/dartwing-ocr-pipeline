# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

Step 2 of the LedgerLinc AP Clerk Agent: an OCR + field-extraction + structuring pipeline for invoice PDFs. The repo currently holds one prototype script (`step2_ocr_ensemble.py`) plus the full design docs, schemas, and PRDs for the real stage 1 implementation that has not been written yet. Most non-trivial work starts by reading `docs/stage1-vendor-identity/`, `.specify/memory/constitution.md`, and the active OpenSpec/Speckit artifacts, then translating those contracts into code.

## Commands

Run the current prototype (images only — PDF path is stubbed):
```bash
python step2_ocr_ensemble.py --input test_invoices/your_invoice.png --client_id test
```
Output is written to `output/<stem>_structured.json`.

Install dependencies:
```bash
pip install -r requirements.txt
```

Devcontainer (defaults to a lightweight Python 3.12 image; runs `pip install -r requirements.txt` as `postCreateCommand`):
- Open in VS Code Dev Containers — the `pipeline-dev` service from `.devcontainer/docker-compose.yml` is used
- `OLLAMA_BASE_URL` defaults to `http://host.docker.internal:11434` so the container calls a host-level Ollama

Start workstation host Ollama for the AMD ROCm/GPU lane:
```bash
scripts/start-host-ollama-rocm-wsl.sh
```
Do not use plain `ollama serve` for the WSL `gfx1151` GPU lane; this host requires the HSA preload and SDMA settings captured in that script.

Optional local Ollama container (CPU-only on WSL; see caveat below):
```bash
docker compose -f .devcontainer/docker-compose.yml --profile ollama up -d
```

Production-style native Linux ROCm Ollama:
```bash
docker compose -f docker/compose.ollama-rocm-linux.yml up -d
```

There is no test suite, linter, or build system configured yet.

Speckit worktree helper:
```bash
source /home/brett/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline/.specify/shell/ct.zsh
```
- After `/speckit.specify`, run `/ct` for the jump target or `/ctp` for full worktree details
- Run `ct` to actually change the shell into that worktree
- `cta` opens an existing Speckit worktree. If the desired `NNN-*` worktree does not exist yet, run `/speckit.specify` from `main` first; do not use `cta` to infer or create the feature.

## OpenSpec and Speckit Workflow

Use OpenSpec as the change-governance layer and Speckit as the implementation layer.

Use OpenSpec before implementation when work changes one of these boundaries:
- stage 1 artifact schemas or folder contracts
- runtime/container/model orchestration
- consensus, routing, review, or escalation policy
- Jetson/edge deployment constraints
- the development workflow itself

Use Speckit for feature worktrees, implementation planning, task breakdown, and code execution. Do not duplicate task lists between the two systems: an OpenSpec change should capture intent and design decisions, then hand off to exactly one Speckit feature under `specs/NNN-*` for implementation.

Before running `/speckit.specify`, verify from the same shell/container with `git status -sb` and `git branch --show-current` that the checkout is on `main` with no unintended worktree changes. Never run `/speckit.specify` from a feature branch, cleanup branch, or existing Speckit worktree. If not on `main`, stop and switch to `main` only after preserving or committing any current work. This rule applies even when updating an existing feature spec.

Do not pre-create Codex-prefixed branches for Speckit features. The normal Codex `codex/` branch prefix applies to ad hoc Codex work, but Speckit features must let the `/speckit.specify` `before_specify` hook create the feature branch/worktree using the canonical `NNN-feature-name` form. After specify creates that worktree, run follow-on Speckit commands (`/speckit.clarify`, `/speckit.plan`, `/speckit.tasks`, `/speckit.implement`) from the generated worktree, not from `main` and not from an unrelated older worktree selected by `cta`.

Run OpenSpec from the bench/workbench container (`py-bench`), where `openspec` is on `PATH`. Do not add OpenSpec to the lightweight LedgerLinc project container; that container remains focused on the pipeline runtime and local validation path.

Skip OpenSpec for small implementation-only fixes where an existing `specs/NNN-*` artifact already defines the behavior and no product or architecture decision is being made.

## Architecture

### Target architecture (long-term)

Three layers, documented in `docs/stage1-vendor-identity/architecture.md`:

1. **Trijunction ingestion** — `PaddleOCR-VL-1.5` (layout/tables/reading order) + `Falcon OCR 0.3B` (text + spam gate) + `Falcon Perception 0.6B` (logos, stamps, spatial grounding). Output is a shared **evidence packet**, not raw OCR text.
2. **Triple-model ensemble extraction** — three independent voters over the same evidence packet: Model A (Qwen3-VL cloud / Qwen3 edge), Model B (Gemma 4 cloud / Gemma 4 E4B/E2B edge), Model C (Phi-4 Mini as the logic/verifier vote).
3. **Deterministic consensus + routing** — field-level vote comparison: unanimous ⇒ high confidence, 2-of-3 majority ⇒ accept with downstream recheck, split ⇒ escalate/review. Consensus and routing are **never** delegated to a model.

### Stage 1 slice (what gets built first)

Stage 1 is intentionally narrow — **PDF input only**, **vendor identity only**, local validation stacks only, no line items, no remote cloud escalation, no latency gate. A single-voter baseline is acceptable as long as the code shape is ensemble-ready (shared evidence packet, pluggable voters, deterministic routing). The cloud solution is tested first as `cloud-workstation` on local workstation GPU hardware, not as a provider-managed cloud path.

### The four artifacts (stable JSON contracts)

Every stage 1 run produces four JSON artifacts, defined in `docs/stage1-vendor-identity/schemas.md`:

- `preprocess_output.json` — pages, blocks, raw OCR lines, tables, quality, `ingestion_sources` (paddleocr_vl / falcon_ocr / falcon_perception status flags). No business inference.
- `edge_extraction_output.json` — model-driven structured extraction with per-field `{value, confidence, evidence}` and `vote_metadata` for future multi-voter runs.
- `routing_decision.json` — deterministic `decision` (`edge_accept` / `edge_review_required`), `scores`, `checks`, and `review_status`.
- `final_structured_payload.json` — clean downstream handoff, references the other three via a `trace` block.

The evaluation harness compares `final_structured_payload.json` against a human-labeled `expected.json` and emits `evaluation_document.json` per doc plus `evaluation_run_summary.json` per run. Corpus layout is per-document folders under `tests/stage1_vendor_identity/inv_XXX_<difficulty>/`.

### Runtime boundaries (do not collapse)

From the constitution (`.specify/memory/constitution.md`):

- **Pipeline code** owns preprocessing, extraction orchestration, consensus, routing, final payload.
- **Test harness** (separate concern — see `prd-test-harness.md`) owns corpus, expected truth, evaluation, reporting.
- **Selected local model runtime over HTTP** owns model inference for stage 1. Full-workstation uses host Ollama, cloud-workstation uses local workstation GPU model endpoints, and edge-fast uses Jetson-local Ollama. Do not embed model runtime into the pipeline container.
- On this workstation only host Ollama is GPU-capable. Start it with `scripts/start-host-ollama-rocm-wsl.sh`, not plain `ollama serve`; the optional `ollama` Docker service on WSL is CPU-only — HIP cannot see the AMD GPU inside Docker Desktop. Treat the native Linux ROCm compose file as the production path, not the WSL container. Details: `docs/stage1-vendor-identity/ollama-runtime.md` and `docs/ollama-rocm-wsl-gfx1151-fix.md`.

### Non-negotiable rules

- **Schema-first, evidence-first.** Prompts and code adapt to the JSON contracts in `schemas.md`, not the reverse. Use `null` for missing fields, never empty strings.
- **Deterministic control.** Spam gates, consensus comparison, explicit-vs-inferred handling, and `manual_review_required` decisions must be code, not model output. Confidence is a signal, not provenance.
- **Company-name provenance.** If no explicit company name is found, a best guess may be stored in `company_name.value`, but `company_name.present` must be `false`, `company_name.inferred` must be `true`, and `manual_review_required` must be `true`. This is mandatory and is enforced by the missing-name subset of the test corpus.

### Current state vs. target

`step2_ocr_ensemble.py` is a prototype only: it runs PaddleOCR + PPStructure on images, stubs the PDF path, and emits an ad-hoc JSON that does **not** match the stage 1 schema. Treat it as scaffolding to be replaced, not as a reference for correct behavior — authoritative behavior lives in `docs/stage1-vendor-identity/`.

## Stage 1 contracts are machine-validated

The stage 1 artifact shapes and the per-document folder contract are now enforced in code, not only documented. The current contract set is `contract_set_version = "1.2.0"`; earlier `v1.0.0` and `v1.1.0` snapshots remain frozen for compatibility and amendment history.

- **Machine-readable contracts**: `contracts/stage1_vendor_identity/v1.2.0/` — one JSON Schema per artifact plus the folder contract and `contract_set.json` metadata. Updated only through `contracts/stage1_vendor_identity/AMENDMENTS.md`.
- **Validator**: `src/ledgerlinc_ocr/validator/` — CLI at `python -m ledgerlinc_ocr.validator` (subcommands: `validate artifact`, `validate folder`, `validate corpus`, `show contract-set`). Importable Python API; see `specs/001-freeze-schemas-folder-contracts/contracts/module-api.md` for stability guarantees.
- **Install**: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`. Test suite: `.venv/bin/pytest tests/contract_tests/`.

## Key References

- `docs/stage1-vendor-identity/architecture.md` — target + stage 1 processing flow
- `docs/stage1-vendor-identity/prd-model-pipeline.md` — what the pipeline must do
- `docs/stage1-vendor-identity/prd-test-harness.md` — what the harness must do (separate concern)
- `docs/stage1-vendor-identity/schemas.md` — authoritative JSON shapes; now cross-linked to the machine layer
- `docs/stage1-vendor-identity/scoring.md` — evaluation rubric and pass criteria
- `docs/stage1-vendor-identity/dataset-layout.md` — per-document folder structure and the closed `challenge_tags` vocabulary
- `docs/stage1-vendor-identity/labeling-guide.md` — conventions for `expected.json` and `notes.md`, PII/license screening checklist
- `docs/stage1-vendor-identity/ollama-runtime.md` — host vs. container Ollama, WSL caveats
- `docs/stage1-vendor-identity/gpu-warmup-and-cache.md` — feature 016 operator guide: cache locations (`~/.cache/miopen`, `~/.cache/comgr`), clearance procedure, `MIOPEN_FIND_MODE=2` rationale, workspace-warning hybrid policy, how to read `phase_timings.warmup` as cold-vs-warm signal, recovery for `WarmupError` cause classes
- `contracts/stage1_vendor_identity/v1.0.0/` — executable contract set
- `contracts/stage1_vendor_identity/AMENDMENTS.md` — amendment checklist + changelog
- `specs/001-freeze-schemas-folder-contracts/quickstart.md` — validator quickstart
- `specs/003-pdf-preprocessing/spec.md` — PDF preprocessing slice requirements and user stories
- `specs/003-pdf-preprocessing/plan.md` — PDF preprocessing technical plan, structure, and milestones
- `specs/003-pdf-preprocessing/research.md` — PDF preprocessing decisions (DPI, determinism, version string, quality thresholds, document_text join)
- `specs/003-pdf-preprocessing/quickstart.md` — end-to-end preprocessing walk-through for devcontainer
- `specs/003-pdf-preprocessing/checklists/contract.md`, `determinism.md`, `failure-handling.md`, `requirements.md`, `scope.md` — release-gate checklists for the preprocessing slice
- `specs/004-evidence-packet-assembly/spec.md` — evidence-packet slice requirements and user stories
- `specs/004-evidence-packet-assembly/plan.md` — evidence-packet technical plan, structure, and milestones
- `specs/005-single-voter-extraction/spec.md` — stage 1 single-voter extractor requirements, user stories, success criteria
- `specs/005-single-voter-extraction/plan.md` — stage 1 extractor architecture, module layout, milestones
- `specs/005-single-voter-extraction/research.md` — stage 1 extractor decisions (R-001 httpx/no-retry, R-002 timeout, R-003 ungrounded-confidence cap, R-007 JSON repair, R-008 status truth table, R-009 pipeline_version, R-011 exit-code table, R-012 blank-packet failure path, R-013 reconcile determinism)
- `specs/005-single-voter-extraction/contracts/cli-contract.md` — `ledgerlinc-extract` CLI surface + exit codes
- `specs/005-single-voter-extraction/contracts/voter-config.md` — voter config schema, extension-key escape hatch, stub-voter contract
- `specs/005-single-voter-extraction/quickstart.md` — end-to-end extractor walk-through and hard-failure smoke tests
- `specs/008-routing/spec.md` — deterministic routing slice requirements (edge_accept vs. edge_review_required; priority-ordered forcing rules)
- `specs/008-routing/plan.md` — routing technical plan; module layout under `src/ledgerlinc_ocr/router/`
- `specs/008-routing/research.md` — routing decisions (exact-vs-major version check, score formulas, status mapping, atomic write, reason vocabulary, `policy_version` lifecycle)
- `specs/008-routing/data-model.md` — routing input/output entity model
- `specs/008-routing/contracts/cli-contract.md` — `python -m ledgerlinc_ocr.router route` CLI surface and exit-code taxonomy (0/1/2/3)
- `specs/008-routing/quickstart.md` — end-to-end routing walk-through for devcontainer
- `specs/008-routing/checklists/contract.md`, `determinism.md`, `failure-handling.md`, `requirements.md`, `routing-policy.md` — release-gate checklists for the routing slice
- `specs/009-final-payload/spec.md` — final-payload assembler slice requirements, user stories, and hard-fail invariants (FR-003 through FR-025)
- `specs/009-final-payload/plan.md` — assembler technical plan, invariant check order, FINAL_KEY_ORDER, error kinds
- `specs/009-final-payload/research.md` — assembler decisions (pipeline_version format, secondary enum ordering, `overall_vendor_confidence` formula pinning, processed_at format, JSON serialization)
- `specs/009-final-payload/quickstart.md` — end-to-end walkthrough for running `python -m ledgerlinc_ocr.assembler`
- `.specify/memory/constitution.md` — governing principles; violations are design issues, not style issues
- `openspec/README.md` — OpenSpec/Speckit split and handoff policy

## Active Technologies
- Python 3.12 (matches `.devcontainer/Dockerfile` base image) + `jsonschema >= 4.22` (Draft 2020-12 validator); `pydantic >= 2.7` for the structured-report model and typed CLI results; Python stdlib (`argparse`, `json`, `pathlib`, `dataclasses`). No PyTorch, no PaddleOCR, no network dependencies for this slice. (001-freeze-schemas-folder-contracts)
- Filesystem only. JSON artifacts on disk. No database. No model weights. No network calls. (001-freeze-schemas-folder-contracts)
- Python 3.12 (matches devcontainer and existing package) + `jsonschema >=4.22` (already installed), `pydantic >=2.7` (already installed), `python-magic` or stdlib `struct` for PDF magic detection (see research.md) (002-cli-contract)
- Filesystem only — JSON artifacts on disk, no database (002-cli-contract)
- Python 3.12 (devcontainer base image) (003-pdf-preprocessing)
- Filesystem only. Reads `tests/stage1_vendor_identity/inv_XXX_<difficulty>/source.pdf`, writes `preprocess_output.json` (and optional debug `page_*.png`) into the same folder. No DB, no network. (003-pdf-preprocessing)
- Python 3.12 (devcontainer base image, matches 001/002/003). (004-evidence-packet-assembly)
- Filesystem only. Reads one `preprocess_output.json` per invocation from `tests/stage1_vendor_identity/inv_XXX_<difficulty>/`. At default logger level, writes nothing. At `DEBUG` (or lower), writes exactly one `evidence_packet.json` into the same folder. No DB. No network. No model weights. (004-evidence-packet-assembly)
- Python 3.12 (devcontainer base image, matches existing package). (005-single-voter-extraction)
- Filesystem only. Reads `tests/stage1_vendor_identity/inv_XXX_<difficulty>/preprocess_output.json`; writes `edge_extraction_output.json` into the same folder. No database. No cloud. The only network call is the host-Ollama HTTP request to `OLLAMA_BASE_URL`. (005-single-voter-extraction)
- Python 3.12 (devcontainer base image, already established) + `pypdf >= 5.0, < 7` (already installed; used for PDF structural-integrity check in the validator); `jsonschema >= 4.22`, `pydantic >= 2.7` (already installed; used by existing validator — no new schemas in this feature) (006-corpus-labeling)
- Filesystem only. 20 `source.pdf` + 20 `expected.json` + ≥10 `notes.md` under `tests/stage1_vendor_identity/`. One new Markdown doc at `docs/stage1-vendor-identity/labeling-guide.md`. No database, no network. (006-corpus-labeling)
- Python 3.12 (matches devcontainer base and existing `pyproject.toml`). + `jsonschema>=4.22,<5` (Draft 2020-12, already declared), `pydantic>=2.7,<3` (already declared; typed result models to match the validator style). Python stdlib only for everything else: `argparse`, `json`, `pathlib`, `dataclasses`, `re`, `hashlib`, `datetime`, `uuid`. (007-evaluator)
- Filesystem only. Reads `expected.json` and `final_structured_payload.json` inside per-document folders under `tests/stage1_vendor_identity/inv_XXX_<difficulty>/` (or a user-supplied corpus root). Writes `evaluation_document.json` into the same folder and `evaluation_run_summary.json` + `evaluation_run_summary.md` at the corpus root. (007-evaluator)
- Python 3.12 (matches devcontainer; matches 001/002/003 slices); reuses `ledgerlinc_ocr.validator` for dual-schema validation; no new third-party dependency. (008-routing)
- Filesystem only. Reads `<per-document-folder>/edge_extraction_output.json`, writes `routing_decision.json` atomically into the same folder. No network, no model calls. (008-routing)
- Python 3.12 (matches devcontainer base image and existing `ledgerlinc-ocr` package) + `jsonschema >= 4.22` (already installed; used for schema validation via the existing `ledgerlinc_ocr.validator.artifact` loader), `pydantic >= 2.7` (already installed; used for typed internal result objects), Python stdlib (`argparse`, `json`, `pathlib`, `datetime`, `dataclasses`). No new runtime dependencies. (009-final-payload)
- Filesystem only. Reads `<per-doc-folder>/edge_extraction_output.json` and `<per-doc-folder>/routing_decision.json`. Writes `<per-doc-folder>/final_structured_payload.json`. Trace block references `source.pdf` and `preprocess_output.json` by relative path but does not read them. (009-final-payload)
- Python 3.12 (devcontainer base image, matches 001/002/003/004/005/006/007) (010-pp-structurev3-preprocessing)
- Filesystem only. Reads `tests/stage1_vendor_identity/inv_XXX_<difficulty>/source.pdf`, writes `preprocess_output.json` (and optional debug `page_*.png`) into the same folder. No DB, no network at steady state; first-run warm-up downloads ~500 MB of weights from `paddlepaddle.bj.bcebos.com` / `paddlex` hosters. (010-pp-structurev3-preprocessing)
- Python 3.12 (matches `.devcontainer/Dockerfile` base image and existing `ledgerlinc-ocr` package pinned in `pyproject.toml`) + no new third-party dependencies; reuses declared `jsonschema`, `pydantic`, `httpx`, `PyYAML`, and Python stdlib. (011-stage-runtime-profiles)
- Filesystem only. Reads `--documents-file` plus per-document prerequisite artifacts, writes selected canonical artifacts into each per-document folder, and emits one final stdout `kind: "run_summary"` line. No database, no new persisted artifact, no remote cloud calls. (011-stage-runtime-profiles)
- Python 3.12 (matches `.devcontainer/Dockerfile` and existing `pyproject.toml` `requires-python = ">=3.12"`). + existing — `paddleocr>=3.5,<4`, `paddlex[ocr]>=3.5,<4`, `paddlepaddle>=3.0,<4` (CPU baseline; the optional GPU wheel `paddlepaddle-gpu` is an out-of-tree workstation install — see research R-014.7), `pypdfium2>=4.30,<5`, `Pillow>=10.4,<11`, `numpy>=1.26,<3`, `jsonschema>=4.22,<5`, `pydantic>=2.7,<3`. No new pinned dependency added by this feature; the GPU wheel is documented as an additive optional install path per FR-024. (014-paddle-gpu-preprocessing)
- Filesystem only. Reads `tests/stage1_vendor_identity/inv_XXX_<difficulty>/source.pdf`; writes `preprocess_output.json` (and optional debug `page_*.png`) into the same folder. Preflight writes nothing to disk per FR-004. No DB. (014-paddle-gpu-preprocessing)
- Python 3.12 (matches `.devcontainer/Dockerfile` base image and `pyproject.toml requires-python = ">=3.12"`). + existing only — `paddleocr>=3.5,<4`, `paddlepaddle-dcu` (workstation-only optional install, already proven in feature 014), `pypdfium2>=4.30,<5`, `Pillow>=10.4,<11`, `numpy>=1.26,<3`, `jsonschema>=4.22,<5`, `pydantic>=2.7,<3`, `httpx>=0.27,<1`. No new pinned dependency. (015-gpu-engine-reuse-timing)
- filesystem only. Reads `tests/stage1_vendor_identity/inv_XXX_<difficulty>/source.pdf`; writes `preprocess_output.json` into the same folder unchanged in shape (FR-010). Phase timings live exclusively in the `kind: "run_summary"` stdout line (FR-014 / Clarification Q1) — no new persisted artifact (FR-014 / SC-002), no preprocess_output.json schema change. (015-gpu-engine-reuse-timing)
- Python 3.12 (matches `.devcontainer/Dockerfile` base image and `pyproject.toml requires-python = ">=3.12"`). + existing only — `paddleocr>=3.5,<4`, `paddlepaddle-dcu` (workstation-only optional install, already proven in features 014–015), `pypdfium2>=4.30,<5`, `Pillow>=10.4,<11`, `numpy>=1.26,<3`, `jsonschema>=4.22,<5`, `pydantic>=2.7,<3`. **No new pinned dependency.** ROCm/MIOpen/COMGR are workstation system dependencies, not Python packages. (016-gpu-warmup-miopen-cache)
- filesystem only. Reads `tests/stage1_vendor_identity/inv_XXX_<difficulty>/source.pdf`. Writes `preprocess_output.json` into the same folder unchanged in shape (FR-018). The warmup pass populates two on-disk OS caches as a side effect — `~/.cache/miopen` and `~/.cache/comgr` — but writes nothing the pipeline owns. Phase timings live exclusively in the existing `kind: "run_summary"` stdout line per feature 015 FR-014; **no new persisted artifact** (FR-019 / SC-002). (016-gpu-warmup-miopen-cache)
- Python 3.12 (matches `.devcontainer/Dockerfile` base image and `pyproject.toml requires-python = ">=3.12"`). + existing only — `paddleocr>=3.5,<4` (the `PPStructureV3` constructor already exposes `use_table_recognition` plus `text_detection_model_name` / `text_recognition_model_name` kwargs that this feature drives via the new presets), `paddlepaddle-dcu` (workstation-only optional install, already proven in features 014–016), `pypdfium2>=4.30,<5`, `Pillow>=10.4,<11`, `numpy>=1.26,<3`, `jsonschema>=4.22,<5`, `pydantic>=2.7,<3`. **No new pinned dependency.** The det/rec model weights for the lighter variants ship inside the existing PaddleOCR weight-download flow — no new wheel / no new download host (R-017.4). (017-ppstructurev3-module-reduction)
- filesystem only. Reads `tests/stage1_vendor_identity/inv_XXX_<difficulty>/source.pdf` (unchanged). Writes `preprocess_output.json` into the same per-document folder unchanged in shape (FR-003 / FR-019). The three new run_summary fields live exclusively in the existing `kind: "run_summary"` stdout line per feature 014/015/016 lineage; **no new persisted artifact** (FR-020 / SC-002 / Out of Scope subsection). The benchmark numbers and FR-001 audit narrative land in this feature's `research.md` Appendix B (audit) and quickstart.md Appendix A (benchmark numbers); both are Markdown documents under `specs/017-ppstructurev3-module-reduction/`, not under `contracts/` and not under `tests/stage1_vendor_identity/`. (017-ppstructurev3-module-reduction)
- Python 3.12 (matches `.devcontainer/Dockerfile` base image and `pyproject.toml requires-python = ">=3.12"`). + existing only — `paddleocr>=3.5,<4`, `paddlepaddle-dcu` (workstation-only optional install, already proven in features 014–017), `pypdfium2>=4.30,<5` (used for the per-page geometry read on skipped pages 2..N — no rasterization required to obtain `width_pt`/`height_pt`/`rotation`, R-018.6), `Pillow>=10.4,<11` (used for the page-1 header-band crop, R-018.5), `numpy>=1.26,<3`, `jsonschema>=4.22,<5`, `pydantic>=2.7,<3`. **No new pinned dependency.** The `header-first-v1` preset uses `pypdfium2` page geometry and a `Pillow` `Image.crop` call after rasterization — both already on the dependency tree. (018-dpi-region-first-preprocess)
- filesystem only. Reads `tests/stage1_vendor_identity/inv_XXX_<difficulty>/source.pdf` (unchanged). Writes `preprocess_output.json` into the same per-document folder unchanged in shape (FR-002 / FR-020). The three new `run_summary` fields live exclusively in the existing `kind: "run_summary"` stdout line per feature 014/015/016/017 lineage; **no new persisted artifact** (FR-021 / Out of Scope). The benchmark numbers and FR-001 audit narrative land in this feature's `quickstart.md` Appendix A (benchmark numbers) and `research.md` Appendix B (quality-gate evidence) at landing time; both are Markdown documents under `specs/018-dpi-region-first-preprocess/`, not under `contracts/` and not under `tests/stage1_vendor_identity/`. (018-dpi-region-first-preprocess)

## Recent Changes
- 005-single-voter-extraction: Stage 1 single-voter edge extractor landed under `src/ledgerlinc_ocr/extract/`. CLI: `ledgerlinc-extract`. Host-Ollama HTTP (httpx, no retries) + pluggable `VoterAdapter` Protocol + deterministic 8-step reconciliation → schema-valid `edge_extraction_output.json`. See `specs/005-single-voter-extraction/quickstart.md`.
- 001-freeze-schemas-folder-contracts: Added Python 3.12 (matches `.devcontainer/Dockerfile` base image) + `jsonschema >= 4.22` (Draft 2020-12 validator); `pydantic >= 2.7` for the structured-report model and typed CLI results; Python stdlib (`argparse`, `json`, `pathlib`, `dataclasses`). No PyTorch, no PaddleOCR, no network dependencies for this slice.
