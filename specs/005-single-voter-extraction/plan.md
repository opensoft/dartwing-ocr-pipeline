# Implementation Plan: Single-Voter Edge Extraction (Stage 1 Vendor-Identity)

**Branch**: `005-single-voter-extraction` | **Date**: 2026-04-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-single-voter-extraction/spec.md`

## Summary

Build the stage 1 edge-extraction slice: one Python package that reads a per-document folder's
`preprocess_output.json` (frozen v1.0.0, produced by 003), calls a single host-Ollama voter
(Gemma 4 E4B by default) over HTTP, reconciles the model's JSON against the preprocessing
packet's evidence identifiers, enforces the company-name provenance invariants, and writes a
schema-valid `edge_extraction_output.json` next to the input. No routing, no consensus, no final
payload, no line items, no cloud path — those are downstream slices.

Shape-wise the slice is ensemble-ready: voters are pluggable behind a thin adapter interface, the
output contract already carries `vote_metadata` and `model_runtime`, and the deterministic
reconciliation step (evidence filtering, null-on-missing defaults, `present`/`inferred` override,
`status` derivation) is code the model never owns. Future Qwen and Phi-4 Mini voters plug in
through voter configuration files alone; the extractor's input/output/reconciliation/folder
behavior stays fixed.

## Technical Context

**Language/Version**: Python 3.12 (devcontainer base image, matches existing package).

**Primary Dependencies**:
- Existing: `jsonschema>=4.22,<5`, `pydantic>=2.7,<3` (contract validation + typed config), already in `pyproject.toml`.
- **New for this slice**:
  - `httpx>=0.27,<1` — sync HTTP client for host Ollama (cleaner timeout semantics than `requests`; well-typed; no retries by default, which matches FR-015 no-internal-retry rule).
  - `PyYAML>=6.0,<7` — voter-config file format. Phase 0 research confirms YAML over JSON for operator ergonomics.
  - (No new Ollama SDK. See Phase 0 — we call the `/api/generate` endpoint directly via `httpx` to keep the dependency surface small and the adapter seam obvious.)
- **Not used**: PyTorch, PaddleOCR, line-item libraries, retry libraries, logging frameworks beyond stdlib.

**Storage**: Filesystem only. Reads `tests/stage1_vendor_identity/inv_XXX_<difficulty>/preprocess_output.json`; writes `edge_extraction_output.json` into the same folder. No database. No cloud. The only network call is the host-Ollama HTTP request to `OLLAMA_BASE_URL`.

**Testing**: `pytest` under `tests/unit/extract/` (pure reconciliation logic, no Ollama) and `tests/integration/extract/` (real host-Ollama smoke tests plus recorded-fixture replay tests using a stub voter). Contract tests under existing `tests/contract_tests/` get one new file asserting any emitted `edge_extraction_output.json` validates against the frozen schema and passes the company-name invariant pair.

**Target Platform**: Linux (devcontainer, native WSL Ubuntu 24.04). The extractor runs CPU-only inside the pipeline container; the Ollama endpoint runs on the host (ROCm GPU) and is reached over HTTP. The native Linux ROCm compose file is the production lane; the optional WSL CPU-only Ollama container is a benchmark lane only (constitution §V).

**Project Type**: Single Python package. This slice adds `src/ledgerlinc_ocr/extract/` alongside the existing `preprocessing/`, `pipeline/`, and `validator/` packages, and exposes a CLI via `python -m ledgerlinc_ocr.extract` (per spec Clarifications, Q4).

**Performance Goals**: None as a release gate (constitution: no latency gate in stage 1). SC-007 pins a soft target of <2 s wall-clock for the extractor's non-model work (packet read, reconciliation, artifact write) on the `pipeline-dev` devcontainer (CPU-only, Python 3.12 — the constitutionally-pinned execution surface for pipeline code). The model call itself is outside the extractor's control and is explicitly not gated.

**Constraints**:
- Artifact MUST validate against `contracts/stage1_vendor_identity/v1.0.0/edge_extraction_output.schema.json` (FR-002, SC-001).
- `contract_set_version == "1.0.0"` required on both input and output (FR-002, FR-003).
- No retries inside the extractor (FR-015); single bounded HTTP timeout.
- No modification of input files (`preprocess_output.json`, `expected.json`, `source.pdf`, `notes.md`) — FR-019.
- `pipeline_version` MUST be a stable string traceable to the build; we use the package version plus the short git SHA when available (research.md §pipeline-version).
- Deterministic reconciliation, null-on-missing defaults, `present`/`inferred` override, and `status` derivation — FR-014 and SC-009.
- Network egress is limited to `OLLAMA_BASE_URL` (no cloud escalation — FR-021).

**Scale/Scope**: One document per invocation. The 20-document stage 1 corpus (5 easy / 5 medium / 5 hard / 5 missing_name) is the evaluation surface. Corpus orchestration lives in the harness, not in this extractor.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md` v1.0.0:

| Principle | Gate | Status |
|-----------|------|--------|
| I. One Repo, Clear Runtime Boundaries | Extraction belongs to the pipeline layer. Must not embed model runtime; must not collapse harness concerns (evaluation, scoring) into this slice. | **PASS** — `src/ledgerlinc_ocr/extract/` is pipeline code only. Model inference lives in host Ollama, reached over HTTP (spec Assumptions, FR-017). No PyTorch, no embedded weights. Routing, consensus, final-payload assembly, and evaluation are all explicitly out of scope (FR-020, FR-021). |
| II. Evidence-First, Schema-First Design | Artifact MUST validate against the frozen `edge_extraction_output` contract; every field MUST carry `{value, confidence, evidence}` per schema; prompts and code adapt to the contract, not the reverse. | **PASS** — FR-002 mandates schema validation before persist. Every `evidence` array is filtered against the preprocessing packet's real `block_id` / `line_id` values (FR-010). No schema amendment; `contract_set_version = "1.0.0"` is consumed as-is. |
| III. Deterministic Control Over Model Output | Evidence reconciliation, null-on-missing defaults, `present`/`inferred` override, `status` derivation, and hard-failure semantics are code, not model judgment. | **PASS** — FR-010, FR-011, FR-012, FR-013, FR-014, FR-015 are all explicitly deterministic post-model passes. The model proposes; code disposes. Confidence is a signal; the ungrounded hard cap (FR-011) is a code-level ceiling, not a model-reported number. |
| IV. Provenance and Review Safety | For `company_name`: if no grounded evidence supports an explicit name, `present = false` AND `inferred = true`, regardless of model claim. Stage 1 pre-answer for routing (006). | **PASS** — FR-012 and FR-013 enforce this at the extractor layer (not downstream). SC-002 is a 100% pass gate on the 5 missing-name corpus documents. |
| V. Benchmarkable and Reproducible Delivery | One-document end-to-end execution; per-document folder layout preserved; reruns are meaningfully deterministic. | **PASS** — CLI processes one document per invocation (FR-001, FR-025). SC-009 scopes reproducibility to schema, reconciliation, status, and provenance — explicitly NOT to bit-exact string values (spec Assumptions). Two benchmark lanes (host Ollama with ROCm GPU vs. optional WSL CPU Ollama) are configuration-only (spec Clarifications, Q3). |

**Stage 1 Scope Constraints** (constitution §"Stage 1 Scope Constraints"):
- PDF input only ✓ (the extractor consumes `preprocess_output.json`, which itself already enforces PDF input in 003)
- Vendor identity focus ✓ (extracts `vendor_candidate` + `invoice_header_fields`; no line items — FR-021)
- No line-item extraction ✓ (FR-021)
- No cloud execution path ✓ (FR-021; only host-Ollama HTTP is allowed)
- No latency gate ✓ (SC-007 is a soft target; constitution forbids it as a release gate)
- Minimal review output ✓ (extractor emits provenance shape; actual `manual_review_required` flag belongs to routing slice 006 — FR-020)

**Quality Gates** (constitution §"Quality Gates"):
1. Pipeline vs. harness boundary preserved — this slice is pipeline-only; it does not compare against `expected.json` or write any harness artifact.
2. Output contracts unchanged — this slice consumes the frozen `edge_extraction_output` schema; no schema edits required. `docs/stage1-vendor-identity/schemas.md` already matches.
3. Runtime behavior — this slice depends on host Ollama over HTTP; `ollama-runtime.md` already documents the host vs. container story. One small addition in research.md pins the timeout + no-retry rule for the extractor; the runtime doc is updated in tasks if we want a cross-link, but no substantive runtime change.
4. Verifiable through concrete local execution — CLI `python -m ledgerlinc_ocr.extract --folder <path> --voter <name>` against a fixture folder with `preprocess_output.json` + a running host Ollama.
5. Runtime/container changes — none. Reuses the existing `pipeline-dev` devcontainer and the existing host Ollama path.
6. Evaluation comparison preserved — the extractor does not touch evaluation. The downstream evaluator (008) still compares `final_structured_payload.json` (not `edge_extraction_output.json`) to `expected.json`; this slice is neutral with respect to scoring.

**Result: PASS. No constitution violations. Complexity Tracking section left empty.**

## Project Structure

### Documentation (this feature)

```text
specs/005-single-voter-extraction/
├── plan.md                         # This file
├── spec.md                         # Feature specification (already exists)
├── research.md                     # Phase 0 output
├── data-model.md                   # Phase 1 output (internal types + reconciliation state machine)
├── quickstart.md                   # Phase 1 output (end-to-end walk-through)
├── contracts/
│   ├── cli-contract.md             # CLI surface — flags, exit codes, artifact path
│   └── voter-config.md             # Voter config file schema + stage 1 Gemma default
├── checklists/                     # Existing (spec-kit checklists)
└── tasks.md                        # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
src/ledgerlinc_ocr/
├── __init__.py                         # existing
├── preprocessing/                      # existing (003 slice)
├── pipeline/                           # existing
├── validator/                          # existing — contract validator
└── extract/                            # NEW — this slice
    ├── __init__.py
    ├── __main__.py                     # `python -m ledgerlinc_ocr.extract`
    ├── cli.py                          # argparse entry point: --folder, --voter
    ├── pipeline.py                     # orchestrates load → voter call → reconcile → write
    ├── config.py                       # pydantic VoterConfig + YAML loader
    ├── voters/
    │   ├── __init__.py
    │   ├── base.py                     # VoterAdapter Protocol (pluggable seam, FR-017)
    │   ├── ollama.py                   # OllamaVoter — httpx client for /api/generate
    │   ├── stub.py                     # StubVoter — reads a canned JSON fixture (test seam, SC-004)
    │   └── configs/
    │       ├── gemma-edge.yaml         # stage 1 Gemma 4 E4B default config
    │       └── stub.yaml               # fixture-driven config for tests
    ├── prompt.py                       # deterministic prompt assembly from preprocess_output packet
    ├── parse.py                        # model-response parsing + JSON repair (records repair in warnings)
    ├── reconcile.py                    # deterministic reconciliation: evidence filter, defaults, present/inferred, status
    ├── artifact.py                     # assembles edge_extraction_output dict, runs validator before returning
    ├── errors.py                       # typed errors: OllamaUnreachable, ModelUnavailable, MalformedResponse, UnrepairableResponse, InputContractDrift
    ├── exit_codes.py                   # stable exit-code table (mirrors preprocessing/exit_codes.py)
    └── version.py                      # build_pipeline_version() — package version + short SHA

tests/
├── contract_tests/                     # existing
│   └── test_edge_extraction_output_shape.py   # NEW — schema-validity spot checks + invariant pair
├── unit/extract/                       # NEW
│   ├── test_prompt.py                  # deterministic prompt assembly
│   ├── test_parse.py                   # malformed-JSON repair, unrepairable → error
│   ├── test_reconcile_evidence.py      # unresolvable-ID filtering, warnings emission
│   ├── test_reconcile_defaults.py      # missing sub-field → null-default + status partial
│   ├── test_reconcile_provenance.py    # company_name present/inferred override (US3)
│   ├── test_reconcile_status.py        # status derivation truth table (success/partial/failure)
│   ├── test_reconcile_confidence_cap.py # FR-011 hard cap on empty-evidence fields
│   ├── test_reconcile_determinism.py   # SC-009 byte-equal proof (T091)
│   ├── test_reconcile_perf.py          # <500 ms inner guardrail (T085)
│   ├── test_config.py                  # voter-config YAML loading + pydantic validation
│   ├── test_version.py                 # pipeline_version composition rules
│   ├── test_artifact.py                # atomic write + schema-invalid dict rejection before write
│   └── test_no_downstream_imports.py   # FR-020/FR-021 module-boundary AST walk (T093)
├── integration/extract/                # NEW
│   ├── test_us1_schema_valid.py        # US1 AC#1 (full happy path, stub voter)
│   ├── test_us1_ids_match.py           # US1 AC#2 (document_id / contract_set_version / processed_at / pipeline_version)
│   ├── test_us1_vendor_block.py        # US1 AC#3 (vendor_candidate shape)
│   ├── test_us1_header_block.py        # US1 AC#4 (invoice_header_fields shape incl. total_amount)
│   ├── test_us1_status_consistency.py  # US1 AC#5 (status vs. warnings consistency)
│   ├── test_us1_no_sidecar_writes.py   # US1 AC#6 (folder write boundaries)
│   ├── test_us2_evidence_grounding.py  # US2 ACs (evidence resolves; bogus IDs filtered)
│   ├── test_us3_missing_name.py        # US3 ACs (missing-name + override path)
│   ├── test_us4_pluggable_voter.py     # US4 ACs (stub voter swap → identical shape)
│   ├── test_us5_hard_failures.py       # US5 ACs (Ollama unreachable, contract drift, malformed input, model unavailable T089)
│   ├── test_us5_soft_failures.py       # US5 ACs (JSON repair, defaulted sub-field, unrepairable response, partial-input propagation T090)
│   ├── test_corpus_walk.py             # stub-voter 20-doc walk (T082–T084): schema/missing-name/evidence at 100%
│   ├── test_pipeline_perf.py           # SC-007 <2 s full-pipeline-minus-model guardrail (T092)
│   └── test_host_ollama_smoke.py       # Real host-Ollama smoke test; skipped if endpoint not reachable
└── fixtures/extract/                   # NEW — canned preprocess + voter responses
    ├── preprocess_easy.json            # small preprocess packet with grounded evidence
    ├── preprocess_missing_name.json    # preprocess packet with no explicit company name
    ├── voter_response_clean.json       # canned model JSON — happy path
    ├── voter_response_malformed.json   # JSON-with-prose wrapper (repair path)
    ├── voter_response_missing_field.json # valid JSON missing a required sub-field (default path)
    ├── voter_response_bogus_evidence.json # evidence IDs that don't resolve (filter path)
    ├── voter_response_unrepairable.txt # deliberately unparseable (hard failure path)
    └── us5_partial_input/              # FR-023 partial-input propagation fixture (T090)
        └── preprocess_output.json      # schema-valid packet with falcon_perception.status == "failure"
```

**Structure Decision**: Single-project Python package. `src/ledgerlinc_ocr/extract/` sits alongside
the existing `preprocessing/`, `pipeline/`, and `validator/` packages. The CLI is exposed as a module
(`python -m ledgerlinc_ocr.extract`, matching spec Clarifications Q4) and will also be registered
as a console script (`ledgerlinc-extract`) in `pyproject.toml` in Phase 2 tasks. The voter seam is a
single `VoterAdapter` Protocol under `voters/base.py`; the stage 1 Gemma implementation and a
fixture-driven `StubVoter` both implement it, proving the pluggable shape required by US4/SC-004.
Reconciliation (`reconcile.py`) is a pure function over `(preprocess_packet, model_response, config)`
so every US2/US3/US5 deterministic-behavior test is a unit test, not an integration test.

## Complexity Tracking

> No constitution violations to justify. Section intentionally empty.
