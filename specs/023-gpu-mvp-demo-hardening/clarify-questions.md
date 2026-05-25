# Speckit Clarify — Session 2026-05-24

Feature: **023-gpu-mvp-demo-hardening**

Spec: `specs/023-gpu-mvp-demo-hardening/spec.md`

Below are 16 clarification questions across 5 themes. Reply to each by letter (e.g. "A"), with "yes" / "recommended" to accept the recommendation, or with your own short answer (<=5 words).

You can answer all 16 at once (e.g. as a list `1: A, 2: B, 3: yes, ...`), or in batches. Answers will be integrated into `spec.md` under `## Clarifications → ### Session 2026-05-24` and the relevant FR / Key Entity / SC / Assumption sections will be updated in place.

## Accepted Answers

- **Q1**: A — canonical command is a new top-level Python CLI: `python -m dartwing_ocr.gpu_demo`, optionally exposed as `dartwing-gpu-demo`.
- **Q2**: A — readiness-only mode is a flag on the same demo CLI, using `--check-only` as the canonical spelling.
- **Q3**: B — use the closed exit-code table: `0` success, `1` readiness failed, `2` invalid input/usage, `3` runtime timeout, `4` runtime failed after readiness, `5` artifact schema validation failed.
- **Q4**: A — emit `DemoRunReport` as a single `{"kind": "demo_run_report", ...}` stdout JSON line; do not persist a new artifact.
- **Q5**: A — `quality_status` enum is `pass` / `weak` / `review_required`.
- **Q6**: A — `runtime_outcome` enum is `success` / `failed_at_preprocess` / `failed_at_extraction` / `failed_at_routing` / `failed_at_final_payload` / `timeout`.
- **Q7**: B — the demo command deterministically overwrites the four canonical artifacts on every run.
- **Q8**: A — `header-first-v1` is the default preprocessing preset; full OCR is opt-in via `--preset full-ocr`.
- **Q9**: B — detect silent CPU fallback through readiness checks plus post-run device interrogation of Ollama and Paddle.
- **Q10**: B — require all artifacts schema-valid with stable `runtime_outcome` and `quality_status` across three consecutive runs. Do not require byte-identity for model-influenced artifacts because `final_structured_payload.json` can legitimately reflect extraction variability.
- **Q11**: B — readiness preflight upper bound is 10 seconds.
- **Q12**: C — preflight checks `OLLAMA_CONTEXT_LENGTH` from `/api/ps` when available, and runtime still catches downstream context-window errors as a backup.
- **Q13**: D — document a minimum supported Ollama version and fail with named `ollama-version` check if the version is too old or `size_vram` is absent.
- **Q14**: C — feature 022 semantic-quality evaluator is flag-controlled through `--with-evaluator`; default is off.
- **Q15**: A — extend `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` in place.
- **Q16**: D — require CPU-isolated pytest coverage with stubbed dependencies plus a workstation-only manual GPU smoke gate captured in the runbook.

---

## A. CLI surface and entry point

### Q1. What is the canonical demo command's surface?

**Recommended:** Option A — a new top-level Python CLI keeps the composite responsibilities (interpreter check + Paddle preflight + Ollama readiness + pipeline run + report aggregation) cleanly scoped, distinct from feature 011's stage-runtime profile selection. Matches the per-feature CLI pattern already used by features 002, 005, 008, 009.

| Option | Description |
|--------|-------------|
| A | New top-level CLI: `python -m dartwing_ocr.gpu_demo` (optionally exposed as `dartwing-gpu-demo` console script in `pyproject.toml`) |
| B | Subcommand on the existing stage-runtime CLI from feature 011 (e.g. `python -m dartwing_ocr.runtime --profile gpu-mvp-demo`) |
| C | Shell wrapper script under `scripts/run-gpu-mvp-demo.sh` that composes existing module CLIs |
| D | Runbook procedure only — no new executable surface; operators run existing CLIs in a documented order |

Reply with the option letter (e.g., "A"), "yes" / "recommended", or your own short answer (<=5 words).

---

### Q2. What is the readiness-preflight surface (US2)?

**Recommended:** Option A — a `--check-only` flag on the demo CLI keeps the operator surface to one command with two modes (full vs. readiness-only), and matches the Assumptions note ("a readiness-only mode on the same canonical demo CLI ... rather than a separate top-level entry point").

| Option | Description |
|--------|-------------|
| A | Flag on the demo CLI: `--check-only` (or `--preflight-only`) |
| B | Subcommand: `dartwing-gpu-demo preflight` vs `dartwing-gpu-demo run` |
| C | Separate top-level CLI: `python -m dartwing_ocr.gpu_preflight` |
| D | Both a flag and a subcommand (operator chooses) |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q3. What is the exit-code taxonomy for the demo command?

**Recommended:** Option B — a small closed table maps the FR-016 closed-vocabulary check classes to distinct exit codes, enabling operations automation to react per-class. Follows the spirit of feature 008's documented exit-code table (0/1/2/3) but extends to cover this feature's named failure classes.

| Option | Description |
|--------|-------------|
| A | Two-state only: `0` success, nonzero failure |
| B | Closed table: `0` success, `1` readiness-failed (specific check named in report), `2` invalid input/usage, `3` pipeline runtime timeout, `4` pipeline runtime failed (after readiness passed), `5` artifact schema validation failed |
| C | Distinct exit code per readiness-check failure class (one code per closed-vocabulary check name) |
| D | Re-use feature 008 routing's `0/1/2/3` taxonomy verbatim |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

## B. DemoRunReport shape, enums, and data model

### Q4. How is `DemoRunReport` emitted and persisted?

**Recommended:** Option A — a single `{"kind": "demo_run_report", ...}` stdout JSON line matches the existing `kind: "run_summary"` lineage from features 014/015/016/017/018/019/020. It is parseable by automation and avoids adding a new persisted artifact (which would force a contract-set bump, violating FR-014).

| Option | Description |
|--------|-------------|
| A | Single stdout JSON line: `{"kind": "demo_run_report", ...}` — no new persisted artifact |
| B | Persisted file in the per-document folder: `demo_run_report.json` |
| C | Both: stdout JSON line **and** a persisted `demo_run_report.json` |
| D | Human-readable stdout text (key=value lines, no JSON) |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q5. What is the closed enum for the demo report's `quality_status` field?

**Recommended:** Option A — `pass` / `weak` / `review_required` matches US4 wording verbatim ("a small enumerated set such as `pass` / `weak` / `review_required`"). Maps cleanly: `pass` = evidence-gate `sufficient` AND `manual_review_required == false`; `weak` = evidence-gate `borderline` OR low-confidence fields without explicit review flag; `review_required` = `manual_review_required == true` or evidence-gate `insufficient`.

| Option | Description |
|--------|-------------|
| A | `pass` / `weak` / `review_required` (per US4 text) |
| B | Binary: `pass` / `review_required` (collapse `weak` into `review_required`) |
| C | Reuse evidence-gate enum: `sufficient` / `borderline` / `insufficient` |
| D | Reuse routing-decision enum: `edge_accept` / `edge_review_required` |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q6. What is the closed enum for the demo report's `runtime_outcome` field?

**Recommended:** Option A — phases match US3 Acceptance Scenario 2 wording exactly (preprocessing, extraction, routing, final-payload assembly) and the existing four canonical artifacts in FR-009. Readiness failures are not a pipeline runtime outcome (pipeline never runs) and are tracked under a separate readiness-result section of the report.

| Option | Description |
|--------|-------------|
| A | `success` / `failed_at_preprocess` / `failed_at_extraction` / `failed_at_routing` / `failed_at_final_payload` / `timeout` |
| B | Option A **plus** `failed_at_readiness` (readiness failure surfaced as a runtime outcome too) |
| C | Two-state: `success` / `failed`, with the failing phase in a separate `failed_phase` field |
| D | A combined `outcome` field merging readiness, runtime, and quality into a single enum |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

## C. Determinism, behavior, and re-run semantics

### Q7. How does the demo command handle stale artifacts in the per-document folder (FR-017)?

**Recommended:** Option B — deterministic overwrite. The four canonical pipeline artifacts are themselves byte-deterministic (features 014–020) on the inputs that the demo controls, so unconditional overwrite gives operators "just run it again" semantics with no manual cleanup. Adding `--force` (Option A) adds friction that hurts demo reliability.

| Option | Description |
|--------|-------------|
| A | Refuse to start if any of the four canonical artifacts already exists; require `--force` to overwrite |
| B | Always deterministically overwrite the four canonical artifacts on every run (no prompt, no flag) |
| C | Refuse only if all four artifacts are present; partial state (some artifacts missing) is silently overwritten |
| D | Operator must pass `--clean` or `--keep` per run; no default |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q8. What is the canonical preprocessing preset for the demo command (FR-011)?

**Recommended:** Option A — `header-first-v1` is the default. Per Assumptions ("the reduced/header-first preset is the currently supported MVP GPU path") and feature 018's benchmark evidence, the header-first preset is what this MVP demo can reliably run within the bounded timeout. Full/default OCR remains opt-in via flag and is promoted to default in a follow-on feature once independently verified.

| Option | Description |
|--------|-------------|
| A | `header-first-v1` is the default; full OCR is opt-in via `--preset full-ocr` |
| B | Full/default OCR is the default; `header-first-v1` is opt-in via `--preset header-first-v1` |
| C | Operator selects per-run via a required `--preset` flag; no default |
| D | `header-first-v1` is the only supported preset for this feature; full OCR is out of scope |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q9. How is silent CPU fallback detected and reported (SC-004)?

**Recommended:** Option B — readiness + post-run device interrogation. Re-query host Ollama `/api/ps` for the extraction model after the pipeline run to confirm the model is still GPU-placed, and re-query the Paddle device backend at end of preprocessing. Cheap, deterministic, and not subject to the timing-heuristic fragility of Option C.

| Option | Description |
|--------|-------------|
| A | Readiness checks only — presume that if readiness passes at start, GPU was used for the whole run |
| B | Readiness + post-run device interrogation (re-query `/api/ps` and re-query Paddle device backend at end of run) |
| C | Readiness + timing heuristic (run longer than N seconds → suspect CPU; fail) |
| D | Both B and C |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q10. What is the "stable enough" scope for SC-006 three-consecutive-runs determinism?

**Recommended:** Option D — byte-identity for the three deterministic artifacts (`preprocess_output.json`, `routing_decision.json`, `final_structured_payload.json`) and outcome-level stability (same readiness verdict, same `runtime_outcome`, same `quality_status`) for `edge_extraction_output.json`. Byte-identity across the full set is impossible without LLM seed control. Outcome-level stability is what "MVP integration-test checkpoint" actually needs.

| Option | Description |
|--------|-------------|
| A | Byte-identical across all four artifacts in three consecutive runs |
| B | All artifacts schema-valid; `runtime_outcome` identical; `quality_status` identical (field-level values may differ) |
| C | All artifacts schema-valid only (any artifact-level differences acceptable) |
| D | Byte-identical for `preprocess_output.json`, `routing_decision.json`, `final_structured_payload.json`; outcome-stable (same `runtime_outcome` + same `quality_status`) for `edge_extraction_output.json` |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

## D. Readiness check details and edge cases

### Q11. What is the upper time bound for the readiness preflight (US2 "within seconds")?

**Recommended:** Option B — 10 seconds. `/api/ps` HTTP call, Paddle import + device check, interpreter path resolution, and voter-config read should all complete in <5 s on warm caches; 10 s gives slack for cold Python imports on first invocation per session, without being so loose that a slow ROCm init goes unnoticed.

| Option | Description |
|--------|-------------|
| A | 5 seconds |
| B | 10 seconds |
| C | 30 seconds |
| D | 60 seconds |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q12. Should the `OLLAMA_CONTEXT_LENGTH` requirement be a readiness preflight check?

**Recommended:** Option A — add it to the readiness preflight as a separate named check ("ollama-context-length"). Recent Ollama versions expose `context_length` on `/api/ps` entries, so the check is cheap. Catching the misconfiguration before the pipeline runs gives operators a clear, actionable diagnostic pointing at the startup script, instead of a downstream context-window error in the middle of extraction.

| Option | Description |
|--------|-------------|
| A | Add to readiness preflight as a new named check ("ollama-context-length"); fail fast with a diagnostic pointing at `scripts/start-host-ollama-rocm-wsl.sh` |
| B | Detect at runtime only; the downstream extraction call surfaces a clear "context-window-too-small" diagnostic |
| C | Both: preflight reads context length from `/api/ps` if available **and** runtime catches downstream errors as a backup |
| D | Out of scope for this feature — the runbook documents the requirement, no code check is added |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q13. How does the GPU-placement check behave if the Ollama `/api/ps` entry omits the `size_vram` field (older Ollama version)?

**Recommended:** Option D — document a minimum supported Ollama version in the runbook and the readiness preflight fails with a distinct named check ("ollama-version") if the probed version is below the minimum or if `size_vram` is unexpectedly absent. Gives operators an explicit "upgrade Ollama" diagnostic instead of a confusing "model loaded but I can't tell if it's on GPU."

| Option | Description |
|--------|-------------|
| A | Treat missing `size_vram` as readiness failure (without a distinct version diagnostic) |
| B | Treat missing `size_vram` as readiness pass (best-effort; assume GPU if the model is loaded) |
| C | Treat missing `size_vram` as a distinct named failure ("ollama-version-too-old") without a documented minimum version |
| D | Document a minimum Ollama version in the runbook; fail with a named "ollama-version" check if the probed version is below the minimum or `size_vram` is absent |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q14. When (if ever) does the demo command invoke the feature 022 semantic-quality evaluator?

**Recommended:** Option C — flag-controlled (`--with-evaluator`). Default is off (matches Assumptions: "not on the critical path of the demo command"). Off by default keeps the demo fast and the canonical fixture independent of the semantic-quality scoring stack; the flag gives maintainers an opt-in way to extend the demo report with evaluator output when running against a fixture that has a `semantic_table_truth.json` sidecar.

| Option | Description |
|--------|-------------|
| A | Always invoke at end of run; `quality_status` derived from evaluator output |
| B | Never invoke; `quality_status` derived solely from evidence-gate + `manual_review_required` |
| C | Flag-controlled: invoke only when `--with-evaluator` is passed; default off |
| D | Auto-invoke when the per-document folder has a `semantic_table_truth.json` sidecar; skip otherwise |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

## E. Documentation and test coverage

### Q15. Where does the canonical demo runbook live?

**Recommended:** Option A — extend the existing feature 021 runbook (`docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`) in place. Feature 023 hardens what feature 021 documented; same audience, same machine, same scope. Avoids doc fragmentation and keeps the runbook as the single source of truth that other features (014–020) already reference.

| Option | Description |
|--------|-------------|
| A | Extend the existing feature 021 runbook (`docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`) in place |
| B | Add a new runbook (e.g. `docs/stage1-vendor-identity/runbook-gpu-mvp-demo-canonical.md`) alongside the feature 021 one |
| C | Replace the feature 021 runbook contents entirely with the canonical demo runbook |
| D | Inline runbook contents into this feature's `quickstart.md` only — no edit under `docs/` |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q16. What integration / smoke test coverage is required for the demo CLI?

**Recommended:** Option D — both CPU-isolated unit/integration tests (stubbed Ollama + stubbed Paddle preflight, exercises CLI flow + readiness check classes + report shape) **and** a workstation-only manual GPU smoke run captured in the runbook. Matches features 020 and 022 CPU-isolation testing patterns: CPU tests gate every PR; the GPU smoke is the manual MVP integration-test checkpoint of SC-006.

| Option | Description |
|--------|-------------|
| A | CI-runnable headless smoke test only (GPU-skip on no-ROCm CI; runs on workstation) |
| B | Manual-only validation per the runbook (no automated test) |
| C | Pytest tests only (CPU-isolated: stubbed Ollama + stubbed Paddle preflight; assert CLI flow, exit codes, report shape) |
| D | Both C (CPU-isolated unit/integration tests in CI) **and** A-style workstation-only GPU smoke (manual gate per runbook) |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

**Questions file:** `/workspace/projects/dartwing/ocr-pipeline-worktrees/023-gpu-mvp-demo-hardening/specs/023-gpu-mvp-demo-hardening/clarify-questions.md`

Answered on 2026-05-24; integrate the accepted answers above into `spec.md` before `/speckit.plan`.
