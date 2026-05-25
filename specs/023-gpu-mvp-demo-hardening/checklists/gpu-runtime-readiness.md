# GPU Runtime Readiness Requirements Quality Checklist: GPU MVP Demo Hardening

**Purpose**: Release-gate audit of the feature's domain-specific requirements quality — GPU placement detection, CPU fallback prevention, Paddle ROCm preflight, Ollama version/context-length checks, multi-Ollama disambiguation, and stale-wheel detection.
**Created**: 2026-05-24
**Feature**: [spec.md](../spec.md)

## GPU Placement Detection

- [ ] CHK001 Is the GPU-placement rule (`size_vram > 0 AND size_vram == size`) precise and arithmetically unambiguous (no tolerance window)? [Clarity, Spec §FR-005]
- [ ] CHK002 Are both `size` and `size_vram` required to be read from the same `/api/ps` entry (no merging across multiple entries)? [Consistency, Spec §FR-005]
- [ ] CHK003 Is the spec explicit that the GPU-placement check operates on the model *identified by the active voter config*, not the first model in `/api/ps`? [Clarity, Spec §FR-005]
- [ ] CHK004 Is the failure-class assignment specified — partial placement (`size_vram < size`) → `ollama-model-gpu-placement` fail, not `ollama-version`? [Consistency, Spec §FR-005/FR-023]

## CPU Fallback Prevention (SC-004)

- [ ] CHK005 Is SC-004 ("CPU-mode result is never reported as success") operationalized — what is the *test* that distinguishes CPU from GPU at run end? [Measurability, Spec §SC-004/FR-012]
- [ ] CHK006 Is post-run device interrogation (FR-012) specified to query the *same* model identity, so a swap mid-run is detected? [Completeness, Spec §FR-012, Gap]
- [ ] CHK007 Is the spec explicit that timing-based heuristics are NOT used for CPU-fallback detection (round-2 Q9 chose interrogation over timing)? [Clarity, Spec §FR-012]
- [ ] CHK008 Is the failure-class assignment for post-run-detected CPU fallback specified (which `runtime_outcome` value, which exit code)? [Completeness, Spec §FR-012, Gap]

## Paddle ROCm Preflight (FR-002)

- [ ] CHK009 Is the spec explicit that the Paddle ROCm preflight is feature 014's existing preflight, not a new one in this feature? [Clarity, Spec §FR-002, Dependencies]
- [ ] CHK010 Is the preflight's expected outcome (Paddle device backend confirmed as GPU) required to be surfaced in the demo report? [Completeness, Spec §US1 AS2]
- [ ] CHK011 Are requirements specified for the case where Paddle imports successfully but the device check reports CPU (e.g., stale wheel, missing ROCm)? [Coverage — Edge Case, Spec §Edge Cases]
- [ ] CHK012 Is the post-run Paddle device interrogation (FR-012) defined as comparing the *post-run* backend with the *preflight* backend? [Coverage, Spec §FR-012, Gap]

## Ollama Version Check (FR-023)

- [ ] CHK013 Is the version probe specified as part of the readiness phase, with a fast failure if version is below minimum? [Clarity, Spec §FR-023]
- [ ] CHK014 Is the named `ollama-version` check enumerated in the FR-016 closed vocabulary, consistent across all spec sections? [Consistency, Spec §FR-016/FR-023]
- [ ] CHK015 Is the version-comparison rule explicit (semver vs string comparison vs `version >= minimum`)? [Clarity, Spec §FR-023]
- [ ] CHK016 Is the "old Ollama omits `size_vram`" edge case (FR-023) explicitly handled by the `ollama-version` check, not by the `ollama-model-gpu-placement` check, so the operator gets an upgrade diagnostic rather than a placement diagnostic? [Consistency, Spec §FR-023/Edge Cases]

## Ollama Context-Length Check (FR-006)

- [ ] CHK017 Is the context-length check specified as part of the readiness phase, with a clear failure when `/api/ps` exposes a context length below the required value? [Clarity, Spec §FR-006]
- [ ] CHK018 Is the runtime fallback (the extraction call fails with a context-window error pointing at the startup script) defined for the case where `/api/ps` does NOT expose the value? [Coverage, Spec §FR-006]
- [ ] CHK019 Is the required `OLLAMA_CONTEXT_LENGTH` value (2048 or "the documented required value") referenced as a single source of truth in the runbook? [Consistency, Spec §FR-006]

## Multi-Ollama Disambiguation

- [ ] CHK020 Is the spec explicit about the rule for selecting the correct Ollama instance when multiple are running (host + container)? [Clarity, Spec §Edge Cases]
- [ ] CHK021 Is "the host Ollama instance identified by the active configuration" defined precisely — e.g., the URL is `localhost:11434` and matches `OLLAMA_BASE_URL`? [Clarity, Spec §Edge Cases, Gap]
- [ ] CHK022 Is the failure mode for hitting the wrong Ollama (e.g., container Ollama responding instead of host) specified (which named check fails)? [Coverage — Edge Case, Spec §Edge Cases, Gap]

## Stale Paddle Wheel Detection

- [ ] CHK023 Is the requirement that a stale or uninstalled Paddle ROCm wheel MUST fail at the Paddle preflight stage (not degrade to CPU silently) enforceable from the spec alone? [Clarity, Spec §Edge Cases]
- [ ] CHK024 Are the symptoms of a stale wheel (import succeeds, device check fails) vs an uninstalled wheel (import fails) both classified under the `paddle-rocm-preflight` check, or are they distinguished? [Coverage, Spec §Edge Cases, Gap]
- [ ] CHK025 Is the operator-facing diagnostic for a stale-wheel failure required to suggest a remediation action (e.g., reinstall the wheel)? [Completeness, Gap]

## Interpreter / Venv Check

- [ ] CHK026 Is the `interpreter/venv` check's pass criterion explicit (interpreter path matches `.venv-paddle-rocm/bin/python` or its successor)? [Clarity, Spec §FR-002/FR-003]
- [ ] CHK027 Is the operator obligation to activate the venv before running the demo explicit, with the diagnostic explaining how to switch venvs on failure? [Completeness, Spec §FR-003, Gap]
- [ ] CHK028 Is the `.venv-paddle-rocm` "or its established successor" wording defined precisely enough that an audit can decide whether the running venv satisfies the requirement? [Clarity, Spec §FR-002]

## Cold Cache vs Warm Cache

- [ ] CHK029 Is the spec explicit about cold-cache implications on readiness (Paddle import is slower; first Ollama call may be slower), and whether the 10 s preflight bound holds in cold-cache state? [Coverage, Spec §SC-007, Gap]
- [ ] CHK030 Is the relationship between feature 016's MIOpen/COMGR cache warmup and this feature's readiness checks specified — does the demo command rely on warmup, or runs the warmup itself? [Completeness, Spec §Dependencies, Gap]

## Primary / Alternate / Exception / Recovery / Non-Functional Coverage

- [ ] CHK031 Are GPU-readiness requirements defined for the **primary** flow (all checks pass; full GPU placement; warm caches)? [Coverage — Primary, Spec §FR-005/FR-002]
- [ ] CHK032 Are GPU-readiness requirements defined for **alternate** flows (partial GPU placement; old Ollama version; multiple Ollama instances)? [Coverage — Alternate, Spec §FR-005/FR-023/Edge Cases]
- [ ] CHK033 Are GPU-readiness requirements defined for **exception** flows (every named GPU-readiness check failing in isolation)? [Coverage — Exception, Spec §FR-016]
- [ ] CHK034 Are GPU-readiness **recovery** requirements defined (operator action per failure class)? [Coverage — Recovery, Gap]
- [ ] CHK035 Are GPU-readiness **non-functional** properties quantified (readiness completes in ≤10 s warm; the 8 checks have individual sub-budgets)? [Coverage — Non-Functional, Spec §SC-007]

## Ambiguities & Conflicts

- [ ] CHK036 Is the FR-005 strict-equality rule (`size_vram == size`) consistent with the FR-023 "older Ollama omits `size_vram`" rule — i.e., the version check pre-empts the placement check when `size_vram` is absent? [Conflict, Spec §FR-005/FR-023]
- [ ] CHK037 Is the relationship between FR-007 (fail fast on Ollama issues) and FR-018 (`--check-only` mode) consistent — `--check-only` SHOULD also fail fast on the same conditions, with no pipeline run? [Consistency, Spec §FR-007/FR-018]


---

**Plan coverage verification (2026-05-25):** see [plan-coverage.md](./plan-coverage.md) for the cross-reference of this checklist's items against `plan.md` / `research.md` / `data-model.md` / `contracts/` / `quickstart.md`.
