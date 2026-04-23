# Stage 1 Architecture

## Purpose

This document records the updated target architecture for the LedgerLinc OCR pipeline and the narrower stage 1 implementation slice that will be built first.

The target architecture is now a high-consensus hybrid pipeline built around:

- a Trijunction ingestion layer
- a three-model extraction ensemble
- deterministic consensus voting and routing

Stage 1 will implement only a constrained subset of that target architecture.

## Updated Target Architecture

### 1. Trijunction Ingestion & Pre-processing

The first layer of the system is a high-fidelity ingestion stack that combines three complementary components:

- `PaddleOCR-VL-1.5`
  - maps document layout, tables, and reading order
- `Falcon OCR (0.3B)`
  - performs fast character recognition and the initial spam gate
- `Falcon Perception (0.6B)`
  - adds spatial grounding and open-vocabulary perception, such as identifying logos, stamps, and other non-standard signals

Together these three components form the "Trijunction Ingestion" layer.

The output of this layer is the shared evidence packet for downstream extraction models.

### 2. Triple-Model Ensemble Extraction

The structured evidence from the Trijunction layer is then passed to three independent models.

#### Model A

- `Qwen3-VL (32B/72B)` in cloud contexts
- `Qwen3 (1.7B/8B)` in edge contexts

Role:

- primary heavy-lifter for complex extraction and reasoning

#### Model B

- `Gemma 4 E4B` in edge contexts
- `Gemma 4 (31B)` in cloud contexts

Role:

- second independent extraction perspective

#### Model C

- `Phi-4 Mini (3.8B)`

Role:

- logic-heavy third vote
- strong verifier for consistency across fields
- particularly useful for math and structured cross-checks such as subtotal, tax, and total relationships

### 3. Consensus Voting & Routing Logic

The three model outputs are compared by a deterministic consensus layer.

> **Stage 1 implementation.** The stage 1 router is a model-free CLI
> at `python -m ledgerlinc_ocr.router route <folder>`. It reads
> `edge_extraction_output.json` and emits a schema-valid
> `routing_decision.json` with `decision ∈ {edge_accept, edge_review_required}`
> plus a priority-ordered `reasons[]` array. Canonical reason strings
> and the four forcing rules (missing-name, spam-gate, secondary-floor,
> upstream-failure) are pinned by `policy_version`. See
> [`specs/008-routing/spec.md`](../../specs/008-routing/spec.md) and
> [`specs/008-routing/contracts/cli-contract.md`](../../specs/008-routing/contracts/cli-contract.md).

#### Consensus Gate

The gate compares field-level JSON outputs across all three models.

Decision policy:

- `Unanimous`
  - if all three models agree on a field, mark the field `High Confidence`
- `Majority (2-of-3)`
  - if two models agree, override the third
  - mark the field for downstream double-checking by later verification workflows
- `Split Decision`
  - if all three disagree, escalate immediately
  - at edge, that means cloud escalation in the future architecture
  - in review contexts, that means controller or yellow-path review

## Why Phi-4 Mini Was Chosen as the Third Vote

Phi-4 Mini was selected over DeepSeek-R1-1.5B, SmolLM3, and Llama 3.2 1B as the third vote because it is the strongest adjudicator for this specific role.

Reasons:

- it is better suited to judging evidence consistency than the smaller 1B to 1.5B options
- it complements Gemma and Qwen rather than duplicating their behavior
- it is well-positioned to catch numeric and structural inconsistencies in invoices
- it has enough capacity to reason over OCR, layout, perception, and candidate vendor signals together

## Evidence Packet Principle

The ensemble should reason over a structured evidence packet, not just raw OCR text.

That packet should include:

- OCR text
- reading order
- layout blocks
- table snippets
- logo and stamp observations
- header and footer candidates
- candidate vendor signals such as:
  - company name
  - tax IDs
  - website
  - email domain
  - phone
  - address

This is important because the value of the Trijunction layer is not just text extraction. It is the combined evidence from structure, OCR, and perception.

## Stage 1 Implementation Slice

Stage 1 does not implement the full target architecture.

Stage 1 remains intentionally narrow:

- PDF input only
- edge-oriented flow only
- no cloud path implementation
- no line item extraction
- no latency targets yet
- vendor identity is the primary evaluation focus

### What Stage 1 Uses From the Target Architecture

Stage 1 should align to the target architecture in shape, even if it does not deliver the whole system.

For stage 1:

- the pipeline should be designed around a shared evidence packet from preprocessing
- the code structure should allow multiple model voters later
- the routing layer must remain deterministic and separate from model output

### What Stage 1 Does Not Yet Deliver

Stage 1 does not yet require:

- full three-model production ensemble execution
- cloud escalation implementation
- investigator-agent integration
- controller review workflow implementation

## Runtime Boundaries

For stage 1, the recommended runtime split remains:

- `pythonBench`
  - owns the test corpus, expected truth, evaluation, and orchestration
- repo pipeline code
  - owns preprocessing, schema validation, extraction orchestration, routing logic, and output assembly
- host `Ollama`
  - owns small-model inference through the already-proven ROCm path

## Stage 1 Processing Flow

1. A PDF test document is selected from the stage 1 corpus.
2. The preprocessing stage builds the stage 1 evidence packet:
   - page images
   - OCR lines
   - reading order
   - layout blocks
   - tables when available
3. The extraction stage produces structured vendor identity output.
4. The routing layer decides whether the result is acceptable or requires manual review.
5. The final structured payload is assembled.
6. The evaluator compares the final payload against the human-labeled expected truth.

### Stage 1 Preprocessing Engine

Stage 1 preprocessing is implemented on top of `PaddleOCR 3.5`:

- `PPStructureV3` — layout detection (PP-DocBlockLayout + PP-DocLayout_plus-L), table structure (SLANeXt_wired, SLANet_plus), cell detectors (RT-DETR-L)
- `PP-OCRv5` — text recognition, invoked through V3's built-in OCR pass (no separate recognizer call)
- CPU-only, single-threaded, `enable_mkldnn=False` for paddle 3.3.1 PIR/oneDNN bug avoidance and determinism (see spec `010-pp-structurev3-preprocessing`)

This realizes the stage-1 subset of the `PaddleOCR-VL-1.5` Trijunction role above; Falcon OCR and Falcon Perception remain `not_implemented` at stage 1.

## Stage 1 Artifacts

Each stage 1 run works with four core artifacts:

- `preprocess_output`
  - OCR and structure only, no business inference
- `edge_extraction_output`
  - model-driven extraction with confidence and evidence
- `routing_decision`
  - deterministic review or acceptance decision
- `final_structured_payload`
  - clean downstream handoff object

The evaluator compares `final_structured_payload` to `expected.json` and produces per-document and per-run evaluation reports.

## Review Policy

Stage 1 intentionally uses a minimal review policy.

- if the company name is explicitly present and vendor identity is strong, the document can be accepted
- if the company name is inferred rather than explicitly found, the document must go to manual review
- the payload should indicate only whether review is required and why

No UI-oriented review actions are defined in stage 1.

## Missing-Name Policy

Some test documents will not contain an explicit company name.

For those documents:

- the pipeline is allowed to make a best guess
- the guessed name is stored in `company_name.value`
- `company_name.present` must be `false`
- `company_name.inferred` must be `true`
- `manual_review_required` must be `true`

Confidence alone is not enough to express provenance. The schema must preserve whether the name was present or inferred.

## Test Set Strategy

The stage 1 dataset remains a 20-document PDF suite:

- 5 easy
- 5 medium
- 5 hard
- 5 missing company name

The missing-name documents exist specifically to test inference behavior and review routing.
