# Stage 1 Vendor Identity

This folder stores the planning documents for stage 1 of the Dartwing OCR pipeline test effort.

Stage 1 is intentionally narrow:

- input type is PDF only
- focus is vendor identification, not line items
- local validation stacks only: full-workstation, cloud-workstation, and edge-fast
- no remote cloud escalation implementation yet
- no latency targets yet
- evaluation is against a curated 20-document real-world test set

## Documents

- `prd-model-pipeline.md`
  - product requirements for the stage 1 OCR/model pipeline itself
- `prd-test-harness.md`
  - product requirements for the stage 1 evaluation and orchestration harness
- `prd-stage-runtime-profiles.md`
  - product requirements for amending the top-level pipeline CLI so the same entrypoint can run real or stubbed stage profiles and stage slices; also records the shared profile direction for `ppstructurev3@cpu` full-workstation preprocessing, `cloud-workstation` local GPU validation, and future `edge-ocr@jetson` edge preprocessing
- `prd-ppstructurev3-migration.md`
  - product requirements for the full-structure preprocessing profile migration from PaddleOCR 2.10 to PPStructureV3 / PP-OCRv5
- `prd-paddle-gpu-preprocessing.md`
  - product requirements for feature 014: validating whether PPStructureV3 can run on the workstation GPU and, if viable, adding an explicit opt-in `ppstructurev3@gpu` preprocessing profile without replacing the CPU default
- `prd-gpu-mvp-promotion.md`
  - product requirements for the post-feature-020 promotion checkpoint that closes deferred GPU verification, records benchmark and quality-gate evidence, and updates the MVP demo path to require GPU profiles without removing CPU/stub CI safety
- `gpu-warmup-and-cache.md`
  - operator guide for feature 016: GPU warmup activation, MIOpen/COMGR cache locations and clearing, cold-vs-warm timing interpretation, and workspace-warning guidance
- `amd-ryzen-ai-max-395-rocm-setup.md`
  - workstation bring-up runbook for installing ROCm on Ryzen AI Max+ 395 / Radeon 8060S class machines and validating the Paddle + Ollama GPU path
- `ollama-runtime.md`
  - how host Ollama and optional containerized Ollama fit into the stage 1 architecture
- `../../docker/compose.ollama-rocm-linux.yml`
  - native Linux ROCm compose file for production-style Ollama deployment
- `architecture.md`
  - stage 1 scope, runtime boundaries, and processing flow
- `schemas.md`
  - first draft JSON contracts for all stage 1 artifacts
- `dataset-layout.md`
  - test corpus structure and labeling rules
- `labeling-guide.md`
  - authoritative conventions for `expected.json` and `notes.md`, plus the PII/license screening checklist applied before any document enters the corpus
- `scoring.md`
  - evaluation rubric, weighting, and pass criteria

## Related Docs

- `../ollama-rocm-wsl-gfx1151-fix.md`
  - records the local Ollama ROCm fix used to get AMD GPU inference working in WSL Ubuntu 24.04
