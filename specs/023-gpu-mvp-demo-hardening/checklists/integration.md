# Integration / Contracts Requirements Quality Checklist: GPU MVP Demo Hardening

**Purpose**: Release-gate audit of integration-related requirements quality — interactions with the eight upstream features the demo composes, and the runbook script the operator runs.
**Created**: 2026-05-24
**Feature**: [spec.md](../spec.md)

## Feature 005 (Single-Voter Extraction)

- [ ] CHK001 Is the integration surface with feature 005 specified — does the demo invoke the extractor as a subprocess (`dartwing-extract`), via library import, or via composed Python API? [Completeness, Spec §Dependencies, Gap]
- [ ] CHK002 Is the voter-config-discovery contract from feature 005 referenced explicitly, with no implicit re-implementation in this feature? [Consistency, Spec §FR-005, §Assumptions]
- [ ] CHK003 Are feature 005's exit codes (0/1/2/3/4) mapped to the demo's exit-code table (0–5)? [Completeness, Spec §FR-021/Dependencies]

## Feature 014 (Paddle GPU Preprocessing)

- [ ] CHK004 Is the existing Paddle ROCm preflight that FR-002 mandates be invoked specified as the *only* preflight (not augmented with new Paddle checks here)? [Clarity, Spec §FR-002, Dependencies]
- [ ] CHK005 Is the preflight's failure semantics (e.g., raises `PaddleROCmPreflightError`, exits 1) carried forward, or is this feature free to translate it? [Coverage, Gap]
- [ ] CHK006 Is the post-run Paddle device interrogation (FR-012) defined as a *new* call vs. a re-use of feature 014's preflight API? [Clarity, Spec §FR-012, Dependencies]

## Feature 015 (GPU Engine Reuse + Timing)

- [ ] CHK007 Is the source of `phase_timings` in the demo report specified — derived from feature 015's `run_summary.phase_timings`, or instrumented separately? [Completeness, Spec §FR-025, Dependencies]
- [ ] CHK008 Is the rule "the demo report MAY surface feature 015 timing fields for context" reconciled with FR-025's mandatory `phase_timings` (which is no longer "MAY")? [Conflict, Spec §FR-025/Dependencies]

## Feature 018 (`header-first-v1` Preset)

- [ ] CHK009 Is the contract for the `header-first-v1` preset (its name, its identity in feature 018) carried into this feature unchanged, so no new preset variant is introduced? [Consistency, Spec §FR-011, Dependencies]
- [ ] CHK010 Is the `--preset full-ocr` value defined as a specific feature-018-known value, or is "full OCR" interpretive? [Clarity, Spec §FR-011, Gap]

## Feature 019 (OCR-Only Fast Lane)

- [ ] CHK011 Is the spec explicit about whether this feature composes with the feature-019 OCR-only profile, or whether they are mutually exclusive run modes? [Clarity, Spec §Dependencies]

## Feature 020 (Vendor Evidence Gate)

- [ ] CHK012 Is the mapping from evidence-gate state (`sufficient` / `borderline` / `insufficient`) to `quality_status` (`pass` / `weak` / `review_required`) defined precisely? [Clarity, Spec §FR-010, Dependencies]
- [ ] CHK013 Is the requirement that the demo command does NOT *change* the evidence gate's behavior (only consumes its state) explicit, so feature 020's contract holds? [Consistency, Spec §FR-014, Dependencies]

## Feature 021 (GPU MVP Promotion)

- [ ] CHK014 Is the relationship to feature 021 specified — this feature *hardens* feature 021's four-run benchmark into a single canonical demo command? [Clarity, Spec §Dependencies]
- [ ] CHK015 Is the runbook path (`docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`) carried over from feature 021, with this feature extending in place rather than replacing? [Consistency, Spec §Clarifications]

## Feature 022 (OCR Semantic Quality Gate)

- [ ] CHK016 Is the invocation contract for feature 022's evaluator (CLI subcommand, library function, etc.) specified, so `--with-evaluator` can be implemented deterministically? [Completeness, Spec §FR-022, Gap]
- [ ] CHK017 Is the requirement that the demo does NOT depend on feature 022's evaluator on the default path explicit, so feature 022's evaluator stack is not a blocker? [Consistency, Spec §FR-022, §Assumptions]
- [ ] CHK018 Is the evaluator's output (`evaluation_document.json`) handled within the demo's overwrite scope, given SC-010 says it is NOT touched by overwrite — i.e., it persists across runs? [Consistency, Spec §SC-010, Gap]

## Host Ollama Startup Script

- [ ] CHK019 Is `scripts/start-host-ollama-rocm-wsl.sh` referenced as the canonical-and-only supported host Ollama startup path, with no alternate (`ollama serve`, container) accepted? [Clarity, Spec §FR-006, Dependencies]
- [ ] CHK020 Is the operator obligation to start Ollama outside the demo command specified, vs. the demo command auto-starting Ollama? [Completeness, Spec §FR-006]

## Pipeline_version Composition

- [ ] CHK021 Is the source of `pipeline_version` specified — composed from sub-module versions (features 003, 005, 008, 009), or a single top-level package version? [Completeness, Spec §FR-024, Gap]
- [ ] CHK022 Is the `pipeline_version` format pinned (`x.y.z`, `git-describe`, composed `pp:0.1.0,ex:0.2.0,...`), so consumers can compare meaningfully? [Clarity, Spec §FR-024, Gap]

## Contract-Set Invariance

- [ ] CHK023 Is the requirement that this feature does NOT bump `contract_set_version` (still v1.3.0) explicit, with the bug-fix exception narrowly scoped? [Clarity, Spec §FR-014]
- [ ] CHK024 Are the four canonical artifact JSON Schemas referenced as unchanged, so this feature does not introduce schema drift? [Consistency, Spec §FR-014]

## Sub-Module Output Composition

- [ ] CHK025 Are the sub-module `kind: "run_summary"` stdout lines (from features 014–020) specified as not appearing on the demo's stdout (would violate FR-019 single-line guarantee)? [Consistency, Spec §FR-019, Dependencies]
- [ ] CHK026 Are sub-module stderr lines specified as composed-and-passed-through to the demo's stderr, or filtered/transformed? [Completeness, Gap]

## Primary / Alternate / Exception / Recovery / Non-Functional Coverage

- [ ] CHK027 Are integration requirements defined for the **primary** flow (all eight features compose successfully)? [Coverage — Primary, Spec §Dependencies]
- [ ] CHK028 Are integration requirements defined for **alternate** flows (`--with-evaluator` invoking feature 022; `--preset full-ocr` switching feature 018 mode)? [Coverage — Alternate, Spec §FR-011/FR-022]
- [ ] CHK029 Are integration requirements defined for **exception** flows (one sub-module fails — exit code, error output, demo response)? [Coverage — Exception, Spec §FR-021]
- [ ] CHK030 Are integration **recovery** requirements defined (no recovery within a run — surface the failure cleanly; operator re-runs)? [Coverage — Recovery, Gap]
- [ ] CHK031 Are integration **non-functional** properties specified (sub-module composition adds <X seconds to total runtime budget)? [Coverage — Non-Functional, Gap]

## Ambiguities & Conflicts

- [ ] CHK032 Is the conflict between Dependencies' "feature 015 timing fields the demo report *may* surface" and FR-025's "MUST include `phase_timings`" resolved as a single source of truth (must, not may)? [Conflict, Spec §FR-025/Dependencies]
- [ ] CHK033 Is the requirement that this feature is composable with feature 011 stage-runtime profiles defined, or is the demo CLI a sibling of feature 011 that does not use profiles? [Clarity, Spec §Dependencies, Gap]


---

**Plan coverage verification (2026-05-25):** see [plan-coverage.md](./plan-coverage.md) for the cross-reference of this checklist's items against `plan.md` / `research.md` / `data-model.md` / `contracts/` / `quickstart.md`.
