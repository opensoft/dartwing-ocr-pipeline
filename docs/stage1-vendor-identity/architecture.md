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

### Preprocessing Profiles

Stage 1 needs two preprocessing runtime shapes under the same repository and
artifact-contract discipline:

- `full-structure`
  - the full PPStructureV3 document stack
  - produces OCR lines, reading order, layout blocks, table projections, and
    document text
  - used for canonical corpus baselines and full-evidence extraction grounding
  - has two workstation-runtime variants under the same artifact contract:
    `ppstructurev3@cpu` (the canonical default; CPU-bound, byte-stable
    on repeat runs) and `ppstructurev3@gpu` (workstation-only, opt-in,
    gated on a per-process Paddle GPU preflight; native Linux ROCm is
    the supported runtime path; WSL Docker Desktop is not). Both
    variants emit the same `preprocess_output.json` shape; the chosen
    variant is recoverable from the artifact's `pipeline_version`
    string by parsing the trailing `.cpu` or `.gpu<N>` lane segment.
    Jetson/edge GPU is out of scope for `full-structure` and is
    served by the separate `edge-ocr@jetson` profile below. See
    `docs/stage1-vendor-identity/paddle-gpu-preflight.md` for the
    operator-facing FR-001 state guide and the additive `paddlepaddle-gpu`
    install path.
- `edge-ocr`
  - a lightweight OCR-first scanner for the Jetson Nano Super edge target
  - runs OCR on the Jetson GPU lane; CPU-only OCR fallback is not supported
  - produces fast text evidence for first-pass edge scanning and triage
  - must not fabricate layout blocks or table structure when the lightweight
    engine did not observe them

Both profiles are selected through pipeline/runtime profile configuration rather
than split into separate repositories. The selected profile must be visible in
`pipeline_version`, and normal pipeline runs have one canonical
`preprocess_output.json` for the selected profile. Side-by-side comparisons use
explicit run namespaces instead of keeping two canonical preprocessing artifacts
in the same document folder.

### End-To-End Runtime Stacks

Stage 1 distinguishes preprocessing profiles from end-to-end runtime stacks:

- `full-workstation`
  - preprocessing: `full-structure` / `ppstructurev3@cpu`
  - extraction: Gemma 4 E4B through the workstation Ollama GPU lane
  - purpose: highest available local evidence quality for corpus baselines and
    full validation runs
- `cloud-workstation`
  - target: workstation with local GPU cards
  - preprocessing: full-structure evidence first, with Trijunction contributors
    added as local workstation capabilities become available
  - extraction: cloud-class voter set on local workstation model endpoints
    rather than remote provider APIs
  - purpose: test the future cloud solution locally before introducing a
    provider-managed cloud deployment or fallback path
- `edge-fast`
  - target: Jetson Nano Super class hardware
  - preprocessing: `edge-ocr@jetson`
  - extraction: Gemma 4 E2B through the Jetson-local Ollama edge lane
  - purpose: fast first-pass edge scanning with a smaller extraction model

`cloud-workstation` and `edge-fast` still use the same downstream routing and
final-payload contracts. Their selected preprocessing evidence, model set, and
runtime lane must be visible through profile/runtime metadata so evaluator
results are not confused with the `full-workstation` baseline.

The edge-fast preprocessing path tries the small Paddle OCR scanner first. If
deterministic quality gates fail, the profile may fall back to a larger Paddle
scanner only when that fallback also runs on the Jetson GPU lane and records the
fallback in metadata. If no Jetson GPU fallback is available, the document is
sent to review or the full-workstation stack instead of running heavy OCR on
CPU.

### 2. Triple-Model Ensemble Extraction

The structured evidence from the Trijunction layer is then passed to three independent models.

#### Model A

- `Qwen3-VL (32B/72B)` in cloud contexts
- `Qwen3 (1.7B/8B)` in edge contexts

Role:

- primary heavy-lifter for complex extraction and reasoning

#### Model B

- `Gemma 4 E2B` in the `edge-fast` Jetson stack
- `Gemma 4 E4B` in the `full-workstation` stack and larger edge contexts
- `Gemma 4 (31B)` in cloud contexts

Role:

- second independent extraction perspective
- for `edge-fast`, judge the OCR evidence packet into normalized
  vendor-identity fields with evidence ids and confidence signals
- never own OCR/layout, final routing, schema validation, or deterministic
  explicit-vs-inferred company-name policy

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
- local validation flow only: full-workstation, cloud-workstation, and edge-fast
- no remote cloud provider path or deployed cloud fallback
- local cloud-class workstation validation is allowed as a runtime stack
- no line item extraction
- no latency targets yet
- vendor identity is the primary evaluation focus

### What Stage 1 Uses From the Target Architecture

Stage 1 should align to the target architecture in shape, even if it does not deliver the whole system.

For stage 1:

- the pipeline should be designed around a shared evidence packet from preprocessing
- preprocessing should support both a full-structure profile and a lightweight
  edge-OCR profile behind a common pipeline contract
- the code structure should allow multiple model voters later
- the routing layer must remain deterministic and separate from model output

### What Stage 1 Does Not Yet Deliver

Stage 1 does not yet require:

- full three-model production ensemble execution
- remote cloud escalation implementation
- investigator-agent integration
- controller review workflow implementation

## Runtime Boundaries

For stage 1, the recommended runtime split remains:

- `pythonBench`
  - owns the test corpus, expected truth, evaluation, and orchestration
- repo pipeline code
  - owns preprocessing, schema validation, extraction orchestration, routing logic, and output assembly
  - owns preprocessing profile selection and warm worker/batch execution for
    live preprocessing profiles
- host `Ollama`
  - owns small-model inference through the already-proven ROCm path
- workstation model endpoints
  - own cloud-class local model validation for the `cloud-workstation` stack
  - must remain local workstation infrastructure until a separate remote-cloud
    change is approved

## Stage 1 Controller (Feature 011)

The pipeline package's `python -m ledgerlinc_ocr.pipeline run` entrypoint
is the stage 1 root/master controller. It owns:

- per-stage profile resolution (`--preprocess-profile`,
  `--extract-profile`, `--routing-profile`, `--final-payload-profile`)
  and the `--stack-preset` convenience expansion (`full-workstation`,
  `cloud-workstation`, `edge-fast`)
- execution slicing (`--start-at` / `--stop-after`) with
  prerequisite-artifact validation against the installed contract set
- overwrite scoping limited to the selected execution slice
- the warm-corpus execution mode invoked via `--documents-file <path>`,
  which initializes each live preprocessing profile exactly once per
  process and reuses the warmed instance across documents
- per-run timing metadata, including a single end-of-run JSON object on
  stdout carrying `kind: "run_summary"` so the harness can distinguish
  it from per-document `002-cli-contract` records

The controller does NOT own corpus selection, repeated benchmark loops,
scoring, evaluation, or report generation; those remain harness
responsibilities. See `specs/011-stage-runtime-profiles/spec.md`
(FR-033) and `specs/011-stage-runtime-profiles/contracts/cli-contract.md`
for the authoritative scope.

The four canonical artifact filenames and JSON Schemas are unchanged
(FR-029); 011 is a CLI-surface amendment only.

## Stage 1 Processing Flow

1. A PDF test document is selected from the stage 1 corpus.
2. The preprocessing stage builds the stage 1 evidence packet using the selected
   preprocessing profile:
   - page images
   - OCR lines
   - reading order
   - layout blocks
   - tables when available
   - for `edge-ocr`, layout and table slots must remain explicit and typed but
     may be empty when the lightweight scanner did not produce that evidence
3. The extraction stage produces structured vendor identity output.
4. The routing layer decides whether the result is acceptable or requires manual review.
5. The final structured payload is assembled.
6. The evaluator compares the final payload against the human-labeled expected truth.

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
