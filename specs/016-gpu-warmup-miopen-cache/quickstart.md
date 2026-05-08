# Quickstart: GPU Warmup And MIOpen Cache Stabilization

**Feature**: 016-gpu-warmup-miopen-cache

This walkthrough exercises the four core paths the feature owns: cold-cache warmup, warm-cache warmup, CPU/stub warn-and-proceed, and warmup failure. Each path is independently runnable on the workstation; the cold-vs-warm comparison fills in SC-003's threshold (research R-016.3) and the actual workstation numbers land in **Appendix A** before merge.

The walkthrough assumes you are inside the worktree at `/workspace/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline-worktrees/016-gpu-warmup-miopen-cache` and that feature 015's GPU lane is already working (`scripts/start-host-ollama-rocm-wsl.sh` runs cleanly; `.venv-paddle-rocm` exists; `paddlepaddle-dcu` imports without error).

## 0. One-time environment

```bash
# Activate the workstation Paddle/ROCm venv (feature 014/015 precedent).
source .venv-paddle-rocm/bin/activate

# (Optional) Pre-set MIOpen defaults explicitly if you want to override what
# warmup.run_warmup() will set on its own. Operator-set values win (R-016.4).
# Skipping this step lets the feature's defaults take effect — that is the
# expected production setup.
# export MIOPEN_FIND_MODE=2
# export MIOPEN_USER_DB_PATH="$HOME/.cache/miopen"
# export MIOPEN_CUSTOM_CACHE_DIR="$HOME/.cache/miopen"
# export MIOPEN_LOG_LEVEL=2

# Confirm Paddle GPU bind works (feature 014 preflight smoke-test).
python -m ledgerlinc_ocr.preprocessing.preflight --device gpu:0
# Expected: state=ppstructurev3_init_succeeded; exit code 0.
```

## 1. Cold-cache warmup (the headline path)

Clears the MIOpen / COMGR caches, runs warmup-enabled `ppstructurev3@gpu` on a single fixture, and reads the cold `phase_timings.warmup.seconds`.

```bash
# Clear the caches. This is the operator action FR-017 / SC-009 documents.
rm -rf "$HOME/.cache/miopen" "$HOME/.cache/comgr"

# Single-doc cold-cache run. Use a scratch copy so the committed corpus
# baseline under tests/stage1_vendor_identity/ is not modified.
rm -rf /tmp/inv_001_easy_cold
cp -R tests/stage1_vendor_identity/inv_001_easy /tmp/inv_001_easy_cold

python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_001_easy_cold \
  --preprocess-profile=ppstructurev3@gpu \
  --gpu-warmup \
  > /tmp/warmup_cold.stdout \
  2> /tmp/warmup_cold.stderr

# Inspect run_summary.
tail -1 /tmp/warmup_cold.stdout | jq '.per_document[0] | {phase_timings, per_page_inference}'
# Warm-corpus equivalent:
# python -m ledgerlinc_ocr.pipeline run ... | tail -1 | jq '.per_document[0] | {phase_timings, per_page_inference}'
```

Expected fragment of the first per-document run_summary entry:

```jsonc
{
  "document_id": "inv_001_easy",
  "status": "success",
  "phase_timings": {
    "paddle_import":     {"seconds": <small>},
    "gpu_bind_probe":    {"seconds": <small>},
    "engine_init":       {"seconds": <few-seconds>},
    "warmup":            {"seconds": <COLD-VALUE>},     // ← key new in 0.1.3
    "rasterization":     {"seconds": <small>},
    "artifact_write":    {"seconds": <small>},
    "total":             {"seconds": <sum-excluding-warmup>}
  },
  "per_page_inference": [{"page": 1, "seconds": <steady-state>}]
}
```

Record `<COLD-VALUE>` in **Appendix A**. Confirm the stderr file has no errors and that `total` does NOT include `warmup` (SC-004): `total ≈ rasterization + per_page_inference[0].seconds + artifact_write` (within rounding).

## 2. Warm-cache warmup

Runs the same command in a fresh process WITHOUT clearing caches; warmup hits the now-populated MIOpen kernel database and COMGR compile cache.

```bash
# DO NOT clear caches — that is the whole point of this run.

rm -rf /tmp/inv_001_easy_warm
cp -R tests/stage1_vendor_identity/inv_001_easy /tmp/inv_001_easy_warm

python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_001_easy_warm \
  --preprocess-profile=ppstructurev3@gpu \
  --gpu-warmup \
  > /tmp/warmup_warm.stdout \
  2> /tmp/warmup_warm.stderr
```

Compare `phase_timings.warmup.seconds` from this run to **Appendix A**'s cold value:

- Expected: `cold_seconds >= 2 * warm_seconds` (SC-003 placeholder; tune per R-016.3 with the values you observed).
- If the ratio is significantly lower (e.g., < 1.2× — close to noise), MIOpen may not be hitting the cache. Triage steps in `docs/stage1-vendor-identity/gpu-warmup-and-cache.md`.
- If the ratio is significantly higher (> 10×), the cold-cache cost is dominated by COMGR compile time more than expected. This is informative but not a regression.

**Byte-identity check** (FR-018 / SC-008):

```bash
sha256sum /tmp/inv_001_easy_warm/preprocess_output.json
# Compare to a non-warmup run:
rm -rf /tmp/inv_001_easy_no_warmup
cp -R tests/stage1_vendor_identity/inv_001_easy /tmp/inv_001_easy_no_warmup
python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_001_easy_no_warmup \
  --preprocess-profile=ppstructurev3@gpu \
  > /tmp/no-warmup.stdout \
  2> /tmp/no-warmup.stderr
sha256sum /tmp/inv_001_easy_no_warmup/preprocess_output.json
# The two digests MUST match.
```

## 3. Cold-cache regression: comgr only

Validates the operator-triage path documented in US2 acceptance #3.

```bash
# Clear ONLY the COMGR cache. MIOpen kernel DB stays warm.
rm -rf "$HOME/.cache/comgr"

rm -rf /tmp/inv_001_easy_comgr_only
cp -R tests/stage1_vendor_identity/inv_001_easy /tmp/inv_001_easy_comgr_only

python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_001_easy_comgr_only \
  --preprocess-profile=ppstructurev3@gpu \
  --gpu-warmup \
  > /tmp/warmup_comgr_only.stdout \
  2> /tmp/warmup_comgr_only.stderr
```

Expected: `phase_timings.warmup.seconds` rises measurably from § 2's warm-cache baseline (because COMGR has to recompile shaders) but is typically below the § 1 cold-cache total. Record the value in **Appendix A** so the docs deliverable can quote a representative number.

## 4. CPU / stub warn-and-proceed (no GPU required)

Validates the FR-010 / SC-007 contract clarified per /speckit.clarify Q1.

```bash
# CPU path with the opt-in set anyway.
rm -rf /tmp/inv_001_easy_cpu_warmup
cp -R tests/stage1_vendor_identity/inv_001_easy /tmp/inv_001_easy_cpu_warmup

python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_001_easy_cpu_warmup \
  --preprocess-profile=ppstructurev3@cpu \
  --gpu-warmup \
  > /tmp/cpu-warmup-check.stdout \
  2> /tmp/cpu-warmup-check.stderr

# Or via env var (matches CI ergonomics):
rm -rf /tmp/inv_001_easy_cpu_warmup_env
cp -R tests/stage1_vendor_identity/inv_001_easy /tmp/inv_001_easy_cpu_warmup_env

LEDGERLINC_GPU_WARMUP=1 python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_001_easy_cpu_warmup_env \
  --preprocess-profile=ppstructurev3@cpu \
  > /tmp/cpu-warmup-envvar-check.stdout \
  2> /tmp/cpu-warmup-envvar-check.stderr

# Both runs MUST:
# - exit 0
# - emit ONE stderr line containing the literal "--gpu-warmup ignored:"
# - emit no `phase_timings.warmup` key in run_summary
# - leave $HOME/.cache/miopen / $HOME/.cache/comgr untouched (check mtime)
grep -c "\\-\\-gpu-warmup ignored:" /tmp/cpu-warmup-check.stderr
# Expected: 1
```

## 5. Warmup-failure fail-fast (manual injection)

Validates SC-011. The failure path is hard to trigger naturally, so this section documents the verification approach rather than scripted reproduction.

**Approach**: temporarily monkeypatch `paddleocr.PPStructureV3.predict` (or set `MIOPEN_FIND_MODE=99` to force a MIOpen-internal error) before invoking the CLI. The runner MUST:

1. Print `error: warmup failed: <cause-class>: <message>` to stderr (FR-007).
2. Exit with code **15** (cli-contract.md § 4).
3. Emit no `run_summary` line (no stdout `kind: "run_summary"` JSON).
4. Write no `preprocess_output.json` (the output dir for the targeted document MUST be empty or unchanged from before the run).
5. NOT silently fall back to a no-warmup run.

The integration test `tests/pipeline_tests/test_warmup_failure_path.py @gpu` exercises this with a controlled monkeypatch. CPU-safe variant in `tests/unit/preprocessing/test_warmup_unit.py::test_warmup_predict_raises_wraps_to_warmup_error`.

## 6. Test suite

```bash
# Default suite — must pass on a host without GPU (FR-013 / SC-006).
.venv/bin/pytest -m "not gpu"

# GPU suite — workstation only (FR-012). Defer with FR-014 if no GPU is
# available at landing time; tasks.md MUST capture the deferred verification.
.venv-paddle-rocm/bin/pytest -m gpu tests/unit/preprocessing/test_warmup_*.py tests/pipeline_tests/test_warmup_*.py
```

## Appendix A: Workstation cold-vs-warm verification log (filled at landing)

Replace `<value>` with observed seconds, six-decimal-rounded.

| Run | Caches before | `phase_timings.warmup.seconds` | Notes |
|---|---|---|---|
| § 1 cold | both empty | `<value>` | gfx1151, ROCm `<version>`, paddleocr `<version>` |
| § 2 warm | both populated | `<value>` | same process or fresh process? `<fresh>` |
| § 3 mixed | comgr cleared only | `<value>` | for docs deliverable |

**SC-003 ratio check**: `cold / warm = <ratio>`. Threshold satisfied (`>= 2.0`)? `<yes/no>`. If no, amend research R-016.3 + spec SC-003 before merge per FR-014.

## Appendix B: Workstation MIOpen / COMGR warning catalog (filled at landing)

For `docs/stage1-vendor-identity/gpu-warmup-and-cache.md`. Each observed warning string from § 1's stderr lands in one of two lists:

**Addressed by default config** — for each warning, list the env var / setting from data-model.md § "Default env-var configuration" that suppresses it after the warmup-enabled run with feature-shipped defaults.

**Residual / known runtime diagnostic** — for each warning that remains: meaning (one sentence), whether the operator should act (yes / no — usually no), and a pointer if there is a known follow-up.

This appendix is the source of truth for the FR-016 hybrid policy deliverable per /speckit.clarify Q3.
