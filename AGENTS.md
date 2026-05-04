# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

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

Optional local Ollama container (CPU-only on WSL; see caveat below):
```bash
docker compose -f .devcontainer/docker-compose.yml --profile ollama up -d
```

Production-style native Linux ROCm Ollama:
```bash
docker compose -f docker/compose.ollama-rocm-linux.yml up -d
```

There is no test suite, linter, or build system configured yet.

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

Run OpenSpec from the bench/workbench container (`py-bench`), where `openspec` is on `PATH`. Do not add OpenSpec to the lightweight LedgerLinc project container; that container remains focused on the pipeline runtime and local validation path.

Skip OpenSpec for small implementation-only fixes where an existing `specs/NNN-*` artifact already defines the behavior and no product or architecture decision is being made.

## Architecture

### Target architecture (long-term)

Three layers, documented in `docs/stage1-vendor-identity/architecture.md`:

1. **Trijunction ingestion** — `PaddleOCR-VL-1.5` (layout/tables/reading order) + `Falcon OCR 0.3B` (text + spam gate) + `Falcon Perception 0.6B` (logos, stamps, spatial grounding). Output is a shared **evidence packet**, not raw OCR text.
2. **Triple-model ensemble extraction** — three independent voters over the same evidence packet: Model A (Qwen3-VL cloud / Qwen3 edge), Model B (Gemma 4 cloud / Gemma 4 E4B edge), Model C (Phi-4 Mini as the logic/verifier vote).
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
- On this workstation only host Ollama is GPU-capable. The optional `ollama` Docker service on WSL is CPU-only — HIP cannot see the AMD GPU inside Docker Desktop. Treat the native Linux ROCm compose file as the production path, not the WSL container. Details: `docs/stage1-vendor-identity/ollama-runtime.md` and `docs/ollama-rocm-wsl-gfx1151-fix.md`.

### Non-negotiable rules

- **Schema-first, evidence-first.** Prompts and code adapt to the JSON contracts in `schemas.md`, not the reverse. Use `null` for missing fields, never empty strings.
- **Deterministic control.** Spam gates, consensus comparison, explicit-vs-inferred handling, and `manual_review_required` decisions must be code, not model output. Confidence is a signal, not provenance.
- **Company-name provenance.** If no explicit company name is found, a best guess may be stored in `company_name.value`, but `company_name.present` must be `false`, `company_name.inferred` must be `true`, and `manual_review_required` must be `true`. This is mandatory and is enforced by the missing-name subset of the test corpus.

### Current state vs. target

`step2_ocr_ensemble.py` is a prototype only: it runs PaddleOCR + PPStructure on images, stubs the PDF path, and emits an ad-hoc JSON that does **not** match the stage 1 schema. Treat it as scaffolding to be replaced, not as a reference for correct behavior — authoritative behavior lives in `docs/stage1-vendor-identity/`.

## Key References

- `docs/stage1-vendor-identity/architecture.md` — target + stage 1 processing flow
- `docs/stage1-vendor-identity/prd-model-pipeline.md` — what the pipeline must do
- `docs/stage1-vendor-identity/prd-test-harness.md` — what the harness must do (separate concern)
- `docs/stage1-vendor-identity/schemas.md` — authoritative JSON contracts for all four artifacts + `expected.json` + evaluation outputs
- `docs/stage1-vendor-identity/scoring.md` — evaluation rubric and pass criteria
- `docs/stage1-vendor-identity/dataset-layout.md` — per-document folder structure and `challenge_tags`
- `docs/stage1-vendor-identity/ollama-runtime.md` — host vs. container Ollama, WSL caveats
- `.specify/memory/constitution.md` — governing principles; violations are design issues, not style issues
- `openspec/README.md` — OpenSpec/Speckit split and handoff policy

## Active Technologies
- Python 3.12 (matches `.devcontainer/Dockerfile` base image) + `jsonschema >= 4.22` (Draft 2020-12 validator); `pydantic >= 2.7` for the structured-report model and typed CLI results; Python stdlib (`argparse`, `json`, `pathlib`, `dataclasses`). No PyTorch, no PaddleOCR, no network dependencies for this slice. (001-freeze-schemas-folder-contracts)
- Filesystem only. JSON artifacts on disk. No database. No model weights. No network calls. (001-freeze-schemas-folder-contracts)

## Recent Changes
- 001-freeze-schemas-folder-contracts: Added Python 3.12 (matches `.devcontainer/Dockerfile` base image) + `jsonschema >= 4.22` (Draft 2020-12 validator); `pydantic >= 2.7` for the structured-report model and typed CLI results; Python stdlib (`argparse`, `json`, `pathlib`, `dataclasses`). No PyTorch, no PaddleOCR, no network dependencies for this slice.
