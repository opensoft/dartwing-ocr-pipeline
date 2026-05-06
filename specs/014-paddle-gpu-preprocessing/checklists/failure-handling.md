# Failure Handling & FR-001 State Vocabulary Checklist: Workstation Paddle GPU Preprocessing Validation

**Purpose**: Validate that failure-handling requirements (preflight gate, fail-fast, multi-doc abort, error contracts) are complete, clear, and consistent before implementation
**Created**: 2026-05-06
**Feature**: [spec.md](../spec.md)
**Domain**: FR-001 state vocabulary, FR-009/FR-010 fail-fast, R-014.4 abort-on-first-GPU-failure, exit codes, error message contracts

> Each item below tests the **requirements**, not the implementation.
> Three of the five clarifications introduced new failure paths; this
> checklist surfaces gaps before implementers have to choose
> defaults.

## Requirement Completeness

- [x] CHK001 - Are all six FR-001 states defined with mutually exclusive entry conditions (no overlap, no gap)? [PASS, Spec §FR-001 + Research R-014.7] — R-014.7 sequences classifier steps so each FR-001 state has a unique entry point; data-model validation rules enforce no overlap.
- [x] CHK002 - Is an exit code specified for every FR-001 fail state? [PASS, Contracts §1.Exit codes + Research R-014.5] — All six states map to exit codes 0/10/11/12/13/14; classifier-internal errors map to exit 2.
- [x] CHK003 - Are recovery requirements defined after a multi-doc GPU abort (e.g., what state must the corpus be in afterward, can the run be resumed)? [Resolved, Plan §Operational posture + Quickstart §1–2] — Plan documents the recovery loop (fix prereq, re-run preflight, re-run pipeline); harness has no automatic resume — successful docs retain artifacts, failed/skipped docs must be re-run.
- [x] CHK004 - Is the failure path defined when the preflight classifier itself crashes (not a paddle/import error, but a classifier bug)? [PASS, Contracts §1.Stderr + §1.Exit codes] — Internal classifier crash returns exit code 2 with a reserved stderr format; recoverable FR-001 states surface on stdout instead.
- [x] CHK005 - Are the failure semantics for network-restricted shells specified (init skipped vs. init failed; readout still actionable)? [PASS, Spec §Edge Cases + Research R-014.3 + Data-model §PreflightEvidence] — `--no-init` sets `attempt_ppstructurev3_init=False`; the readout records `ppstructurev3_init_skipped_reason` and labels the step "not exercised" rather than "failed".

## Requirement Clarity

- [x] CHK006 - Is the boundary between "GPU init failure" (preflight gate) and "per-document GPU inference failure" (post-gate) specified precisely so an implementer can decide which code path catches which exception class? [PASS, Spec §FR-009 / §FR-010 + Research R-014.4] — FR-009 covers pre-artifact gate failures; FR-010 covers per-doc inference failures after the gate; R-014.4 separates the two control-flow paths.
- [x] CHK007 - Are FR-001 state name strings (e.g., `paddle_cpu_only`) normative — used verbatim in error messages and JSON payloads — or merely descriptive labels? [PASS, Research R-014.3 + Contracts §2] — `PreflightState` enum values are the single source of truth and are used verbatim in JSON, exit-code mapping, error messages, and skip reasons.
- [x] CHK008 - Is "fail before any artifact write" defined per-document, per-run, or both, when the GPU lane is selected for a multi-doc warm-corpus run? [PASS, Spec §FR-009 + Contracts §2.Pre-write GPU gate] — Per-run gate: classifier runs once before the first artifact; on any non-success state, no artifact is written for any document in the run.
- [x] CHK009 - Is the user-vs-system boundary explicit in error message requirements (what should the user fix vs. what indicates a system bug)? [Resolved, Spec §FR-003] — FR-003 now requires each fail-state recommendation to name a specific remediation action (install command, container change, runtime switch); recoverable FR-001 states are user-fixable, classifier-internal errors (exit 2) are system bugs.

## Requirement Consistency

- [x] CHK010 - Are FR-009, FR-010, and Clarification Q3 internally consistent on multi-doc abort semantics (no scenario where they disagree)? [PASS, Spec §FR-009 / §FR-010 / §Clarifications Q3 + Research R-014.4] — All three converge on: pre-artifact gate failures use FR-009 fail-fast; post-gate per-doc failures use FR-010 abort-on-first; `gpu_lane_forced_abort: true` records the override.
- [x] CHK011 - Is the FR-001 state vocabulary used consistently in (a) preflight readout, (b) pipeline error messages, (c) pytest skip reasons, (d) `run_summary.per_document.message`? [PASS, Research R-014.3 / R-014.5 / R-014.9 / R-014.4] — Single enum source; states used verbatim in all four surfaces.
- [x] CHK012 - Do the existing feature-011 `--on-failure` semantics and the Q3 GPU-lane override use compatible terminology in the spec (no contradiction with `continue` mode being silently overridden)? [PASS, Research R-014.4] — Override is documented as behavioral (not flag-level); user's requested `on_failure` is preserved in `run_summary.on_failure` while `gpu_lane_forced_abort: true` records the override.

## Acceptance Criteria Quality

- [x] CHK013 - Is "100% of attempts" in SC-003 defined with a measurable test method (how many attempts, on which environments)? [PASS, Plan §Contract Test Coverage point 5] — `tests/integration/test_pipeline_gpu_gate_failfast.py` injects each FR-001 fail state via mocked classifier and asserts no artifact write + correct stderr + correct exit code; covers all five fail states.
- [x] CHK014 - Can FR-009 ("failure message names both the selected profile and the specific missing GPU prerequisite") be objectively verified by a unit test? [PASS, Contracts §2.Pre-write GPU gate + Plan §Contract Test Coverage point 5] — Stderr format `error: --preprocess-profile=ppstructurev3@gpu: <STATE>; <recommendation>` is unit-testable via mocked FR-001 states.

## Scenario Coverage

- [x] CHK015 - Are requirements specified for **primary** GPU success path? [PASS, Spec §US2 Acceptance #1 / §FR-014 / §FR-016] — Primary path: artifact written, schema-valid, lane segment in `pipeline_version`.
- [x] CHK016 - Are requirements specified for **alternate** GPU paths (e.g., second device index, DCU fallback) or are they explicitly out of scope? [Resolved, Spec §Out Of Scope] — Out Of Scope now explicitly excludes multi-GPU device selection and non-x86-CUDA / non-ROCm lanes (DCU, NPU, XPU, MetaX, Iluvatar).
- [x] CHK017 - Are requirements specified for **exception** paths — each FR-001 fail state, including init-time vs. inference-time? [PASS, Spec §FR-001 / §FR-009 / §FR-010] — Init-time = FR-009 gate; inference-time = FR-010 per-doc abort; both control-flow paths covered.
- [x] CHK018 - Are requirements specified for **recovery** paths (e.g., user installs the right wheel, re-runs preflight, then re-runs the pipeline)? [Resolved, Plan §Operational posture + Quickstart §1–2] — Plan documents the four-step recovery loop end-to-end.
- [x] CHK019 - Are requirements specified for **partial failure** mid-corpus (which artifacts exist, which don't, what `run_summary` looks like)? [PASS, Research R-014.4 + Contracts §2 / §3] — Successful docs retain artifacts; failed doc + subsequent docs have no artifacts; partial `run_summary` emitted with `gpu_lane_forced_abort: true`.

## Edge Case Coverage

- [x] CHK020 - Are the failure semantics for "preflight gate passes but the very first per-document inference call fails" defined (init-time vs. first-doc inference is a real distinction)? [PASS, Spec §FR-010 + Research R-014.4] — First-doc inference failure is the canonical FR-010 case; aborts the run with `gpu_lane_forced_abort: true`.
- [x] CHK021 - Is the failure path defined when GPU init succeeds, the first document succeeds, but the second document hits ROCm OOM (mid-corpus)? [PASS, Spec §Edge Cases + Research R-014.4] — Edge-case bullet covers ROCm OOM mid-document; multi-doc abort applies regardless of which document index fails first.
- [x] CHK022 - Are the failure semantics for `stub@gpu` (which must be rejected) consistent with the rejection of any other invalid lane combinations? [PASS, Spec §FR-011 + §Edge Cases bullet 5 + Contracts §2.Profile vocabulary] — `stub` remains lane-less by parser construction; `stub@gpu` and any other `stub@<lane>` are rejected at flag parse time.
- [x] CHK023 - Is the failure path defined when PaddleOCR is mid-version-upgrade and `device="gpu:0"` accepts but binds to a different device than reported? [Resolved, Research R-014.7 §Edge-case behavior] — Classifier records whatever device Paddle bound (`evidence.selected_device`) and proceeds; reconciling driver-level inconsistencies is Paddle's responsibility, not the classifier's.

## Non-Functional Requirements

- [x] CHK024 - Is the latency budget for preflight specified (SC-001 says "within five minutes" — is that wallclock from cold weights, warm weights, or both)? [Resolved, Spec §SC-001] — SC-001 now specifies "five minutes wall-clock from a cold weights cache" with a separate "seconds rather than minutes" budget for warm runs.
- [x] CHK025 - Are the security/privacy implications of error messages specified (do error messages need to redact paths, env vars, or other host details)? [Resolved, Plan §Operational posture + Contracts §1.Output posture] — Stage 1 is dev-internal; no automatic redaction required; operators sharing readouts publicly are responsible for their own review.

## Dependencies & Assumptions

- [x] CHK026 - Is the assumption that `--on-failure` flag's `continue` default is overridable at runtime (per Q3) documented in the existing feature-011 contract, or is the override a new requirement? [PASS, Research R-014.4] — The override is a new requirement introduced by this feature; documented as a runtime decision in `corpus_run.py` with `gpu_lane_forced_abort: true` audit record.
- [x] CHK027 - Are the dependencies on PaddleOCR's exception classes (which exception means "GPU build mismatch" vs. "OOM") documented as assumptions or pinned via test? [Resolved, Research R-014.7 §Edge-case behavior §PaddleOCR exception class taxonomy] — Classifier does NOT rely on exception-class taxonomy; state is determined by which classifier step raised. `str(exc)` is captured verbatim into evidence.

## Ambiguities & Conflicts

- [x] CHK028 - Does FR-005 ("must NOT use Ollama GPU state as evidence") conflict with the runtime device exposure heuristics in R-014.10 (which detect HIP/ROCm env vars Ollama also uses)? [Resolved, Spec §FR-005 / §Clarifications 2026-05-06 / Research R-014.10] — FR-005 now narrows "Ollama GPU state" to *Ollama-process-specific* signals (daemon running, serving, GPU-bound). Shared host indicators (`/dev/kfd`, `/dev/dri`, `HIP_VISIBLE_DEVICES`, `ROCM_PATH`, `CUDA_VISIBLE_DEVICES`) are GPU-exposure evidence under FR-002, not Ollama state. R-014.10 cross-references this resolution.
- [x] CHK029 - Is "the failure must be attributable to the GPU profile" (Spec §US2 #5) defined operationally (which field in which output makes it attributable)? [Resolved, Research R-014.4 + Contracts §2 / §3] — Attribution is via `pipeline_version` lane segment (`.gpu0`) on the artifact (when produced) and `gpu_lane_forced_abort: true` on the `run_summary.per_document` failure record.

## Notes

- This checklist tests requirement quality, not implementation behavior.
- Items marked `[Resolved]` had a wording-only gap patched in spec/plan/research/data-model/contracts during the 2026-05-06 checklist-resolution pass.
- Items marked `[PASS]` were already satisfied by existing artifacts at the time of evaluation.
