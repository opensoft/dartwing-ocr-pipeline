# Speckit Clarify — Session 2026-05-24 (Round 2)

Feature: **023-gpu-mvp-demo-hardening**

Spec: `specs/023-gpu-mvp-demo-hardening/spec.md`

Round 1 closed 16 questions. Re-scanning the updated spec surfaces 12 remaining second-order ambiguities — mostly second-order details of the `DemoRunReport` shape, the stale-artifact overwrite semantics (timing + scope), and a few CLI-interface edge cases that were not addressed in round 1.

Reply to each by letter (e.g. "A"), with "yes" / "recommended" to accept the recommendation, or with your own short answer (<=5 words). You can answer all 12 at once (e.g. `1: A, 2: B, 3: yes, ...`) or in batches.

## Accepted Answers

- **Q1**: A — default bounded pipeline-runtime timeout is 600 seconds.
- **Q2**: A — `DemoRunReport` readiness summary emits all named checks with `pass` / `fail` / `skipped`; the failing check name is also surfaced separately on failure.
- **Q3**: B — timeout uses `runtime_outcome: "timeout"` plus a separate `stalled_phase` enum: `preprocess` / `extraction` / `routing` / `final_payload`.
- **Q4**: D — `DemoRunReport` includes both `schema_version` (starting at `"0.1.0"`) and `pipeline_version`.
- **Q5**: A — `DemoRunReport` must include `phase_timings` for `preprocess`, `extraction`, `routing`, `final_payload`, plus `total_runtime_seconds`.
- **Q6**: B — default document folder is `tests/stage1_vendor_identity/inv_001_easy/`; `--document-folder <path>` can override it.
- **Q7**: B — when `--with-evaluator` is passed but `semantic_table_truth.json` is absent, warn and skip evaluator, then derive `quality_status` from default sources.
- **Q8**: A — stdout contains exactly one `DemoRunReport` JSON line and nothing else; stderr carries progress, warnings, and errors.
- **Q9**: A — accept `--voter-config <path>` to override auto-discovery; otherwise use existing feature 005 / 021 discovery.
- **Q10**: B — missing `source.pdf` is invalid input/usage and exits 2.
- **Q11**: A — eagerly delete the four canonical artifacts at run start; each phase writes its new artifact as it completes; partial new state remains on timeout/failure.
- **Q12**: A — overwrite scope is only the four canonical stage 1 artifacts.

---

## A. Performance and measurability

### Q1. What is the pinned numerical default for the bounded pipeline-runtime timeout (FR-008, SC-006/SC-007 context)?

**Recommended:** Option A — 600 seconds. The Assumptions section already names "the order of 10 minutes (600 seconds)" as the working default, comfortably above feature 018/019 header-first benchmarks. Pinning it at the spec level makes FR-008 / SC-006 testable without dragging the number into planning.

| Option | Description |
|--------|-------------|
| A | 600 seconds (10 minutes) — match existing Assumption value; the canonical default |
| B | 300 seconds (5 minutes) — tighter regression gate; aggressive given uncertainty in cold-cache behavior |
| C | 900 seconds (15 minutes) — looser, more headroom for cold MIOpen caches and first-run model loads |
| D | Defer the numeric default to planning; spec just requires "bounded" |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

## B. DemoRunReport shape and forward compatibility

### Q2. How is the readiness summary represented inside `DemoRunReport`?

**Recommended:** Option A — full per-check status for all 8 named checks (`pass` / `fail` / `skipped`), with the failing check name surfaced separately on failure. Gives operators and triage automation complete visibility into which checks ran, which short-circuited, and which failed, without parsing prose. Defines a concrete use for the `skipped` status (a check that did not run because an earlier required check failed).

| Option | Description |
|--------|-------------|
| A | Full list — for all 8 named checks, emit per-check status `pass` / `fail` / `skipped`; on failure, also emit the failing check name as a top-level field |
| B | Only the failing check name + diagnostic; passing checks omitted entirely; on success, a single `readiness: passed` field |
| C | Full list, but only of *executed* checks (skipped checks omitted entirely); `skipped` never appears |
| D | Two fields — `executed_checks` (closed list of names with `pass`/`fail`) plus `skipped_checks` (closed list of names short-circuited by an upstream fail) |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q3. How is the timeout's stalled phase captured (US3 AS2 says it must be identified)?

**Recommended:** Option B — keep `runtime_outcome: timeout` and add a separate `stalled_phase` field (closed enum `preprocess` / `extraction` / `routing` / `final_payload`). Keeps the `runtime_outcome` enum stable (no new values added to the round-1 set), mirrors the pattern of `quality_status` being a separate field from `runtime_outcome`, and gives structured access to the stalled phase without parsing the diagnostic string.

| Option | Description |
|--------|-------------|
| A | Expand the enum to `timeout_at_preprocess` / `timeout_at_extraction` / `timeout_at_routing` / `timeout_at_final_payload`; drop the bare `timeout` value from round-1's enum |
| B | Keep `runtime_outcome: timeout`; add a separate `stalled_phase` field with closed enum `preprocess` / `extraction` / `routing` / `final_payload` |
| C | Keep `runtime_outcome: timeout`; put the stalled phase only in the human-readable diagnostic string |
| D | Drop `timeout` from `runtime_outcome` entirely; reuse `failed_at_<phase>` for timeouts and add a separate `failure_kind: timeout` field |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q4. Does `DemoRunReport` carry an explicit `schema_version` field?

**Recommended:** Option A — add an explicit `schema_version` field (e.g. starting at `"0.1.0"`). Matches the feature 014–020 `RunSummary.SCHEMA_VERSION` lineage. Cheap addition; pays off the first time automation needs to react to an additive field bump.

| Option | Description |
|--------|-------------|
| A | Add an explicit `schema_version` field starting at `"0.1.0"`; bump via the conventions established by `RunSummary.SCHEMA_VERSION` in features 014–020 |
| B | No version field; the JSON line is best-effort and automation must tolerate additive changes |
| C | Reuse the existing `RunSummary.schema_version` (do not invent a new one); the demo report is logically a wrapper over `RunSummary` |
| D | Add `schema_version` **and** a `pipeline_version` field (so operators can see both the report shape version and the pipeline build) |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q5. Does `DemoRunReport` include phase timings (feature 015 lineage)?

**Recommended:** Option A — MUST include phase timings mirroring feature 015's `phase_timings` structure (`preprocess`, `extraction`, `routing`, `final_payload`). SC-006 ("stable enough across three runs") and SC-007 (10-second `--check-only` bound) both benefit from per-phase wall-clock numbers in the report. Feature 015 already tracks them, so this is essentially "include what is already measured" not "instrument new code".

| Option | Description |
|--------|-------------|
| A | MUST include `phase_timings` (`preprocess`, `extraction`, `routing`, `final_payload`) and `total_runtime_seconds`; mirror feature 015 conventions |
| B | MAY include phase timings; not required |
| C | Include `total_runtime_seconds` only; per-phase timings optional |
| D | No timings in the demo report; operator inspects underlying `run_summary` artifacts/logs separately |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

## C. CLI interface and behavior

### Q6. How is the per-document folder selected / overridable?

**Recommended:** Option B — default to `tests/stage1_vendor_identity/inv_001_easy/` (matching the existing Assumption) and accept an override via `--document-folder <path>`. The default enables the one-command MVP demo (FR-001); the override supports CPU-isolated pytest stubs (SC-008) and ad-hoc testing of other fixtures without changing the canonical demo's promise.

| Option | Description |
|--------|-------------|
| A | Hard-coded `tests/stage1_vendor_identity/inv_001_easy/`; no operator override |
| B | Default to `tests/stage1_vendor_identity/inv_001_easy/`; allow `--document-folder <path>` to override |
| C | Required `--document-folder <path>`; no default |
| D | Operator must `cd` to the per-doc folder and run the CLI from there; no `--document-folder` flag |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q7. What happens when `--with-evaluator` is passed but no `semantic_table_truth.json` sidecar exists in the per-doc folder?

**Recommended:** Option B — warn-and-skip. Log a clear "sidecar not found, skipping evaluator" message to stderr, derive `quality_status` from the default sources (evidence-gate + `manual_review_required`), and proceed. Doesn't crash a demo run on a missing optional artifact, but tells the operator the flag was ineffective.

| Option | Description |
|--------|-------------|
| A | Silently skip evaluator (no warning); `quality_status` derived from gate + `manual_review_required` as if the flag was not passed |
| B | Warn-and-skip — emit a clear "sidecar not found, skipping evaluator" diagnostic, then derive `quality_status` from the default sources |
| C | Fail with a diagnostic — operator passed `--with-evaluator` but the prerequisite sidecar is missing; exit 2 (invalid input/usage) |
| D | Auto-fall-back to default and surface a new `quality_status_source` field in the report (`gate` vs `evaluator`) so automation can distinguish |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q8. How does the demo CLI use stdout vs stderr?

**Recommended:** Option A — stdout carries the JSON-only `DemoRunReport` line (so `tail -n 1 | jq` works); stderr carries human-readable progress, info, warning, and error lines. Standard Unix convention; supports both automation and operator-visible progress without contaminating the JSON line.

| Option | Description |
|--------|-------------|
| A | stdout: exactly one `DemoRunReport` JSON line (and nothing else); stderr: human-readable progress, warnings, errors |
| B | stdout: JSON line; stderr: errors only; progress to a separate log file under `~/.cache/dartwing-gpu-demo/` |
| C | stdout: JSON + human-readable progress interleaved; stderr: empty |
| D | stdout: human-readable progress + final JSON line as the last line; no stderr usage |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q9. Does the demo CLI accept a `--voter-config <path>` override?

**Recommended:** Option A — accept `--voter-config <path>` to override auto-discovery. Required for the CPU-isolated pytest coverage in SC-008 (tests can point at fixture configs without monkeypatching discovery internals). Matches the feature 005 / 021 CLI conventions and keeps the test stubs from depending on global filesystem state.

| Option | Description |
|--------|-------------|
| A | Accept `--voter-config <path>` to override auto-discovery; falls back to feature 005 / 021 auto-discovery when not supplied |
| B | No override; tests must monkeypatch the auto-discovery internals |
| C | Accept `DARTWING_VOTER_CONFIG` environment variable as the override mechanism (no CLI flag) |
| D | Accept both `--voter-config <path>` and `DARTWING_VOTER_CONFIG`; CLI flag wins when both are set |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

## D. Edge cases and stale-artifact details

### Q10. How is a missing `source.pdf` in the target per-doc folder treated?

**Recommended:** Option B — treat as invalid input / usage (exit code 2 from the round-1 exit-code table). The per-doc folder and its `source.pdf` are operator-supplied input; missing input is a usage error, not a readiness check class. Avoids expanding the FR-016 closed vocabulary and matches the exit-code semantics established in round 1.

| Option | Description |
|--------|-------------|
| A | Treat as readiness check failure under a new named check (e.g. `fixture-availability`); expands FR-016 closed vocabulary |
| B | Treat as invalid input / usage; exit code 2 per the round-1 closed exit-code table; no expansion of the readiness vocabulary |
| C | Treat as readiness failure under `artifact-schema-validation` (since `source.pdf` is a prerequisite artifact) |
| D | Treat as `runtime_outcome: failed_at_preprocess` and let the existing preprocessing module raise its own error |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q11. When does the deterministic overwrite happen — eager or incremental?

**Recommended:** Option A — eagerly delete the four canonical artifacts at run start, before any pipeline phase runs. Gives a clean operator-visible state: at any point during a run, the per-doc folder contains either the new artifacts (produced so far) or nothing (for phases not yet reached). On timeout (US3 AS2: "leaves any partially written artifacts in place for inspection"), the partial new state is preserved — which is the desired diagnostic outcome. Option D (atomic temp-rename) conflicts with US3 AS2 because it would hide partial state.

| Option | Description |
|--------|-------------|
| A | Eager: delete the four canonical artifacts at run start; each phase writes its artifact when it completes; on mid-run failure / timeout, the per-doc folder shows exactly the artifacts produced so far (no stale data from previous runs) |
| B | Incremental: each module overwrites only its own artifact when it produces that artifact; a failed mid-run leaves a mix of new and old artifacts in the folder |
| C | Eager + wider: delete *all* known pipeline artifact paths in the per-doc folder at run start (incl. `evaluation_document.json`, debug `page_*.png`) — start completely clean |
| D | Incremental + atomic on-success: artifacts written to temp paths and renamed atomically only at run end; conflicts with US3 AS2 (partial state would be hidden on timeout) |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q12. Which files are within the overwrite scope (FR-017 stale-artifact behavior)?

**Recommended:** Option A — only the four canonical stage 1 artifacts. Preserves operator-curated and out-of-pipeline files (`source.pdf`, `expected.json`, `notes.md`, `semantic_table_truth.json`, and any debug PNGs the operator may have kept from earlier inspection). Minimum blast radius; aligns with FR-014 (no contract changes) and the principle that the demo should not own files outside the four-artifact contract.

| Option | Description |
|--------|-------------|
| A | Only the four canonical stage 1 artifacts (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`); do not touch any other file in the per-doc folder |
| B | The four canonical artifacts **plus** any debug `page_*.png` from earlier preprocessing runs |
| C | The four canonical artifacts **plus** any `evaluation_document.json` (relevant when `--with-evaluator` was used in a previous run) |
| D | Wider: delete everything in the per-doc folder that the pipeline writes; **never** touch `source.pdf`, `expected.json`, `notes.md`, `semantic_table_truth.json` (operator-owned) |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

**Questions file:** `/workspace/projects/dartwing/ocr-pipeline-worktrees/023-gpu-mvp-demo-hardening/specs/023-gpu-mvp-demo-hardening/clarify-questions-round-2.md`

Answered on 2026-05-24; integrate the accepted answers above into `spec.md` before `/speckit.plan`.
