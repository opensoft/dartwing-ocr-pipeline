# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

Step 2 of the LedgerLinc AP Clerk Agent: an OCR + field-extraction + structuring pipeline for invoice PDFs. The repo currently holds one prototype script (`step2_ocr_ensemble.py`) plus the full design docs, schemas, and PRDs for the real stage 1 implementation that has not been written yet. Most non-trivial work starts by reading `docs/stage1-vendor-identity/` and `.specify/memory/constitution.md`, then translating those contracts into code.

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

Speckit worktree helper:
```bash
source /home/brett/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline/.specify/shell/ct.zsh
```
- After `/speckit.specify`, run `/ct` for the jump target or `/ctp` for full worktree details
- Run `ct` to actually change the shell into that worktree

## Architecture

### Target architecture (long-term)

Three layers, documented in `docs/stage1-vendor-identity/architecture.md`:

1. **Trijunction ingestion** — `PaddleOCR-VL-1.5` (layout/tables/reading order) + `Falcon OCR 0.3B` (text + spam gate) + `Falcon Perception 0.6B` (logos, stamps, spatial grounding). Output is a shared **evidence packet**, not raw OCR text.
2. **Triple-model ensemble extraction** — three independent voters over the same evidence packet: Model A (Qwen3-VL cloud / Qwen3 edge), Model B (Gemma 4 cloud / Gemma 3 edge), Model C (Phi-4 Mini as the logic/verifier vote).
3. **Deterministic consensus + routing** — field-level vote comparison: unanimous ⇒ high confidence, 2-of-3 majority ⇒ accept with downstream recheck, split ⇒ escalate/review. Consensus and routing are **never** delegated to a model.

### Stage 1 slice (what gets built first)

Stage 1 is intentionally narrow — **PDF input only**, **vendor identity only**, **edge path only**, no line items, no cloud escalation, no latency gate. A single-voter baseline is acceptable as long as the code shape is ensemble-ready (shared evidence packet, pluggable voters, deterministic routing).

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
- **Host Ollama over HTTP** owns model inference for stage 1. Do not embed model runtime into the pipeline container.
- On this workstation only host Ollama is GPU-capable. The optional `ollama` Docker service on WSL is CPU-only — HIP cannot see the AMD GPU inside Docker Desktop. Treat the native Linux ROCm compose file as the production path, not the WSL container. Details: `docs/stage1-vendor-identity/ollama-runtime.md` and `docs/ollama-rocm-wsl-gfx1151-fix.md`.

### Non-negotiable rules

- **Schema-first, evidence-first.** Prompts and code adapt to the JSON contracts in `schemas.md`, not the reverse. Use `null` for missing fields, never empty strings.
- **Deterministic control.** Spam gates, consensus comparison, explicit-vs-inferred handling, and `manual_review_required` decisions must be code, not model output. Confidence is a signal, not provenance.
- **Company-name provenance.** If no explicit company name is found, a best guess may be stored in `company_name.value`, but `company_name.present` must be `false`, `company_name.inferred` must be `true`, and `manual_review_required` must be `true`. This is mandatory and is enforced by the missing-name subset of the test corpus.

### Current state vs. target

`step2_ocr_ensemble.py` is a prototype only: it runs PaddleOCR + PPStructure on images, stubs the PDF path, and emits an ad-hoc JSON that does **not** match the stage 1 schema. Treat it as scaffolding to be replaced, not as a reference for correct behavior — authoritative behavior lives in `docs/stage1-vendor-identity/`.

## Stage 1 contracts are machine-validated

The seven stage 1 artifact shapes and the per-document folder contract are now enforced in code, not only documented. Frozen at `contract_set_version = "1.0.0"`.

- **Machine-readable contracts**: `contracts/stage1_vendor_identity/v1.0.0/` — one JSON Schema per artifact plus the folder contract and `contract_set.json` metadata. Updated only through `contracts/stage1_vendor_identity/AMENDMENTS.md`.
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
- `.specify/memory/constitution.md` — governing principles; violations are design issues, not style issues

## Active Technologies
- Python 3.12 (matches `.devcontainer/Dockerfile` base image) + `jsonschema >= 4.22` (Draft 2020-12 validator); `pydantic >= 2.7` for the structured-report model and typed CLI results; Python stdlib (`argparse`, `json`, `pathlib`, `dataclasses`). No PyTorch, no PaddleOCR, no network dependencies for this slice. (001-freeze-schemas-folder-contracts)
- Filesystem only. JSON artifacts on disk. No database. No model weights. No network calls. (001-freeze-schemas-folder-contracts)
- Python 3.12 (matches devcontainer and existing package) + `jsonschema >=4.22` (already installed), `pydantic >=2.7` (already installed), `python-magic` or stdlib `struct` for PDF magic detection (see research.md) (002-cli-contract)
- Filesystem only — JSON artifacts on disk, no database (002-cli-contract)
- Python 3.12 (devcontainer base image) (003-pdf-preprocessing)
- Filesystem only. Reads `tests/stage1_vendor_identity/inv_XXX_<difficulty>/source.pdf`, writes `preprocess_output.json` (and optional debug `page_*.png`) into the same folder. No DB, no network. (003-pdf-preprocessing)
- Python 3.12 (devcontainer base image, matches 001/002/003). (004-evidence-packet-assembly)
- Filesystem only. Reads one `preprocess_output.json` per invocation from `tests/stage1_vendor_identity/inv_XXX_<difficulty>/`. At default logger level, writes nothing. At `DEBUG` (or lower), writes exactly one `evidence_packet.json` into the same folder. No DB. No network. No model weights. (004-evidence-packet-assembly)
- Python 3.12 (devcontainer base image, already established) + `pypdf >= 5.0, < 7` (already installed; used for PDF structural-integrity check in the validator); `jsonschema >= 4.22`, `pydantic >= 2.7` (already installed; used by existing validator — no new schemas in this feature) (006-corpus-labeling)
- Filesystem only. 20 `source.pdf` + 20 `expected.json` + ≥10 `notes.md` under `tests/stage1_vendor_identity/`. One new Markdown doc at `docs/stage1-vendor-identity/labeling-guide.md`. No database, no network. (006-corpus-labeling)

## Recent Changes
- 001-freeze-schemas-folder-contracts: Added Python 3.12 (matches `.devcontainer/Dockerfile` base image) + `jsonschema >= 4.22` (Draft 2020-12 validator); `pydantic >= 2.7` for the structured-report model and typed CLI results; Python stdlib (`argparse`, `json`, `pathlib`, `dataclasses`). No PyTorch, no PaddleOCR, no network dependencies for this slice.
