# Integration-readiness review — round 2

**Date:** 2026-05-25
**Reviewer:** integration-readiness-r2 (general-purpose, swarm round 2)
**Branch:** 023-gpu-mvp-demo-hardening @ 7f4aa00
**Question:** Will the first real workstation smoke run succeed? What's still missing?

---

## Smoke-run prediction table

Assumes the operator has done: ROCm + paddlepaddle-dcu in `.venv-paddle-rocm`, `scripts/start-host-ollama-rocm-wsl.sh` running, the `gemma4:e4b` model GPU-placed, `OLLAMA_CONTEXT_LENGTH=2048` exported. Predictions are for **after issue #53 lands** (real `_DefaultPipelineComposer`).

| Phase / step | Predicted outcome | Why | Operator remediation if fail |
|---|---|---|---|
| Readiness 1 — `interpreter/venv` | **pass** | Interpreter under `.venv-paddle-rocm/bin/python` will satisfy `InterpreterVenvCheck`. | Re-`source` the venv. |
| Readiness 2 — `paddle-rocm-preflight` | **pass-after-cold-cost** | First call to `preflight.classify(attempt_ppstructurev3_init=True)` constructs PPStructureV3 — cold MIOpen this is **30 – 300 s**, not the 30 s the runbook implies. Result is cached process-wide (`_LAST_READOUT`). | If `WarmupError` cause: see `gpu-warmup-and-cache.md` clearance procedure. |
| Readiness 3 — `ollama-reachability` | **pass** | `httpx.get /api/ps` against `localhost:11434` succeeds; cached body threaded into checks 5/6. | Start Ollama via the documented script. |
| Readiness 4 — `ollama-version` | **pass** | Ollama ≥ 0.4.0 is a stated prerequisite. | Upgrade Ollama. |
| Readiness 5 — `ollama-model-gpu-placement` | **pass** | Model `gemma4:e4b` from `configs/voter/ollama-gpu.yaml` will match an `/api/ps` entry with `size_vram == size > 0` when the startup script ran correctly. | `ollama pull gemma4:e4b`; restart with GPU env. |
| Readiness 6 — `ollama-context-length` | **pass** | Soft-pass when `/api/ps` omits `context_length`; hard-pass when it reports ≥ 2048. | Re-export `OLLAMA_CONTEXT_LENGTH=2048` before startup. |
| Pipeline: preprocess | **FAIL — composer stub** today; **plausible-pass** after #53 | `_DefaultPipelineComposer.preprocess` currently raises `PipelineUnavailable` (orchestrator.py:106–115). The real wiring needs to construct `preprocessing.pipeline.Invocation(document_folder, preprocess_lane="gpu0", preprocess_strategy_id="ocr-only-v1", module_set_id=..., det_rec_variant_id=..., raster_profile_id=..., region_strategy_id=...)` and call `pipeline.run()`. That `run()` returns a `Path`, NOT a dict-with-`run_summary` — see §2 below. | After #53: re-run; for transient ROCm hangs check `rocm-smi`. |
| Pipeline: extraction | **FAIL — composer stub**; **pass after #53** if Ollama healthy | `extract.pipeline.run(folder_path, voter_config, voter, template_path, *, pipeline_version, contract_set_version)` exposes an in-process API. The composer must (a) parse the voter-config into a `VoterConfig`, (b) instantiate the Ollama `VoterAdapter`, (c) locate the prompt template. The demo's `VoterConfigReference` is **not** the extract module's `VoterConfig` — they're two different shapes; #53 has to translate. | After #53: check Ollama health; context-window errors → bigger `OLLAMA_CONTEXT_LENGTH`. |
| Pipeline: routing | **pass after #53** | `router.pipeline.run(folder, *, pipeline_version, policy_version, ...)` is a thin, deterministic CPU-only step. | Inspect `routing_decision.json`. |
| Pipeline: final_payload | **pass after #53** | `assembler.pipeline.run(Invocation(document_folder=..., pipeline_version=..., contract_set_version=...))` — straightforward. | Read assembler invariant error stderr. |
| Readiness 7 — `artifact-schema-validation` | **pass on happy path; AttributeError-buggy on failure** | **BUG**: `schema_validation.py:64` uses `first.code` and `first.message` on `Violation` (real fields: `violation_code`, `reason`). Any real validation failure surfaces as `AttributeError: 'Violation' object has no attribute 'code'` via the outer `except Exception`. Diagnostic still fires, but content is wrong. | Patch the field names. |
| Readiness 8 — `pipeline-runtime-timeout` | **pass** | Reads `runtime_timeout_observed` flag set by orchestrator. No real-world risk. | n/a |
| CPU-fallback interrogation | **likely pass / occasionally unreachable** | Ollama re-probe is a 2 s `httpx.get`. Paddle re-probe goes through `preflight.classify()` — **cache hit** because the readiness call already populated `_LAST_READOUT`, so returns in ~milliseconds. The 2 s per-probe / 5 s aggregate budget is comfortable. | On `unreachable`: check Ollama still up; on `fell_back`: re-warm GPU. |
| Quality-status derivation | **defaults to safe** but **NOT gate-derived** until the composer publishes `run_summary` | `quality_derivation.derive` reads `preprocess_run_summary["evidence_gate_documents"][doc_id]["state"]`. `_extract_run_summary` looks for `result["run_summary"]` or `result.run_summary` on what `composer.preprocess()` returns. **Real `preprocessing.pipeline.run()` returns a `Path`, not a dict** — and emits its `RunSummary` line **only via stdout from the CLI wrapper**, not from `pipeline.run()`. Result: `quality_status` will default to `"insufficient"`-based-fallback (`review_required`), which is the safe default but not the SC-004 truth. | #53 must adapt `pipeline.run()` to also surface the in-memory `RunSummary` (either return `{"output_path": Path, "run_summary": dict}` from the composer wrapper, or have the composer read the persisted `run_summary.json` if one is written — see §5). |

**Cold-cache total wall time prediction**: readiness ~30 s + first PPStructureV3 init 30–300 s (cold MIOpen) + preprocess 5–30 s + extract 5–30 s + routing+assemble ~1 s ≈ **1.5 – 6 minutes**. Inside the 600 s ceiling on a clean MIOpen cache; *at the edge* on first-ever cache build. The runbook's `5× expected wall-time` heuristic (≈ 10 min) is wider than the 600 s SIGALRM ceiling — those two numbers disagree.

---

## Missing-piece inventory (cap: 20)

| # | Piece | Status | Tracked where | Smallest-shippable-now version |
|---|---|---|---|---|
| 1 | Real `_DefaultPipelineComposer` (in-process composition) | Stub raises `PipelineUnavailable` | Issue #53 | Thin adapter file `gpu_demo/composer_default.py` calling `preprocessing.pipeline.run`, `extract.pipeline.run`, `router.pipeline.run`, `assembler.pipeline.run` with translated args. |
| 2 | `composer.preprocess()` must surface `run_summary` dict | Not surfaced | #53 acceptance | Adapter wraps return: `{"output_path": p, "run_summary": <captured from emit_run_summary callback>}`. Requires preprocessing CLI/runner to expose a programmatic hook, OR composer reads `<folder>/run_summary.json` sidecar if one is added. |
| 3 | `VoterConfigReference` ↔ extract `VoterConfig` translation | Missing | #53 acceptance | The composer's `extract` method must read `voter_ref.path` and construct the extract module's `VoterConfig` + `VoterAdapter` + template path. Sketch: `gpu_demo.composer_default._build_extract_inputs(voter_ref)`. |
| 4 | Schema-validation `first.code`/`first.message` bug | Live bug | Fix in this PR | Rename to `first.violation_code` / `first.reason` in `readiness/schema_validation.py:64`. **Land before PR.** |
| 5 | MIOpen cache pre-warm guidance in runbook | Implicit only | Runbook §Prerequisites | Add explicit "first cold run may take 5+ minutes; consider `python -m dartwing_ocr.preprocessing.preflight` once before the demo to populate `~/.cache/miopen`." |
| 6 | 600 s ceiling vs runbook's "5× expected wall-time" | Inconsistent | Runbook §Step 2b vs FR-008 | Reconcile: either raise ceiling or tighten runbook wording. Cold-cache run could legitimately exceed 5 min. |
| 7 | `voter_config.yaml` discovery vs `configs/voter/ollama-gpu.yaml` | Discovery paths don't include `configs/voter/` | `voter_config_loader._auto_discover` | Either add `Path.cwd() / "configs" / "voter" / "ollama-gpu.yaml"` to the search path, or document `--voter-config` as required for the demo. **Currently the operator MUST pass `--voter-config configs/voter/ollama-gpu.yaml`** or the auto-discovery falls through to the bundled extract default whose `model_name` is **`gemma-edge.yaml::ollama.model_tag`** — different shape, may not parse cleanly. |
| 8 | Pre-run model presence verification | Not in runbook | Runbook §Prerequisites | Add `ollama list | grep gemma4:e4b` as a verification line. |
| 9 | `--with-evaluator` happy-path test fixture | Not landed | Coverage matrix | Hand-author a `semantic_table_truth.json` fixture pairing with `inv_001_easy` so US3 isn't only tested with `sidecar_missing` / subprocess-failed paths. |
| 10 | Sample `DemoRunReport` updated with new fields | `data-model.md` examples missing `pre_run_ollama_snapshot`, `quality_status_source` keys ARE present but inline | data-model.md §6 | Refresh the three sample reports inline; ensure 17 keys match `DEMO_REPORT_SCHEMA_VERSION`. |
| 11 | Runbook §Multi-Ollama disambiguation | Missing | Runbook | Add a paragraph: "`OLLAMA_BASE_URL` defaults to `http://localhost:11434`; set to `http://<host>:11434` only when running against a remote workstation. The demo emits an INFO line on non-localhost hosts." |
| 12 | Workstation `@pytest.mark.gpu` smoke | Not landed | Issue #54 | Tracked; depends on #53. Smallest version: one parametrized test that runs the demo 3× against `inv_001_easy` and diffs the three deterministic artifacts. |
| 13 | Realistic stub artifacts for happy-path tests | `bypass_schema_validation` monkey-patches check 7 | conftest.py | Hand-author v1.3.0-schema-valid stubs in `tests/fixtures/gpu_demo/realistic/` so happy-path tests can drop `bypass_schema_validation`. Surfaces the §4 bug. |
| 14 | Cold vs warm guidance for `--check-only` | Runbook says "≤ 10 s warm, ≤ 30 s informal cold" | Runbook prereq #5 | Already documented but should also note: first `--check-only` on a fresh shell triggers cold MIOpen init, which CAN exceed 30 s on this workstation. |
| 15 | `quality_status_source` "preset" not in `QualityStatusSource` enum check | Existing enum: `"gate" / "evaluator"` (or similar) | data-model | Confirm the enum spelling matches `R-023.20` and tests. |
| 16 | Eager-delete & re-run safety | Documented FR-017 | Already covered | n/a — well covered. |
| 17 | `OLLAMA_CONTEXT_LENGTH` reading from env vs CLI | CLI does not expose; only env-var | `_build_options_from_args` | Documented; OK. Add a runbook note: "set in same shell as Ollama startup." (already in runbook line 222) |
| 18 | `--with-evaluator` runbook section | Not in §Canonical Demo Command | Runbook | Add a paragraph on when to use it and the warn-and-skip fallback. |
| 19 | Promotion-decision lockstep with f.020 quickstart | Placeholder "stay opt-in" | Runbook §Promotion Decision | Acceptable as TBD. |
| 20 | Diagnostic on `post-run-interrogation-unreachable` is now non-null | Already addressed by triage K6 | Closed | Confirmed. |

---

## Runbook readiness scorecard

| Section | Score | Notes |
|---|---|---|
| Pre-flight steps | **PARTIAL** | Prerequisites table is solid; missing explicit "first run cold MIOpen can take 5+ min" warning and `ollama list` model verification step. |
| Cold vs warm run | **PARTIAL** | `--check-only` cold budget documented; full demo cold-cache wall-time NOT documented (the 5× heuristic implicitly maxes at ~10 min but no calibrated number). |
| Failure interpretation (6 exit codes) | **PASS** | §Readiness Failure Recovery Matrix covers exit 1 thoroughly; exit-code table is closed. Could add "exit 4 with `cpu-fallback-detected`" sub-row for the SC-004 case. |
| Sample output | **PARTIAL** | `data-model.md §6` has three sample reports but they're stale relative to the latest fields (`pre_run_ollama_snapshot`, `quality_status_source`). Update + cross-link from the runbook. |
| Multi-Ollama disambiguation | **MISSING** | `OLLAMA_BASE_URL` is honored but the runbook doesn't explain when to set it or what the INFO line looks like. |

---

## Pre-PR checklist (cap: 20)

Concrete items that should land **before** the PR opens:

1. **[BUG]** Fix `readiness/schema_validation.py:64` field names: `first.code` → `first.violation_code`, `first.message` → `first.reason`. One-line fix; otherwise schema failures surface as `AttributeError` strings.
2. Refresh `data-model.md` §6 sample reports to match the 17-key `DemoRunReport` shape (include `pre_run_ollama_snapshot` and `quality_status_source` populated examples).
3. Reconcile the 600 s SIGALRM ceiling vs runbook's "5× expected wall-time (~10 min)" heuristic — align to one number (recommend keeping 600 s and tightening runbook prose).
4. Add a `Realistic stub artifacts` fixture set in `tests/fixtures/gpu_demo/` (v1.3.0-schema-valid) so at least one happy-path test can drop `bypass_schema_validation` — this is also how the §1 bug would have been caught.
5. Add runbook §Multi-Ollama disambiguation paragraph (under §Canonical Demo Command).
6. Add explicit cold-MIOpen warning under runbook §Prerequisites — "first run after fresh shell may take 5+ min; pre-warm via `python -m dartwing_ocr.preprocessing.preflight` once."
7. Add `ollama list | grep <model>` to the Step 1b prerequisites checklist.
8. Coverage matrix audit: confirm rows for the 4 new tests and modified one landed in 7f4aa00 (`coverage-fr-task-test.md` mentions Date 2026-05-25 — verify it covers the triage fixes).
9. (Optional) Decide whether `voter_config_loader._auto_discover` should also include `configs/voter/ollama-gpu.yaml`, or document `--voter-config` as required. The runbook demo command does NOT pass `--voter-config`, so auto-discovery is what runs — and auto-discovery doesn't find the GPU config.

Items 1, 2, 3 are blockers; the rest are quality-of-life.

---

## Sign-off

**NOT-READY-TO-OPEN-PR**

Reasons:
- §1 bug (`first.code` / `first.message`) means the schema-validation diagnostic is broken on the failure path — a regression in a feature whose whole point is hardening the demo's failure surface.
- §2 stale `data-model.md` examples will confuse reviewers AND fail to demonstrate the new fields.
- §3 the 600 s vs 5×-expected (~10 min) gap leaves the operator without a clear "is this a hang or is it cold-cache?" rule.

After items 1–3 land, the branch is **READY-TO-OPEN-PR with workstation smoke deferred to #53/#54**. CPU-isolated story (56+ passing tests + the orchestration logic) is solid; the workstation gaps are honestly tracked.
