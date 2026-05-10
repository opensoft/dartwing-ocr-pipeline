# Quickstart: DPI Reduction And Region-First Vendor Identity Preprocess

**Feature**: 018-dpi-region-first-preprocess

This walkthrough exercises the seven core paths the feature owns: (0) one-time environment + identifier-surface smoke-test on CPU; (1) legacy GPU run (no flags), (2) reduced-DPI GPU run (`--raster-profile=reduced-v1`), (3) region-first GPU run (`--region-strategy=header-first-v1`), (4) combined GPU run (`--raster-profile=reduced-v1 --region-strategy=header-first-v1`), (5) CPU warn-and-proceed (flags set on `ppstructurev3@cpu`), (6) unknown-preset fail-fast on either axis, and (7) FR-007 fallback path verification on a fixture chosen to force the trigger. Each path is independently runnable on the workstation; the FR-005 four-corner benchmark numbers fill in **Appendix A** and the FR-016 quality-gate evidence fills in `research.md` Appendix B before merge.

The walkthrough assumes you are inside the worktree at `/workspace/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline-worktrees/018-dpi-region-first-preprocess` and that feature 015's GPU lane is already working (`scripts/start-host-ollama-rocm-wsl.sh` runs cleanly; `.venv-paddle-rocm` exists; `paddlepaddle-dcu` imports without error). Feature 016's `--gpu-warmup` and feature 017's `--module-set` / `--det-rec-variant` flags are orthogonal to this feature's flags and may be combined freely.

## 0. One-time environment

```bash
# Activate the workstation Paddle/ROCm venv (feature 014/015/016/017 precedent).
source .venv-paddle-rocm/bin/activate

# Confirm Paddle GPU bind works (feature 014 preflight smoke-test).
python -m ledgerlinc_ocr.preprocessing.preflight
# Expected: state=ppstructurev3_init_succeeded; exit code 0.

# Confirm the new identifier surface lands on every run_summary (CPU-safe; no GPU required).
rm -rf /tmp/inv_001_easy_cpu_no_flag
cp -R tests/stage1_vendor_identity/inv_001_easy /tmp/inv_001_easy_cpu_no_flag

python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_001_easy_cpu_no_flag \
  --preprocess-profile=ppstructurev3@cpu \
  > /tmp/cpu_no_flag.stdout
tail -1 /tmp/cpu_no_flag.stdout | jq '{schema_version, raster_profile_id, region_strategy_id, region_strategy_fallback_count}'
# Expected:
# {
#   "schema_version": "0.1.5",
#   "raster_profile_id": "cpu-default",
#   "region_strategy_id": "cpu-default",
#   "region_strategy_fallback_count": 0
# }
```

## 1. Legacy GPU run (the no-flag baseline)

Runs `ppstructurev3@gpu` with no preset flags; both new identifiers default to `legacy` / `full-page`; `region_strategy_fallback_count` is `0`.

```bash
# Use a scratch copy so the committed corpus baseline is not modified.
rm -rf /tmp/inv_001_easy_legacy
cp -R tests/stage1_vendor_identity/inv_001_easy /tmp/inv_001_easy_legacy

python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_001_easy_legacy \
  --preprocess-profile=ppstructurev3@gpu \
  > /tmp/legacy.stdout \
  2> /tmp/legacy.stderr

tail -1 /tmp/legacy.stdout | jq '{schema_version, raster_profile_id, region_strategy_id, region_strategy_fallback_count}'
# Expected:
# {
#   "schema_version": "0.1.5",
#   "raster_profile_id": "legacy",
#   "region_strategy_id": "full-page",
#   "region_strategy_fallback_count": 0
# }
```

`preprocess_output.json` is byte-identical to a no-flag (pre-018) GPU run on this fixture (verified by `test_legacy_byte_identity.py`). Record `phase_timings.rasterization` and `phase_timings.per_page_inference` for the legacy baseline cell of Appendix A.

## 2. Reduced-DPI GPU run

Same fixture, with `--raster-profile=reduced-v1` to drop rasterization DPI from 300 to 200. `phase_timings.rasterization` MUST be lower than the legacy run on this fixture (SC-001).

```bash
rm -rf /tmp/inv_001_easy_reduced_dpi
cp -R tests/stage1_vendor_identity/inv_001_easy /tmp/inv_001_easy_reduced_dpi

python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_001_easy_reduced_dpi \
  --preprocess-profile=ppstructurev3@gpu \
  --raster-profile=reduced-v1 \
  > /tmp/reduced_dpi.stdout \
  2> /tmp/reduced_dpi.stderr

tail -1 /tmp/reduced_dpi.stdout | jq '{raster_profile_id, region_strategy_id, region_strategy_fallback_count, rasterization, per_page_inference}'
# Expected:
# {
#   "raster_profile_id": "reduced-v1",
#   "region_strategy_id": "full-page",
#   "region_strategy_fallback_count": 0,
#   "rasterization": <lower than legacy>,
#   "per_page_inference": <lower than legacy>
# }

# Schema validation: preprocess_output.json must still validate against the v1.2.0 schema
python -m ledgerlinc_ocr.validator validate artifact \
  --artifact-kind preprocess_output \
  /tmp/inv_001_easy_reduced_dpi/preprocess_output.json
# Expected: VALID (per FR-002 / I-018.7).
```

## 3. Region-first GPU run (multi-page invoice; clean — no fallback)

Runs `ppstructurev3@gpu` with `--region-strategy=header-first-v1`. On a multi-page invoice with vendor identity in page 1's top 30%, the trigger does NOT fire and `region_strategy_fallback_count` stays `0`.

```bash
# Use a multi-page invoice fixture.
rm -rf /tmp/inv_002_easy_region_first
cp -R tests/stage1_vendor_identity/inv_002_easy /tmp/inv_002_easy_region_first

python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_002_easy_region_first \
  --preprocess-profile=ppstructurev3@gpu \
  --region-strategy=header-first-v1 \
  > /tmp/region_first.stdout \
  2> /tmp/region_first.stderr

tail -1 /tmp/region_first.stdout | jq '{raster_profile_id, region_strategy_id, region_strategy_fallback_count}'
# Expected:
# {
#   "raster_profile_id": "legacy",
#   "region_strategy_id": "header-first-v1",
#   "region_strategy_fallback_count": 0
# }

# Verify pages[] invariant: page 1 populated; pages 2..N empty
jq '.pages | map({page_number, blocks_count: (.blocks | length), lines_count: (.raw_ocr_lines | length)})' \
  /tmp/inv_002_easy_region_first/preprocess_output.json
# Expected:
# [
#   {"page_number": 1, "blocks_count": <some N > 0>, "lines_count": <some M > 0>},
#   {"page_number": 2, "blocks_count": 0, "lines_count": 0},
#   …
# ]

# Schema validation
python -m ledgerlinc_ocr.validator validate artifact \
  --artifact-kind preprocess_output \
  /tmp/inv_002_easy_region_first/preprocess_output.json
# Expected: VALID (per Clarifications Q2 / I-018.6).
```

## 4. Combined: reduced-DPI + region-first

```bash
rm -rf /tmp/inv_002_easy_combined
cp -R tests/stage1_vendor_identity/inv_002_easy /tmp/inv_002_easy_combined

python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_002_easy_combined \
  --preprocess-profile=ppstructurev3@gpu \
  --raster-profile=reduced-v1 \
  --region-strategy=header-first-v1 \
  > /tmp/combined.stdout

tail -1 /tmp/combined.stdout | jq '{raster_profile_id, region_strategy_id, region_strategy_fallback_count}'
# Expected:
# {
#   "raster_profile_id": "reduced-v1",
#   "region_strategy_id": "header-first-v1",
#   "region_strategy_fallback_count": 0
# }
```

This is the cell of the FR-005 four-corner matrix the team is most likely to consider promoting under FR-016. Record numbers in Appendix A.

## 5. CPU warn-and-proceed

Set either flag (or both) on `ppstructurev3@cpu` and verify warn-and-proceed: stderr carries the `… ignored:` line(s); the run completes with the same exit status it would produce without the flag(s); identifiers reflect the CPU defaults.

```bash
rm -rf /tmp/inv_001_easy_cpu_warn
cp -R tests/stage1_vendor_identity/inv_001_easy /tmp/inv_001_easy_cpu_warn

python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_001_easy_cpu_warn \
  --preprocess-profile=ppstructurev3@cpu \
  --raster-profile=reduced-v1 \
  --region-strategy=header-first-v1 \
  > /tmp/cpu_warn.stdout \
  2> /tmp/cpu_warn.stderr
echo "Exit: $?"
# Expected: Exit: 0 (same as a no-flag CPU run)

grep -E '^warning: --(raster-profile|region-strategy) ignored:' /tmp/cpu_warn.stderr
# Expected: two lines, one per ignored flag (substring `--raster-profile ignored:` and `--region-strategy ignored:` per CLI contract §3).

tail -1 /tmp/cpu_warn.stdout | jq '{raster_profile_id, region_strategy_id, region_strategy_fallback_count}'
# Expected:
# {
#   "raster_profile_id": "cpu-default",
#   "region_strategy_id": "cpu-default",
#   "region_strategy_fallback_count": 0
# }
```

`preprocess_output.json` for this CPU run is byte-identical to a no-flag CPU run on this fixture (FR-019 / I-018.7).

## 6. Unknown-preset fail-fast (either axis)

Selecting an unknown identifier value on either new axis exits with code 16 and prints the standard `error: unknown <preset_axis>: <value!r> — valid values are: <…>` line on stderr (extends feature 017 R-017.12 to the two new axes).

```bash
# Unknown raster_profile
python -m ledgerlinc_ocr.preprocessing \
  --document-folder tests/stage1_vendor_identity/inv_001_easy \
  --preprocess-profile=ppstructurev3@gpu \
  --raster-profile=reduced-v99 \
  > /tmp/unk_raster.stdout 2> /tmp/unk_raster.stderr
echo "Exit: $?"
# Expected: Exit: 16

cat /tmp/unk_raster.stderr
# Expected: error: unknown raster_profile: 'reduced-v99' — valid values are: legacy, reduced-v1, cpu-default, stub-default

# Unknown region_strategy
python -m ledgerlinc_ocr.preprocessing \
  --document-folder tests/stage1_vendor_identity/inv_001_easy \
  --preprocess-profile=ppstructurev3@gpu \
  --region-strategy=header-first-v99 \
  > /tmp/unk_region.stdout 2> /tmp/unk_region.stderr
echo "Exit: $?"
# Expected: Exit: 16

cat /tmp/unk_region.stderr
# Expected: error: unknown region_strategy: 'header-first-v99' — valid values are: full-page, header-first-v1, cpu-default, stub-default

# Verify NO run_summary line is emitted on the fail-fast path
grep -c '"kind": "run_summary"' /tmp/unk_raster.stdout /tmp/unk_region.stdout
# Expected: both files report 0 (no run_summary)
```

## 7. FR-007 fallback path verification

To exercise the FR-007 fallback path, you need a fixture where page 1's top 30% has no vendor-identity-relevant text — e.g., a scanned invoice whose first page is a cover sheet, blank page, or starts the company logo below the 30% line. Pick one such fixture from the corpus (or construct a synthetic one); below uses the placeholder `inv_NNN_fallback_smoke` — replace with the actual chosen fixture name from `tasks.md`.

```bash
rm -rf /tmp/inv_fallback_smoke
cp -R tests/stage1_vendor_identity/inv_NNN_fallback_smoke /tmp/inv_fallback_smoke

python -m ledgerlinc_ocr.preprocessing \
  --document-folder /tmp/inv_fallback_smoke \
  --preprocess-profile=ppstructurev3@gpu \
  --region-strategy=header-first-v1 \
  > /tmp/fallback.stdout \
  2> /tmp/fallback.stderr

tail -1 /tmp/fallback.stdout | jq '{region_strategy_id, region_strategy_fallback_count, rasterization, per_page_inference}'
# Expected:
# {
#   "region_strategy_id": "header-first-v1",
#   "region_strategy_fallback_count": 1,
#   "rasterization": <combined cost: page-1 band attempt + full pages 1..N>,
#   "per_page_inference": <combined cost: page-1 band attempt + full pages 1..N>
# }

# Verify pages[] shape: ALL pages populated (because the full-page strategy ran after fallback)
jq '.pages | map({page_number, blocks_count: (.blocks | length)})' \
  /tmp/inv_fallback_smoke/preprocess_output.json
# Expected:
# [
#   {"page_number": 1, "blocks_count": <N > 0>},
#   {"page_number": 2, "blocks_count": <M > 0>},
#   …
# ]
```

This is the operator-visible signature of a fallback: `region_strategy_fallback_count` advanced by 1 on `run_summary`; `pages[]` is fully populated (the per-document attribution rule from Clarifications Q4 matches "fallen-back document").

## 8. End-to-end pipeline (preprocess → evidence packet → extract → route → assemble → evaluate)

For each evaluated `(raster_profile_id, region_strategy_id)` configuration, run the full pipeline on the fixed 5-doc subset and verify every emitted artifact validates against its existing schema in the active contract set (SC-008).

```bash
SUBSET="inv_001_easy inv_002_easy inv_003_medium inv_004_challenging inv_005_challenging"   # actual 5-doc subset from R-017.11 / R-018.13

for doc in $SUBSET; do
  rm -rf /tmp/$doc
  cp -R tests/stage1_vendor_identity/$doc /tmp/$doc

  # Preprocess (this feature)
  python -m ledgerlinc_ocr.preprocessing \
    --document-folder /tmp/$doc \
    --preprocess-profile=ppstructurev3@gpu \
    --raster-profile=reduced-v1 \
    --region-strategy=header-first-v1 \
    > /tmp/$doc/preprocess.stdout

  # Evidence packet → extract → route → assemble (existing stages)
  python -m ledgerlinc_ocr.evidence_packet --document-folder /tmp/$doc
  python -m ledgerlinc_ocr.extract        --document-folder /tmp/$doc
  python -m ledgerlinc_ocr.router route   --document-folder /tmp/$doc
  python -m ledgerlinc_ocr.assembler      --document-folder /tmp/$doc
done

# Evaluate the corpus subset
python -m ledgerlinc_ocr.evaluator validate corpus /tmp
# Expected: every artifact validates against its existing schema; an evaluation_run_summary.json is produced.
```

## Appendix A: Four-corner benchmark numbers (filled at landing)

The fixed 5-doc subset is the same one feature 017 used (R-017.11 / R-018.13).

### A.1: Per-document `phase_timings.rasterization` (seconds)

| Document | `(legacy, full-page)` | `(reduced-v1, full-page)` | `(legacy, header-first-v1)` | `(reduced-v1, header-first-v1)` | Fallback in cell? |
|---|---|---|---|---|---|
| `inv_001_easy` | _filled_ | _filled_ | _filled_ | _filled_ | yes / no |
| `inv_002_easy` | _filled_ | _filled_ | _filled_ | _filled_ | yes / no |
| `inv_003_medium` | _filled_ | _filled_ | _filled_ | _filled_ | yes / no |
| `inv_004_challenging` | _filled_ | _filled_ | _filled_ | _filled_ | yes / no |
| `inv_005_challenging` | _filled_ | _filled_ | _filled_ | _filled_ | yes / no |
| **Cell total** | _sum_ | _sum_ | _sum_ | _sum_ | n/a |

### A.2: Per-document `phase_timings.per_page_inference` (seconds)

Same table shape as A.1, replace `phase_timings.rasterization` with `phase_timings.per_page_inference`.

### A.3: Per-cell `region_strategy_fallback_count` (corpus aggregate)

| Cell | `region_strategy_fallback_count` |
|---|---|
| `(legacy, full-page)` | 0 (always; full-page has no fallback) |
| `(reduced-v1, full-page)` | 0 (always; full-page has no fallback) |
| `(legacy, header-first-v1)` | _filled_ |
| `(reduced-v1, header-first-v1)` | _filled_ |

### A.4: Per-cell aggregate vendor-identity field score (FR-016 metric 1)

Read `aggregate.vendor_identity_field_score` from `evaluation_run_summary.json` for each cell.

| Cell | Aggregate field score | Pass vs. legacy |
|---|---|---|
| `(legacy, full-page)` | _filled_ (legacy baseline) | — |
| `(reduced-v1, full-page)` | _filled_ | _≥ legacy / < legacy_ |
| `(legacy, header-first-v1)` | _filled_ | _≥ legacy / < legacy_ |
| `(reduced-v1, header-first-v1)` | _filled_ | _≥ legacy / < legacy_ |

### A.5: Per-cell per-document pass count (FR-016 metric 2)

Count of documents in the subset where `evaluation_document.json.pass_status == "pass"`.

| Cell | Per-document pass count (out of 5) | Pass vs. legacy |
|---|---|---|
| `(legacy, full-page)` | _filled_ (legacy baseline) | — |
| `(reduced-v1, full-page)` | _filled_ | _≥ legacy / < legacy_ |
| `(legacy, header-first-v1)` | _filled_ | _≥ legacy / < legacy_ |
| `(reduced-v1, header-first-v1)` | _filled_ | _≥ legacy / < legacy_ |

The promotion gate (FR-016) passes for a cell iff its scores in A.4 AND A.5 are both ≥ the legacy baseline. If any cell passes the gate AND the team chooses to promote it, record the decision in `research.md` Appendix B.

## Appendix B: Deferred-GPU-verification follow-ups (if FR-025 deferral is taken at landing)

If workstation GPU hardware is unavailable at landing time and the FR-005 / FR-016 verification is deferred per FR-025, capture the deferral in `tasks.md` and reference it here. Verification items deferred:

- Section 1: legacy GPU run (no flags). Test: `test_run_summary_schema_0_1_5.py @gpu` (or the legacy-byte-identity subset).
- Section 2: reduced-DPI GPU run. Test: `test_dpi_benchmark.py @gpu` (cell `(reduced-v1, full-page)` row).
- Section 3: region-first GPU run. Tests: `test_region_first_pages_invariant.py @gpu`, `test_dpi_benchmark.py @gpu` (cell `(legacy, header-first-v1)` row).
- Section 4: combined GPU run. Test: `test_dpi_benchmark.py @gpu` (cell `(reduced-v1, header-first-v1)` row).
- Section 7: FR-007 fallback path. Test: `test_region_first_fallback.py @gpu`.
- Section 8: end-to-end pipeline on the 5-doc subset.
- Appendix A: all four benchmark cells, all five rows of A.1 / A.2.
- Appendix A: A.3 / A.4 / A.5 quality-gate evidence.

The deferral MUST be captured in this feature's `tasks.md` and is referenced here so the verification cannot be quietly skipped (FR-025 / Spec §Edge Cases / failure-handling.md CHK033).
