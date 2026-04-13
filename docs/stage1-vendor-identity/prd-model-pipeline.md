# PRD: Stage 1 Model Pipeline

## Purpose

This PRD defines the product requirements for the stage 1 LedgerLinc OCR model pipeline.

This document is specifically about the pipeline that ingests PDF invoices, performs preprocessing and extraction, and emits structured vendor identity results. It is not the PRD for the evaluation harness around that pipeline.

## Product Boundary

This PRD covers:

- PDF ingestion
- Trijunction preprocessing
- OCR, layout, and perception evidence extraction
- multi-voter edge-model extraction
- deterministic consensus logic
- deterministic routing decision
- final structured payload generation

This PRD does not cover:

- test corpus management
- dataset scoring
- benchmark reporting
- experiment orchestration across many documents

Those are covered in `prd-test-harness.md`.

## Problem Statement

LedgerLinc needs a reliable first-stage edge pipeline that can process real-world invoice PDFs and produce a structured vendor identity payload suitable for downstream accounting, CRM verification, and later investigator workflows.

The current repository only contains a prototype script. It does not yet support the required PDF-first, schema-driven, review-aware stage 1 workflow.

## Stage 1 Goal

Build a working edge-side vendor identity pipeline that:

- accepts PDF invoices
- builds a structured evidence packet from ingestion
- extracts vendor identity fields
- distinguishes explicit from inferred company names
- supports multiple model votes in the target architecture
- determines whether the result can be accepted or requires manual review
- emits stable JSON artifacts aligned to the documented contracts

## Users and Stakeholders

Primary users:

- internal developers building the pipeline
- internal operators reviewing stage 1 outputs
- downstream systems consuming structured vendor identity output

Stakeholders:

- LedgerLinc OCR/model pipeline engineering
- accounting and CRM workflow owners
- future investigator-agent workflow owners

## Stage 1 Scope

Included:

- PDF input only
- one-document processing flow
- Trijunction-oriented preprocessing and evidence assembly
- edge-model extraction using host Ollama
- vendor identity extraction
- decomposed postal address extraction
- typed tax ID extraction
- website, phone, and email extraction
- consensus-ready extraction architecture
- deterministic review routing
- final structured payload output

Explicitly out of scope:

- cloud path implementation
- actual cloud fallback execution
- line item extraction
- latency or throughput optimization
- production deployment topology
- UI implementation for review workflows
- investigator-agent enrichment

## Product Requirements

### Functional Requirements

1. The pipeline must accept a PDF invoice as input.
2. The pipeline must rasterize the PDF into page images suitable for OCR.
3. The pipeline must produce a `preprocess_output` artifact containing page-level OCR and layout information.
4. The preprocessing layer must be structured so it can incorporate:
   - `PaddleOCR-VL-1.5`
   - `Falcon OCR`
   - `Falcon Perception`
5. The pipeline must call edge models through host Ollama over HTTP.
6. The model extraction stage must produce `edge_extraction_output` aligned to the documented schema.
7. The implementation must be organized so multiple voters can be executed against the same evidence packet.
8. The pipeline must support a consensus layer that can eventually evaluate:
   - unanimous agreement
   - 2-of-3 majority agreement
   - split decisions
9. The pipeline must extract vendor identity fields at minimum:
   - company name
   - decomposed address
   - typed tax IDs
   - website
   - phone
   - email
10. The pipeline must preserve whether the company name was explicitly present or inferred.
11. The pipeline must allow a best-guess company name when no explicit company name is present.
12. The pipeline must create a deterministic `routing_decision` artifact.
13. The pipeline must create a `final_structured_payload` artifact for downstream use.
14. The pipeline must store missing fields as `null`, not empty strings.
15. The pipeline must support processing one document end to end from source PDF to final payload.

### Review and Decision Requirements

1. If the company name is explicitly found and vendor identity is sufficiently strong, the pipeline may emit `edge_accept`.
2. If the company name is inferred rather than explicitly found, the pipeline must emit `edge_review_required`.
3. If the explicit company name is missing, the pipeline must set:
   - `company_name.present = false`
   - `company_name.inferred = true`
   - `review_status.manual_review_required = true`
4. The pipeline must include a minimal review status only:
   - whether review is required
   - why review is required

### Contract Requirements

The pipeline must emit these artifacts with stable schemas:

- `preprocess_output.json`
- `edge_extraction_output.json`
- `routing_decision.json`
- `final_structured_payload.json`

The implementation should also remain compatible with later addition of:

- per-voter raw outputs
- richer consensus metadata

The schema definitions in `schemas.md` are the current stage 1 contract baseline.

## Non-Functional Requirements

1. The stage 1 code should start as a Python module and CLI, not a service.
2. The implementation should remain compatible with the lightweight devcontainer setup in this repo.
3. The pipeline should not require PyTorch unless a chosen implementation component truly depends on it.
4. The pipeline should use host Ollama rather than embedding model runtime into the pipeline container for stage 1.
5. The code should be structured so a later API wrapper can be added without rewriting core logic.
6. The code should be structured so additional model voters can be added without rewriting preprocessing or routing.

## Dependencies

Required stage 1 dependencies include:

- a PDF rasterization path
- OCR/layout tooling
- a Trijunction-ready evidence packet structure
- host Ollama available at the configured base URL
- schema validation models

Operational dependency:

- the host Ollama ROCm path described in `../ollama-rocm-wsl-gfx1151-fix.md`

## Dependency Map

### Hard Dependencies

These items block downstream work and must be respected in order:

1. schema baseline
   - `preprocess_output`
   - `edge_extraction_output`
   - `routing_decision`
   - `final_structured_payload`
2. PDF rasterization path
   - required before real OCR or preprocessing
3. deterministic preprocessing and evidence packet assembly
   - required before any voter can run consistently
4. model adapter interface
   - required before single-voter extraction or future ensemble work
5. normalized extraction output
   - required before deterministic routing or consensus comparison
6. routing decision logic
   - required before final payload assembly
7. final payload contract
   - required before the harness can score real outputs

### Orthogonal Or Low-Coupled Work

These can proceed without blocking the core first slice once the contracts are stable:

- native Linux ROCm production deployment assets
- local CPU versus GPU benchmark wiring
- prompt iteration for additional voters
- future service wrapper design
- later cloud-path planning

## Recommended Delivery Order

The recommended implementation order for the model pipeline is:

1. freeze the schema models and output path conventions
2. build the CLI skeleton for one-document processing
3. implement PDF rasterization and deterministic preprocessing
4. assemble the evidence packet
5. implement a single-voter model adapter over host Ollama
6. produce `edge_extraction_output`
7. implement deterministic routing
8. assemble `final_structured_payload`
9. add multi-voter normalization and consensus logic
10. add production-facing runtime wrappers and deployment assets

This order is intentional:

- stages 1 through 4 are foundational and should not be skipped
- stage 5 proves the model boundary without waiting for the full ensemble
- stage 9 should be layered on top of a working single-voter flow, not built first

## Parallelizable Work

After the schema and CLI contract are stable, the following work can happen in parallel:

### Workstream A: Pipeline Foundation

- schema models
- CLI entry point
- PDF rasterization
- preprocessing
- evidence packet assembly

This is the critical path.

### Workstream B: Model And Prompt Preparation

- use `Gemma 4 E4B` as the stage 1 Gemma edge voter
- choose the initial Qwen stage 1 variant
- define per-voter prompt strategy
- define normalized extraction shape for future consensus

This work can start once the evidence packet structure is stable.

### Workstream C: Runtime And Benchmark Support

- validate host Ollama connectivity
- validate optional CPU-only container path
- capture benchmark commands and runtime notes

This can proceed in parallel with pipeline coding once the model adapter contract exists.

### Workstream D: Production ROCm Containerization

- maintain native Linux ROCm compose assets
- document deployment assumptions for cloud GPU hosts

This is orthogonal to the local stage 1 feature path and must not block the first end-to-end build.

## Success Criteria

Stage 1 pipeline success means:

1. A single PDF can be processed end to end through all four artifacts.
2. The output aligns with the documented schemas.
3. Missing-name cases are represented correctly as inferred and review-required.
4. The pipeline structure is ready for multiple voters and consensus logic.
5. The pipeline is stable enough to be exercised by the test harness across the 20-document corpus.

## Acceptance Criteria

The model pipeline is acceptable for stage 1 when:

1. A CLI command can process one PDF into:
   - `preprocess_output.json`
   - `edge_extraction_output.json`
   - `routing_decision.json`
   - `final_structured_payload.json`
2. The emitted JSON passes schema validation.
3. The routing decision is deterministic and not delegated to the model.
4. Inferred-name behavior follows the documented rules.
5. The pipeline is callable from the external test harness without requiring code changes.

## Assumptions

The following assumptions are currently baked into this draft:

- stage 1 uses host Ollama over HTTP
- stage 1 is PDF-only
- stage 1 focuses on vendor identity, not line items
- stage 1 uses a minimal review policy
- cloud escalation remains a future path, not a delivered feature in this stage
- the long-term architecture uses a three-model ensemble with Phi-4 Mini as the third vote

## Risks

1. OCR quality on difficult PDFs may dominate extraction quality more than the model itself.
2. Model prompts may drift from schema requirements without strict validation.
3. Inferred company names may appear plausible but still be wrong without explicit provenance tracking.
4. The chosen PDF rasterization approach may affect OCR performance materially.
5. Ensemble disagreement handling may become complex if voter outputs are not normalized consistently.

## Open Questions

1. In stage 1, do we execute the full three-voter ensemble immediately, or ship a single-voter baseline with ensemble-ready interfaces?
2. Which exact local Qwen variant is the intended stage 1 runtime choice alongside `Gemma 4 E4B`?
3. Which PDF rasterization library should be standardized for the stage 1 implementation?
4. Should invoice header fields remain emitted in stage 1 even though the evaluation focus is vendor identity?
