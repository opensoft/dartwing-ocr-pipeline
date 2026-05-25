# Idempotency / Determinism Requirements Quality Checklist: GPU MVP Demo Hardening

**Purpose**: Release-gate audit of idempotency and determinism requirements — the deterministic overwrite contract (FR-017), three-run stability (SC-006), overwrite scope (SC-010), and the "MVP integration-test checkpoint" promise.
**Created**: 2026-05-24
**Feature**: [spec.md](../spec.md)

## Deterministic Overwrite Contract

- [ ] CHK001 Is the eager-delete-at-run-start sequence defined precisely (before readiness? after readiness? before preprocessing?)? [Clarity, Spec §FR-017]
- [ ] CHK002 Is the requirement that re-running the demo against the same per-doc folder produces an operator-visible-equivalent outcome (modulo extraction variability) explicit? [Completeness, Spec §FR-017/SC-006]
- [ ] CHK003 Is the spec explicit that NO interactive prompt is issued (e.g., "overwrite stale artifacts? Y/n"), so automation can run the demo non-interactively? [Clarity, Spec §FR-017]
- [ ] CHK004 Is the requirement that no `--force` flag is required reconciled with the security concern about accidentally pointing `--document-folder` at the wrong path? [Conflict, Spec §FR-017/FR-027]

## Eager-Delete Failure Modes

- [ ] CHK005 Are requirements specified for partial-eager-delete failure (e.g., permission error on one of the four artifact paths)? [Coverage — Exception, Gap]
- [ ] CHK006 Is the spec explicit that eager-delete operates on the four canonical filenames only (no glob, no recursive delete), so the failure mode cannot escalate beyond the four paths? [Clarity, Spec §FR-017/SC-010]
- [ ] CHK007 Is eager-delete required to be idempotent on missing files (no failure if one of the four doesn't exist)? [Clarity, Spec §FR-017, Gap]

## Overwrite Scope

- [ ] CHK008 Is the exclusion list (`source.pdf`, `expected.json`, `notes.md`, `semantic_table_truth.json`, evaluation outputs, debug images) explicit and exhaustive in SC-010? [Completeness, Spec §SC-010]
- [ ] CHK009 Is the spec explicit about whether evaluation outputs from a previous `--with-evaluator` run persist (i.e., are NOT overwritten) into the next plain run? [Coverage, Spec §SC-010, Gap]
- [ ] CHK010 Are debug PNGs (`page_*.png`) from previous preprocessing runs explicitly preserved on subsequent runs, even though they are pipeline-produced artifacts? [Clarity, Spec §SC-010]

## Three-Run Stability (SC-006)

- [ ] CHK011 Is "same operator, same machine, same fixture" defined precisely enough that SC-006 is reproducible (i.e., excludes environmental changes like Ollama restart between runs)? [Clarity, Spec §SC-006]
- [ ] CHK012 Is the stability scope (schema-valid + identical `runtime_outcome` + identical `quality_status`) the *only* thing required, with no implicit byte-identity for extraction-influenced artifacts? [Clarity, Spec §SC-006]
- [ ] CHK013 Is the readiness verdict stability across three runs explicit (all 8 readiness checks return the same statuses on all three runs)? [Completeness, Spec §SC-006]
- [ ] CHK014 Is the cold-vs-warm cache implication addressed — e.g., the first of three runs may be cold (slow) but must still produce the same outcome class? [Coverage, Gap]

## Determinism of Sub-Module Output

- [ ] CHK015 Is the spec explicit about which of the four canonical artifacts is expected to be byte-deterministic (preprocess, routing, final_payload) and which is allowed to vary (edge_extraction_output due to model nondeterminism)? [Clarity, Spec §Round-2 Q10 implicit]
- [ ] CHK016 Is the requirement that `preprocess_output.json` be byte-identical across three runs (features 014–020 lineage of deterministic preprocessing) referenced? [Coverage, Spec §SC-006/Dependencies, Gap]
- [ ] CHK017 Is the requirement that `routing_decision.json` be byte-identical across three runs given the same `edge_extraction_output.json` referenced? [Coverage, Spec §Dependencies, Gap]

## Concurrent Execution

- [ ] CHK018 Are requirements specified for concurrent invocations of the demo command against the *same* per-doc folder (e.g., two operators on the same machine, or a re-launch before the previous run completes)? [Coverage — Edge Case, Gap]
- [ ] CHK019 Is the spec explicit about whether file-locking, lock files, or other concurrent-write guards are required, or whether operator discipline is sufficient? [Coverage, Gap]

## Re-Run After Partial Failure

- [ ] CHK020 Is the spec explicit that a re-run after a mid-run failure (which left partial new artifacts per FR-017) eagerly deletes those partial artifacts at the next run start? [Consistency, Spec §FR-017]
- [ ] CHK021 Is the operator workflow on a re-run after timeout defined (just re-run; no cleanup required)? [Clarity, Spec §FR-017, §US3 AS2]

## Side Effects on Caches

- [ ] CHK022 Are side effects on OS caches (`~/.cache/miopen`, `~/.cache/comgr` from feature 016) referenced as expected, so SC-006 stability is interpreted relative to them? [Completeness, Spec §Dependencies, Gap]
- [ ] CHK023 Is the spec explicit that the demo command does NOT clear or invalidate those caches (so warm-cache stability is preserved)? [Clarity, Gap]

## Determinism of Diagnostics

- [ ] CHK024 Is the diagnostic content (stderr lines) on identical failing inputs required to be deterministic across runs, or is run-to-run variation in diagnostic strings acceptable? [Coverage, Gap]
- [ ] CHK025 Is the `DemoRunReport` JSON's field-order stability across runs specified (so byte-comparison is meaningful), or is automation expected to be key-order-agnostic? [Coverage, Spec §FR-019, Gap]

## MVP Integration-Test Checkpoint Promise

- [ ] CHK026 Is the criterion for adopting the demo as the MVP integration-test checkpoint operationalized — three consecutive runs over a defined cadence (one day? one PR cycle?) with documented evidence? [Measurability, Spec §SC-006]
- [ ] CHK027 Is the "gates the start of Jetson edge-fast implementation" promise referenced as a deliverable handoff (e.g., a sign-off note in the runbook), so the gate is auditable? [Traceability, Spec §SC-006]

## Primary / Alternate / Exception / Recovery / Non-Functional Coverage

- [ ] CHK028 Are idempotency requirements defined for the **primary** flow (clean per-doc folder; one demo run)? [Coverage — Primary, Spec §FR-017]
- [ ] CHK029 Are idempotency requirements defined for **alternate** flows (re-run with stale artifacts; re-run with custom `--document-folder`; re-run after `--check-only`)? [Coverage — Alternate, Spec §FR-017, Gap]
- [ ] CHK030 Are idempotency requirements defined for **exception** flows (re-run after readiness fail; re-run after runtime fail; re-run after timeout)? [Coverage — Exception, Spec §FR-017/US3 AS2]
- [ ] CHK031 Are idempotency **recovery** requirements defined — i.e., a single re-run is sufficient to return to a known-clean state, no manual cleanup required? [Coverage — Recovery, Spec §FR-017]
- [ ] CHK032 Are idempotency **non-functional** properties specified (no race conditions; no time-of-check-to-time-of-use bugs on the four artifact paths)? [Coverage — Non-Functional, Gap]

## Ambiguities & Conflicts

- [ ] CHK033 Is the requirement that partial new artifacts remain on timeout (US3 AS2) consistent with the eager-delete on next run (FR-017) — i.e., operator inspects partial state *before* re-running, not in parallel with it? [Consistency, Spec §FR-017/US3 AS2]
- [ ] CHK034 Is the requirement that the demo never touches files outside the four canonical artifact paths (SC-010) consistent with the requirement to validate against the *folder* contract (which knows about `source.pdf`, `expected.json`, etc.)? [Consistency, Spec §SC-010, §FR-009]


---

**Plan coverage verification (2026-05-25):** see [plan-coverage.md](./plan-coverage.md) for the cross-reference of this checklist's items against `plan.md` / `research.md` / `data-model.md` / `contracts/` / `quickstart.md`.
