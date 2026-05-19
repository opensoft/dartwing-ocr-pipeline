# GPU Readiness Gate Checklist: GPU MVP Promotion

**Purpose**: Validate that the requirements for the GPU readiness gate (Paddle preflight + Ollama placement + interpreter visibility + fail-fast posture) are written with the precision needed to make a "no silent CPU under GPU label" claim defensible.
**Created**: 2026-05-18
**Feature**: [spec.md](../spec.md)

This checklist tests the *requirements writing* of the readiness gate, not the gate's runtime behavior. Items target completeness, clarity, consistency, and measurability of the FR-001 through FR-005 surface and its supporting scenarios/entities.

## Preflight Gate Definition (FR-001)

- [X] CHK001 Is the FR-001 preflight invocation named precisely (`python -m dartwing_ocr.preprocessing.preflight`) in every place the gate is described? [Clarity, Consistency, Spec §FR-001]
- [X] CHK002 Is `state == "ppstructurev3_init_succeeded"` named as the single PASS literal, with no synonym (e.g., "preflight success", "preflight passes") drifting in user-story narrative? [Consistency, Spec §FR-001, §US1]
- [X] CHK003 Is the requirement to STOP on a non-success state stated in both FR-001 (system rule) and US1 scenarios (operator-observable behavior)? [Completeness, Spec §FR-001, §US1]
- [X] CHK004 Is the prerequisite that preflight runs BEFORE any GPU benchmark or GPU demo named explicitly, with no scenario allowing post-hoc preflight? [Clarity, Spec §FR-001]
- [X] CHK005 Are the failure modes preflight is expected to catch (CPU wheel, missing ROCm, no GPU device, wrong interpreter) enumerated so a reviewer can verify each is in the spec's mental model? [Completeness, Spec §FR-004, §Edge Cases]

## Ollama Check Definition (FR-002)

- [X] CHK006 Is the FR-002 check method (`GET http://localhost:11434/api/ps`) specified at the wire level (HTTP verb + path) rather than at the tool level (`ollama ps`)? [Clarity, Spec §FR-002]
- [X] CHK007 Is the assertion `size_vram > 0 AND size_vram == size` written identically in FR-002, the Edge Cases section, and US1 scenario 2? [Consistency, Spec §FR-002]
- [X] CHK008 Is partial GPU placement (`0 < size_vram < size`) explicitly named as a FAIL condition (not silently treated as success)? [Clarity, Spec §FR-002, §Edge Cases]
- [X] CHK009 Is the "model entry whose name matches the active voter config" rule unambiguous about which Ollama field is matched against which voter-config key? [Clarity, Spec §FR-002]
- [X] CHK010 Is the FR-002 "operator-run or shell helper outside the package" language explicit that no module inside `dartwing_ocr` is added? [Clarity, Spec §FR-002, §FR-032]
- [X] CHK011 Is the handling for "extraction model NOT loaded in Ollama at the time of the check" specified — does the check fail, retry, or instruct the operator to warm Ollama first? [Coverage, Gap]
- [X] CHK012 Is the handling for multiple loaded models in `/api/ps` consistent — does the check ignore non-matching entries (per Clarifications) or require all to be GPU-placed? [Consistency, Spec §FR-002, §Clarifications]
- [X] CHK013 Is the FR-002 check's localhost-only assumption (`http://localhost:11434`) explicit, or could a reviewer mistake it as applicable to remote Ollama? [Clarity, Spec §FR-002]

## Independence of Checks (FR-001 ∧ FR-002)

- [X] CHK014 Is the requirement that neither verdict substitutes for the other stated in both FR-001/FR-002 and the Edge Cases for one-side-pass scenarios? [Consistency, Completeness, Spec §FR-002, §Edge Cases]
- [X] CHK015 Are both edge cases (Paddle-pass/Ollama-fail and Ollama-pass/Paddle-fail) explicitly required to fail the composite gate? [Coverage, Spec §Edge Cases]
- [X] CHK016 Is the recording of each check's verdict required to be *separate* in the run record, so a reviewer can see which side failed? [Clarity, Spec §US1 Scenario 2]

## Interpreter Visibility (FR-003)

- [X] CHK017 Is FR-003 explicit that interpreter visibility is a *forensic* requirement, not a *gating* requirement (gating happens via FR-001)? [Clarity, Spec §FR-003, §Clarifications]
- [X] CHK018 Are the acceptable visibility surfaces (log line / run notes / `run_summary` field) enumerated, leaving implementor latitude without ambiguity? [Clarity, Spec §FR-003]
- [X] CHK019 Is "determinable from the run record" defined in operator-testable terms (a reviewer can pick the right interpreter path from the recorded artifact alone)? [Measurability, Spec §FR-003]
- [X] CHK020 Is the relationship between FR-003 (path visible) and the Q3 clarification (no path allowlist) consistent throughout the spec? [Consistency, Spec §Clarifications]
- [X] CHK021 Is the case "interpreter path is visible but is the wrong path" handled — i.e., is the spec clear that visibility alone is not gating, and preflight is what fails? [Coverage, Spec §Edge Cases]

## Fail-Fast Surface (FR-004)

- [X] CHK022 Is FR-004's composite fail-fast surface stated as the union of FR-001 + FR-002 (no third gate), so a reviewer can enumerate the failure paths? [Completeness, Spec §FR-004]
- [X] CHK023 Is "non-zero exit" specified at the FR level (not only at the SC level), so the requirement is uniformly testable? [Clarity, Spec §FR-004, §SC-002]
- [X] CHK024 Is "names the unmet prerequisite" defined precisely enough that a reviewer can confirm or reject a given error message? [Measurability, Spec §SC-002, §US1 Scenario 3]
- [X] CHK025 Is the prohibition "MUST NOT silently substitute the CPU profile or write a GPU-labelled artifact when running on CPU" stated in a single canonical location with cross-references, or is it duplicated? [Consistency, Spec §FR-004]
- [X] CHK026 Is the boundary between "GPU profile explicitly selected" (FR-004 applies) and "CPU profile explicitly selected" (FR-005 carve-out) precise enough to apply to a single command line? [Clarity, Spec §FR-004, §FR-005]

## CPU / Stub Preservation (FR-005)

- [X] CHK027 Is FR-005 explicit that CPU and stub profiles MUST remain available — i.e., is a future deletion forbidden? [Clarity, Spec §FR-005, §FR-030]
- [X] CHK028 Is the carve-out "MUST NOT require GPU preflight to run" stated for both `ppstructurev3@cpu` and the stub voter profile? [Coverage, Spec §FR-005]
- [X] CHK029 Are the CI implications of FR-005 (CPU/stub CI remains green) traceable to SC-010 ("CPU/stub CI remains green throughout this feature's landing")? [Traceability, Spec §FR-005, §SC-010]

## Composite Readiness Verdict Entity

- [X] CHK030 Is the GPU Readiness Verdict entity defined with all three composing facts (preflight state, Ollama placement, interpreter path)? [Completeness, Spec §Key Entities]
- [X] CHK031 Is the verdict's PASS condition stated as a single boolean expression (preflight succeeded AND Ollama fully GPU-backed)? [Clarity, Spec §Key Entities]
- [X] CHK032 Is the verdict's role ("used to gate every GPU benchmark and GPU demo run") stated in a way that ties to FR-001 and FR-018 (scratch-copy runs are still gated)? [Coverage, Spec §Key Entities]
- [X] CHK033 Is the verdict's recording medium implied or explicit — i.e., is there a single canonical place where the composite PASS/FAIL is observable per run? [Clarity, Gap]

## Edge Case Coverage

- [X] CHK034 Is the "Paddle pass, Ollama CPU-only" edge case requirement consistent with FR-002's `size_vram` rule? [Consistency, Spec §Edge Cases, §FR-002]
- [X] CHK035 Is the "Ollama pass, Paddle preflight non-success" edge case requirement consistent with FR-001's gating role? [Consistency, Spec §Edge Cases, §FR-001]
- [X] CHK036 Is the "wrong interpreter" edge case requirement consistent with the Q3 clarification (preflight authoritative, no separate interpreter check)? [Consistency, Spec §Edge Cases, §Clarifications]
- [X] CHK037 Is the "GPU hardware or runtime unavailable for the entire promotion attempt" edge case mapped to the Fallback discipline (skip-fallback off, CPU/stub CI baseline, blocked evidence recorded)? [Coverage, Spec §Edge Cases, §Fallback]

## Acceptance Criteria for Readiness

- [X] CHK038 Is SC-001 measurable against run records alone (no operator testimony) — i.e., can a reviewer count GPU-labelled runs and confirm 100% had both passing checks? [Measurability, Spec §SC-001]
- [X] CHK039 Is SC-002's "100% / Zero" framing free of soft hedges (no "should", no "typically")? [Clarity, Spec §SC-002]
- [X] CHK040 Is SC-003's "interpreter ambiguous" condition explicitly testable — i.e., is the negative case (the run record does not let a reviewer determine the interpreter) defined? [Measurability, Spec §SC-003]

## Gaps to Flag

- [X] CHK041 Are requirements defined for the case where Ollama is running but the extraction model is not yet loaded (cold-start sequence vs. failed gate)? [Gap]
- [X] CHK042 Are requirements defined for the case where the same readiness gate is invoked twice in rapid succession (idempotence expectations)? [Gap, Coverage]
- [X] CHK043 Are requirements defined for the demo case where readiness passes initially but Ollama unloads the model mid-demo (re-check obligation)? [Gap, Edge Case]
- [X] CHK044 Is the relationship between this feature's readiness gate and feature 016's `MIOPEN_FIND_MODE=2` warmup discipline explicit, or could a reviewer miss the dependency? [Gap, Traceability]

## Notes

- This checklist tests whether the readiness-gate *requirements* are well-written — not whether the gate itself behaves correctly.
- The principal failure mode for this surface is silent CPU execution under a GPU label; items CHK022–CHK026 and CHK034–CHK037 are the primary defense against it at the requirements-writing layer.
- Items CHK041–CHK044 flag genuine gaps that a future spec amendment may want to address; they are not necessarily blocking but should be reviewed.
