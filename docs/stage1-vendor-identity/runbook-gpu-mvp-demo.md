# GPU MVP Demo Runbook

This runbook is the canonical operator path for the stage-1 vendor-identity GPU-required demo (feature 021). It starts with the FR-001 / FR-002 readiness gate, runs the demo using `ppstructurev3@gpu` for preprocessing and `ollama@gpu` for extraction, surfaces the seven feature-020 `run_summary` observability fields, and ends with the recorded promotion decision. CPU paths are NOT in scope here (see `docs/stage1-vendor-identity/ollama-runtime.md` for CPU/stub operational guidance).

## Prerequisites

- AMD ROCm workstation (WSL or native Linux).
- `paddlepaddle-dcu` installed in `.venv-paddle-rocm` (matching feature 014–019 conventions).
- Host Ollama started via `scripts/start-host-ollama-rocm-wsl.sh` (WSL) or the equivalent native Linux path; the extraction model named by the demo's voter config is loaded with GPU placement.
- A scratch directory `/tmp/021-bench/` available (or another explicit scratch root).
- The voter config at `configs/voter/ollama-gpu.yaml` (R-021.7) names the loaded extraction model.

**Operator skills**: this runbook assumes operator familiarity with `git`, Python venvs, and basic shell (`bash` / `zsh`). Anything beyond that floor is explained inline below.

**Demo audience**: internal pipeline engineers and reviewers. External stakeholders (compliance, legal) by invitation only — the demo surfaces internal observability fields that may carry context-sensitive information.

**Expected wall-time**: the readiness gate (Step 1) takes ≈ 30 seconds; the canonical demo command (Step 2b) takes ≈ 60–120 seconds per run on this workstation. A run that exceeds 5× expected wall-time is a finding and should be investigated before the demo continues.

## Step 1 — GPU Readiness Gate (REQUIRED)

The demo MUST NOT proceed if either of the two readiness sub-steps fails. The composite GPU Readiness Verdict (FR-001 + FR-002) is PASS only when both checks PASS.

### Step 1a — Paddle preflight (FR-001)

```bash
.venv-paddle-rocm/bin/python -m dartwing_ocr.preprocessing.preflight 2>readiness-paddle.log
```

Expected outcome: stdout shows `state: ppstructurev3_init_succeeded`. On any other state, STOP and read `readiness-paddle.log` for the named blocker. Do NOT continue under degraded conditions — the FR-004 fail-fast surface requires it.

Common blockers and remediation:

| Stderr blocker (paraphrased)                  | Likely cause                                  | Operator action                                     |
|----------------------------------------------|----------------------------------------------|----------------------------------------------------|
| `paddle_cpu_only`                             | Wrong interpreter / CPU `.venv` selected      | Re-run from `.venv-paddle-rocm/bin/python`         |
| `paddle_not_installed`                        | `paddlepaddle-dcu` not in active venv         | `pip install paddlepaddle-dcu` (workstation only)  |
| `gpu_bind_failed` / `rocm_missing`            | ROCm runtime not visible to Python            | Check `rocm-smi`; ensure HSA env is set correctly  |
| Other named state                             | See FR-010 closed list of named-cause categories | Read full `readiness-paddle.log` and remediate |

### Step 1b — Ollama placement (FR-002)

```bash
scripts/check-ollama-gpu-readiness.sh \
    --voter-config configs/voter/ollama-gpu.yaml \
    2>readiness-ollama.log
```

Expected outcome: exit 0 + a single JSON line on stdout with `"status": "pass"`. Specifically, the helper asserts that the matched-model entry in `/api/ps` has `size_vram > 0 AND size_vram == size` (fully on GPU per Clarification Q2 / FR-002). Partial CPU/GPU placement (`0 < size_vram < size`) fails the check.

Common remediation:

| Helper exit | Likely cause                         | Operator action                                                                          |
|------------:|--------------------------------------|------------------------------------------------------------------------------------------|
| `1`         | Mixed CPU/GPU placement              | Restart Ollama with GPU env set; verify with `rocm-smi` that VRAM is available           |
| `2`         | Model not loaded                     | Run `ollama run <model_name> ""` once to warm the model into Ollama, then re-check       |
| `3`         | Ollama unreachable                   | Confirm `scripts/start-host-ollama-rocm-wsl.sh` is running; check port 11434 is open     |
| `4`         | Voter config missing / malformed     | Confirm `configs/voter/ollama-gpu.yaml` exists and has a non-empty top-level `model_name` |

Only proceed to Step 2 when both Step 1a AND Step 1b PASS. Capture both `readiness-paddle.log` and the helper's stdout PASS JSON for the run record (see Step 5 / Appendix A environment fingerprint).

## Step 2 — Run the Canonical Demo Command

### Step 2a — Scratch-prep the demo corpus

The pipeline writes outputs back into each per-doc folder listed in `--documents-file` (warm-corpus mode does not honor `--output-dir` per research.md §R-021.14). To preserve FR-018 / FR-025(f) / SC-011 (no committed-corpus mutation), mirror `source.pdf` for each demo document into a scratch tree first:

```bash
DEMO_DOCS=(inv_001_easy inv_002_easy)   # whichever subset the demo audience expects
for D in "${DEMO_DOCS[@]}"; do
    mkdir -p "/tmp/021-bench/demo/$D"
    cp "tests/stage1_vendor_identity/$D/source.pdf" "/tmp/021-bench/demo/$D/"
done
: >/tmp/021-bench/demo/docs.txt
for D in "${DEMO_DOCS[@]}"; do
    echo "/tmp/021-bench/demo/$D" >>/tmp/021-bench/demo/docs.txt
done
```

### Step 2b — Run the demo

```bash
.venv-paddle-rocm/bin/python -m dartwing_ocr.pipeline run \
    --documents-file /tmp/021-bench/demo/docs.txt \
    --preprocess-profile ppstructurev3@gpu \
    --preprocess-strategy ocr-only-v1 \
    --extract-profile ollama@gpu
```

Required flag set (all verified against the actual CLI):

- `--documents-file <PATH>` — text file listing scratch per-document folders (one per line, e.g., `/tmp/021-bench/demo/inv_001_easy`). MUST point at the scratch tree from Step 2a, NEVER at `tests/stage1_vendor_identity/` directly.
- `--preprocess-profile ppstructurev3@gpu` — selects the GPU preprocessing profile.
- `--preprocess-strategy ocr-only-v1` — enables the OCR-only fast lane that the evidence gate's skip-fallback acts on. Both flags are required together for the documented behavior.
- `--extract-profile ollama@gpu` — selects the GPU-backed Ollama extraction voter. The voter-config YAML at `configs/voter/ollama-gpu.yaml` is consumed by the readiness helper (Step 1b), NOT by this command.

Optional flags for documented variants:

- `--evidence-gate-skip-fallback` — enable OCR-only skip-fallback suppression (the candidate lane in feature 020 / 021 promotion evidence).
- `--gpu-warmup` — force PPStructureV3 construction even when every document is suppressed (FR-009 operator trade-off).

## Step 3 — Read the `run_summary` Line

The demo emits a single `kind: "run_summary"` JSON line on stdout (feature 015 lineage). The runbook explains each of the seven required FR-025(d) observability fields:

- **`schema_version`** — feature 020 `RunSummary.SCHEMA_VERSION` (currently `0.1.7`). Audit signal: confirms the demo is running on the feature-020 baseline.
- **`preprocess_lane`** — `gpu0` for this demo (the lane suffix is the device index; CPU lanes emit `cpu`). If this field reads `cpu`, something has gone wrong; STOP and re-run Step 1.
- **`preprocess_strategy_id`** — `ocr-only-v1` (matches the `--preprocess-strategy ocr-only-v1` flag passed in Step 2b; the `--preprocess-profile ppstructurev3@gpu` flag selects the lane, not the strategy).
- **`evidence_gate_id`** — must be `"v1"` (the closed vocabulary at landing per feature 020 R-020.2). Anything other than `"v1"` means either a future preset has been added or the serializer is buggy; STOP and investigate.
- **`evidence_gate_state_counts`** — distribution of `sufficient` / `borderline` / `insufficient` across the processed documents. Reads as a per-state count map.
- **`evidence_gate_documents`** — per-document table of decisions; cross-check against scratch outputs at `/tmp/021-bench/demo/<doc>/`.
- **`evidence_gate_suppressed_fallback_count`** — non-zero iff at least one `sufficient` document was suppressed (i.e., the demo was run with `--evidence-gate-skip-fallback` or its default-on equivalent if promote-to-default is the recorded posture; see §Promotion Decision below).

## Step 4 — Demonstrate Suppression Behavior (Optional)

If the audience wants to see suppression in action, re-run Step 2b twice — once with and once without `--evidence-gate-skip-fallback`:

```bash
# Default lane (skip-fallback OFF; PPStructureV3 fallback fires on every doc).
.venv-paddle-rocm/bin/python -m dartwing_ocr.pipeline run \
    --documents-file /tmp/021-bench/demo/docs.txt \
    --preprocess-profile ppstructurev3@gpu \
    --preprocess-strategy ocr-only-v1 \
    --extract-profile ollama@gpu

# Candidate lane (skip-fallback ON; PPStructureV3 fallback suppressed on sufficient docs).
.venv-paddle-rocm/bin/python -m dartwing_ocr.pipeline run \
    --documents-file /tmp/021-bench/demo/docs.txt \
    --preprocess-profile ppstructurev3@gpu \
    --preprocess-strategy ocr-only-v1 \
    --extract-profile ollama@gpu \
    --evidence-gate-skip-fallback
```

Compare the two `run_summary` lines:

- The candidate run's `evidence_gate_suppressed_fallback_count` MUST be > 0 (one increment per `sufficient` document).
- The candidate run's per-doc `phase_timings.engine_init` and `phase_timings.warmup` keys MUST be absent on suppressed documents (lazy construction; FR-008).
- Default-lane `phase_timings.engine_init` and `phase_timings.warmup` keys MUST be present (PPStructureV3 fallback ran for every doc).

## Scratch Discipline

A short reminder reproducing FR-018 + FR-025(f): all output lands under `/tmp/021-bench/` (or another explicit scratch root); committed corpus under `tests/stage1_vendor_identity/` is NEVER mutated by a demo run. Operators concerned about contamination can `git status tests/stage1_vendor_identity/` after the demo and confirm zero changes.

**Cleanup discipline**: after the demo / benchmark, the operator MAY `rm -rf /tmp/021-bench/` to remove scratch outputs. Scratch retention is operator choice — the runbook does not require it but does not forbid it.

## Promotion Decision

This section mirrors the authoritative `### Promotion Decision (YYYY-MM-DD)` subsection in [feature-020 `quickstart.md` Appendix B](../../specs/020-vendor-evidence-gate/quickstart.md). Mirror content MUST agree with Appendix B on the binary `Decision:` literal; a CPU-safe contract test at `tests/contract_tests/test_promotion_decision_sync.py` verifies the agreement.

**Decision**: _(placeholder — populate from Appendix B when the team records the decision per T028. Allowed values: `stay opt-in` or `promote to default`. Default at landing: `stay opt-in`.)_

**Gating verdict**: see [Appendix B §Quality-Gate Verdict](../../specs/020-vendor-evidence-gate/quickstart.md) for the FR-019 verdict (`PASS` / `FAIL` / `BLOCKED`) that gates this decision. FR-027 — if the gating verdict is FAIL or BLOCKED, the recorded Decision MUST be `stay opt-in`; promotion is not a permitted option.

If the recorded Decision is `promote to default`, the operator can opt back to legacy behavior for a CPU-safe smoke run with:

```bash
DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=0 .venv/bin/pytest tests/unit/preprocessing/test_skip_fallback_explicit_off_legacy.py -v
```

(The legacy-path test is created by T030 when promote-to-default lands. Until then, the test file does not exist.)

## When Things Go Wrong

Concise table of common failure paths with named-cause remediation:

| Symptom                                                  | Likely cause                          | Remediation                                                                              |
|----------------------------------------------------------|----------------------------------------|------------------------------------------------------------------------------------------|
| Paddle preflight returns a non-success state             | Wrong interpreter, missing ROCm, …    | Read `readiness-paddle.log`; fix the named blocker; re-run Step 1a.                       |
| `check-ollama-gpu-readiness.sh` exits non-zero           | See Step 1b remediation table.         | Read the script's `FAIL:` stderr line; apply the Step 1b remediation table row matching that named cause; re-run Step 1b. |
| Demo command exits non-zero                              | Likely a missed readiness step.        | Re-run Step 1; if Step 1 passes, capture the demo stderr and escalate.                    |
| `evidence_gate_suppressed_fallback_count` is unexpectedly 0 on a `sufficient` document | Skip-fallback not enabled. | Either pass `--evidence-gate-skip-fallback` (stay-opt-in operational mode) or confirm the runbook reflects the current promotion decision. |
| Demo wall-time exceeds 5× expected (Step 2b > ~10 min)   | GPU contention, cache cold, ROCm drift | Verify exclusive GPU access (no other process consuming `rocm-smi`-reported VRAM); re-run; if persistent, raise a workstation finding. |

**Abort path** (mid-demo cleanup): `Ctrl+C` interrupts the running pipeline command. After interrupt, the operator MAY `rm -rf /tmp/021-bench/` to clean up scratch outputs. Readiness state (Paddle preflight + Ollama placement) is unchanged by the interrupt — re-running the demo from Step 2 does not require re-running Step 1 unless Ollama state has changed (e.g., the model was unloaded).

## Documentation discipline

- Runbook examples MUST use document IDs (e.g., `inv_001_easy`) and synthetic vendor strings where any vendor-identity content is shown.
- This runbook MUST NEVER include real vendor names, addresses, or other PII extracted from any document in `tests/stage1_vendor_identity/`. Feature 006's PII screening covers the corpus; the runbook MUST NOT undo that screening by reproducing screened content in example output.

## See also

- [feature-020 quickstart Appendix A](../../specs/020-vendor-evidence-gate/quickstart.md) — recorded benchmark numbers (the four-run + jitter-band tables operators populate after running T014).
- [feature-020 quickstart Appendix B](../../specs/020-vendor-evidence-gate/quickstart.md) — Quality-Gate Verdict + Promotion Decision (the authoritative copy of which this runbook mirrors).
- [docs/stage1-vendor-identity/ollama-runtime.md](./ollama-runtime.md) — host Ollama setup, WSL caveats.
- [docs/stage1-vendor-identity/gpu-warmup-and-cache.md](./gpu-warmup-and-cache.md) — `MIOPEN_FIND_MODE=2`, warmup behavior, cache locations (feature 016 lineage).
- [feature-021 `contracts/runbook.md`](../../specs/021-gpu-mvp-promotion/contracts/runbook.md) — the structural contract this runbook implements.
