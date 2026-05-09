# Quickstart: PPStructureV3 Module And Model Reduction

**Feature**: 017-ppstructurev3-module-reduction

This walkthrough exercises the five core paths the feature owns: (1) legacy GPU run (no flags), (2) reduced module set GPU run (`--module-set=reduced-v1`), (3) lighter det/rec variant GPU run (`--det-rec-variant=ppocrv5-mobile`), (4) CPU warn-and-proceed (flags set on `ppstructurev3@cpu`), and (5) unknown-preset fail-fast. Each path is independently runnable on the workstation; the FR-005 benchmark numbers and the FR-001 audit landing observation fill in **Appendix A** and `research.md` Appendix B respectively before merge.

The walkthrough assumes you are inside the worktree at `/workspace/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline-worktrees/017-ppstructurev3-module-reduction` and that feature 015's GPU lane is already working (`scripts/start-host-ollama-rocm-wsl.sh` runs cleanly; `.venv-paddle-rocm` exists; `paddlepaddle-dcu` imports without error). Feature 016's `--gpu-warmup` is orthogonal to this feature's flags and may be combined freely.

## 0. One-time environment

```bash
# Activate the workstation Paddle/ROCm venv (feature 014/015/016 precedent).
source .venv-paddle-rocm/bin/activate

# Confirm Paddle GPU bind works (feature 014 preflight smoke-test).
python -m ledgerlinc_ocr.preprocessing.preflight --device gpu:0
# Expected: state=ppstructurev3_init_succeeded; exit code 0.

# Confirm the new identifier surface lands on every run_summary (CPU-safe).
python -m ledgerlinc_ocr.preprocessing \
  --document-folder tests/stage1_vendor_identity/inv_001_easy \
  --preprocess-profile=ppstructurev3@cpu \
  > /tmp/cpu_no_flag.stdout
tail -1 /tmp/cpu_no_flag.stdout | jq '{schema_version, module_set_id, det_rec_variant_id, ppstructure_modules_invoked}'
# Expected:
# {
#   "schema_version": "0.1.4",
#   "module_set_id": "cpu-default",
#   "det_rec_variant_id": "cpu-default",
#   "ppstructure_modules_invoked": []
# }
```

## 1. Legacy GPU run (the no-flag baseline)

Runs `ppstructurev3@gpu` with no preset flags; both identifiers default to `legacy`; the audit lists every sub-module the legacy GPU configuration invokes on a real vendor-identity invoice.

```bash
# Use a scratch copy so the committed corpus baseline is not modified.
rm -rf /tmp/inv_001_easy_legacy
cp -R tests/stage1_vendor_identity/inv_001_easy /tmp/inv_001_easy_legacy

python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_001_easy_legacy \
  --preprocess-profile=ppstructurev3@gpu \
  > /tmp/legacy.stdout \
  2> /tmp/legacy.stderr

tail -1 /tmp/legacy.stdout | jq '{schema_version, module_set_id, det_rec_variant_id, ppstructure_modules_invoked}'
# Expected (illustrative — exact list pinned at landing per research.md Appendix B):
# {
#   "schema_version": "0.1.4",
#   "module_set_id": "legacy",
#   "det_rec_variant_id": "legacy",
#   "ppstructure_modules_invoked": ["layout_detection", "ocr_det", "ocr_rec", "table_recognition"]
# }
```

Record the observed `ppstructure_modules_invoked` list in **`research.md` Appendix B** (the FR-001 audit landing observation).

## 2. Reduced module set GPU run

Same fixture, with `--module-set=reduced-v1` to disable `use_table_recognition`. The audit list MUST be a strict subset of the legacy list (typically loses `table_recognition`).

```bash
rm -rf /tmp/inv_001_easy_reduced
cp -R tests/stage1_vendor_identity/inv_001_easy /tmp/inv_001_easy_reduced

python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_001_easy_reduced \
  --preprocess-profile=ppstructurev3@gpu \
  --module-set=reduced-v1 \
  > /tmp/reduced.stdout \
  2> /tmp/reduced.stderr

tail -1 /tmp/reduced.stdout | jq '{module_set_id, det_rec_variant_id, ppstructure_modules_invoked}'
# Expected (illustrative):
# {
#   "module_set_id": "reduced-v1",
#   "det_rec_variant_id": "legacy",
#   "ppstructure_modules_invoked": ["layout_detection", "ocr_det", "ocr_rec"]
# }
```

Then assert preprocess_output.json validates against the existing v1.2.0 schema:

```bash
python -m ledgerlinc_ocr.validator validate artifact \
  --kind preprocess_output \
  --path /tmp/inv_001_easy_reduced/preprocess_output.json
# Expected: validates against contracts/stage1_vendor_identity/v1.2.0/preprocess_output.schema.json (FR-003 / SC-001).
```

## 3. Lighter det/rec variant GPU run

Same fixture, with `--det-rec-variant=ppocrv5-mobile` to swap detection + recognition models to PP-OCRv5 mobile pair. Module set stays `legacy` (axes are orthogonal). Per-page inference time should drop materially; the audit list is unchanged from §1 (det/rec variants change weights inside `ocr_det` / `ocr_rec`, not which sub-modules execute).

```bash
rm -rf /tmp/inv_001_easy_v5mobile
cp -R tests/stage1_vendor_identity/inv_001_easy /tmp/inv_001_easy_v5mobile

python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_001_easy_v5mobile \
  --preprocess-profile=ppstructurev3@gpu \
  --det-rec-variant=ppocrv5-mobile \
  > /tmp/v5mobile.stdout \
  2> /tmp/v5mobile.stderr

tail -1 /tmp/v5mobile.stdout | jq '{module_set_id, det_rec_variant_id, ppstructure_modules_invoked, "per_doc": .per_document[0].phase_timings.per_page_inference}'
# Expected:
# {
#   "module_set_id": "legacy",
#   "det_rec_variant_id": "ppocrv5-mobile",
#   "ppstructure_modules_invoked": ["layout_detection", "ocr_det", "ocr_rec", "table_recognition"]
# }
```

Repeat with `--det-rec-variant=ppocrv4-mobile` for the second comparison point. Record the per-page inference seconds for each variant in **Appendix A** (the FR-005 benchmark observation).

## 4. CPU warn-and-proceed

Verifies that GPU-only flags set on `ppstructurev3@cpu` do not silently apply (FR-013). The run completes normally; one stderr warning per ignored flag is emitted; both identifiers on `run_summary` reflect the CPU defaults.

```bash
rm -rf /tmp/inv_001_easy_cpu_with_flags
cp -R tests/stage1_vendor_identity/inv_001_easy /tmp/inv_001_easy_cpu_with_flags

python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_001_easy_cpu_with_flags \
  --preprocess-profile=ppstructurev3@cpu \
  --module-set=reduced-v1 \
  --det-rec-variant=ppocrv5-mobile \
  > /tmp/cpu_with_flags.stdout \
  2> /tmp/cpu_with_flags.stderr

# stderr should contain two warning lines, one per flag:
grep "ignored:" /tmp/cpu_with_flags.stderr
# Expected:
# warning: --module-set ignored: active preprocess profile is 'ppstructurev3@cpu', not 'ppstructurev3@gpu'
# warning: --det-rec-variant ignored: active preprocess profile is 'ppstructurev3@cpu', not 'ppstructurev3@gpu'

# run_summary identifiers reflect the CPU defaults — the flags had no effect:
tail -1 /tmp/cpu_with_flags.stdout | jq '{module_set_id, det_rec_variant_id}'
# Expected:
# { "module_set_id": "cpu-default", "det_rec_variant_id": "cpu-default" }

# preprocess_output.json is byte-identical to the no-flag CPU run:
sha256sum /tmp/inv_001_easy_cpu_with_flags/preprocess_output.json /tmp/cpu_no_flag.stdout
# (Compare against the no-flag CPU run from §0 — preprocess_output.json sha256 must match.)
```

## 5. Unknown-preset fail-fast

Verifies that a typo'd identifier value fails before any Paddle import (R-017.9 / R-017.12). Exit code is **16**; stderr names the valid values.

```bash
python -m ledgerlinc_ocr.preprocessing \
  --document-folder tests/stage1_vendor_identity/inv_001_easy \
  --preprocess-profile=ppstructurev3@cpu \
  --module-set=reduced-v99
echo $?
# Expected: 16
# Expected stderr line:
# error: unknown module_set: 'reduced-v99' — valid values are: legacy, reduced-v1, cpu-default, stub-default

python -m ledgerlinc_ocr.preprocessing \
  --document-folder tests/stage1_vendor_identity/inv_001_easy \
  --preprocess-profile=ppstructurev3@cpu \
  --det-rec-variant=ppocrv9_imaginary
echo $?
# Expected: 16
# Expected stderr line:
# error: unknown det_rec_variant: 'ppocrv9_imaginary' — valid values are: legacy, ppocrv5-mobile, ppocrv4-mobile, cpu-default, stub-default
```

## 6. Quality-gate evaluation (release-gate procedure, not a runtime check)

Verifies the FR-015 / SC-008 two-metric gate against the legacy GPU baseline, using only existing evaluator outputs (R-017.10).

```bash
# 1. Run the full pipeline (preprocess → evidence-packet → extract → route → assemble → evaluate)
#    on the fixed 5-doc subset under the legacy GPU configuration. The evaluator emits
#    evaluation_run_summary.json under the corpus root.
python -m ledgerlinc_ocr.pipeline run \
  --documents-file <path-to-fixed-5-doc-list> \
  --preprocess-profile=ppstructurev3@gpu \
  --module-set=legacy --det-rec-variant=legacy \
  --evaluate

# 2. Repeat for the candidate configuration (e.g., reduced-v1 + ppocrv5-mobile).
python -m ledgerlinc_ocr.pipeline run \
  --documents-file <path-to-fixed-5-doc-list> \
  --preprocess-profile=ppstructurev3@gpu \
  --module-set=reduced-v1 --det-rec-variant=ppocrv5-mobile \
  --evaluate

# 3. Read both metrics from each run's evaluation_run_summary.json:
#    - aggregate.field_score
#    - documents_passed
#    Promotion gate: candidate >= legacy on BOTH metrics simultaneously.

jq '{aggregate_field_score: .aggregate.field_score, documents_passed: .documents_passed}' \
   <legacy-evaluation_run_summary.json>
jq '{aggregate_field_score: .aggregate.field_score, documents_passed: .documents_passed}' \
   <candidate-evaluation_run_summary.json>
```

Record both pairs of numbers in **Appendix A** alongside the per-page inference seconds from §3.

## Appendix A — Benchmark numbers and quality-gate evidence (filled at landing)

> **`<filled at landing time after running the FR-005 benchmark + FR-015 gate>`** — current placeholder. At landing, this section MUST list:
>
> ### A.1 Benchmark wall-clock numbers (FR-005 / SC-002)
>
> Fixed 5-doc subset (R-017.11): `inv_001_easy`, `inv_002_easy`, `<medium-doc>`, `<hard-doc-1>`, `<hard-doc-2>` — pin the exact medium and hard names at landing.
>
> | `module_set_id` | `det_rec_variant_id` | mean per-page inference (s) | mean total (s) | sample size |
> |---|---|---|---|---|
> | `legacy` | `legacy` | `<TBD>` | `<TBD>` | 5 |
> | `legacy` | `ppocrv5-mobile` | `<TBD>` | `<TBD>` | 5 |
> | `legacy` | `ppocrv4-mobile` | `<TBD>` | `<TBD>` | 5 |
> | `reduced-v1` | `legacy` | `<TBD>` | `<TBD>` | 5 |
> | `reduced-v1` | `ppocrv5-mobile` | `<TBD>` | `<TBD>` | 5 |
> | `reduced-v1` | `ppocrv4-mobile` | `<TBD>` | `<TBD>` | 5 |
>
> ### A.2 Quality-gate evidence (FR-015 / FR-016 / SC-008 / Clarifications Q1)
>
> | Configuration | aggregate field score | documents passed (5 max) | gate vs legacy | promote? |
> |---|---|---|---|---|
> | `legacy` × `legacy` (baseline) | `<TBD>` | `<TBD>` | — | (legacy default) |
> | `legacy` × `ppocrv5-mobile` | `<TBD>` | `<TBD>` | `<>= legacy on both?>` | `<TBD>` |
> | `legacy` × `ppocrv4-mobile` | `<TBD>` | `<TBD>` | `<>= legacy on both?>` | `<TBD>` |
> | `reduced-v1` × `legacy` | `<TBD>` | `<TBD>` | `<>= legacy on both?>` | `<TBD>` |
> | `reduced-v1` × `ppocrv5-mobile` | `<TBD>` | `<TBD>` | `<>= legacy on both?>` | `<TBD>` |
> | `reduced-v1` × `ppocrv4-mobile` | `<TBD>` | `<TBD>` | `<>= legacy on both?>` | `<TBD>` |
>
> ### A.3 Promotion decision (FR-015 / FR-017)
>
> - `<one of: keep legacy default; promote <module_set_id> × <det_rec_variant_id> to new GPU default — recording the candidate's identifier values that will appear in subsequent run_summary lines>`
> - Both metrics on the chosen candidate (if any) MUST be ≥ legacy on the same subset; otherwise legacy stays the default and the candidate remains opt-in only.
>
> If GPU verification is deferred per FR-024, this Appendix must list the deferred-task ID(s) from `tasks.md` instead of being silently empty.
