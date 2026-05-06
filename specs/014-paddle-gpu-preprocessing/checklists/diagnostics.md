# Diagnostics & Preflight Readout Checklist: Workstation Paddle GPU Preprocessing Validation

**Purpose**: Validate that diagnostic-output requirements (preflight readout completeness, FR-002 evidence fields, FR-003 actionability) are complete, clear, and consistent before implementation
**Created**: 2026-05-06
**Feature**: [spec.md](../spec.md)
**Domain**: FR-001 / FR-002 / FR-003 preflight readout shape, runtime device-exposure detection, recommendation strings, dual-format stdout

> Each item below tests the **requirements**, not the implementation.
> A diagnostic that doesn't tell a developer what to do is worse than
> no diagnostic; this checklist surfaces gaps in actionability and
> evidence completeness before code is written.

## Requirement Completeness

- [x] CHK001 - Are all FR-002 evidence fields enumerated with type, provenance, and presence-rule (always set / optional / set only when prior step succeeded)? [PASS, Data-model §PreflightEvidence] — All 13 fields enumerated with Type and Source/Provenance columns plus validation-rule presence semantics.
- [x] CHK002 - Are runtime device exposure flags (`/dev/dri`, `/dev/kfd`, `HIP_VISIBLE_DEVICES`, etc.) named in the spec, or only in research? [Resolved, Spec §FR-002 + Research R-014.10] — FR-002 now names `/dev/kfd`, `/dev/dri`, `HIP_VISIBLE_DEVICES`, `ROCM_PATH`, `CUDA_VISIBLE_DEVICES` and containerization indicators; R-014.10 details the full detection table.
- [x] CHK003 - Is the JSON payload's `kind`, `schema_version`, `state`, `evidence`, `recommendation` shape specified as a normative contract, or only as an example? [PASS, Contracts §1.Stdout shape] — Contracts/cli-contract.md specifies the exact JSON shape as a normative contract surface (with the caveat that the readout shape may evolve without amendment per Spec §Key Entities).
- [x] CHK004 - Are the conditions under which `ppstructurev3_init_skipped_reason` may be non-None enumerated (only `--no-init`, or any other case)? [PASS, Data-model §PreflightEvidence + Research R-014.3] — Only set to `"caller_disabled_init_attempt"` when the classifier is invoked with `attempt_ppstructurev3_init=False` (today, only via `--no-init`).
- [x] CHK005 - Is each FR-001 state's recommendation requirement specified (must reference a remediation; must point at a doc; must be one sentence)? [Resolved, Spec §FR-003] — FR-003 now requires each fail-state recommendation to (a) name a specific remediation action, (b) reference `docs/stage1-vendor-identity/paddle-gpu-preflight.md`, and (c) fit on one line.

## Requirement Clarity

- [x] CHK006 - Is "self-contained enough that a developer can decide the next action" (FR-003) defined operationally — what specifically must the readout name (file path? command? doc link?)? [Resolved, Spec §FR-003] — FR-003 now specifies "install command, container configuration change, or a runtime switch" plus the doc reference and one-line constraint.
- [x] CHK007 - Is the JSON payload's null-vs-absent semantics specified (e.g., is a field always present in JSON with `null` when unobserved, or sometimes omitted)? [PASS, Contracts §1.Stdout shape] — "Lines whose underlying field is `None` are omitted from the text section but always appear in the JSON object as `null`."
- [x] CHK008 - Is the human-readable text section's exact line ordering specified (alphabetical? evidence order? grouping by category)? [PASS, Contracts §1.Stdout shape] — Contracts gives the exact ordered template: state header → evidence fields in the documented order → blank line → recommendation.
- [x] CHK009 - Is the boundary between "I observed this" (evidence) and "I recommend that" (recommendation) explicit in requirement language? [PASS, Spec §FR-002 / §FR-003 + Data-model §PreflightReadout] — `evidence` field captures observations; `recommendation` field captures advice; the dataclass enforces the separation.
- [x] CHK010 - Is "single documented command" (FR-006) constrained to one specific invocation surface (e.g., `python -m …`) or open to alternatives? [PASS, Research R-014.1 + Contracts §1.Invocation] — Research R-014.1 picks `python -m ledgerlinc_ocr.preprocessing.preflight` and rejects alternatives; contracts fixes the form.

## Requirement Consistency

- [x] CHK011 - Are FR-002 evidence fields and the data-model `PreflightEvidence` dataclass aligned 1:1 (no drift)? [Resolved, Spec §FR-002 + Data-model §PreflightEvidence] — FR-002 now explicitly names data-model.md as the operational expansion and is satisfied if the readout surfaces every `PreflightEvidence` field; alignment is enforced by definition.
- [x] CHK012 - Are the six FR-001 states uniquely distinguishable from the readout alone (no two states could map to the same evidence)? [PASS, Data-model §PreflightEvidence validation rules + Research R-014.7] — Validation rules ensure each state corresponds to a distinct evidence pattern; classifier sequences guarantee unique entry points.
- [x] CHK013 - Are the FR-001 state names used consistently in (a) the readout, (b) exit-code mapping, (c) skip reasons, (d) error messages? [PASS, Research R-014.3 / R-014.5 / R-014.9 + Contracts §2] — Single enum source used verbatim in all four surfaces.

## Acceptance Criteria Quality

- [x] CHK014 - Can FR-001's "distinguishes at minimum all of the following states" be objectively verified by a table-driven classifier test? [PASS, Plan §Project Structure] — `tests/unit/test_preflight_classifier.py` is named as a "table-driven FR-001 state classification (mocked Paddle)" test.
- [x] CHK015 - Is SC-001's "within five minutes" measurable with a documented test (which environment, cold or warm weights)? [Resolved, Spec §SC-001] — SC-001 now specifies "five minutes wall-clock from a cold weights cache" with a separate "seconds rather than minutes" budget for warm runs.
- [x] CHK016 - Are the recommendation strings testable (e.g., must reference `paddle-gpu-preflight.md` for fail states)? [Resolved, Spec §FR-003 + Research R-014.11] — FR-003 now requires fail-state recommendations to reference `paddle-gpu-preflight.md`; this is unit-testable via regex match on the readout JSON.

## Scenario Coverage

- [x] CHK017 - Is the readout's behavior specified for the network-restricted-shell case (which fields *can* still be observed; what `state` is reported)? [PASS, Spec §Edge Cases + Data-model §PreflightEvidence + Research R-014.3] — `--no-init` flag triggers `ppstructurev3_init_skipped_reason="caller_disabled_init_attempt"`; the classifier still produces well-defined state classification through step 5 (bind probe).
- [x] CHK018 - Is the readout's behavior specified when paddle imports successfully but the wheel is mid-upgrade (e.g., `paddleocr` and `paddlepaddle` versions disagree)? [Resolved, Research R-014.7 §Edge-case behavior] — Both versions captured in evidence; if init fails because of mismatch, state is `PPSTRUCTUREV3_INIT_FAILED` with the captured exception. No separate state required.
- [x] CHK019 - Are the readout's stability guarantees specified across repeat invocations (which fields are stable, which are wallclock observations)? [PASS, Contracts §1.Determinism] — Contracts/cli-contract.md lists stable fields and enumerates `ppstructurev3_init_seconds` as the sole wallclock observation.
- [x] CHK020 - Are the FR-001 state-to-recommendation mappings traceable 1:1 (each state has exactly one recommendation template)? [PASS, Research R-014.10 + Spec §FR-003] — One recommendation template per state family; some states (e.g., GPU_NOT_EXPOSED) parameterize the recommendation by sub-evidence (missing /dev/kfd vs missing /dev/dri vs missing env vars).

## Edge Case Coverage

- [x] CHK021 - Is the readout's behavior defined when paddle imports but `paddle.is_compiled_with_cuda()` raises (e.g., paddle internals broken)? [Resolved, Research R-014.7 §Edge-case behavior] — Exception captured into evidence; classifier conservatively classifies as `PADDLE_CPU_ONLY` (safest fallback for remediation guidance).
- [x] CHK022 - Is the readout's behavior defined when `device_count > 0` but the bind probe times out rather than raises? [Resolved, Research R-014.7 §Edge-case behavior] — Bind probe runs synchronously without an explicit timeout; a hang is itself a diagnostic signal. Operator workaround: `timeout(1)` at the shell level. Adding a Python-level timeout is out of scope at stage 1.
- [x] CHK023 - Is the readout's behavior defined when the venv interpreter and the system interpreter disagree on paddle availability? [PASS, Spec §Edge Cases bullet 1 + Data-model §PreflightEvidence] — Spec mandates the readout report the exact executing interpreter; data-model exposes `interpreter_path` and `venv_path` so any disagreement is visible.

## Non-Functional Requirements

- [x] CHK024 - Is the readout's natural-language requirement specified (English only? localized? terminal-safe encoding)? [Resolved, Plan §Operational posture + Contracts §1.Output posture] — English UTF-8; localization out of scope for stage 1; terminal-safe (no ANSI).
- [x] CHK025 - Is the readout's privacy/PII posture specified (the readout includes paths and env-var presence — are any redactions required)? [Resolved, Plan §Operational posture + Contracts §1.Output posture] — Stage 1 is dev-internal; no automatic redaction required; operators sharing readouts publicly are responsible for their own review.
- [x] CHK026 - Is the readout's terminal-rendering requirement specified (e.g., must render in 80-column terminals, must avoid ANSI escapes by default)? [Resolved, Plan §Operational posture + Contracts §1.Output posture] — No ANSI escapes; 80-column soft target; long evidence values may exceed it as a diagnostic necessity.

## Dependencies & Assumptions

- [x] CHK027 - Are the assumptions about Paddle 3.x stable APIs (`is_compiled_with_cuda`, `is_compiled_with_rocm`, `device.cuda.device_count`) documented as dependencies the classifier relies on? [PASS, Research R-014.7] — R-014.7 documents the four Paddle 3.x APIs as stable dependencies; grounded via `mcp__plugin_context7_context7__query-docs` against `/paddlepaddle/docs`.
- [x] CHK028 - Is the assumption that PPStructureV3 init exceptions surface meaningful messages documented (vs. opaque internal errors)? [Resolved, Research R-014.7 §Edge-case behavior §PaddleOCR exception class taxonomy] — `str(exc)` is captured verbatim into evidence (truncated to 1000 chars per data-model); the classifier does NOT depend on a specific exception-class taxonomy.

## Ambiguities & Conflicts

- [x] CHK029 - Does FR-005 ("must not use Ollama GPU state as evidence") conflict with detecting `HIP_VISIBLE_DEVICES` (which Ollama also sets)? [Resolved, Spec §FR-005 / §Clarifications 2026-05-06 / Research R-014.10] — FR-005 now distinguishes Ollama-process-specific state from shared host GPU-exposure evidence. `HIP_VISIBLE_DEVICES` is a host-environment indicator that any GPU-aware process sets; it is allowed as FR-002 evidence and never alone satisfies state (f).
- [x] CHK030 - Is "in plain language" (Spec §US1) defined in measurable terms, or is it left to author judgment? [Resolved, Spec §FR-003] — FR-003 now operationalizes "plain language" via the one-line constraint: avoid jargon, name the issue once, state the next user action.

## Notes

- This checklist tests requirement quality, not implementation behavior.
- Items marked `[Resolved]` had a wording-only gap patched in spec/plan/research/data-model/contracts during the 2026-05-06 checklist-resolution pass.
- Items marked `[PASS]` were already satisfied by existing artifacts at the time of evaluation.
