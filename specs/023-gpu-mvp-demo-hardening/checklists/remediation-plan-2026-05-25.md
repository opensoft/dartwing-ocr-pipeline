# Remediation Plan — Plan-Coverage Findings (2026-05-25)

**Goal:** Close all 15 open findings from `plan-coverage.md` (3 Conflicts + 12 Gaps) before `/speckit-tasks` runs.

**Scope:** All edits are to planning artifacts (`research.md`, `data-model.md`, `contracts/*.md`). **No spec edits required** — every finding is a planning-level refinement, not a spec ambiguity. The 32 spec clarifications + triage already done are unchanged.

**Strategy:** Apply edits in a deliberate order that avoids re-entrancy (later edits never invalidate earlier ones). After each Section, the plan-coverage CHK item is marked resolved. Final pass updates `plan-coverage.md` itself with checkboxes.

**Estimated impact:** ~20 surgical edits across 4 files (`research.md`, `data-model.md`, `contracts/cli-contract.md`, `contracts/demo-report-schema.md`, `contracts/readiness-vocabulary.md`). No `spec.md` change. No `pyproject.toml` change.

---

## Order of operations

| # | File | Edits | Why this order |
|---|---|---:|---|
| 1 | `contracts/demo-report-schema.md` | 1 | Fix the self-contradiction in §"Readiness sub-shape" first — it blocks anyone reading the contract |
| 2 | `data-model.md` | 3 | Reorder lifecycle + tighten field descriptions before downstream contract refs cite it |
| 3 | `contracts/readiness-vocabulary.md` | 4 | Update check 7 diagnostic + add umbrella-term note + add forward-compat note + check-7/8 timing note |
| 4 | `contracts/cli-contract.md` | 3 | Refine env-var table, run_id prefix, post-run timing |
| 5 | `research.md` | 9 | Append new sub-decisions to R-023.6, R-023.12, R-023.13, R-023.15, R-023.17, R-023.18, R-023.20; close gaps in one pass |
| 6 | `checklists/plan-coverage.md` | mark all 15 items `[x]` | Final tracking update |

---

## Section A — Conflicts (3)

### CHK050 — Voter-config vs interpreter/venv ordering [Conflict, `data-model.md` §1 vs §8]

**Root cause:** The lifecycle in `§8` shows voter-config loading BEFORE the readiness phase (which contains the `interpreter/venv` check as check 1). But `§1` describes `voter_config_path` as `null` "when the readiness phase failed before voter-config discovery completed" — implying discovery is *part of* readiness.

**Resolution:** The lifecycle in `§8` is correct (interpreter usability is implicit — if the interpreter were broken, the demo CLI wouldn't even start). The `interpreter/venv` check is a *post-hoc validation* that the running interpreter matches the expected venv path; it does NOT precede Python module imports (those happen at `import time` before argparse).

**Edit target 1:** `data-model.md` §1 — `voter_config_path` description.

```diff
-`voter_config_path` (str | null): The absolute path to the voter config file that was actually loaded. `null` only when the readiness phase failed before voter-config discovery completed (e.g., interpreter/venv check failed) or under invalid-input outcomes where discovery was not attempted.
+`voter_config_path` (str | null): The path to the voter config file that was loaded (post-override, post-auto-discovery, canonicalized). On voter-config-load failure (file missing / unreadable / malformed YAML / missing model-name field — exit 2), this field records the *attempted* path so operators can reproduce the discovery. `null` only when the demo aborted during argparse, before voter-config loading was attempted (e.g., `--help`, `--version`, unrecognized flag).
```

**Edit target 2:** `data-model.md` §8 — lifecycle clarifying note.

Add this paragraph after the lifecycle ASCII diagram:

```markdown
**Interpreter/venv check ordering.** The lifecycle shows voter-config loading before the readiness phase. This is correct: the `interpreter/venv` check (check 1) is a path comparison that validates the *already-running* interpreter matches `.venv-paddle-rocm`. If the interpreter were too broken to run, the demo CLI would not start at all and no `DemoRunReport` would be emitted. The check therefore runs after voter-config loading without circularity.
```

**Plan-coverage CHK affected:** CHK050 → resolved.

---

### CHK062 — `readiness.overall_passed` self-contradiction [Conflict, `contracts/demo-report-schema.md` §"Readiness sub-shape"]

**Root cause:** The contract first says "`overall_passed` is true iff every check.status is `pass`", then immediately corrects to "every check that ran returned `pass`". The two readings give different verdicts on `--check-only` (where checks 7–8 are `skipped`).

**Resolution:** Authoritative reading is the correction. `"skipped"` is treated as "not applicable", not as "did not pass". Under `--check-only`, all 6 infrastructure checks `pass` and 7–8 are `skipped` → `overall_passed: true`.

**Edit target:** `contracts/demo-report-schema.md` §"Readiness sub-shape".

Replace the contradictory paragraph entirely:

```diff
-- `overall_passed`: true iff every check.status is `"pass"`. Note: a check with status `"skipped"` is NOT a pass; `overall_passed` is false whenever there's any non-`"pass"` entry. This means a `--check-only` run has `overall_passed: true` only when all 6 infrastructure checks pass and checks 7–8 are skipped; the `overall_passed` field considers `"skipped"` as "did not pass" semantically.
-
-  **Correction:** Per FR-026's stable-shape rule, `--check-only` runs have `overall_passed: true` even though checks 7–8 are skipped (those checks are not applicable to readiness-only mode). The interpretation is: "every check that ran returned `pass`". On a `--check-only` pass, checks 1–6 are all `pass` and checks 7–8 are `skipped`; this counts as `overall_passed: true`.
-
-  On a full-pipeline pass, all 8 checks must be `pass` for `overall_passed: true`.
+- `overall_passed`: true iff every check that ran returned `"pass"`. Formally: there is at least one check with status `"pass"`, AND no check has status `"fail"`. Status `"skipped"` is treated as "not applicable to this run mode" and does NOT block `overall_passed: true`.
+  - Under `--check-only`: checks 1–6 must all be `"pass"`; checks 7–8 are `"skipped"` (not applicable); `overall_passed: true`.
+  - Under a full pipeline pass: all 8 checks must be `"pass"`; `overall_passed: true`.
+  - When any check has status `"fail"`: `overall_passed: false`, regardless of how many others passed or were skipped.
```

**Plan-coverage CHK affected:** CHK062 → resolved.

---

### CHK063 — `pipeline-runtime-timeout` is misnamed as a "readiness" check [Clarity / Terminology, `contracts/readiness-vocabulary.md` + FR-016]

**Root cause:** Check 8 (`pipeline-runtime-timeout`) and check 7 (`artifact-schema-validation`) execute *during* or *after* the pipeline, not before it. The "readiness" umbrella misleads about their execution semantics.

**Resolution:** Keep the existing closed vocabulary (it's already in the spec FR-016 — changing it would be a spec edit). Add a clarifying note that the term "readiness vocabulary" covers diagnostic naming, not strict pre-pipeline ordering. Document checks 7–8 as runtime/post-pipeline monitors that emit into the same vocabulary.

**Edit target:** `contracts/readiness-vocabulary.md` — header of the file (just above the "Fixed execution order" section).

Insert this paragraph:

```markdown
## Vocabulary scope note

The 8 named checks form the **closed diagnostic vocabulary** for the `failing_check_name` field and the per-check status entries in `readiness.checks[]`. They are NOT all pre-pipeline:

- **Pre-pipeline (checks 1–6)** run during the readiness phase before any pipeline work. These are the "infrastructure readiness" checks `--check-only` exercises (FR-018).
- **Runtime / post-pipeline (checks 7–8)** are gates that emit verdicts during or after pipeline execution:
  - Check 7 `artifact-schema-validation` runs after the pipeline completes, validating each of the 4 canonical artifacts.
  - Check 8 `pipeline-runtime-timeout` is a `signal.alarm` monitor that fires if the 600 s budget elapses during any pipeline phase.

The fixed-order skip rule (FR-026) applies to all 8 in declaration order: a failure at any earlier check marks every later check as `"skipped"`, even when the later check would have been a runtime monitor. This keeps the diagnostic vocabulary self-consistent across run modes.
```

**Plan-coverage CHK affected:** CHK063 → resolved.

---

## Section B — Gaps (12)

### CHK051 — Evaluator subprocess failure mode [Gap, `research.md` R-023.13]

**Edit target:** `research.md` — append to R-023.13 ("`--with-evaluator` invocation mechanism") under its **Decision** subsection.

```markdown
**Evaluator subprocess failure handling.** If the evaluator subprocess exits non-zero, fails to start (missing binary, PATH issue), or crashes (signal kill):

- The demo emits a `WARN:[run_id] --with-evaluator: evaluator subprocess failed with exit <N> / signal <S>; falling back to gate-derived quality_status` stderr line.
- `quality_status_source` stays `"gate"` in the `DemoRunReport` (the evaluator did not produce a verdict).
- The demo's own exit code is NOT modified by the evaluator failure — the pipeline outcome remains authoritative. A successful pipeline + failed evaluator subprocess still exits `0`; a failed pipeline + failed evaluator subprocess still exits per the pipeline failure (3 / 4 / 5).
- The evaluator subprocess has its own 60 s wall-clock budget; exceeding it is treated identically to a non-zero exit.

This preserves the "evaluator is off the critical path" property (per FR-022).
```

**Plan-coverage CHK affected:** CHK051 → resolved.

---

### CHK052 — Multi-artifact validation diagnostic aggregation [Gap, `contracts/readiness-vocabulary.md` check 7]

**Edit target:** `contracts/readiness-vocabulary.md` § "7 · `artifact-schema-validation`" — replace the existing diagnostic block.

```diff
 **Fail diagnostic:**
 - `checked`: `"Schema validation of 4 canonical artifacts"`
-- `observed`: the offending artifact path + the validator's error message
+- `observed`: a list of `{path: "<artifact path>", error: "<validator message>"}` objects covering every artifact that failed validation. Length 1–4. The list preserves the canonical artifact order (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`).
 - `expected`: `"all four artifacts schema-valid against v1.3.0 contract set"`
-- `remediation`: `"Inspect the failing artifact; this may indicate a pipeline regression."`
+- `remediation`: `"Inspect the listed artifact(s); a multi-artifact failure usually indicates a deeper pipeline regression — start with the earliest failure in canonical order."`
```

**Plan-coverage CHK affected:** CHK052 → resolved.

---

### CHK053 — `run_id` prefix detail [Clarity, `research.md` R-023.6]

**Edit target:** `research.md` R-023.6 — append a clarifying paragraph.

```markdown
**Prefix construction.** The 8-character stderr prefix is `run_id[0:8]` — the UUID4's first hex segment (8 characters before the first hyphen). For example, `run_id = "a1b2c3d4-1234-5678-9abc-def012345678"` → prefix `a1b2c3d4`. The prefix is computed once at process start and is identical across every stderr line within the same run. Automation that needs the full UUID reads it from `DemoRunReport.run_id` (always 36 characters including hyphens, lowercase hex).
```

**Plan-coverage CHK affected:** CHK053 → resolved.

---

### CHK054 — `OLLAMA_CONTEXT_LENGTH` consumption clarity [Clarity, `contracts/cli-contract.md` vs `contracts/readiness-vocabulary.md`]

**Edit target 1:** `contracts/cli-contract.md` §"Environment variables" — replace the `OLLAMA_CONTEXT_LENGTH` row.

```diff
-| `OLLAMA_CONTEXT_LENGTH` | runbook | `2048` | The context length the host Ollama startup script sets; FR-006 readiness check verifies the running Ollama exposes ≥ this value when `/api/ps` exposes context_length. Read by the operator-side startup script, not by the demo command. |
+| `OLLAMA_CONTEXT_LENGTH` | yes (read by both demo + startup script) | `2048` | Read by `scripts/start-host-ollama-rocm-wsl.sh` to configure the running Ollama, AND read by the demo's `ollama-context-length` readiness check (FR-006, check 6 in the vocabulary) to know what minimum to require. When unset in the demo's environment, the demo defaults to requiring `2048` regardless. When set, the demo requires that the running Ollama's `/api/ps.context_length` ≥ the env var's value. |
```

**Edit target 2:** `contracts/readiness-vocabulary.md` §"6 · `ollama-context-length`" — refine the pass criterion clause.

```diff
 **Pass criterion:**
-- If `/api/ps` exposes `context_length`: required value ≥ `OLLAMA_CONTEXT_LENGTH` env var (default `2048`).
+- If `/api/ps` exposes `context_length`: required value ≥ `int(os.environ.get("OLLAMA_CONTEXT_LENGTH", "2048"))`. The env var is the upper bound the demo requires; when unset, the demo requires `2048`. When set above `2048`, the demo requires the higher value (operator-overridable up, not down).
 - If `/api/ps` does NOT expose `context_length` (which would only happen if the Ollama version probe missed something — defensive case): the check returns `"pass"` and a soft `WARN:` stderr line, with the runtime path catching the downstream context-window error (FR-006 fallback).
```

**Plan-coverage CHK affected:** CHK054 → resolved.

---

### CHK055 + CHK059 — Float precision in `elapsed_seconds` and `phase_timings` [Gap, `data-model.md` §2 + §3]

**Edit target:** `research.md` — append a new sub-decision R-023.21.

```markdown
## R-023.21 · Float precision for wall-clock fields

**Decision:** All wall-clock float fields in `DemoRunReport` are rounded to **3 decimal places** (millisecond resolution) before JSON serialization. Applies to:

- `ReadinessCheck.elapsed_seconds`
- `ReadinessSummary.elapsed_seconds`
- `PhaseTimings.preprocess`, `.extraction`, `.routing`, `.final_payload`
- `total_runtime_seconds`

Rounding uses Python's `round(value, 3)` (banker's rounding, IEEE 754). Serialization uses standard `json.dumps` for these floats — `round()` returns a Python `float`, and `json.dumps` produces a stable string form for 3-decimal floats (e.g., `0.123`, `2.500`, `18.050`).

**Rationale:**
- Millisecond resolution is sufficient for SC-006 operator-visible comparison across three runs; raw nanosecond precision would surface IEEE-754 noise that varies by CPU scheduler.
- Stable byte form of `DemoRunReport` lines is not a hard requirement (SC-006 byte-identity applies to the 4 artifacts, not the report line), but the 3-dp rounding makes spot-comparison of report lines tractable for triage.
- 3 dp is consistent with feature 015's `run_summary.phase_timings` precision in the existing implementations.

**Alternatives considered:**
- **Microsecond (6 dp):** unnecessary precision; introduces noise in operator-readable diff.
- **Integer milliseconds (no dp):** loses sub-millisecond signal that may matter for the `interpreter/venv` check.
- **No rounding:** invites IEEE-754 noise in the JSON line.
```

**Plan-coverage CHK affected:** CHK055, CHK059 → resolved.

---

### CHK056 — Forward-compat of fixed-order check vocabulary [Gap, `contracts/readiness-vocabulary.md`]

**Edit target:** `contracts/demo-report-schema.md` §"Compatibility & versioning" — append a paragraph.

```markdown
**Adding a 9th (or Nth) readiness check.** A new readiness check name is an additive vocabulary change → **minor** schema_version bump (e.g., 0.1.x → 0.2.0). The new check is inserted into the fixed-order vocabulary at a position determined by its dependencies (e.g., a new check that depends on Ollama reachability slots after check 3 but before any check depending on it). Existing 8 names retain their existing positions; consumers iterating `readiness.checks[]` by position must not assume a fixed length, only that the order respects declared dependencies.
```

**Plan-coverage CHK affected:** CHK056 → resolved.

---

### CHK057 — Multi-voter voter-config handling [Gap, `data-model.md` §6]

**Edit target:** `data-model.md` §6 (`VoterConfigReference`) — append a precondition note.

```markdown
**Precondition: single-voter only (v0.1.0).** This feature's `VoterConfigReference` assumes the voter config defines exactly one voter (the canonical stage 1 single-voter shape per feature 005). If the voter config defines multiple voters (a future feature 005 extension), the demo selects the first voter declared in the YAML document and emits `WARN:[run_id] voter config has multiple voters; demo uses the first (model: <name>)` to stderr. Multi-voter awareness is out of scope for v0.1.0 and is a future feature. Operators with multi-voter configs MUST author a single-voter config file for the demo and pass it via `--voter-config <path>` to avoid the warning.
```

**Plan-coverage CHK affected:** CHK057 → resolved.

---

### CHK058 — Post-run interrogation timing budget [Gap, `research.md` R-023.15]

**Edit target:** `research.md` R-023.15 — append a timing-budget paragraph.

```markdown
**Probe timing budget.** Each of the two post-run probes (Ollama `/api/ps` re-query, Paddle device re-interrogation) has a **2-second wall-clock timeout** (matching the readiness HTTP timeout). The combined post-run interrogation phase has a **5-second aggregate budget**. These budgets do NOT count against the 600 s pipeline timeout (FR-008) — post-run interrogation happens after the pipeline completes (or fails / times out).

- Probe timeout exceeded → result is `"unreachable"`, not `"fell_back"`.
- Combined budget exceeded → both probes are marked `"unreachable"`; demo emits `WARN:[run_id] post-run interrogation exceeded 5s budget; CPU-fallback detection inconclusive`.
- An `"unreachable"` result does NOT downgrade a `success` outcome to `failed_at_extraction`. It DOES set `failure_kind: "post-run-interrogation-unreachable"` on the report so operators know the SC-004 guarantee was best-effort, not confirmed.
```

**Plan-coverage CHK affected:** CHK058 → resolved.

---

### CHK060 — Fixture symlink stability [Gap, `research.md` R-023.18]

**Edit target:** `research.md` R-023.18 — append a symlink-canonicalization note.

```markdown
**Symlink + FR-017 canonicalization interaction.** The `fixtures/ok/` folder contains a symlink at `fixtures/ok/source.pdf` pointing to `tests/stage1_vendor_identity/inv_001_easy/source.pdf`. The other six fixture folders (`missing_source_pdf/`, `malformed_voter_config/`, `symlink_escape/`, etc.) own their own files.

FR-017's canonicalization rule applies to the per-document folder path supplied via `--document-folder`. The symlinked `source.pdf` inside the folder is not affected by canonicalization because:

- The demo never deletes `source.pdf` (it is preserved per SC-010 — only the 4 canonical artifact filenames are eligible for eager-delete).
- The 4 canonical artifact filenames (`preprocess_output.json`, etc.) are NOT symlinked in `fixtures/ok/` — each test invocation writes them fresh into the canonicalized folder.

If the canonical corpus is updated (e.g., feature 022's labeling round adds a `notes.md`), the fixture continues to symlink the same `source.pdf` file. New files added to the canonical corpus are not symlinked into the fixture; tests that need them author their own copies. This keeps the fixture stable against unrelated corpus changes.
```

**Plan-coverage CHK affected:** CHK060 → resolved.

---

### CHK061 — `quality_status_source` on warn-and-skip [Clarity, `research.md` R-023.20]

**Edit target:** `research.md` R-023.20 — append a clarifying sentence to the **Decision** subsection.

```markdown
**Warn-and-skip outcome.** When `--with-evaluator` is supplied AND the per-document folder lacks `semantic_table_truth.json`, the evaluator subprocess is NOT invoked (warn-and-skip per FR-022). In this case `quality_status_source` is `"gate"` in the report (the gate-derived value is the actual source) — NOT `null` and NOT `"evaluator"`. This is consistent with the warn-and-skip behavior being "the operator wanted evaluator but the demo fell back to gate-only derivation".
```

**Plan-coverage CHK affected:** CHK061 → resolved.

---

### CHK064 — Eager-delete vs post-pipeline check timing [Clarity, `data-model.md` §8 + `contracts/readiness-vocabulary.md`]

**Edit target:** `data-model.md` §8 — append a clarifying paragraph after the lifecycle diagram.

```markdown
**Checks 7–8 timing vs FR-017 eager-delete.** The eager-delete of the 4 canonical artifacts happens at run start (before phase 1). Checks 7 (`artifact-schema-validation`) and 8 (`pipeline-runtime-timeout`) execute AFTER the pipeline phases (check 7 validates the just-written artifacts; check 8 fires its `signal.alarm` if the pipeline didn't complete within 600 s).

If check 7 fails (one or more artifacts schema-invalid), the demo exits 5 with the artifacts left on disk in their as-written (invalid) state. FR-017's eager-delete does NOT re-trigger on this exit path; it only re-triggers at the start of the NEXT invocation. This is intentional — operators inspecting a failed run benefit from seeing the actual artifact content that failed validation, not an empty folder.

If check 8 fires (timeout), partial artifacts from whichever phase was executing remain in the folder per US3 AS2. Subsequent re-runs eager-delete those partial artifacts at start.
```

**Plan-coverage CHK affected:** CHK064 → resolved.

---

## Section C — Post-edit cleanup

After Sections A and B land:

1. **Update `plan-coverage.md`:** mark CHK050–CHK064 with `[x]` and a one-line resolution note pointing at the section above.
2. **Update `plan-coverage.md` scorecard (§G):** all 64 items now covered; 0 open.
3. **No spec.md edits required.** No FR additions; no SC additions; no Edge Cases additions. The remediation operates entirely on planning artifacts.

---

## Verification checklist

After applying all 20 edits, run these spot-checks:

- [ ] `grep -n "voter-config discovery completed" data-model.md` → no results (old text removed).
- [ ] `grep -n "every check that ran returned" contracts/demo-report-schema.md` → exactly 1 result (the canonical statement; no nearby contradiction).
- [ ] `grep -n "Vocabulary scope note" contracts/readiness-vocabulary.md` → exactly 1 result (new section header present).
- [ ] `grep -n "R-023.21" research.md` → exactly 1 result (new sub-decision present).
- [ ] `grep -n "OLLAMA_CONTEXT_LENGTH" contracts/cli-contract.md` → row in env-var table reads "yes (read by both demo + startup script)".
- [ ] `grep -n "single-voter only (v0.1.0)" data-model.md` → exactly 1 result.
- [ ] `grep -n "Probe timing budget" research.md` → exactly 1 result.
- [ ] `grep -n "post-run-interrogation-unreachable" research.md` → at least 1 result (the new R-023.15 text).
- [ ] `grep -n "warn-and-skip" research.md` → at least 1 result (the new R-023.20 text).
- [ ] `grep -n "Checks 7–8 timing" data-model.md` → exactly 1 result.

If all 10 spot-checks pass, the remediation is complete and `/speckit-tasks` is unblocked.

---

## Rollback / risk

- **No source code is touched.** All edits are to planning artifacts under `specs/023-gpu-mvp-demo-hardening/`.
- **No commits required during this remediation.** Git working tree changes only — the worktree commit hook will pick up the diff on the next `/speckit-git-commit` or before `/speckit-tasks` if the operator opts in to the `before_tasks` hook.
- **Reversibility:** `git diff` shows every edit; `git checkout -- specs/` rolls back the whole remediation pass.
- **No production risk:** these are spec-adjacent planning documents that nothing downstream consumes at runtime.

---

## Recommendation

**Apply the remediation as a single batch.** All 20 edits are independent (no edit invalidates another). After applying, `plan-coverage.md` reflects 64/64 covered and `/speckit-tasks` runs unblocked.

If you'd prefer to defer some items to `tasks.md` (so they become implementation-time discoveries rather than spec-time decisions), the safe defer-candidates are:

- CHK055 / CHK059 (float precision) — can be a single task `"Round wall-clock fields to 3 dp before JSON serialization"`.
- CHK051 (evaluator subprocess failure handling) — can be a task `"Handle evaluator subprocess non-zero exit / timeout"`.
- CHK058 (post-run interrogation timing budget) — can be a task `"Enforce 2 s per-probe, 5 s aggregate timeout on post-run interrogation"`.

The remaining 12 items are best resolved at planning time so `tasks.md` has them as fixed inputs, not open questions.
