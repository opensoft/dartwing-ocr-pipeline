# Stage 1 Implementation Plan

## Purpose

This document records the first implementation slice for stage 1 so coding can begin without relying on thread-only context.

The target architecture now assumes:

- a Trijunction ingestion layer
- a three-model voting ensemble
- a deterministic consensus gate

Stage 1 implementation should be built so those capabilities can be added without restructuring the entire codebase.

## Readiness Status

Stage 1 is ready for coding after this document.

The schema set, dataset structure, runtime boundaries, and scoring rubric are now defined well enough to implement the first vertical slice.

## Current Repo Reality

The current repository is still an early stub:

- the existing OCR script is CPU-oriented
- PDF handling is incomplete
- the current structured output is placeholder data
- the current requirements file pins CPU-only Torch

This means stage 1 implementation should not try to preserve the current script shape as the final architecture. It is better treated as a placeholder prototype.

## Runtime Decision

Stage 1 will use:

- `pythonBench`
  - for orchestration, test data management, and evaluation
- repo Python code
  - for preprocessing, schema validation, extraction orchestration, routing, and output assembly
- host `Ollama`
  - for local-model inference through the already-working ROCm path
- workstation GPU model endpoints
  - for testing the future cloud solution locally before remote cloud deployment
    exists

Stage 1 will not require a production service boundary yet. Local model
endpoints for workstation validation may run as host processes while contracts
stabilize.

Reason:

- host Ollama with ROCm has already been proven to use the AMD GPU
- adding a remote or production-grade runtime boundary before the contracts are
  stable would add unnecessary complexity

## PyTorch Placement Decision

Host-installed PyTorch is not considered the intended long-term placement for stage 1 pipeline code.

For stage 1:

- host GPU stack is for Ollama only
- Python dependencies should live in the bench or project environment
- stage 1 may not need PyTorch at all unless a selected preprocessing or extraction component specifically requires it

## Implementation Shape

Stage 1 should start as a Python-first module and CLI, not as a service.

Reason:

- the main need is repeatable testing, not service deployment
- a CLI is simpler to validate against the per-document folder corpus
- the HTTP boundary can be added later once the contracts stabilize

Potential later evolution:

- keep the same internal pipeline functions
- add a thin FastAPI wrapper if service mode becomes useful

The code should also be organized so multiple model adapters can be plugged into the same evidence packet and consensus layer later.

## First Vertical Slice

Implement in this order:

1. test corpus folder structure
2. schema models
3. PDF preprocessing
4. evidence-packet assembly
5. edge extraction orchestration
6. routing and consensus logic
7. final payload assembly
8. evaluator

This order ensures deterministic components exist before model behavior is introduced.

## Dependency And Parallel Work Summary

### Critical Path

The stage 1 critical path is:

1. schema and folder contract freeze
2. CLI contract
3. PDF preprocessing
4. evidence packet
5. single-voter extraction
6. routing
7. final payload
8. evaluation

These steps should be treated as blocking dependencies.

### Parallel Workstreams

Once the schema and CLI contracts are stable, the following can move in parallel:

- corpus scaffolding and human labeling
- prompt preparation for additional voters
- evaluator and reporting implementation
- local benchmark support for host GPU versus container CPU
- cloud-workstation voter-set validation on local workstation GPU hardware
- native Linux production ROCm deployment assets

The full three-voter ensemble should not block the first end-to-end single-document milestone.

## First Code Milestone

Milestone 1 should prove the following end to end for a single PDF:

- read `source.pdf`
- generate `preprocess_output.json`
- generate a structured evidence packet suitable for multiple voters
- call at least one host-Ollama model through the same adapter interface that later voters will use
- generate `edge_extraction_output.json`
- apply deterministic routing
- generate `routing_decision.json`
- generate `final_structured_payload.json`
- compare against `expected.json`
- generate `evaluation_document.json`

Once that works for one document, scale it to the full 20-document set.

## Recommended Project Structure

Suggested code structure:

```text
src/dartwing_ocr/
  schemas/
  preprocess/
  evidence/
  extract/
  consensus/
  routing/
  evaluate/
  cli.py
```

Suggested output structure for each test folder:

- `source.pdf`
- `expected.json`
- `notes.md`
- generated artifact JSON files

## PDF Handling Decision

Stage 1 is PDF-only.

The pipeline therefore needs a reliable PDF-to-image path before OCR or layout processing.

Selection criteria for the PDF rasterization library:

- stable on Ubuntu 24.04
- easy to install in the chosen Python environment
- deterministic output
- acceptable image quality for OCR

The exact library selection should be made during implementation, but it should be documented in code and requirements once chosen.

## OCR and Structure Decision

Stage 1 preprocessing should remain deterministic and model-agnostic.

The preprocessing stage should produce:

- page images
- OCR lines
- reading order
- layout blocks
- extracted tables if available
- consolidated document text

The preprocessing code should be structured around a Trijunction-ready evidence packet, even if all three ingestion components are not implemented on day one.

Target ingestion contributors:

- `PaddleOCR-VL-1.5`
- `Falcon OCR`
- `Falcon Perception`

## Model Invocation Decision

Stage 1 extraction should call the selected Ollama lane over HTTP:
full-workstation runs use host Ollama, cloud-workstation runs use local
workstation model endpoints, and edge-fast uses the Jetson-local lane.

The extraction layer should be built as a multi-voter-capable interface, even if the earliest milestone starts with a smaller subset.

Target voter roles:

- Qwen-family voter
- `Gemma 4 E4B` full-workstation voter
- cloud-class workstation voter set for local testing of the future cloud
  solution
- `Gemma 4 E2B` edge-fast Jetson voter
- Phi-4 Mini third-vote judge

Model selection should be recorded in code configuration rather than left
implicit. For stage 1, the full-workstation Gemma slot is `Gemma 4 E4B`; the
edge-fast Jetson slot is `Gemma 4 E2B`.

## Routing Decision

Routing and consensus must be deterministic and rule-based.

The models should not decide final acceptance.

Stage 1 decisions:

- `edge_accept`
- `edge_review_required`

The long-term target architecture also includes:

- unanimous field agreement
- 2-of-3 majority override
- split-decision escalation

The cloud-workstation path should exercise the long-term cloud-style voter set
locally, but routing remains deterministic code. It is not allowed to make a
model the final arbiter just because the model is larger.

Rules already defined elsewhere remain authoritative:

- inferred company names always require manual review
- missing explicit company name always requires manual review

## Evaluation Decision

Evaluation should compare:

- `expected.json`
- `final_structured_payload.json`

It should produce:

- per-field results
- per-document pass/fail
- run summary metrics

Normalization rules and pass gates are defined in `scoring.md`.

## Initial Non-Goals

The first implementation pass should not attempt:

- remote cloud provider path or deployed cloud fallback
- multi-model ensemble logic
- line item extraction
- service deployment
- latency optimization
- GPU containerization for Ollama

## Immediate Next Coding Tasks

1. create the `tests/stage1_vendor_identity/` root
2. create schema models for all persisted contracts
3. create a CLI entry point for one-document processing
4. implement PDF preprocessing into `preprocess_output`
5. implement a Trijunction-ready evidence packet
6. add model adapter and response parsing
7. add consensus and routing logic
8. add evaluation logic

## Definition of "Ready to Build"

The project is ready to build when:

- contracts are stable enough to code against
- stage 1 scope is constrained
- missing-name handling is explicit
- scoring rules are defined
- runtime boundaries are understood

Those conditions are now satisfied.
