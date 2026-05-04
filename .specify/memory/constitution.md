# LedgerLinc OCR Pipeline Constitution

## Core Principles

### I. One Repo, Clear Runtime Boundaries

This project keeps pipeline code, harness code, schemas, specs, and documentation in one repository, but runtime responsibilities must stay separate.

Required boundary:

- the pipeline implementation owns preprocessing, extraction orchestration, consensus, routing, and final payload assembly
- the test harness owns the labeled corpus, expected truth, evaluation, and reporting
- local development uses a lightweight pipeline container plus host Ollama by default
- production-style GPU container validation targets native Linux ROCm hosts, not Docker Desktop on Windows

No change may collapse these concerns into a single ad hoc runtime without explicit justification.

### II. Evidence-First, Schema-First Design

The pipeline is built around a shared evidence packet and stable JSON contracts, not around freeform model output.

The authoritative stage 1 artifacts are:

- `preprocess_output`
- `edge_extraction_output`
- `routing_decision`
- `final_structured_payload`

Any change to extraction shape, routing semantics, or evaluation inputs must update the documented schema contract and keep artifacts machine-validated. Model prompts and implementations must adapt to the contracts, not the reverse.

### III. Deterministic Control Over Model Output

Models may propose extracted values, but they do not own acceptance, review, or routing policy.

The following must remain deterministic code:

- spam gates
- consensus comparison
- explicit versus inferred field handling
- review-required decisions
- future escalation decisions

Confidence is a signal, not a substitute for provenance or policy.

### IV. Provenance and Review Safety

The system must preserve whether a field was explicitly found or inferred. This is mandatory for vendor identity.

Non-negotiable stage 1 rules:

- if no explicit company name is found, the pipeline may store a best guess in `company_name.value`
- when that occurs, `company_name.present` must be `false`
- when that occurs, `company_name.inferred` must be `true`
- inferred company names must force `manual_review_required = true`

Confidence alone must never be used to imply that a field was explicitly present.

### V. Benchmarkable and Reproducible Delivery

Every substantial pipeline change must preserve reproducible evaluation against labeled truth.

The repository must support:

- one-document end-to-end execution
- corpus-based evaluation from per-document folders
- per-field and overall scoring
- comparison across runtime modes where useful

On the current workstation, local benchmark/validation lanes are explicitly supported:

- host Ollama with ROCm GPU
- optional Ollama container as a CPU-only benchmark lane
- cloud-class workstation validation on local GPU hardware

## Stage 1 Scope Constraints

Until explicitly amended, stage 1 remains intentionally narrow:

- PDF input only
- vendor identity focus only
- no line item extraction
- no remote cloud execution or provider-managed fallback path
- local cloud-class workstation validation is allowed when it uses the same
  artifact contracts and keeps remote deployment concerns out of the pipeline
- no latency target as a release gate
- minimal review output only: whether review is required and why

The target architecture is larger and includes:

- Trijunction ingestion using PaddleOCR plus Falcon OCR plus Falcon Perception
- a three-voter ensemble using Qwen, Gemma, and Phi-4 Mini
- deterministic consensus and routing

Stage 1 implementation may be narrower, but new work must not block that target architecture.

## Quality Gates

The following gates apply to work in this repository:

1. Changes that affect pipeline or harness boundaries must keep the separation between `prd-model-pipeline.md` and `prd-test-harness.md`.
2. Changes that affect output contracts must update `docs/stage1-vendor-identity/schemas.md`.
3. Changes that affect runtime behavior must update `docs/stage1-vendor-identity/architecture.md` or `ollama-runtime.md` when relevant.
4. Pipeline code changes must be verifiable through at least one concrete local execution path.
5. Runtime/container changes must verify both container health and model reachability, and must distinguish local WSL behavior from native Linux production assumptions.
6. Evaluation changes must preserve comparison against human-labeled `expected.json` truth files.
7. Every OpenSpec and Speckit artifact must be consistent with `docs/stage1-vendor-identity/architecture.md`. Deviations are permitted but must be declared in the artifact with a one-line reason, and must not block the long-term target architecture described there.

## Development Workflow

Expected workflow for non-trivial work:

1. Use OpenSpec to capture change intent and design decisions when the work affects schemas, runtime/model orchestration, deterministic policy, edge deployment constraints, or this workflow.
2. Define or update the product boundary in the relevant PRD.
3. Update architecture or schema documentation if the contract changes.
4. Use Speckit to create the implementation worktree, plan the work, and execute tasks.
5. Implement code in the pipeline or harness layer without blurring responsibilities.
6. Validate the affected runtime path.
7. Record any local-versus-production differences in repo documentation.

Schema changes, routing changes, and runtime changes are not complete until the documentation and the implementation match.

## Governance

This constitution governs the LedgerLinc OCR pipeline repository and takes precedence over informal local habits.

Amendment rules:

- amendments must be committed in the repository
- amendments must preserve a clear reason for change
- if an amendment changes stage 1 contracts or scope, the related PRDs and supporting docs must be updated in the same body of work

Compliance rules:

- reviews should treat violations of these principles as design issues, not style issues
- complexity must be justified against the stage 1 scope
- unsupported local behavior on WSL must not be represented as production-ready GPU behavior

Supporting project documents:

- `docs/stage1-vendor-identity/architecture.md`
- `docs/stage1-vendor-identity/prd-model-pipeline.md`
- `docs/stage1-vendor-identity/prd-test-harness.md`
- `docs/stage1-vendor-identity/schemas.md`
- `docs/stage1-vendor-identity/scoring.md`
- `docs/stage1-vendor-identity/ollama-runtime.md`

## Amendment History

- **1.2.0 (2026-04-30)** — Added OpenSpec as the change-governance layer while keeping Speckit as the implementation worktree/task layer. Updated Quality Gate #7 to apply to both OpenSpec and Speckit artifacts. Reason: capture architecture, schema, runtime, model-orchestration, and workflow decisions before implementation without replacing the existing Speckit feature history.
- **1.3.0 (2026-05-01)** — Clarified that stage 1 excludes remote cloud execution while allowing cloud-class workstation validation on local GPU hardware. Reason: test the future cloud solution locally before introducing provider-managed deployment or fallback.
- **1.1.0 (2026-04-22)** — Added Quality Gate #7 requiring `/speckit.specify` and `/speckit.plan` artifacts to be consistent with `architecture.md`, with declared justification for any deviation. Reason: keep spec and plan work anchored to the long-term target architecture so narrow stage 1 slices do not drift from it.
- **1.0.0 (2026-04-12)** — Initial ratification.

**Version**: 1.3.0 | **Ratified**: 2026-04-12 | **Last Amended**: 2026-05-01
