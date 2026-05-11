# Quickstart: OCR-Only Fast Lane For Vendor Identity

**Feature**: 019-ocr-only-fast-lane
**Date**: 2026-05-11
**Prerequisites**: features 014–018 landed (`raster_profile_id`, `region_strategy_id`, `region_strategy_fallback_count` on `run_summary`; `RunSummary.SCHEMA_VERSION = "0.1.5"`); workstation with host Ollama or `.venv-paddle-rocm` for GPU paths.

This quickstart walks through the six operational paths the feature introduces, then captures benchmark numbers (Appendix A) and deferred-verification follow-ups (Appendix B). Run each path from the repo root in the devcontainer or on the workstation.

## Path 1 — Default `ppstructurev3` strategy (no flag set)

The baseline path: a `ppstructurev3@gpu` run with no `--preprocess-strategy` flag set. This is what the GPU lane does today on `main` post-feature-018; this feature does NOT change it.

```bash
# Single-doc, GPU lane (workstation .venv-paddle-rocm)
.venv-paddle-rocm/bin/python -m ledgerlinc_ocr.preprocessing \
  --preprocess-profile=ppstructurev3@gpu \
  --source-file=tests/stage1_vendor_identity/inv_001_easy/source.pdf \
  --output-folder=tests/stage1_vendor_identity/inv_001_easy/
```

Expected `run_summary` line includes:
```text
"schema_version": "0.1.6",
"preprocess_strategy_id": "ppstructurev3",
"ocr_only_fallback_count": 0,
"raster_profile_id": "legacy",
"region_strategy_id": "full-page",
"region_strategy_fallback_count": 0,
... (feature 017's three identifiers) ...
```

Verification: `preprocess_output.json` is byte-identical to a pre-019 run on the same fixture (FR-019 / SC-007).

## Path 2 — OCR-only strategy explicitly selected

The new candidate path. The CLI flag `--preprocess-strategy=ocr-only-v1` selects the OCR-only preset.

```bash
.venv-paddle-rocm/bin/python -m ledgerlinc_ocr.preprocessing \
  --preprocess-profile=ppstructurev3@gpu \
  --preprocess-strategy=ocr-only-v1 \
  --source-file=tests/stage1_vendor_identity/inv_001_easy/source.pdf \
  --output-folder=tests/stage1_vendor_identity/inv_001_easy/
```

Expected `run_summary` line includes:
```text
"preprocess_strategy_id": "ocr-only-v1",
"ocr_only_fallback_count": 0,  (assuming this fixture passes the FR-005 trigger)
```

Expected `preprocess_output.json`: schema-valid; `blocks[]` are reassembled from OCR lines by Y-axis clustering (R-019.8); all blocks have `block_type = "text"` (I-019.6); coordinate origin, units, page index, and `pages.length == page_count` invariants are identical to a Path 1 run on the same fixture.

The `phase_timings.per_page_inference` value should be **measurably lower** than Path 1's on the same fixture (PaddleOCR det+rec only vs. full PPStructureV3 layout pipeline) — this is SC-001 / SC-003's observable signal.

## Path 3 — OCR-only combined with feature 018's region-first strategy

OCR-only composes orthogonally with `--region-strategy=header-first-v1`. The OCR-only pass rasterizes only the page-1 header band and runs det+rec on that crop.

```bash
.venv-paddle-rocm/bin/python -m ledgerlinc_ocr.preprocessing \
  --preprocess-profile=ppstructurev3@gpu \
  --preprocess-strategy=ocr-only-v1 \
  --region-strategy=header-first-v1 \
  --source-file=tests/stage1_vendor_identity/inv_001_easy/source.pdf \
  --output-folder=tests/stage1_vendor_identity/inv_001_easy/
```

Expected:
- `preprocess_strategy_id == "ocr-only-v1"`, `region_strategy_id == "header-first-v1"`.
- `preprocess_output.json.pages[0].blocks[]` populated with header-band blocks; `pages[1..N]` are empty records (per feature 018 Clarifications Q2).
- `pages.length == page_count` invariant preserved.
- Both `ocr_only_fallback_count` and `region_strategy_fallback_count` MAY independently fire (`0` if neither trigger trips; `1`/`1` if both axes' triggers trip on the same document).

## Path 4 — Warn-and-proceed on `ppstructurev3@cpu`

Setting `--preprocess-strategy` on a non-GPU profile triggers the FR-013 warn-and-proceed path. The flag is ignored; the run proceeds normally.

```bash
python -m ledgerlinc_ocr.preprocessing \
  --preprocess-profile=ppstructurev3@cpu \
  --preprocess-strategy=ocr-only-v1 \
  --source-file=tests/stage1_vendor_identity/inv_001_easy/source.pdf \
  --output-folder=tests/stage1_vendor_identity/inv_001_easy/
```

Expected:
- One stderr line containing the literal substring `--preprocess-strategy ignored:`.
- `preprocess_strategy_id == "cpu-default"` (the CPU lane's default; the flag is ignored).
- `ocr_only_fallback_count == 0`.
- Same exit status as a no-flag CPU run (FR-013 / SC-005).
- `preprocess_output.json` is byte-identical to a no-flag CPU run (the CPU path doesn't exercise the preset axis).

The same applies to stub-adapter runs (`preprocess_strategy_id == "stub-default"`).

## Path 5 — Fail-fast on unknown preset value

Setting `--preprocess-strategy` to an unknown value (typo or removed preset) fails fast with exit code 16.

```bash
.venv-paddle-rocm/bin/python -m ledgerlinc_ocr.preprocessing \
  --preprocess-profile=ppstructurev3@gpu \
  --preprocess-strategy=ocr-only-v99 \
  --source-file=tests/stage1_vendor_identity/inv_001_easy/source.pdf \
  --output-folder=tests/stage1_vendor_identity/inv_001_easy/
echo "Exit code: $?"
```

Expected:
- stderr line: `error: unknown preprocess_strategy: 'ocr-only-v99' — valid values are: ppstructurev3, ocr-only-v1, cpu-default, stub-default`
- Exit code: 16 (R-019.12 / cli-contract.md §4).
- No `run_summary` line emitted.
- No `preprocess_output.json` written.

## Path 6 — OCR-only fallback verification

A fixture chosen to trip the FR-005 combined trigger (token count below threshold OR mean confidence below threshold) exercises the fallback path. Pick a fixture where the targeted region (header band on page 1, if `header-first-v1` is active; full page otherwise) genuinely has insufficient evidence.

```bash
.venv-paddle-rocm/bin/python -m ledgerlinc_ocr.preprocessing \
  --preprocess-profile=ppstructurev3@gpu \
  --preprocess-strategy=ocr-only-v1 \
  --source-file=tests/stage1_vendor_identity/inv_017_thin/source.pdf \
  --output-folder=tests/stage1_vendor_identity/inv_017_thin/
# (Pick a fixture whose page-1 OCR-only output is genuinely sparse — see R-019.13 for the benchmark subset; pick from outside that subset for the fallback verification fixture so it doesn't bias the benchmark.)
```

Expected:
- `preprocess_strategy_id == "ocr-only-v1"`.
- `ocr_only_fallback_count == 1` for this single-doc run.
- `preprocess_output.json` is the `ppstructurev3` strategy's output on that document (validates against the existing schema; layout-derived blocks; `block_type` may be `"text"`, `"title"`, etc. as PPStructureV3 layout classifies).
- `phase_timings.rasterization` and `phase_timings.per_page_inference` reflect the **combined** cost (OCR-only attempt + PPStructureV3 fallback) per R-019.15.

## Appendix A — Benchmark numbers (FR-015 — filled at landing time)

The FR-015 benchmark cells are: `ppstructurev3` baseline AND `ocr-only-v1` candidate, both on the fixed 5-doc subset features 017 and 018 used (R-019.13):

| Cell | Subset | per-doc `phase_timings.rasterization` (mean) | per-doc `phase_timings.per_page_inference` (mean) | per-doc `phase_timings.total` (mean) | aggregate field score | per-doc pass count |
|---|---|---|---|---|---|---|
| `ppstructurev3` (baseline) | `inv_001_easy`, `inv_002_easy`, + 3 from R-017.11 | TBD | TBD | TBD | TBD | TBD |
| `ocr-only-v1` (candidate) | same as above | TBD | TBD | TBD | TBD | TBD |

Numbers are filled in by `tests/pipeline_tests/test_ocr_only_benchmark.py` output at landing time. If GPU verification is deferred per FR-025, the deferral is captured in Appendix B and the numbers land in a follow-up PR.

## Appendix B — Deferred-GPU-verification follow-ups (FR-025)

If workstation GPU verification cannot complete before merge, the following are deferred and tracked as follow-up issues / tasks per FR-025 (feature 016 FR-014 / feature 017 FR-024 / feature 018 FR-025 precedent):

- [ ] FR-015 benchmark — runs `test_ocr_only_benchmark.py` on the fixed 5-doc subset; fills Appendix A above.
- [ ] FR-016 quality-gate verification — runs `test_quality_gate_two_metric_ocr.py`; reads `evaluation_run_summary.json` for both `ppstructurev3` baseline and `ocr-only-v1` candidate; fills `research.md` Appendix B.
- [ ] GPU-marked test: `test_ocr_only_per_page_inference.py` — verifies SC-001 / SC-003 measurable latency reduction.
- [ ] GPU-marked test: `test_ocr_only_fallback.py` — verifies R-019.10 fallback orchestration end-to-end.
- [ ] GPU-marked test: `test_ocr_only_with_header_first.py` — verifies R-019.11 orthogonality with feature 018's region-strategy axis.
- [ ] GPU-marked test: `test_legacy_byte_identity.py` (`@gpu` variant) — verifies SC-007 / FR-019 on the GPU lane.

Each deferred item is added to `tasks.md` as a tracked follow-up. The deferral MUST NOT block merge of the CPU-safe implementation (FR-025); the CPU-safe pieces — preset registry, env-var resolution, warn-and-proceed, unknown-preset exit-16, schema-version bump, block-clustering and eligibility unit tests — MUST land complete.

## Troubleshooting

| Symptom | Probable cause | Resolution |
|---|---|---|
| `error: unknown preprocess_strategy: 'X'` on GPU lane | Typo or removed preset value | Use one of `ppstructurev3`, `ocr-only-v1`, `cpu-default`, `stub-default` |
| `--preprocess-strategy ignored:` warning on CPU lane | Flag set on a non-GPU profile (FR-013) | Expected behavior; the flag only takes effect on `ppstructurev3@gpu`. Drop the flag or switch to GPU lane. |
| `ocr_only_fallback_count` is `documents_total` on the OCR-only candidate | Every document tripped the trigger | Likely thresholds too aggressive for this corpus. Inspect per-doc `phase_timings` and consider a different fixture or a future `ocr-only-v2` preset with tuned thresholds. |
| GPU bind error on `--preprocess-strategy=ocr-only-v1` | PaddleOCR engine can't bind `gpu:0` | Same root cause as PPStructureV3 bind failures: ROCm `gfx1151` env vars (`HSA_*`, `SDMA_*`); see `docs/ollama-rocm-wsl-gfx1151-fix.md`. The OCR-only engine binds the same device the PPStructureV3 engine does. |
| `preprocess_output.json.blocks[]` empty on OCR-only output | OCR detected zero boxes on the targeted region | Eligibility check should have returned INSUFFICIENT and the document should have fallen back. If `ocr_only_fallback_count == 0` and `blocks == []`, check that the eligibility check is wired to the orchestrator correctly. |
