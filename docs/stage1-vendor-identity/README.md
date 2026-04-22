# Stage 1 Vendor Identity

This folder stores the planning documents for stage 1 of the LedgerLinc OCR pipeline test effort.

Stage 1 is intentionally narrow:

- input type is PDF only
- focus is vendor identification, not line items
- edge path only
- no cloud escalation implementation yet
- no latency targets yet
- evaluation is against a curated 20-document real-world test set

## Documents

- `prd-model-pipeline.md`
  - product requirements for the stage 1 OCR/model pipeline itself
- `prd-test-harness.md`
  - product requirements for the stage 1 evaluation and orchestration harness
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
