# Clarifications Consistency Checklist: GPU MVP Promotion

**Purpose**: Validate that the five decisions resolved by `/speckit.clarify` Session 2026-05-18 (jitter-band formula, Ollama `/api/ps` `size_vram == size`, wrong-interpreter via preflight only, canonical extraction = `ollama@gpu` only, voter-config-named model id) are reproduced consistently across every downstream artifact — spec, research, data-model, contracts, plan, tasks, quickstart, and the new GPU demo runbook — with no synonym drift, no residual ambiguity, and no contradictory remnant.
**Created**: 2026-05-18
**Feature**: [spec.md](../spec.md)

This checklist is a meta-quality gate: it tests whether the `/speckit.clarify` outcomes survived the subsequent `/speckit.plan` / `/speckit.tasks` artifact landing. Each clarification gets its own category. The principal failure mode is *clarification rot* — the answer is captured in the §Clarifications block but later sections were copy-edited from a pre-clarify draft and silently disagree.

## Q1 — Jitter-Band Formula (per phase key)

> **Answer**: `threshold = max(|legacy_run2 − legacy_run1|, |candidate_run2 − candidate_run1|)`; change is material iff `|candidate_run2 − legacy_run2| > threshold`. Per-document, per-phase-key.

- [ ] CHK001 Is the exact formula `max(|legacy_run2 − legacy_run1|, |candidate_run2 − candidate_run1|)` reproduced character-for-character in spec.md §FR-015, the Jitter Band entity, §Assumptions, and §Clarifications? [Consistency, Spec §FR-015, §Clarifications Q1]
- [ ] CHK002 Is the material-change rule stated as **strict** `>` (not `≥`) everywhere it appears (spec, research, contracts/appendix-recording, data-model)? [Consistency, Clarity, Spec §FR-015]
- [ ] CHK003 Is "per-document, per-phase-key" granularity reproduced wherever the jitter band is named (no place implies a global or per-document-aggregate band)? [Consistency, Spec §FR-015, §Jitter Band entity]
- [ ] CHK004 Is the formula free of any layered percentage band (e.g., "the larger of the formula or 5%") in research.md, data-model.md, and contracts/appendix-recording.md? [Consistency, Conflict, Spec §FR-015]
- [ ] CHK005 Does the term "material change" / "material decrease" wherever used (FR-016, SC-006, US3 Scenario 3, performance.md, benchmark.md) trace back to the Q1 formula with no synonym ("noticeable", "significant", "real") drift? [Consistency, Spec §FR-016, §SC-006]
- [ ] CHK006 Is the `threshold == 0` degenerate case (`legacy_run1 == legacy_run2 AND candidate_run1 == candidate_run2`) addressed identically in spec and research (any non-zero delta is material, OR explicit edge-case rule)? [Coverage, Spec §FR-015]

## Q2 — Ollama Readiness Check (`/api/ps` wire shape)

> **Answer**: `GET http://localhost:11434/api/ps`; assert the named entry has `size_vram > 0 AND size_vram == size`. Partial CPU/GPU split fails. Operator or shell helper outside the package — no new pipeline module.

- [ ] CHK007 Is `GET http://localhost:11434/api/ps` reproduced identically in spec §FR-002, §US1 Scenario 2, §Edge Cases, contracts/ollama-readiness-helper.md, and the GPU demo runbook contract? [Consistency, Spec §FR-002, §Clarifications Q2]
- [ ] CHK008 Is the assertion `size_vram > 0 AND size_vram == size` reproduced character-for-character in every place the check is described (no `>=`, no `>`, no `==` drift)? [Consistency, Clarity, Spec §FR-002]
- [ ] CHK009 Is the "partial CPU/GPU split fails the check" rule (i.e., `0 < size_vram < size`) explicitly named as FAIL in spec §Edge Cases and contracts/ollama-readiness-helper.md? [Consistency, Spec §FR-002, §Edge Cases]
- [ ] CHK010 Is the "operator or shell helper outside the package — no new pipeline module" constraint reproduced everywhere the check is described, consistent with FR-032's no-new-product-behavior boundary? [Consistency, Spec §FR-002, §FR-032]
- [ ] CHK011 Is the localhost-only assumption (`http://localhost:11434`) reproduced without a remote-Ollama escape hatch in any document (spec, runbook contract, helper contract)? [Consistency, Spec §FR-002]

## Q3 — Wrong-Interpreter Detection (preflight-only, no separate check)

> **Answer**: Paddle preflight is the authoritative gating contract. A wrong interpreter manifests as a non-`ppstructurev3_init_succeeded` state. The FR-003 interpreter path is recorded for forensics only; no separate interpreter-name check, env var, or wheel-symbol probe is added.

- [ ] CHK012 Is the FR-003 framing "interpreter path is forensic, not gating" reproduced consistently in spec §FR-003, §Clarifications, §Edge Cases ("Operator runs from the CPU `.venv`"), and gpu-readiness.md CHK017–CHK020? [Consistency, Spec §FR-003, §Clarifications Q3]
- [ ] CHK013 Is the spec free of any remnant text suggesting an interpreter allow-list, interpreter-name match, env-var probe, or wheel-symbol probe (the rejected alternatives)? [Consistency, Conflict, Spec §FR-003]
- [ ] CHK014 Is the "wrong interpreter manifests as a non-`ppstructurev3_init_succeeded` state" rule traceable from §Edge Cases through FR-001 (preflight is the gate) without losing the causal chain? [Traceability, Spec §FR-001, §FR-003, §Edge Cases]
- [ ] CHK015 Is the failure-mode enumeration in gpu-readiness.md CHK005 (CPU wheel, missing ROCm, no GPU device, wrong interpreter) consistent with Q3 — i.e., is "wrong interpreter" listed as a *manifestation* of preflight failure, not as a *separate* check? [Consistency, gpu-readiness.md CHK005, Spec §Clarifications Q3]
- [ ] CHK016 Does any document (research, plan, tasks, runbook contract) attempt to add an interpreter-validation step beyond what Q3 permits? [Consistency, Conflict, Gap]

## Q4 — Canonical Extraction Lane (`ollama@gpu` only, NOT `full-workstation`)

> **Answer**: `ollama@gpu` only. The documented demo path uses the atomic, explicit GPU profile for extraction. `full-workstation` is NOT used by the demo path; expanding/verifying that preset is left to a future feature so this slice remains validation/promotion-only.

- [ ] CHK017 Is `ollama@gpu` named as the only canonical demo extraction profile in spec §FR-025(b), §US5 narrative, §US5 Scenario 2, §US1 Scenario 3, contracts/runbook.md, and the new GPU demo runbook? [Consistency, Spec §FR-025, §Clarifications Q4]
- [ ] CHK018 Is every appearance of `full-workstation` in spec / plan / research / runbook contract qualified as "out of scope for this feature's demo path" or explicitly removed? [Consistency, Conflict, Spec §FR-025]
- [ ] CHK019 Is spec §Assumptions §8 (the `full-workstation` resolution path) reconciled with Q4 — i.e., does it state the §8 carve-out only applies to documentation framing, not to the demo path the runbook actually uses? [Conflict, Spec §Assumptions, §Clarifications Q4]
- [ ] CHK020 Is the "expanding/verifying `full-workstation` is left to a future feature" deferral reproduced in scope.md, promotion.md, and the new runbook, so a reviewer does not mistake it as a deliverable here? [Consistency, Spec §Clarifications Q4, §FR-032]
- [ ] CHK021 Is the demo command surface free of compound profile choices ("`ollama@gpu` OR `full-workstation`") in the actual command lines (as opposed to historical PRD prose)? [Consistency, Clarity, Spec §FR-025]

## Q5 — Voter-Config-Named Model ID (FR-002 model identity)

> **Answer**: The Ollama `/api/ps` entry whose `name` matches the active voter config's model identity (the same config feature 005's extractor consumes). Only that named entry is gated; other loaded models in `/api/ps` are ignored. The runbook spells out the resolution path so operators don't hardcode a model name.

- [ ] CHK022 Is the voter-config-derivation procedure ("read voter config X at key Y to get the model name; match against `/api/ps[].name`") documented identically in spec §FR-002, contracts/ollama-readiness-helper.md, AND the new GPU demo runbook? [Consistency, Completeness, Spec §FR-002, §Clarifications Q5]
- [ ] CHK023 Is the voter-config path (or "the same config feature 005's extractor consumes — see `specs/005-single-voter-extraction/contracts/voter-config.md`") cross-linked at least once in the helper contract and the runbook so an operator does not have to guess? [Traceability, Spec §FR-002]
- [ ] CHK024 Is "only that named entry is gated; other loaded models in `/api/ps` are ignored by the check" reproduced wherever multi-model behavior could be misread (helper contract, runbook, gpu-readiness.md CHK012)? [Consistency, Spec §FR-002]
- [ ] CHK025 Is the prohibition on hardcoding a model name in the helper or runbook explicit ("the runbook spells out the resolution path so operators don't hardcode")? [Clarity, Spec §Clarifications Q5]
- [ ] CHK026 Is the voter-config-derivation step free of any text suggesting the model name should be derived from the Ollama default-pull list, the `OLLAMA_MODELS` env var, or an Ollama Modelfile — all of which would violate Q5? [Consistency, Conflict, Spec §FR-002]

## Cross-Cutting Clarification Hygiene

- [ ] CHK027 Is every Q1–Q5 answer reproduced verbatim in spec §Clarifications, with the question text preserved (so a future reader sees what was asked and what was decided)? [Traceability, Spec §Clarifications]
- [ ] CHK028 Has any spec edit since Session 2026-05-18 introduced new ambiguity in territory that the session ruled on (i.e., are any new sentences inconsistent with Q1–Q5)? [Consistency, Spec-wide]
- [ ] CHK029 Do plan.md, research.md, data-model.md, and tasks.md each carry forward the Q1–Q5 decisions without re-opening any of them as a "to-decide" item? [Consistency, Spec §Clarifications]
- [ ] CHK030 Is the §Clarifications block stable — i.e., is there a written rule that further session decisions append (not overwrite) so historical resolution is auditable? [Clarity, Gap]
- [ ] CHK031 Are the five clarifications cross-referenced from the affected FRs (each FR that one of Q1–Q5 touched links back to §Clarifications), so a reviewer following the FR thread sees the resolution context? [Traceability, Spec §Clarifications]

## Notes

- This checklist tests whether the Clarifications decisions *propagated* through subsequent artifact landings; it does not re-litigate the decisions themselves.
- The principal failure mode is clarification rot — `/speckit.plan` or `/speckit.tasks` regenerating prose from a pre-clarify mental model and silently re-introducing the rejected alternative.
- A passing run of this checklist is a soft prerequisite for `/speckit.implement`: if Q1–Q5 do not survive the artifact set, implementation will diverge from the intended design even though every FR/SC reads "well-written" individually.
