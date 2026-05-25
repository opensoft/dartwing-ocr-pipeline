# Audit Checklist Walkthrough — 2026-05-25

**Purpose:** Walk all 15 audit checklists and identify items that surface genuine open questions (vs items satisfied by existing spec/plan/research/contracts). Output: a consolidated, focused block of 12 net-new clarifying questions.

**Pre-existing state:** `/speckit.analyze` returned GREEN; 32 spec clarifications + triage + plan-coverage-remediation already closed. The 514 audit items below are scanned for items NOT already covered by those passes.

---

## Per-file scan summary

| File | Total | Satisfied (rationale below) | Raises Q? | Open question IDs |
|---|---:|---:|---:|---|
| `ux.md` | 30 | 28 | 2 | Q1, Q2 |
| `api.md` | 32 | 31 | 1 | Q6 |
| `data-model.md` | 39 | 36 | 3 | Q3, Q13, Q14 |
| `security.md` | 30 | 29 | 1 | Q5 |
| `performance.md` | 30 | 29 | 1 | Q9 |
| `error-handling.md` | 38 | 37 | 1 | Q4 |
| `observability.md` | 36 | 35 | 1 | Q10 (cross-file with integration) |
| `integration.md` | 33 | 32 | 1 | Q10 |
| `configuration.md` | 34 | 33 | 1 | Q12 |
| `idempotency.md` | 34 | 34 | 0 | — |
| `testing-strategy.md` | 35 | 34 | 1 | Q8 |
| `deployment.md` | 33 | 32 | 1 | Q11 |
| `gpu-runtime-readiness.md` | 37 | 36 | 1 | Q7 |
| `demo-report-shape.md` | 40 | 39 | 1 | Q15 |
| `requirements.md` (cross-cutting) | 36 | 36 | 0 | — |
| **Total** | **517** | **501** | **15 items → 12 unique Qs** | |

**Satisfaction sources** (most-referenced):

- 14 audit files were already mapped against `plan.md` / `research.md` / `data-model.md` / `contracts/*.md` in `plan-coverage.md` (49 Category-D items closed by R-023.1–R-023.21).
- Spec FRs (28 of them) cover ~210 audit items directly.
- Triage-2026-05-24 closed 17 conflicts + 3 ambiguities at spec level (rolled into the spec itself).
- The plan-coverage remediation pass closed 15 plan-level findings.

The 501 "satisfied" items are NOT individually walked here — they all trace to one of those sources. The 12 net-new questions below are the ones that surface genuine open decisions.

---

## Clarifying questions (12)

Reply with the option letter, "yes" / "recommended" to accept the recommendation, or a short answer (<=5 words). You can answer all 12 at once or in batches; I'll integrate the answers into spec.md / plan.md / data-model.md / contracts/* as appropriate.

## Accepted Answers

- **Q1**: A — emit final `INFO:[run_id] runtime: success / quality: <status>` to stderr on successful full runs.
- **Q2**: A — emit final `INFO:[run_id] readiness passed (<elapsed>s)` to stderr on successful `--check-only` runs.
- **Q3**: A — `quality_status = null` whenever `runtime_outcome != "success"`, including timeout, every `failed_at_<phase>`, readiness failure, invalid input, and `--check-only`.
- **Q4**: A — keep `quality_status_source = "gate"` when `--with-evaluator` is requested but skipped because `semantic_table_truth.json` is absent; the stderr `WARN:` line is the audit trail.
- **Q5**: A — truncate embedded JSON blobs in `CheckDiagnostic.observed` at 2 KiB with a trailing `… [truncated]` sentinel.
- **Q6**: Suggested — evaluator subprocess invocation is `python -m dartwing_ocr.evaluator evaluate-document --folder <doc-folder> --quiet`, with `cwd=<doc-folder>`, inherited environment, and 60 s timeout.
- **Q7**: A — keep a single `paddle-rocm-preflight` check name, but distinguish stale wheel vs uninstalled Paddle through different `observed` shapes and remediation strings.
- **Q8**: A — add `specs/023-gpu-mvp-demo-hardening/coverage-fr-task-test.md` during Phase 7 polish, mirroring feature 022.
- **Q9**: A — keep SC-007 warm-only at 10 s and add a 30 s cold-cache informal target to the runbook.
- **Q10**: B — capture and replay sub-module stderr through `log.info(run_id, f"<phase>: <line>")` so every stderr line has run_id and phase context.
- **Q11**: B — add a runbook appendix for colleague dry-run sign-off; do not add a new success criterion.
- **Q12**: A — demo reads only `OLLAMA_BASE_URL` and `OLLAMA_CONTEXT_LENGTH`; ROCm/HSA vars remain operator-managed through the startup script and inherited environment.

### Q1. Success-run stderr signal (origin: ux.md:CHK017)

**Recommended:** Option A — emit one final `INFO:[run_id] runtime: success / quality: <status>` stderr line on the success path. Operators get a clear visual cue without parsing JSON; automation ignores stderr.

| Option | Description |
|--------|-------------|
| A | Emit final `INFO:[run_id] runtime: success / quality: <status>` line to stderr before the JSON-line stdout emit |
| B | Stay silent on success; operators rely on exit 0 + the stdout JSON line |
| C | Emit only when an interactive tty is attached to stderr (auto-quiet when piped) |

---

### Q2. `--check-only` pass stderr signal (origin: ux.md:CHK019)

**Recommended:** Option A — same pattern as Q1: emit `INFO:[run_id] readiness passed (X.XXs)` on success. Consistent with the full-run pattern (Q1).

| Option | Description |
|--------|-------------|
| A | Emit final `INFO:[run_id] readiness passed (<elapsed>s)` to stderr on `--check-only` success |
| B | Stay silent; exit 0 + JSON line is enough |
| C | Emit only when interactive |

---

### Q3. `quality_status` value when `runtime_outcome` is a `failed_at_<phase>` value (origin: data-model.md:CHK032 + demo-report-shape.md:CHK032)

**Recommended:** Option A — `quality_status` is `null` whenever `runtime_outcome != "success"` (including timeout and every `failed_at_<phase>`). Quality is not assessed when the pipeline didn't complete. This tightens FR-019/FR-020's stable-shape rule.

| Option | Description |
|--------|-------------|
| A | `quality_status = null` whenever `runtime_outcome != "success"` (covers timeout + all `failed_at_<phase>` + readiness-fail + invalid-input + `--check-only`) |
| B | Compute `quality_status` from whatever artifacts exist on disk, even partial — useful for debugging |
| C | `null` when `runtime_outcome == null` (no pipeline ran); compute "review_required" sentinel for any `failed_at_<phase>` (pipeline started but did not finish — never declare quality "pass") |

---

### Q4. `quality_status_source` distinguishability on `--with-evaluator` warn-and-skip (origin: error-handling.md:CHK020)

**Recommended:** Option A — keep `"gate"` (per R-023.20) for both "operator passed `--with-evaluator` but sidecar missing" and "operator never passed `--with-evaluator`". Both cases derive quality from the gate alone. The stderr `WARN:` line is the audit trail for the distinction; the report field doesn't need to encode it.

| Option | Description |
|--------|-------------|
| A | Keep `quality_status_source = "gate"` for both cases; the stderr `WARN:` line is the audit trail (current R-023.20) |
| B | Add a third value `"gate_after_evaluator_skip"` so automation can distinguish the warn-and-skip case from the no-flag case |
| C | Add a separate boolean field `evaluator_requested: bool` to disambiguate without changing the enum |

---

### Q5. `/api/ps` JSON-snippet truncation in `CheckDiagnostic.observed` (origin: security.md:CHK013)

**Recommended:** Option A — truncate any embedded `/api/ps` snippet (or any large JSON blob inside `observed`) to **2 KiB**, with a trailing `… [truncated]` sentinel. Keeps the demo report bounded and prevents an unusually-large model record from blowing up the JSON line.

| Option | Description |
|--------|-------------|
| A | Truncate embedded JSON blobs in `observed` at 2 KiB with `… [truncated]` sentinel |
| B | Truncate at 4 KiB (more generous; allows multi-model `/api/ps` entries) |
| C | No truncation; rely on the natural size of `/api/ps` entries being small |
| D | Truncate AND record the original byte length in a sibling field `observed_original_bytes` |

---

### Q6. Evaluator subprocess invocation pin-down (origin: integration.md:CHK016)

**Suggested:** Pin the subprocess invocation as `python -m dartwing_ocr.evaluator evaluate-document --folder <doc-folder> --quiet`, run with `cwd=<doc-folder>`, inheriting the demo's environment unchanged, with a 60 s wall-clock timeout per R-023.13.

Format: short answer (<=5 words). You can accept the suggestion, refine the CLI subcommand name (e.g., is it `evaluate-document` or another verb?), or specify a different argv shape.

---

### Q7. `paddle-rocm-preflight` diagnostic: distinguish stale wheel from uninstalled? (origin: gpu-runtime-readiness.md:CHK024)

**Recommended:** Option A — distinguish in the diagnostic's `observed` value but keep both under the single named check `paddle-rocm-preflight` (don't expand FR-016's closed vocabulary). Stale wheel: `observed: {device: "cpu", import_ok: true}`. Uninstalled: `observed: {import_error: "ImportError: No module named ..."}`. Operator sees two distinct remediations.

| Option | Description |
|--------|-------------|
| A | Same check name; different `observed` shapes ({import_error: ...} vs {device: "cpu", import_ok: true}); different `remediation` strings |
| B | Same check, same diagnostic — operator reads "Paddle preflight failed" and decides whether to install or reinstall |
| C | Split into two named checks (`paddle-import` and `paddle-device`) — expands FR-016 vocabulary to 9 names, requires schema_version minor bump |

---

### Q8. FR↔task↔test traceability matrix file? (origin: testing-strategy.md:CHK018 + requirements.md cross-cutting)

**Recommended:** Option A — author `specs/023-gpu-mvp-demo-hardening/coverage-fr-task-test.md` as part of Phase 7 polish, mirroring feature 022's `coverage-fr-task-test.md`. Single source of truth for FR ↔ task ID ↔ test ID, regenerated as new tasks land.

| Option | Description |
|--------|-------------|
| A | Author a standalone `coverage-fr-task-test.md` file in Phase 7 (mirrors feature 022's pattern) |
| B | Add a coverage matrix table to the bottom of `tasks.md` instead of a standalone file |
| C | Skip — `/speckit.analyze` already validates coverage at 100% on every run |

---

### Q9. Cold-cache `--check-only` budget (origin: performance.md:CHK008)

**Recommended:** Option A — make SC-007's 10 s warm-only explicit in the spec, and add an informal **30 s cold-cache target** to the runbook (not a spec-level SC, not enforced). R-023.9 already documents the warm/cold split; this just lifts the cold-target prose into the runbook.

| Option | Description |
|--------|-------------|
| A | SC-007 stays warm-only (current); runbook adds a `30 s` cold-cache informal target |
| B | Add SC-007a: cold-cache `--check-only` MUST complete in ≤30 s (becomes a release-gate SC) |
| C | Leave entirely as-is; cold-cache behavior is operator-visible but not specified |

---

### Q10. Sub-module stderr propagation (origin: integration.md:CHK026 + observability.md:CHK034)

**Recommended:** Option B — capture and replay sub-module stderr through the demo's `log.info(run_id, line)` helper so every stderr line has the unified `INFO:[run_id] preprocess: <text>` prefix. Operators see one continuous progress stream; automation can grep by run_id.

| Option | Description |
|--------|-------------|
| A | Pass-through: sub-module stderr goes straight to the demo's stderr without modification (interleaved with the demo's own INFO lines) |
| B | Capture and replay through `log.info(run_id, f"<phase>: <line>")` so every stderr line carries the run_id prefix and a phase tag |
| C | Suppress sub-module stderr entirely; rely on each sub-module's `run_summary` JSON line for its own progress signal |
| D | Pass-through with a phase-tag prefix (`PREPROCESS:` etc.) but no run_id prefix |

---

### Q11. Runbook dry-run validation procedure (origin: deployment.md:CHK016 + ux.md:CHK023)

**Recommended:** Option B — include the dry-run validation as a runbook *appendix* (not a separate FR/SC). The appendix says "before promoting this runbook, a colleague who has not previously run the demo follows it end-to-end and signs the entry below". Lightweight; gives SC-001 a concrete verification ritual without a new spec gate.

| Option | Description |
|--------|-------------|
| A | Add a hard SC: `SC-011 — colleague-dry-run verification` requiring a separate operator to validate the runbook before release |
| B | Include a runbook appendix with a sign-off line; no new SC |
| C | No formal procedure; SC-001 self-validates via T072 + the three-run SC-006 gate |

---

### Q12. Paddle/ROCm environment variables the demo reads (origin: configuration.md:CHK014, gpu-runtime-readiness.md:CHK030)

**Recommended:** Option A — the demo reads ONLY `OLLAMA_BASE_URL` and `OLLAMA_CONTEXT_LENGTH`. ROCm/HSA env vars (`HSA_OVERRIDE_GFX_VERSION`, `HIP_VISIBLE_DEVICES`, `MIOPEN_FIND_MODE`, `MIOPEN_USER_DB_PATH`, etc.) are read by the host Ollama startup script and inherited via `os.environ` into the Paddle preflight subprocess — but the demo CLI itself does NOT read or validate them. The runbook documents that operators should not unset them.

| Option | Description |
|--------|-------------|
| A | Demo reads only `OLLAMA_BASE_URL` + `OLLAMA_CONTEXT_LENGTH`; ROCm/HSA vars are operator-managed via the startup script |
| B | Demo reads ROCm/HSA vars too and includes them in `paddle-rocm-preflight.diagnostic.observed` for triage when the preflight fails |
| C | Demo validates a fixed list of required ROCm/HSA vars at readiness time and fails check 2 if any are missing |

---

## Summary

12 net-new clarifying questions extracted from 514 audit items across 15 files. The other 502 items are satisfied by existing artifacts (spec FRs, plan R-023 decisions, contracts, and the triage / remediation passes).

**Disposition after you answer:**
- Q3, Q4, Q14 (data-model invariants): tighten `data-model.md §1` invariants and `contracts/demo-report-schema.md` outcome matrix
- Q5, Q15, Q13 (report-shape bounds): add to `contracts/demo-report-schema.md` §"Compatibility & versioning"
- Q1, Q2, Q10 (stderr discipline): tighten `contracts/cli-contract.md §"stdout / stderr discipline"`
- Q6 (evaluator subprocess): pin in `research.md` R-023.13
- Q7 (Paddle preflight diagnostic): update `contracts/readiness-vocabulary.md` check 2
- Q8 (traceability matrix): add a Polish task in `tasks.md`
- Q9 (cold-cache bound): update `research.md` R-023.9 + runbook (T072)
- Q11 (dry-run appendix): update runbook (T072)
- Q12 (env vars): update `contracts/cli-contract.md §"Environment variables"` + runbook

None of the 12 questions block `/speckit.implement` MVP scope (T001–T035) since they affect Phase 7 polish + edge cases. But pinning them now keeps `tasks.md` from accumulating "Refine: …" sub-tasks during implementation.

**Answered on 2026-05-25.** Accepted answers are recorded above; propagate them into `spec.md`, `plan.md`, `data-model.md`, `contracts/*`, `tasks.md`, and the runbook per the disposition list before implementation proceeds.
