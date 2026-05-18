# Quickstart: GPU MVP Promotion (Feature 021)

**Date**: 2026-05-18 · **Branch**: `021-gpu-mvp-promotion` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md)

This walk-through is for a pipeline developer or workstation operator validating the GPU MVP promotion checkpoint end-to-end. It covers (a) the readiness gate, (b) running the four converted GPU-deferred tests, (c) executing the four-run benchmark and recording Appendix A, (d) running the two-metric quality gate and recording Appendix B, (e) updating the demo runbook, (f) recording the promotion decision.

> **Audience**: a pipeline developer who already has the `.venv-paddle-rocm` interpreter and host Ollama running. This is NOT the operator-facing demo runbook (that lives at `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` — see [contracts/runbook.md](./contracts/runbook.md)). This quickstart is the dev-facing implementation guide; the demo runbook is a deliverable of FR-025.

## Prerequisites (one-time)

- `.venv-paddle-rocm` with `paddlepaddle-dcu` installed (features 014–019 conventions).
- Host Ollama running via `scripts/start-host-ollama-rocm-wsl.sh` (WSL) or the native Linux equivalent.
- `configs/voter/ollama-gpu.yaml` exists with a non-empty `model_name` matching the loaded Ollama extraction model (R-021.7). If missing, create it as a single-line YAML:
  ```yaml
  model_name: "qwen2.5vl:7b"   # or whichever model is loaded on this workstation's Ollama
  ```
- `jq` and `yq` available on PATH (system packages).
- A clean `/tmp/021-bench/` (or accept that prior runs will be overwritten by lane/run identity).

## Path 1 — Readiness Gate (US1, FR-001 + FR-002)

```bash
# 1a. Paddle preflight (FR-001)
.venv-paddle-rocm/bin/python -m dartwing_ocr.preprocessing.preflight 2>readiness-paddle.log
# Expected: stdout shows state: ppstructurev3_init_succeeded; exit 0.

# 1b. Ollama placement (FR-002, via the new shell helper)
scripts/check-ollama-gpu-readiness.sh \
    --voter-config configs/voter/ollama-gpu.yaml \
    2>readiness-ollama.log
# Expected: exit 0 + a single JSON line on stdout with status:"pass".
```

If either check fails, STOP. Read the corresponding `.log` for the named blocker. Do NOT proceed to Path 2.

Smoke test (CPU-safe, no live Ollama needed): the contract for the helper lives in [contracts/ollama-readiness-helper.md](./contracts/ollama-readiness-helper.md); the helper's exit-code taxonomy is the testable surface.

## Path 2 — Convert the Four Feature-020 Deferred GPU Tests (US2, FR-006 – FR-010)

Each of the five placeholder files retains its top-level `pytestmark = pytest.mark.gpu` (collection-level GPU gate). Per-test `@pytest.mark.skip(reason="R-020.15")` decorators are removed and replaced with real assertion bodies that match the spec's US2 / US4 scenarios:

```bash
# Confirm the GPU marker is registered in pyproject.toml (silences PytestUnknownMarkWarning)
grep -A2 '\[tool.pytest.ini_options\]' pyproject.toml | grep -F '"gpu:'

# Run the converted tests on the GPU lane
.venv-paddle-rocm/bin/pytest -m gpu -v \
    tests/pipeline_tests/test_evidence_gate_skip_fallback.py \
    tests/pipeline_tests/test_evidence_gate_skip_fallback_borderline.py \
    tests/pipeline_tests/test_evidence_gate_all_suppressed_lazy_construction.py \
    tests/unit/preprocessing/test_warmup_skip_fallback_exception.py \
    tests/pipeline_tests/test_quality_gate_two_metric_evidence_gate.py
```

Per [contracts/gpu-test-marker.md](./contracts/gpu-test-marker.md):

- Each test passes (real assertion) OR marks itself BLOCKED via `pytest.xfail(strict=False)` with a named hardware/runtime cause (FR-010, R-021.6 spirit applied to test reporting).
- Silent skips are NOT permitted (SC-004).

CPU CI behavior is unchanged: `pytest -m 'not gpu'` continues to skip all five files at collection.

## Path 3 — Four-Run Benchmark on the Fixed Five-Document Subset (US3, FR-011 – FR-018)

```bash
# Establish scratch tree (R-021.1)
mkdir -p /tmp/021-bench/{warmup,legacy,candidate}/{run1,run2}

# Copy the five FR-011 documents into each (lane, run) subdir
DOCS=(inv_001_easy inv_002_easy inv_006_medium inv_011_hard inv_012_hard)
for LANE in warmup legacy candidate; do
    for RUN in run1 run2; do
        # warmup only has run1 — skip warmup/run2
        [[ "$LANE" == "warmup" && "$RUN" == "run2" ]] && continue
        for D in "${DOCS[@]}"; do
            mkdir -p "/tmp/021-bench/$LANE/$RUN/$D"
            cp "tests/stage1_vendor_identity/$D/source.pdf" "/tmp/021-bench/$LANE/$RUN/$D/"
        done
    done
done

# Generate per-(lane, run) documents-file pointing at the scratch folders just created.
# IMPORTANT: in warm-corpus mode the pipeline writes outputs back into each folder
# listed in --documents-file. The list MUST point at scratch copies, NOT the committed
# corpus, to satisfy FR-018 (no committed-corpus mutation).
for LANE in warmup legacy candidate; do
    for RUN in run1 run2; do
        [[ "$LANE" == "warmup" && "$RUN" == "run2" ]] && continue
        DOCSFILE="/tmp/021-bench/$LANE/$RUN/docs.txt"
        : >"$DOCSFILE"
        for D in "${DOCS[@]}"; do
            echo "/tmp/021-bench/$LANE/$RUN/$D" >>"$DOCSFILE"
        done
    done
done

# Run the four-run discipline (FR-012) — warmup, legacy x2, candidate x2.

# warmup — discardable
.venv-paddle-rocm/bin/python -m dartwing_ocr.pipeline run \
    --documents-file /tmp/021-bench/warmup/run1/docs.txt \
    --preprocess-profile ppstructurev3@gpu \
    --preprocess-strategy ocr-only-v1 \
    --extract-profile ollama@gpu \
    2>warmup.stderr | tee warmup.run_summary.jsonl

# legacy lane — DEFAULT skip-fallback OFF (legacy posture); captures `run_summary` per doc.
for RUN in run1 run2; do
    .venv-paddle-rocm/bin/python -m dartwing_ocr.pipeline run \
        --documents-file "/tmp/021-bench/legacy/$RUN/docs.txt" \
        --preprocess-profile ppstructurev3@gpu \
        --preprocess-strategy ocr-only-v1 \
        --extract-profile ollama@gpu \
        2>"legacy.$RUN.stderr" | tee "legacy.$RUN.run_summary.jsonl"
done

# candidate lane — `--evidence-gate-skip-fallback` ON
for RUN in run1 run2; do
    .venv-paddle-rocm/bin/python -m dartwing_ocr.pipeline run \
        --documents-file "/tmp/021-bench/candidate/$RUN/docs.txt" \
        --preprocess-profile ppstructurev3@gpu \
        --preprocess-strategy ocr-only-v1 \
        --extract-profile ollama@gpu \
        --evidence-gate-skip-fallback \
        2>"candidate.$RUN.stderr" | tee "candidate.$RUN.run_summary.jsonl"
done
```

> **CLI flag note**: The flags above are verified against `src/dartwing_ocr/pipeline/cli.py` as of 2026-05-18. Pipeline CLI is `python -m dartwing_ocr.pipeline run` (the package's `__main__.py` dispatches to the `run` subcommand). The OCR-only skip-fallback lane requires BOTH `--preprocess-profile ppstructurev3@gpu` AND `--preprocess-strategy ocr-only-v1` (per the CLI's `--preprocess-strategy` help text). The voter is selected via `--extract-profile ollama@gpu` (a profile preset that encodes the Ollama GPU lane); the voter-config YAML at `configs/voter/ollama-gpu.yaml` is consumed by the readiness helper only — it is NOT a pipeline CLI flag.
>
> **Scratch-output discipline note (C6)**: In warm-corpus mode (`--documents-file`), the pipeline writes per-document output artifacts BACK INTO each folder listed in the documents-file (per `src/dartwing_ocr/pipeline/runner.py` `run_plan(plan, folder=folder_resolved)` — the per-doc folder IS the destination; `--output-dir` is only honored in single-document `--input <pdf>` mode). To satisfy FR-018 / SC-011, the documents-file MUST list **scratch-copied** per-doc folders under `/tmp/021-bench/<lane>/<run>/<doc>/` — NOT the committed corpus paths under `tests/stage1_vendor_identity/`. The shell block above mirrors `source.pdf` into the scratch tree and generates per-lane-per-run `docs.txt` files pointing at the scratch folders, so all outputs land in `/tmp/021-bench/...` and `git status tests/stage1_vendor_identity/` remains clean.
>
> If feature 011 / 020's CLI surface drifts in a future feature, re-pin from `python -m dartwing_ocr.pipeline run --help`. The structural discipline (one warmup + two-of-each-lane) is fixed.

Then extract the run-2 `phase_timings.*` per document per lane from the `run_summary.jsonl` lines and populate [Appendix A](../020-vendor-evidence-gate/quickstart.md) per [contracts/appendix-recording.md §Appendix A](./contracts/appendix-recording.md).

## Path 4 — Two-Metric Quality Gate (US4, FR-019 – FR-022)

```bash
# Score each lane via the existing feature-007 evaluator (R-021.13)
# CLI: `python -m dartwing_ocr.evaluator evaluate corpus <root>` (subcommand pattern; verified against
# src/dartwing_ocr/evaluator/cli.py — `evaluate` group with `doc` and `corpus` subcommands).
.venv-paddle-rocm/bin/python -m dartwing_ocr.evaluator evaluate corpus \
    /tmp/021-bench/legacy/run2/

.venv-paddle-rocm/bin/python -m dartwing_ocr.evaluator evaluate corpus \
    /tmp/021-bench/candidate/run2/

# Each command writes `evaluation_document.json` into every per-doc folder under <root> and
# `evaluation_run_summary.json` at <root>. Then compute the verdict per FR-020 (PASS = candidate >= legacy on BOTH metrics):
.venv-paddle-rocm/bin/python -m pytest -m gpu tests/pipeline_tests/test_quality_gate_two_metric_evidence_gate.py -v
```

> **Evaluator CLI flag note**: The `evaluate corpus <root>` invocation above is verified against `src/dartwing_ocr/evaluator/cli.py` as of 2026-05-18. The evaluator may accept additional optional flags (e.g., output destination overrides); re-pin from `python -m dartwing_ocr.evaluator evaluate corpus --help` if a future feature 007 amendment changes them.

Record the verdict in [Appendix B](../020-vendor-evidence-gate/quickstart.md) per [contracts/appendix-recording.md §Appendix B](./contracts/appendix-recording.md):

- PASS: both metrics non-regressing → permitted (but not automatic) operator decision to promote.
- FAIL: at least one metric regresses → skip-fallback MUST remain opt-in (FR-027) and the regressing metric + magnitude are recorded.
- BLOCKED: gate cannot run because of a named hardware/runtime cause → skip-fallback MUST remain opt-in (FR-027) and the named cause is recorded.

## Path 5 — Update the Demo Runbook (US5, FR-025)

Create `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` following [contracts/runbook.md](./contracts/runbook.md) section structure. Key invariants:

- Readiness gate (Step 1) comes BEFORE the demo command (Step 2).
- Step 2 uses `ppstructurev3@gpu` + `configs/voter/ollama-gpu.yaml` only — NO `@cpu` or `stub` command in the documented path.
- Step 3 walks through every one of the seven feature-020 `run_summary` observability fields.
- Step 7 (Scratch discipline) reproduces FR-018 + FR-025(f).
- Step 8 (Promotion Decision) mirrors the Appendix B subsection.

Self-check after writing: `grep -E '@cpu|stub-voter' docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` MUST return zero matches (FR-025(c), SC-008).

## Path 6 — Record the Promotion Decision (US6, FR-026 – FR-029)

After the FR-019 verdict is recorded in Appendix B:

- **If FAIL or BLOCKED** (FR-027): the recorded decision MUST be `stay opt-in`. Add the `### Promotion Decision (YYYY-MM-DD)` subsection to Appendix B with `Decision: stay opt-in`, the rationale, and the gating-verdict back-pointer. Mirror in the runbook §Promotion Decision.

- **If PASS** (FR-029): the team makes an explicit decision (PASS PERMITS but does NOT REQUIRE promotion):
  - **Stay opt-in path**: record `Decision: stay opt-in` in Appendix B + runbook mirror. No code change.
  - **Promote-to-default path**: invert the default at `src/dartwing_ocr/preprocessing/evidence_gate_optin.py` (or wherever the skip-fallback default currently lives — confirm via `grep -rn "evidence_gate_skip_fallback" src/dartwing_ocr/preprocessing/` before editing). Add the FR-028 explicit-off legacy-path test at `tests/unit/preprocessing/test_skip_fallback_explicit_off_legacy.py` and ensure it passes under `pytest -m 'not gpu'`. Record the full Promotion Decision Record shape (see [data-model.md §5](./data-model.md)).

Verify synchronization (per [contracts/appendix-recording.md §Promotion-decision synchronization contract](./contracts/appendix-recording.md)):

```bash
.venv/bin/pytest tests/contract_tests/test_promotion_decision_sync.py -v
```

(This contract test is created by this feature's `/speckit.tasks` output; it loads both files and asserts the binary decision literal matches.)

## Smoke Tests (CPU-Safe — Always Available)

These run without GPU and confirm the feature's CPU-touchable surfaces:

```bash
# 1. Helper exit-code contract (mocked HTTP via fixture)
.venv/bin/pytest tests/contract_tests/test_ollama_readiness_helper_contract.py -v

# 2. Promotion decision synchronization (Appendix B vs. runbook mirror)
.venv/bin/pytest tests/contract_tests/test_promotion_decision_sync.py -v

# 3. CPU-safe twin tests of the converted GPU tests' invariants — UNCHANGED from feature 020
.venv/bin/pytest tests/pipeline_tests/test_evidence_gate_skip_fallback_borderline_cpu.py -v
.venv/bin/pytest tests/pipeline_tests/test_evidence_gate_recorded_over_final.py -v

# 4. Runbook GPU-discipline grep (FR-025(c))
grep -E '@cpu|stub-voter' docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md && exit 1 || echo "PASS: no CPU fallback in demo runbook"
```

## What this feature does NOT change

- No new canonical artifact schema (FR-031).
- No new `run_summary` field (FR-032). Feature 020's `RunSummary.SCHEMA_VERSION = 0.1.7` is used as-is.
- No new evaluator metric (R-021.13).
- No remote cloud (Constitution §I, Stage 1 Scope Constraint).
- No Jetson `edge-fast` validation.
- No corpus baseline regeneration (FR-033).

## Cross-references

- [spec.md](./spec.md) — feature spec + Clarifications 2026-05-18.
- [plan.md](./plan.md) — this feature's implementation plan.
- [research.md](./research.md) — R-021.1 through R-021.13 planning decisions.
- [data-model.md](./data-model.md) — entity shapes for verdicts, run records, jitter band, promotion decision.
- [contracts/ollama-readiness-helper.md](./contracts/ollama-readiness-helper.md) — shell helper invocation contract.
- [contracts/gpu-test-marker.md](./contracts/gpu-test-marker.md) — pytest marker + test-conversion contract.
- [contracts/appendix-recording.md](./contracts/appendix-recording.md) — Appendix A + B table shapes.
- [contracts/runbook.md](./contracts/runbook.md) — demo runbook structural contract.
- [checklists/*.md](./checklists/) — eight release-gate checklists (355 deep items).
