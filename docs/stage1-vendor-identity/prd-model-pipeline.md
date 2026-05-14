# PRD: Stage 1 Model Pipeline

## Purpose

This PRD defines the product requirements for the stage 1 Dartwing OCR model pipeline.

This document is specifically about the pipeline that ingests PDF invoices, performs preprocessing and extraction, and emits structured vendor identity results. It is not the PRD for the evaluation harness around that pipeline.

## Product Boundary

This PRD covers:

- PDF ingestion
- Trijunction preprocessing
- preprocessing runtime profiles, including full-structure and lightweight edge-OCR paths
- OCR, layout, and perception evidence extraction
- multi-voter local-model extraction
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

Dartwing needs a reliable first-stage edge pipeline that can process real-world invoice PDFs and produce a structured vendor identity payload suitable for downstream accounting, CRM verification, and later investigator workflows.

The current repository only contains a prototype script. It does not yet support the required PDF-first, schema-driven, review-aware stage 1 workflow.

## Stage 1 Goal

Build a working edge-side vendor identity pipeline that:

- accepts PDF invoices
- builds a structured evidence packet from ingestion using the selected preprocessing profile
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

- Dartwing OCR/model pipeline engineering
- accounting and CRM workflow owners
- future investigator-agent workflow owners

## Stage 1 Scope

Included:

- PDF input only
- one-document processing flow
- Trijunction-oriented preprocessing and evidence assembly
- two preprocessing runtime shapes in one repo:
  - full-structure evidence generation
  - lightweight Jetson Nano Super edge-OCR scanning
- model extraction through the selected local runtime lane
- vendor identity extraction
- decomposed postal address extraction
- typed tax ID extraction
- website, phone, and email extraction
- consensus-ready extraction architecture
- cloud-class workstation validation before remote cloud deployment
- deterministic review routing
- final structured payload output

Explicitly out of scope:

- remote cloud provider path implementation
- actual provider-managed cloud fallback execution
- line item extraction
- latency or throughput optimization
- production deployment topology
- separate repository ownership for the lightweight edge-OCR scanner
- multiple canonical preprocessing artifacts in the same per-document folder
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
5. The preprocessing layer must support named runtime profiles so the same repository can run:
   - a full document-structure profile for layout, table, reading-order, and corpus-baseline work
   - a lightweight edge-OCR profile for fast first-pass scanning on the Jetson Nano Super GPU lane
6. The selected preprocessing profile must be encoded in `pipeline_version` or equivalent profile metadata visible to downstream consumers.
7. A lightweight edge-OCR profile must not fabricate layout blocks or table structure; absent profile-dependent evidence must remain explicit, typed, and schema-valid.
8. The edge-fast OCR and model inference path must run on the Jetson GPU lane; CPU-only heavy OCR or CPU-only model inference is not an acceptable fallback for that stack.
9. The pipeline must call models through the selected local HTTP model endpoint, depending on the selected runtime profile.
10. The model extraction stage must produce `edge_extraction_output` aligned to the documented schema.
11. The implementation must be organized so multiple voters can be executed against the same evidence packet.
12. The pipeline must support a consensus layer that can eventually evaluate:
   - unanimous agreement
   - 2-of-3 majority agreement
   - split decisions
13. The pipeline must extract vendor identity fields at minimum:
   - company name
   - decomposed address
   - typed tax IDs
   - website
   - phone
   - email
14. The pipeline must preserve whether the company name was explicitly present or inferred.
15. The pipeline must allow a best-guess company name when no explicit company name is present.
16. Gemma 4 E2B in the edge-fast stack must act as an evidence judge/extractor: read OCR evidence, propose normalized vendor-identity fields, cite evidence ids, and return confidence signals.
17. Gemma 4 E2B must not perform OCR/layout work, own schema validation, override explicit-vs-inferred company-name provenance, or make the final routing decision.
18. The cloud-workstation stack must run cloud-class voters on local workstation GPU endpoints so cloud-model behavior can be evaluated before a remote cloud provider path exists.
19. The cloud-workstation stack must not require provider credentials, external cloud APIs, or a deployed cloud fallback service.
20. The pipeline must create a deterministic `routing_decision` artifact.
21. The pipeline must create a `final_structured_payload` artifact for downstream use.
22. The pipeline must store missing fields as `null`, not empty strings.
23. The pipeline must support processing one document end to end from source PDF to final payload.
24. Corpus or worker execution must be able to initialize a selected live preprocessing profile once and process multiple document folders without re-importing and reconstructing the same model stack per document.

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

### Runtime Stack Presets

The pipeline should support named stack presets as convenience wrappers around
explicit stage profiles:

- `full-workstation`
  - full-structure preprocessing
  - Gemma 4 E4B extraction on the workstation GPU lane
  - deterministic routing and final payload assembly
- `cloud-workstation`
  - target: workstation with local GPU cards
  - full-structure preprocessing first, with Trijunction-local contributors
    added as those components become available
  - cloud-class voter set on local workstation model endpoints
  - deterministic consensus, routing, and final payload assembly
- `edge-fast`
  - target: Jetson Nano Super class hardware
  - lightweight edge-OCR preprocessing on the Jetson GPU lane
  - Gemma 4 E2B extraction on the Jetson-local edge lane
  - deterministic routing and final payload assembly

All stacks emit the same four artifact filenames for a selected run. The
selected stack and model runtime must be visible in artifact metadata so
evaluation reports can separate `cloud-workstation` and `edge-fast` results
from `full-workstation` results.

`cloud-workstation` is the test path for the future cloud solution. It is local
workstation execution of cloud-class models, not a remote provider integration.
It must not require cloud credentials or call external provider APIs in this
stage.

The edge-fast stack uses small Paddle OCR first. A larger Paddle fallback is
allowed only when it also runs on the Jetson GPU lane and the fallback is
recorded in runtime metadata; otherwise the document must be reviewed or moved
to the full-workstation stack rather than running heavy OCR on CPU.

## Non-Functional Requirements

1. The stage 1 code should start as a Python module and CLI, not a service.
2. The implementation should remain compatible with the lightweight devcontainer setup in this repo.
3. The pipeline should not require PyTorch unless a chosen implementation component truly depends on it.
4. The full-workstation path should use host Ollama rather than embedding model runtime into the pipeline container for stage 1; cloud-workstation may use local workstation model endpoints, but not remote provider APIs.
5. The code should be structured so a later API wrapper can be added without rewriting core logic.
6. The code should be structured so additional model voters can be added without rewriting preprocessing or routing.
7. The code should be structured so additional preprocessing profiles can be added without rewriting artifact assembly, validation, extraction, or routing.
8. The single-document CLI remains a supported debugging shape, but production-style and corpus execution should use warm profile instances rather than launching one process per document.

## Dependencies

Required stage 1 dependencies include:

- a PDF rasterization path
- OCR/layout tooling
- profile-selectable preprocessing engines
- a Trijunction-ready evidence packet structure
- selected local model endpoint available at the configured base URL
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
3. deterministic preprocessing profile contract
   - required so full-structure and edge-OCR outputs are distinguishable but still safe for downstream consumers
4. deterministic preprocessing and evidence packet assembly
   - required before any voter can run consistently
5. model adapter interface
   - required before single-voter extraction or future ensemble work
6. normalized extraction output
   - required before deterministic routing or consensus comparison
7. routing decision logic
   - required before final payload assembly
8. final payload contract
   - required before the harness can score real outputs

### Orthogonal Or Low-Coupled Work

These can proceed without blocking the core first slice once the contracts are stable:

- native Linux ROCm production deployment assets
- local CPU versus GPU benchmark wiring
- cloud-workstation voter-set validation on local GPU hardware
- edge-OCR Jetson profile implementation once the full-structure profile contract is stable
- prompt iteration for additional voters
- future service wrapper design
- later remote cloud-path planning

## Recommended Delivery Order

The recommended implementation order for the model pipeline is:

1. freeze the schema models and output path conventions
2. build the CLI skeleton for one-document processing
3. implement PDF rasterization and deterministic preprocessing
4. implement the full-structure preprocessing profile and regenerate baselines
5. add preprocessing profile selection and warm corpus/worker execution
6. add the lightweight edge-OCR preprocessing profile
7. assemble the evidence packet
8. implement a single-voter model adapter over host Ollama
9. produce `edge_extraction_output`
10. implement deterministic routing
11. assemble `final_structured_payload`
12. add `cloud-workstation` voter-set validation on local workstation GPUs
13. add multi-voter normalization and consensus logic
14. add production-facing runtime wrappers and deployment assets

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
- preprocessing profile abstraction
- warm corpus/worker execution for live preprocessing profiles
- evidence packet assembly

This is the critical path.

### Workstream B: Model And Prompt Preparation

- use `Gemma 4 E4B` as the stage 1 full-workstation Gemma voter
- use `Gemma 4 E2B` as the smaller Jetson edge-fast extractor profile once the
  lightweight preprocessing profile exists
- define the `cloud-workstation` voter set for local workstation GPU testing of
  the future cloud solution
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
6. The preprocessing layer can run the full-structure and edge-OCR profiles from the same repository and distinguish their outputs through profile metadata.
7. Corpus preprocessing can run without reconstructing the selected live preprocessing stack once per document.

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
6. A developer can choose between the full-structure and edge-OCR preprocessing profiles without changing artifact consumers or repository boundaries.

## Assumptions

The following assumptions are currently baked into this draft:

- stage 1 uses local model endpoints over HTTP: host Ollama for full-workstation, workstation GPU endpoints for cloud-workstation, and Jetson-local Ollama for edge-fast
- stage 1 is PDF-only
- full-structure preprocessing remains the default profile until the edge-OCR profile has evaluator evidence
- stage 1 focuses on vendor identity, not line items
- stage 1 uses a minimal review policy
- remote cloud escalation remains a future path, not a delivered feature in this stage
- the long-term architecture uses a three-model ensemble with Phi-4 Mini as the third vote

## Risks

1. OCR quality on difficult PDFs may dominate extraction quality more than the model itself.
2. Model prompts may drift from schema requirements without strict validation.
3. Inferred company names may appear plausible but still be wrong without explicit provenance tracking.
4. The chosen PDF rasterization approach may affect OCR performance materially.
5. A lightweight edge-OCR profile may omit evidence that downstream extraction previously assumed came from full-structure preprocessing.
6. Process-per-document execution may hide production performance characteristics by repeatedly rebuilding model stacks.
7. Ensemble disagreement handling may become complex if voter outputs are not normalized consistently.

## Open Questions

1. In stage 1, do we execute the full three-voter ensemble immediately, or ship a single-voter baseline with ensemble-ready interfaces?
2. Which exact local Qwen variant is the intended stage 1 runtime choice alongside `Gemma 4 E4B` on the full-workstation stack?
3. Which PDF rasterization library should be standardized for the stage 1 implementation?
4. Should invoice header fields remain emitted in stage 1 even though the evaluation focus is vendor identity?
5. Which lightweight Paddle OCR engine/package should back the first `edge-ocr@jetson` preprocessing profile?
6. Does the edge-OCR profile emit the same `preprocess_output.json` schema with empty layout/table evidence, or does it require a contract amendment for profile-dependent fields?
