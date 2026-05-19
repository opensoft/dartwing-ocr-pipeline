---
description: "Task list for feature 021-gpu-mvp-promotion"
---

# Tasks: GPU MVP Promotion

**Input**: Design documents from `/specs/021-gpu-mvp-promotion/`
**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required for user stories), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md), [checklists/](./checklists/) (**15 files, 657 items** — canonical count, used throughout this document and `quickstart.md`)

**Tests**: Tests are central to this feature's scope (US2 = converting placeholder tests; US4 = wiring the two-metric quality-gate test; US6 conditional = explicit-off legacy-path test). Test tasks below are NOT optional — they are the primary deliverable of US2 and US4.

**Organization**: Tasks grouped by user story per spec.md priorities (US1 P1 → US6 P3). Implementation order is priority-driven, but stories may be implemented in parallel by different developers since each touches distinct files (with the exception of US3 / US4 / US6 sharing the Appendix B file in `specs/020-vendor-evidence-gate/quickstart.md`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to spec.md user story (US1–US6); Setup, Foundational, and Polish phases carry no story label
- All paths absolute or repo-relative; assume repo root `/workspace/projects/dartwing/ocr-pipeline-worktrees/021-gpu-mvp-promotion/`

## Path Conventions

Single-project Python package (`src/dartwing_ocr/`) + harness (`tests/`) + docs (`docs/stage1-vendor-identity/`) + new config (`configs/voter/`) + scripts (`scripts/`). No new top-level directory.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Register the `gpu` pytest marker and create the canonical voter-config file the readiness helper will read.

- [X] T001 [P] Register `gpu` pytest marker in `pyproject.toml` under `[tool.pytest.ini_options].markers` with description `"gpu: requires AMD ROCm + paddlepaddle-dcu + host Ollama on GPU (workstation only; CPU CI skips)"` per [contracts/gpu-test-marker.md](./contracts/gpu-test-marker.md) §Marker registration. File: `pyproject.toml`.
- [X] T002 [P] Create voter-config file `configs/voter/ollama-gpu.yaml` with single top-level key `model_name: "<value>"` (operator pins value to the loaded Ollama extraction model identifier; e.g., `qwen2.5vl:7b`) per [research.md §R-021.7](./research.md). File: `configs/voter/ollama-gpu.yaml`.

**Checkpoint**: pytest collection now recognizes the `gpu` marker without `PytestUnknownMarkWarning`; the readiness helper has a canonical voter-config to read.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No truly story-blocking foundational work — US1 is itself the readiness-gate story, and US2–US6 depend on US1 only at *runtime* (workstation operator must run readiness before tests/benchmark/demo). Code-level, all user stories can proceed in parallel once Setup completes.

> **No tasks in this phase.** The intentional empty Phase 2 reflects the validation/promotion/documentation nature of this feature — there is no shared model/service layer that all stories need before they can start.

**Checkpoint**: After Setup, all user stories (US1 → US6) can begin work in parallel.

---

## Phase 3: User Story 1 — GPU Readiness Gate (Priority: P1) 🎯 MVP

**Goal**: Deterministic readiness gate (Paddle preflight + Ollama `/api/ps` check) that fails fast when GPU prerequisites are missing.

**Independent Test**: On a known-good GPU workstation, `python -m dartwing_ocr.preprocessing.preflight` returns `state == "ppstructurev3_init_succeeded"` and `scripts/check-ollama-gpu-readiness.sh --voter-config configs/voter/ollama-gpu.yaml` exits 0 with a PASS JSON line on stdout. On a deliberately broken environment (CPU `.venv`, Ollama with model not loaded, etc.), the corresponding check exits non-zero with a stderr message naming the unmet prerequisite. CPU-safe contract test exercises each of the five helper exit codes against captured `/api/ps` JSON fixtures.

### Implementation for User Story 1

- [X] T003 [US1] Create shell helper `scripts/check-ollama-gpu-readiness.sh` implementing the full invocation contract from [contracts/ollama-readiness-helper.md](./contracts/ollama-readiness-helper.md): `--voter-config <PATH>` required + `--base-url <URL>` optional (default `http://localhost:11434`); seven behavioral steps (argument parsing → voter-config YAML read via `yq -r '.model_name'` → `curl --silent --show-error --fail --max-time 10 <base_url>/api/ps` → `jq -e --arg n "<model>" '.models[] | select(.name == $n)'` → size/size_vram check → stdout JSON on PASS / stderr template on FAIL → exit-code emission); exit codes 0–4 per the contract; stdout-PASS / stderr-FAIL stream discipline per [research.md §R-021.10](./research.md). Make executable via `chmod +x`. File: `scripts/check-ollama-gpu-readiness.sh`.
- [X] T004 [P] [US1] Create fixture `tests/contract_tests/fixtures/ollama_api_ps_pass.json` containing a sample `/api/ps` response where the matched model entry has `size > 0 AND size_vram == size` (exit 0 PASS path). File: `tests/contract_tests/fixtures/ollama_api_ps_pass.json`.
- [X] T005 [P] [US1] Create fixture `tests/contract_tests/fixtures/ollama_api_ps_partial.json` where the matched model entry has `0 < size_vram < size` (exit 1 partial-GPU path). File: `tests/contract_tests/fixtures/ollama_api_ps_partial.json`.
- [X] T006 [P] [US1] Create fixture `tests/contract_tests/fixtures/ollama_api_ps_cpu_only.json` where the matched model entry has `size_vram == 0` (exit 1 CPU-only path, alternate of partial-GPU). File: `tests/contract_tests/fixtures/ollama_api_ps_cpu_only.json`.
- [X] T007 [P] [US1] Create fixture `tests/contract_tests/fixtures/ollama_api_ps_missing.json` where the response lacks any entry matching the target model_name (exit 2 not-loaded path). File: `tests/contract_tests/fixtures/ollama_api_ps_missing.json`.
- [X] T008 [US1] Create CPU-safe contract test `tests/contract_tests/test_ollama_readiness_helper_contract.py` that invokes the helper via `subprocess.run` against a **stdlib-only** ephemeral HTTP mock: a `pytest` fixture starts `http.server.ThreadingHTTPServer` bound to `127.0.0.1:0` (ephemeral port) with a tiny request handler that serves the right `tests/contract_tests/fixtures/ollama_api_ps_*.json` payload at `/api/ps`. The test passes the resulting `http://127.0.0.1:<port>` to the helper via `--base-url`, plus a tmp voter-config YAML created via `tmp_path`. Asserts each of the five exit codes (0 PASS, 1 partial, 2 not-loaded, 3 unreachable [server shut down], 4 config [malformed YAML]) with the corresponding stderr template per [contracts/ollama-readiness-helper.md](./contracts/ollama-readiness-helper.md) §Stderr table. No new pytest dependency; uses stdlib `http.server`, `threading`, `socket` only. Runs under `pytest -m 'not gpu'`. Depends on T003, T004, T005, T006, T007. File: `tests/contract_tests/test_ollama_readiness_helper_contract.py`.

**Checkpoint**: US1 is fully deliverable. The composite readiness gate (Paddle preflight from feature 014/015 + new Ollama helper) is operator-runnable. CPU CI green; GPU validation gated.

---

## Phase 4: User Story 2 — Feature-020 GPU-Deferred Verification (Priority: P2)

**Goal**: Convert the four (+1) feature-020 deferred GPU placeholder tests from inert (`@pytest.mark.skip(reason="R-020.15")`) to real GPU-asserting tests, preserving the file-level `pytestmark = pytest.mark.gpu` collection marker so CPU CI continues to skip.

**Independent Test**: Running `.venv-paddle-rocm/bin/pytest -m gpu -v <converted-test-files>` on a workstation with the readiness gate passing produces real PASS / FAIL / xfail-with-named-blocker results — none silently skipped. CPU CI (`pytest -m 'not gpu'`) continues to skip all five files at collection time.

> **Reads**: requires Setup T001 (gpu marker registered). Depends on US1 ONLY at runtime (workstation must pass readiness before the tests are meaningful). Code-level, T009–T012 can start in parallel with T003–T008.

### Implementation for User Story 2

- [X] T009 [P] [US2] In `tests/pipeline_tests/test_evidence_gate_skip_fallback.py`, remove the per-test `@pytest.mark.skip(reason="R-020.15")` decorator from `test_skip_fallback_sufficient_suppresses_ppstructurev3_gpu`; implement the Given/When/Then per [contracts/gpu-test-marker.md](./contracts/gpu-test-marker.md) §Body Contracts (run pipeline on a `sufficient` OCR-only document like `inv_001_easy` with `--evidence-gate-skip-fallback` against `ppstructurev3@gpu`; assert `run_summary.evidence_gate_suppressed_fallback_count == 1` for that document AND `phase_timings.engine_init` / `phase_timings.warmup` absent from the per-document `run_summary` line). Preserve the file-level `pytestmark = pytest.mark.gpu`. File: `tests/pipeline_tests/test_evidence_gate_skip_fallback.py`.
- [X] T010 [P] [US2] In `tests/pipeline_tests/test_evidence_gate_skip_fallback_borderline.py`, remove the skip decorator and implement the Given/When/Then: pipeline runs on a known `borderline` / `insufficient` document with the same `--evidence-gate-skip-fallback` invocation; assert PPStructureV3 fallback IS executed (`phase_timings.engine_init` AND `phase_timings.warmup` present in `run_summary` line) AND `evidence_gate_suppressed_fallback_count` does NOT increment for that document. Preserve `pytestmark = pytest.mark.gpu`. File: `tests/pipeline_tests/test_evidence_gate_skip_fallback_borderline.py`.
- [X] T011 [P] [US2] In `tests/pipeline_tests/test_evidence_gate_all_suppressed_lazy_construction.py`, remove skip decorators from both tests; implement (a) `test_all_sufficient_no_warmup_keeps_ppstructurev3_unconstructed_gpu` (all-`sufficient` corpus + no `--gpu-warmup` → `engine_init` and `warmup` absent across every per-document `run_summary` line); and (b) `test_all_sufficient_with_gpu_warmup_constructs_ppstructurev3_gpu` (same corpus + `--gpu-warmup` set → both keys present, the explicit operator trade-off per FR-009). Preserve `pytestmark = pytest.mark.gpu`. File: `tests/pipeline_tests/test_evidence_gate_all_suppressed_lazy_construction.py`.
- [X] T012 [P] [US2] In `tests/unit/preprocessing/test_warmup_skip_fallback_exception.py`, remove the skip decorator from `test_gpu_warmup_overrides_skip_fallback_lazy_construction`; implement the assertion that `--gpu-warmup` triggers PPStructureV3 construction (warmup phase key present in `run_summary`) even when every document is subsequently suppressed by skip-fallback. Preserve `pytestmark = pytest.mark.gpu`. File: `tests/unit/preprocessing/test_warmup_skip_fallback_exception.py`.

**Checkpoint**: US2 closes feature-020's four formerly-deferred GPU verification placeholders. SC-004 ("Zero formerly-deferred items remain silently inert") is now satisfiable. CPU-safe twins (`*_cpu.py`) remain untouched.

---

## Phase 5: User Story 3 — Recorded Benchmark Numbers in Appendix A (Priority: P3)

**Goal**: Run the four-run benchmark (warmup → legacy ×2 → candidate ×2) on the fixed five-document subset and populate feature-020 quickstart Appendix A with run-2 phase timings, jitter bands, run_summary observability, and findings.

**Independent Test**: Appendix A in `specs/020-vendor-evidence-gate/quickstart.md` contains: (a) environment fingerprint with GPU readiness verdict; (b) the five-document subset confirmation; (c) four-run timeline; (d) per-document phase-key tables with the FR-015 threshold formula values + Material? column; (e) per-document run_summary observability table; (f) §Findings list. A third party reading Appendix A alone can re-derive each Material? cell without re-running.

> **Reads**: T012 depends on `configs/voter/ollama-gpu.yaml` (Setup T002) so the operator can invoke the demo command. T013 (operator runs benchmark) depends at runtime on US1 readiness gate passing.

### Implementation for User Story 3

- [X] T013 [US3] Add Appendix A skeleton subsections to `specs/020-vendor-evidence-gate/quickstart.md` per [contracts/appendix-recording.md §Appendix A](./contracts/appendix-recording.md): six required subsections (Environment fingerprint → Document subset confirmation → Four-run timeline → Per-document phase-key tables → Per-document `run_summary` observability table → Findings). Use empty tables with the contract-pinned column order; add the threshold-zero inline-note convention per [research.md §R-021.3](./research.md). File: `specs/020-vendor-evidence-gate/quickstart.md`.
- [ ] T014 [US3] **Operator step (workstation, GPU lane required)**: Mirror `source.pdf` for the fixed five-document subset (`inv_001_easy`, `inv_002_easy`, `inv_006_medium`, `inv_011_hard`, `inv_012_hard`) into the scratch tree `/tmp/021-bench/<lane>/run<N>/<doc>/source.pdf` for `lane ∈ {warmup, legacy, candidate}` and `run ∈ {run1, run2}` (warmup only has run1), then generate one `docs.txt` per `(lane, run)` listing the scratch folders, then run the four-run benchmark sequence per [quickstart.md Path 3](./quickstart.md) — warmup ×1, legacy default ×2, candidate (with `--evidence-gate-skip-fallback`) ×2. Each run uses `--documents-file /tmp/021-bench/<lane>/<run>/docs.txt`; outputs land back in each scratch per-doc folder (warm-corpus mode does not honor `--output-dir`, per `runner.run_plan`). Capture each lane's `run_summary.jsonl` stdout for transcription. (No file in the repo changes here; the artifact is the captured stdout to be transcribed in T015–T018.) Layout convention per [research.md §R-021.1](./research.md).
- [ ] T015 [US3] Populate the Appendix A environment fingerprint and four-run timeline subsections with: GPU readiness verdict (PASS), interpreter path (`.venv-paddle-rocm/bin/python`), ROCm version, Paddle wheel version, Ollama version, Ollama readiness PASS JSON, voter-config path + model_name, hostname/OS/kernel, and the four-run start/end timestamps + exit codes. Depends on T013, T014. File: `specs/020-vendor-evidence-gate/quickstart.md`.
- [ ] T016 [US3] Populate the Appendix A per-document phase-key tables for all five documents × both lanes (legacy, candidate). For each (document, phase_key) row, record legacy run1+run2, candidate run1+run2, the two pair spreads, `threshold = max(legacy_spread, candidate_spread)`, `Δ = |candidate_run2 − legacy_run2|`, and the Material? cell (`YES` / `NO` / `YES ↓ ✓` / `YES ↑ ⚠` / `LAZY`) per [research.md §R-021.4](./research.md) direction-symmetric reading. Values in seconds, 3 decimals (R-021.2). Depends on T014. File: `specs/020-vendor-evidence-gate/quickstart.md`.
- [ ] T017 [US3] Populate the Appendix A per-document `run_summary` observability table for all five documents × both lanes (run-2 only): gate_decision, evidence_gate_state_counts, evidence_gate_suppressed_fallback_count, ocr_only_fallback_count, preprocess_strategy_id. Depends on T014. File: `specs/020-vendor-evidence-gate/quickstart.md`.
- [ ] T018 [US3] Populate the Appendix A §Findings subsection: list every `YES ↑ ⚠` cell, every `YES` cell on a phase key other than `per_page_inference` / `total` (these are findings under FR-016), and any other anomaly (lane lengths differ, document missing, etc.). Each finding cites the (document, phase_key, lane) triple per [contracts/appendix-recording.md §6](./contracts/appendix-recording.md). Depends on T016. File: `specs/020-vendor-evidence-gate/quickstart.md`.

**Checkpoint**: US3 satisfies SC-005 (Appendix A sufficient for third-party re-derivation) and SC-006 (only `per_page_inference` and `total` material-decrease on suppressed documents; everything else within jitter or flagged).

---

## Phase 6: User Story 4 — Recorded Two-Metric Quality-Gate Verdict in Appendix B (Priority: P3)

**Goal**: Run the two-metric quality gate (aggregate vendor-identity sum + per-document pass count, candidate ≥ legacy) on the same scratch outputs from US3, and record the PASS / FAIL / BLOCKED verdict in Appendix B.

**Independent Test**: `tests/pipeline_tests/test_quality_gate_two_metric_evidence_gate.py` runs under `pytest -m gpu` and produces a deterministic verdict against the same `/tmp/021-bench/<lane>/run2/` scratch tree US3 produced. Appendix B in `specs/020-vendor-evidence-gate/quickstart.md` contains the verdict literal + per-document score/pass table + aggregate + pass count + (if FAIL) regressing_metric + magnitude + (if BLOCKED) named blocker.

> **Reads**: T019 can start in parallel with US2 / US3 tasks (different file). T020 depends on T014 (US3 scratch tree exists). T021–T022 depend on T020.

### Implementation for User Story 4

- [X] T019 [P] [US4] In `tests/pipeline_tests/test_quality_gate_two_metric_evidence_gate.py`, remove the skip decorator from `test_two_metric_quality_gate_pass_or_fail_or_blocked_gpu`; implement: load `evaluation_run_summary.json` from `/tmp/021-bench/legacy/run2/` and `/tmp/021-bench/candidate/run2/`; compute `legacy_aggregate = sum(per-doc vendor_identity_score)`, `candidate_aggregate = sum(...)`, `legacy_pass_count = count(vendor_identity_pass == True)`, `candidate_pass_count = count(...)` per [research.md §R-021.13](./research.md); assert the verdict via FR-020 conjunction (PASS iff candidate ≥ legacy on BOTH metrics). On BLOCKED (unable to load evaluator output, named hardware/runtime cause), mark via `pytest.xfail(strict=False)` with the cause string. Preserve `pytestmark = pytest.mark.gpu`. File: `tests/pipeline_tests/test_quality_gate_two_metric_evidence_gate.py`.
- [ ] T020 [US4] **Operator step (workstation, GPU lane required)**: Run feature-007 evaluator on each lane's run-2 scratch tree: `python -m dartwing_ocr.evaluator --corpus-root /tmp/021-bench/legacy/run2/` and again with `--corpus-root /tmp/021-bench/candidate/run2/`. Produces `evaluation_document.json` per per-document folder + `evaluation_run_summary.json` per lane root. Depends on T014 (US3 scratch tree exists). (Operator step; no file in repo changes.)
- [X] T021 [US4] Add Appendix B `### Quality-Gate Verdict (YYYY-MM-DD)` subsection skeleton to `specs/020-vendor-evidence-gate/quickstart.md` per [contracts/appendix-recording.md §Appendix B](./contracts/appendix-recording.md): verdict literal placeholder, per-document score+pass table (5 rows × 4 columns: legacy score, candidate score, legacy pass, candidate pass), aggregate sum line, pass count line, regressing_metric placeholder, blocked_cause placeholder. File: `specs/020-vendor-evidence-gate/quickstart.md`.
- [ ] T022 [US4] Populate Appendix B with actual values from T020 outputs: per-document score table; legacy/candidate aggregate sums and Δ; legacy/candidate pass counts and Δ; verdict literal (PASS / FAIL / BLOCKED). If FAIL: populate regressing_metric and magnitude. If BLOCKED: populate blocked_cause with the named hardware/runtime cause. Depends on T020, T021. File: `specs/020-vendor-evidence-gate/quickstart.md`.

**Checkpoint**: US4 satisfies SC-007 (single explicit verdict with required content) and gates the US6 promotion decision (FR-027 forbids promote-to-default on FAIL/BLOCKED).

---

## Phase 7: User Story 5 — GPU-Required Fail-Fast MVP Demo Runbook (Priority: P3)

**Goal**: Author `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` so a new operator can run the MVP demo end-to-end using only the runbook (SC-008).

**Independent Test**: A new operator follows the runbook from a clean terminal and (a) hits the readiness step first; (b) every demo command uses `ppstructurev3@gpu` + `configs/voter/ollama-gpu.yaml`; (c) `grep -E '@cpu|stub-voter' docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` returns zero matches; (d) the seven `run_summary` observability fields are walked through with reader-facing context; (e) the operator never consults source code.

> **Reads**: T023 can start in parallel with US1–US4 tasks (different file). T024 is a self-check (validation step).

### Implementation for User Story 5

- [ ] T023 [US5] Create `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` following [contracts/runbook.md](./contracts/runbook.md) §Required sections: 10 sections in fixed order (Title → Prerequisites → Step 1 Readiness Gate (1a Paddle preflight `python -m dartwing_ocr.preprocessing.preflight` + 1b Ollama helper `scripts/check-ollama-gpu-readiness.sh --voter-config configs/voter/ollama-gpu.yaml`) → Step 2a Scratch-prep (`mkdir -p /tmp/021-bench/demo/<doc>` + `cp tests/stage1_vendor_identity/<doc>/source.pdf` + build `/tmp/021-bench/demo/docs.txt`) → Step 2b Canonical Demo Command (`python -m dartwing_ocr.pipeline run --documents-file /tmp/021-bench/demo/docs.txt --preprocess-profile ppstructurev3@gpu --preprocess-strategy ocr-only-v1 --extract-profile ollama@gpu`) → Step 3 Read `run_summary` (walkthrough of seven fields) → Step 4 Suppression Demonstration → Scratch Discipline → Promotion Decision section (placeholder for US6 mirror) → When Things Go Wrong → See Also). The runbook MUST NOT show `--output-dir` (not honored in warm-corpus mode — outputs land in each `--documents-file` folder; scratch-copy mirror is the discipline). No `@cpu`, `ollama@cpu`, or `stub` voter in any command block. File: `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`.
- [ ] T024 [US5] Verify the SC-008 self-sufficiency invariant from the runbook contract: `grep -E '@cpu|stub-voter' docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` MUST return zero matches. Depends on T023. (Validation step; can be folded into the T023 review.)

**Checkpoint**: US5 satisfies SC-008 (zero CPU-fallback commands, new-operator self-sufficient). The runbook's §Promotion Decision section is a placeholder awaiting US6.

---

## Phase 8: User Story 6 — Recorded Promotion Decision for Skip-Fallback (Priority: P3)

**Goal**: Record the team's binary promotion decision (`stay opt-in` or `promote to default`) in Appendix B AND mirror it in the runbook §Promotion Decision section, with the synchronization verified by a CPU-safe contract test.

**Independent Test**: Appendix B contains a dated `### Promotion Decision (YYYY-MM-DD)` subsection citing the FR-019 verdict; the runbook §Promotion Decision section's `Decision:` literal matches Appendix B exactly; `pytest tests/contract_tests/test_promotion_decision_sync.py -v` passes. If `promote to default` was chosen, the inverted-default code change + FR-028 explicit-off legacy-path test are present and the latter passes under `pytest -m 'not gpu'`.

> **Reads**: T025–T027 can start in parallel with the rest of US3/US4/US5 (different files except for shared Appendix B file). T028 depends on US4 verdict being recorded (T022). T029–T030 are conditional on the team's decision being `promote to default`.

### Implementation for User Story 6

- [ ] T025 [US6] Add `### Promotion Decision (YYYY-MM-DD)` subsection skeleton to Appendix B in `specs/020-vendor-evidence-gate/quickstart.md` per [contracts/appendix-recording.md §Appendix B Promotion Decision](./contracts/appendix-recording.md): Decision placeholder, Gating verdict back-pointer placeholder, Decided by, Decided at, Rationale, optional promotion_artifacts block (Inverted default location, Explicit-off flag, Explicit-off env var, Legacy-path test). File: `specs/020-vendor-evidence-gate/quickstart.md`.
- [ ] T026 [P] [US6] Add `## Promotion Decision` section to `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` (mirror per [research.md §R-021.11](./research.md)): `Decision:` literal placeholder, link back to Appendix B authoritative subsection, optional one-liner naming the explicit-off flag/env-var if `promote to default` lands. Depends on T023. File: `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`.
- [ ] T027 [P] [US6] Create CPU-safe sync contract test `tests/contract_tests/test_promotion_decision_sync.py` that loads `specs/020-vendor-evidence-gate/quickstart.md` and `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`, extracts the `Decision:` literal from each (via regex match on `Decision: (stay opt-in|promote to default)`), and asserts both literals are identical. Test runs under `pytest -m 'not gpu'`. File: `tests/contract_tests/test_promotion_decision_sync.py`.
- [ ] T028 [US6] **Team step**: Record the actual binary decision. Populate Appendix B Promotion Decision subsection (T025) and the runbook §Promotion Decision section (T026) with the chosen `Decision:` literal (`stay opt-in` if FR-019 verdict is FAIL/BLOCKED — mandatory per FR-027; or either literal if PASS), `Decided by`, `Decided at`, `Rationale` (2–4 sentences), and `Gating verdict:` back-reference to the Appendix B Quality-Gate Verdict subsection from T022. If `promote to default`: populate the promotion_artifacts block. Depends on T022, T025, T026.
- [ ] T029 [US6] **Conditional (only if T028 records `promote to default`)**: Locate the existing skip-fallback default in the pipeline code (`grep -rn "evidence_gate_skip_fallback" src/dartwing_ocr/preprocessing/` to find the canonical default site, likely in `src/dartwing_ocr/preprocessing/evidence_gate_optin.py` or its caller). Flip the **existing** `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK` env var's default from OFF to ON — the env var name and the `--evidence-gate-skip-fallback` CLI flag remain unchanged. After this change: unset or `=1` means skip-fallback ON (new default); `=0` means OFF (the new explicit-off legacy path). NO new env var is introduced. **Backwards-compatibility sub-step (required)**: verify that the `--evidence-gate-skip-fallback` CLI flag and the `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=1` env value both remain accepted as no-op aliases for the new default — existing feature-020 scripts, CI invocations, and operator runbooks that pass the flag or set the env-var-to-1 to enable skip-fallback MUST continue to work without error. This is a separate invariant from T030 (which only tests the off path); covering the unchanged-flag invariant prevents silent breakage of feature-020-era callers. Update the inverted-default location reference (`file:line`) in the Appendix B promotion_artifacts block (T028). File: `src/dartwing_ocr/preprocessing/evidence_gate_optin.py` (or wherever the default actually lives).
- [ ] T030 [US6] **Conditional (only if T028 records `promote to default`)**: Create CPU-safe legacy-path test `tests/unit/preprocessing/test_skip_fallback_explicit_off_legacy.py` that invokes the pipeline with the explicit-off flag (or env var) and asserts skip-fallback is disabled — `evidence_gate_suppressed_fallback_count == 0` even on a `sufficient` document, and PPStructureV3 fallback executes. Test runs under `pytest -m 'not gpu'` (uses fixture data, not GPU). **The test MUST pass deterministically on every CPU CI run** — a flaky test violates SC-009's "passes" requirement and BLOCKS promote-to-default landing until the flake is eliminated. Depends on T029. File: `tests/unit/preprocessing/test_skip_fallback_explicit_off_legacy.py`.

**Checkpoint**: US6 satisfies SC-009 (explicit binary decision recorded, gating verdict cited, legacy-path test passing if promote-to-default chosen).

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across the 657-item / 15-file checklist surface and the eleven success criteria.

- [ ] T031 [P] Run all CPU-safe contract and unit tests; ensure green: `.venv/bin/pytest tests/contract_tests/ tests/unit/preprocessing/ -m 'not gpu' -v`. Includes new tests from T008, T027, and (if landed) T030.
- [ ] T032 [P] Verify zero mutation of the committed corpus AND the committed contract-schema set after all benchmark / demo runs: `git status tests/stage1_vendor_identity/ contracts/stage1_vendor_identity/` returns no modifications. The combined check covers SC-011 (corpus invariant), FR-031 (schema-preservation invariant — `contracts/stage1_vendor_identity/v1.2.0/*.json` schemas unchanged), AND FR-033 (no committed-corpus baseline regeneration — every `expected.json` lives under `tests/stage1_vendor_identity/<inv>/` so the corpus check transitively covers them). One `git status` invocation closes all three negative-invariant requirements with a single grep-able output.
- [ ] T033 [P] Verify the demo runbook GPU-only invariant (SC-008): `grep -nE '@cpu|stub-voter' docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` returns zero matches.
- [ ] T034 [P] Verify the promotion-decision sync contract: `.venv/bin/pytest tests/contract_tests/test_promotion_decision_sync.py -v` passes.
- [ ] T035 Cross-checklist sweep: walk the **15 files (657 items)** in `specs/021-gpu-mvp-promotion/checklists/` and check off items now satisfied by landed artifacts. The 15 = the auto-generated `requirements.md` + 14 deep-rigor domain checklists (the original 12 + `dependencies.md` + `clarifications.md` added during the post-`/speckit.analyze` checklist reverify) + the appended `benchmark.md` CHK049 covering FR-007. Flag any `[Gap]` items that remain genuinely open as known limitations (recorded inline in the relevant checklist Notes section). Expect ~30 to remain flagged as deferred-to-future-features. File: `specs/021-gpu-mvp-promotion/checklists/*.md`.
- [ ] T036 Validate every SC (SC-001 through SC-011) against landed artifacts. Use this **SC → task-IDs mapping** as the starting point (closes the `/speckit.analyze` C11 transitive-coverage observation by making the SC↔task linkage explicit and auditable from this file alone): SC-001 → {T008, T014, T023, T037}; SC-002 → {T003, T008}; SC-003 → {T037}; **SC-004 → {T009, T010, T011, T012, T019}** (each conversion closes one of the five formerly-deferred items — four `tests/pipeline_tests/` placeholders plus the warmup-exception test, plus the quality-gate test placeholder); SC-005 → {T013, T015, T016, T017, T018}; SC-006 → {T016, T018}; SC-007 → {T021, T022}; SC-008 → {T023, T024, T033}; SC-009 → {T025, T026, T027, T028, T029, T030, T034}; SC-010 → {T031, T032}; SC-011 → {T014, T032}. For each SC, confirm the named tasks landed and identify the demonstrating artifact (Appendix A entry, Appendix B verdict, runbook content, test results, `git status` output). Document any deviations in `specs/021-gpu-mvp-promotion/spec.md` under a new Notes subsection (or confirm zero deviations and record that). File: `specs/021-gpu-mvp-promotion/spec.md`.
- [ ] T037 [P] Verify the SC-003 "interpreter determinable" invariant covers DEMO runs as well as benchmark runs: after at least one operator demo invocation (T023 runbook Step 2), inspect the captured `readiness-paddle.log` (FR-001 stderr redirection per [contracts/runbook.md §3](./contracts/runbook.md) Step 1a) and confirm the interpreter path (e.g., `.venv-paddle-rocm/bin/python`) is recorded. If absent, raise it against feature 014/015 (the upstream that owns preflight emission) rather than amending this feature's surface. (Closes the analyze §C5 coverage gap.) File: `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` (review only; no edit unless preflight stderr lacks the path).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No prerequisites. T001 and T002 are independent and [P]; both must complete before any later phase reads them.
- **Foundational (Phase 2)**: Empty — no shared foundational layer to block on.
- **User Stories (Phases 3–8)**: All depend on Setup completion only. Code-level, all six stories may proceed in parallel (with the caveat that US3, US4, US6 share `specs/020-vendor-evidence-gate/quickstart.md` — sequence those edits or coordinate hand-offs).
- **Polish (Phase 9)**: Depends on the user stories deemed in-scope for landing being complete.

### Inter-Story Dependencies (Code-Level)

- **US1 → US2, US3, US4, US5, US6**: Runtime only (operator must pass readiness gate before invoking GPU tests / benchmark / demo). No code dependency.
- **US3 → US4**: Runtime only (T020 evaluator needs T014 scratch tree). Code edits to Appendix B (T021–T022) can start in parallel with T013–T018.
- **US3 → US6**: Indirect via US4 verdict (T028 records the verdict-gated decision).
- **US4 → US6**: T028 cites the verdict from T022.
- **US5 → US6**: T026 (runbook mirror) depends on T023 (runbook file exists).

### File-Sharing Dependencies (`specs/020-vendor-evidence-gate/quickstart.md`)

Tasks T013, T015, T016, T017, T018, T021, T022, T025 all edit the same file. Order them sequentially to avoid merge conflicts: T013 → T015 → T016 → T017 → T018 → T021 → T022 → T025 → T028 (the T028 final population of T025's skeleton). Within a single committer's session this is natural; across multiple developers, coordinate via per-task PRs.

### Within Each User Story

- US1: T003 + T004–T007 (parallel fixtures) → T008 (test). Helper file (T003) and fixtures (T004–T007) can all be authored in parallel; T008 reads all five.
- US2: T009, T010, T011, T012 — all different files, fully parallel.
- US3: skeleton (T013) → operator run (T014) → transcription (T015, T016, T017 — same file, sequential) → findings (T018).
- US4: skeleton (T021) + test conversion (T019, parallel) → operator run (T020, depends on T014) → population (T022, depends on T020 + T021).
- US5: T023 → T024 verification.
- US6: T025, T026 [P], T027 [P] → T028 (team decision) → conditional T029 → T030.
- Polish: T031, T032, T033, T034 all [P]; T035, T036 sequential per file.

### Parallel Opportunities

**Setup**: T001 [P] T002.
**US1**: T004 [P] T005 [P] T006 [P] T007 (after T003).
**US2**: T009 [P] T010 [P] T011 [P] T012.
**US3**: T015 / T016 / T017 each follow T014 individually but all edit the same file — sequence rather than parallelize.
**US4**: T019 [P] T021 in parallel with US3 transcription; T020 sequential after T014.
**US5 / US6 / Polish**: independent files where marked [P].

---

## Parallel Example: User Story 2

```bash
# Launch four placeholder-test conversions in parallel (different files, no shared dependencies):
Task: "Convert tests/pipeline_tests/test_evidence_gate_skip_fallback.py per contracts/gpu-test-marker.md (US2-1)"
Task: "Convert tests/pipeline_tests/test_evidence_gate_skip_fallback_borderline.py per contracts/gpu-test-marker.md (US2-2)"
Task: "Convert tests/pipeline_tests/test_evidence_gate_all_suppressed_lazy_construction.py per contracts/gpu-test-marker.md (US2-3 + US2-4)"
Task: "Convert tests/unit/preprocessing/test_warmup_skip_fallback_exception.py per contracts/gpu-test-marker.md (US2-4)"
```

## Parallel Example: User Story 1 fixtures

```bash
# Launch four fixture files in parallel:
Task: "Create tests/contract_tests/fixtures/ollama_api_ps_pass.json (PASS shape)"
Task: "Create tests/contract_tests/fixtures/ollama_api_ps_partial.json (size_vram < size)"
Task: "Create tests/contract_tests/fixtures/ollama_api_ps_cpu_only.json (size_vram == 0)"
Task: "Create tests/contract_tests/fixtures/ollama_api_ps_missing.json (model absent)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001, T002).
2. Phase 2 is empty — skip.
3. Complete Phase 3: US1 (T003–T008). Helper shipped; CPU-safe contract test passes.
4. **STOP and VALIDATE**: Operator runs Paddle preflight + the new Ollama helper on the workstation; both pass. CPU CI green.
5. MVP — feature 021's gate is now operational; the rest can land incrementally.

### Incremental Delivery

1. Setup + US1 → MVP gate operational.
2. US2 → feature-020 GPU-deferred verification closed (SC-004).
3. US3 → Appendix A populated (SC-005, SC-006).
4. US4 → Appendix B Quality-Gate Verdict (SC-007).
5. US5 → Demo runbook ready (SC-008).
6. US6 → Promotion decision recorded (SC-009); conditional inverted default if PASS + team chooses promote.
7. Polish → SC-010, SC-011, full checklist sweep.

### Parallel Team Strategy

With multiple developers:

1. All complete Setup together (T001 + T002 — small).
2. Dev A: US1 (T003–T008).
3. Dev B: US2 (T009–T012, fully parallel internally).
4. Dev C: US5 runbook scaffold (T023) — can start before US3/US4 because the §Promotion Decision section is a placeholder updated later.
5. Dev D: US3 Appendix A skeleton (T013) + US4 test conversion (T019) + US6 skeletons (T025, T026, T027).
6. Operator (with workstation): T014 (four-run benchmark) + T020 (evaluator) — gates US3 / US4 populations.
7. Team session: T028 promotion decision.
8. Polish: any developer.

---

## Notes

- **Conditional tasks** (T029, T030) execute only if T028 records `promote to default`. If `stay opt-in` is the recorded decision, both are skipped — the FR-028 explicit-off legacy path does NOT need to exist when the operational default is unchanged.
- **Operator steps** (T014, T020, T028) require workstation hardware. They are not blocking for code-level authoring of skeletons and tests; an implementor agent without workstation access can complete every other task and leave operator-pending markers for T014, T020, T028.
- **File-sharing on Appendix B**: T013, T015–T018, T021, T022, T025, T028 all touch `specs/020-vendor-evidence-gate/quickstart.md`. Single-developer flow handles this naturally; multi-developer flow should coordinate via per-task PRs.
- **No new pinned dependencies**: T001 only registers a marker; T002 creates a YAML file; no `pyproject.toml` `[project] dependencies` change required.
- **FR-004 negative invariant ("MUST NOT write a GPU-labelled artifact when running on CPU") is enforced procedurally, not by a dedicated negative test**: FR-001 Paddle preflight aborts a GPU-labelled run before any artifact is written, so the artifact-write path is unreachable from a CPU interpreter. No additional CPU-path negative test is added; T031 verifies CPU CI green, T032 verifies the committed corpus and contract schemas are untouched, T008 verifies the Ollama helper's exit codes, and the preflight gate (feature 014/015 surface) is the load-bearing contract. Acknowledged as an accepted limitation of this feature's test surface — closes the `/speckit.analyze` G2 coverage observation.
- **Constitution compliance** is verified by Phase 1 plan §Post-Phase-1 Re-evaluation (already PASS); the polish T035/T036 sweep confirms no drift introduced during Phases 3–8.
- Commit after each task or logical group. Stop at any checkpoint to validate independently.
- Avoid: vague tasks, cross-story dependencies that break independence, force-pushing or destructive git operations.
