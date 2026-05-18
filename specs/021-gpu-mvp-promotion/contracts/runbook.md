# Contract: Demo Runbook Structure (FR-025)

**Path**: `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` (new; R-021.5)
**Spec refs**: [spec.md §FR-025, §US5](../spec.md), [research.md §R-021.5, §R-021.7, §R-021.9](../research.md)
**Constitution refs**: §I (runtime boundaries — WSL vs. native Linux), §V (reproducible delivery)

This contract pins the runbook's structural shape so a new operator can complete the MVP demo end-to-end without source-code consultation (SC-008).

## Required sections (in order)

### 1. `# GPU MVP Demo Runbook`

Single-sentence purpose: this runbook is the canonical operator path for the stage-1 vendor-identity GPU-required demo. CPU paths are NOT in scope here (see `docs/stage1-vendor-identity/ollama-runtime.md` for CPU/stub operational guidance).

### 2. `## Prerequisites`

Bulleted list (no commands yet):

- AMD ROCm workstation (WSL or native Linux).
- `paddlepaddle-dcu` installed in `.venv-paddle-rocm` (matching feature 014–019 conventions).
- Host Ollama started via `scripts/start-host-ollama-rocm-wsl.sh` (WSL) or the equivalent native Linux path; the extraction model named by the demo's voter config is loaded with GPU placement.
- A scratch directory `/tmp/021-bench/` available (or another explicit scratch root).
- The voter config at `configs/voter/ollama-gpu.yaml` (R-021.7) names the loaded extraction model.

### 3. `## Step 1 — GPU Readiness Gate (REQUIRED)`

Two sub-steps in fixed order:

**3a. Paddle preflight (FR-001)**

```bash
.venv-paddle-rocm/bin/python -m dartwing_ocr.preprocessing.preflight 2>readiness-paddle.log
```

Expected outcome: stdout shows `state: ppstructurev3_init_succeeded`. On any other state, STOP and read `readiness-paddle.log` for the named blocker (FR-004). Do NOT continue under degraded conditions.

**3b. Ollama placement (FR-002)**

```bash
scripts/check-ollama-gpu-readiness.sh \
    --voter-config configs/voter/ollama-gpu.yaml \
    2>readiness-ollama.log
```

Expected outcome: exit 0 + a single JSON line on stdout matching the `OllamaReadinessProbeResult` PASS shape (see [data-model.md §6](../data-model.md)). Specifically, `size_vram > 0 AND size_vram == size` for the matched model. On any non-zero exit, STOP and read `readiness-ollama.log` for the named blocker.

Common remediation table (matched to exit codes from [ollama-readiness-helper.md](./ollama-readiness-helper.md)):

| Exit | Likely cause                         | Operator action                                                                          |
|-----:|--------------------------------------|------------------------------------------------------------------------------------------|
| `1`  | Mixed CPU/GPU placement              | Unload + reload the model on a GPU-only Ollama session, or restart Ollama with GPU env. |
| `2`  | Model not loaded                     | Run `ollama run <model_name> ""` once to warm the model into Ollama, then re-check.     |
| `3`  | Ollama unreachable                   | Confirm `scripts/start-host-ollama-rocm-wsl.sh` is running; check port 11434 is open.   |
| `4`  | Voter config missing / malformed     | Confirm `configs/voter/ollama-gpu.yaml` exists and has a non-empty top-level `model_name`. |

### 4. `## Step 2 — Run the Canonical Demo Command`

GPU profiles only, no CPU fallback. CLI flags and warm-corpus output semantics verified against `src/dartwing_ocr/pipeline/cli.py` + `src/dartwing_ocr/pipeline/runner.py` as of 2026-05-18.

**Step 2a — Scratch-prep the demo corpus**. The pipeline writes outputs back into each per-doc folder listed in `--documents-file` (warm-corpus mode does not honor `--output-dir`). To preserve FR-018 / FR-025(f) / SC-011 (no committed-corpus mutation), the runbook directs the operator to mirror `source.pdf` for each demo document into a scratch tree first:

```bash
DEMO_DOCS=(inv_001_easy inv_002_easy)   # whichever subset the demo audience expects
for D in "${DEMO_DOCS[@]}"; do
    mkdir -p "/tmp/021-bench/demo/$D"
    cp "tests/stage1_vendor_identity/$D/source.pdf" "/tmp/021-bench/demo/$D/"
done
: >/tmp/021-bench/demo/docs.txt
for D in "${DEMO_DOCS[@]}"; do echo "/tmp/021-bench/demo/$D" >>/tmp/021-bench/demo/docs.txt; done
```

**Step 2b — Run the demo**:

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
- `--preprocess-strategy ocr-only-v1` — enables the OCR-only fast lane that the evidence gate's skip-fallback acts on. Both flags are required together for the documented behavior (per CLI `--preprocess-strategy` help text).
- `--extract-profile ollama@gpu` — selects the GPU-backed Ollama extraction voter. The voter-config YAML at `configs/voter/ollama-gpu.yaml` is consumed by the readiness helper (Step 1b), NOT by this command.

Optional flags for documented variants:

- `--evidence-gate-skip-fallback` — enable OCR-only skip-fallback suppression (the candidate lane in feature 020). The default (skip-fallback OFF / opt-in) holds unless the promotion decision recorded in §8 is `promote to default`, in which case the legacy posture is invoked via `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=0` (the *same* env var, with the inverted-default disabled).
- `--gpu-warmup` — force PPStructureV3 construction even when every document is suppressed (FR-009 operator trade-off).

The runbook MUST NOT show a `ppstructurev3@cpu` alternative, an `ollama@cpu` alternative, a `stub` voter alternative, an `--output-dir` flag (it is not honored in warm-corpus mode), or any inline "if GPU fails, try …" degraded path.

### 5. `## Step 3 — Read the `run_summary` Line`

The demo emits a single `kind: "run_summary"` JSON line on stdout (feature 015 lineage). The runbook explains each of the seven required observability fields with operator-facing reading guidance:

- `schema_version` — must be `0.1.7` (feature 020 baseline).
- `preprocess_lane` — must be `gpu` (audit signal; FR-003 interpreter-path verification).
- `preprocess_strategy_id` — must be `ppstructurev3@gpu`.
- `evidence_gate_id` — should match the active preset (feature 020 `header-default-v1` or operator's chosen preset).
- `evidence_gate_state_counts` — distribution of `sufficient` / `borderline` / `insufficient` across the processed documents.
- `evidence_gate_documents` — per-document table of decisions; cross-check against scratch outputs.
- `evidence_gate_suppressed_fallback_count` — non-zero iff at least one `sufficient` document was suppressed (i.e., demo was run with `--evidence-gate-skip-fallback` or its default-on equivalent if promote-to-default landed).

### 6. `## Step 4 — Demonstrate Suppression Behavior (Optional)`

If the audience wants to see suppression in action: re-run Step 2 with and without `--evidence-gate-skip-fallback`. The runbook shows the expected delta in `evidence_gate_suppressed_fallback_count` and the expected absence of `phase_timings.engine_init` / `phase_timings.warmup` when lazy construction is in effect.

### 7. `## Scratch Discipline`

A short reminder reproducing FR-018 + FR-025(f): all output lands under `/tmp/021-bench/` (or another explicit scratch root); committed corpus under `tests/stage1_vendor_identity/` is NEVER mutated by a demo run. Operators concerned about contamination can `git status tests/stage1_vendor_identity/` after the demo and confirm zero changes.

### 8. `## Promotion Decision`

Mirror of the Appendix B `### Promotion Decision (YYYY-MM-DD)` subsection (per [appendix-recording.md §Promotion-decision synchronization contract](./appendix-recording.md)). Must contain:

- The binary decision literal (`stay opt-in` or `promote to default`).
- A link to the Appendix B authoritative subsection.
- If `promote to default`: a one-liner naming the explicit-off flag/env-var so an operator can opt back to legacy behavior for a CPU-safe smoke run.

### 9. `## When Things Go Wrong`

Concise table of common failure paths with named-cause remediation:

| Symptom                                                  | Likely cause                          | Remediation                                                         |
|----------------------------------------------------------|----------------------------------------|---------------------------------------------------------------------|
| Paddle preflight returns a non-success state             | Wrong interpreter, missing ROCm, …    | Read `readiness-paddle.log`; fix the named blocker; re-run Step 1a. |
| `check-ollama-gpu-readiness.sh` exits non-zero           | See Step 1b table.                     | …                                                                   |
| Demo command exits non-zero                              | Likely a missed readiness step.       | Re-run Step 1; if Step 1 passes, capture the demo stderr and escalate. |
| `evidence_gate_suppressed_fallback_count` is unexpectedly 0 on a `sufficient` document | Skip-fallback not enabled. | Either pass `--evidence-gate-skip-fallback` (stay-opt-in operational mode) or confirm the runbook reflects the current promotion decision. |

### 10. `## See also`

- [feature-020 quickstart Appendix A](../../specs/020-vendor-evidence-gate/quickstart.md) — recorded benchmark numbers.
- [feature-020 quickstart Appendix B](../../specs/020-vendor-evidence-gate/quickstart.md) — quality-gate verdict + promotion decision authority.
- [docs/stage1-vendor-identity/ollama-runtime.md](./ollama-runtime.md) — host Ollama setup, WSL caveats.
- [docs/stage1-vendor-identity/gpu-warmup-and-cache.md](./gpu-warmup-and-cache.md) — `MIOPEN_FIND_MODE=2`, warmup behavior, cache locations.

## Runbook update lifecycle

- The runbook is owned by this feature at landing. Future features that change `evidence_gate_id`, add a `phase_timings.*` key, or rename a CLI flag MUST update the runbook in the same body of work (Constitution §V; QG #3).
- The runbook MUST NOT contain CPU profile commands (FR-025(c)). A CPU smoke path lives in a separate operational doc.
- A reviewer auditing this runbook MUST be able to grep for `@cpu` and `stub` and find zero matches in any documented command block.

## Testability (runbook self-sufficiency)

- The runbook is self-sufficient (SC-008) iff: a fresh operator on a known-good workstation can execute every Step 1 → Step 4 command verbatim and reach a passing demo without consulting source code.
- The runbook does NOT include "see the code for details" pointers in any command-level instruction.

## What this contract does NOT cover

- It does not pin the prose tone or detailed examples — the runbook author has latitude within the structural shape above.
- It does not define which Ollama model is canonical (named by `configs/voter/ollama-gpu.yaml`); the runbook reads from the config rather than naming a model literally.
- It does not constrain the operator's choice of scratch root beyond requiring it to be outside `tests/stage1_vendor_identity/`.
