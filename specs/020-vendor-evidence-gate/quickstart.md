# Quickstart: Vendor-Identity Evidence Gate

End-to-end walkthrough for feature 020 — the deterministic vendor-identity evidence gate over `preprocess_output.json`. Seven representative paths cover the FR-007 shape (b) skip-fallback behavioral surface, the FR-013 CPU/stub warn-and-proceed surface, and the FR-001 / FR-006 always-emit observability surface. Run from the worktree root.

---

> **Implementation status (stacked-PR delivery)**: PR #38 (MVP) implements **Paths 1 + 2 + 6 + 7** (the always-emit observability surface + the v1 re-derivation walkthrough + the warm-corpus pipeline mode). **Paths 3, 4, and 5** exercise the `--evidence-gate-skip-fallback` flag + `LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK` env var, which land on stacked PR #40 (US4); running those commands against PR #38's tip will exit with `argparse: unknown argument --evidence-gate-skip-fallback`. The Appendix A FR-015 benchmark numbers and Appendix B FR-016 quality-gate numbers will be filled in by the US7 stacked PR.

Prerequisites:
- Devcontainer is built (`pip install -r requirements.txt` already ran on `postCreateCommand`), OR you have a host Python 3.12 venv with `pip install -e ".[dev]"`.
- For GPU paths: `paddlepaddle-dcu` installed in `.venv-paddle-rocm` and `scripts/start-host-ollama-rocm-wsl.sh` is the canonical Ollama startup (per feature 016 / 019 quickstart).
- For CPU paths: no GPU prerequisites; the gate is CPU-safe.

---

## Path 1 — Default `ppstructurev3@cpu` run (no opt-in, no GPU)

**Command**:
```bash
python -m ledgerlinc_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --preprocess-profile ppstructurev3@cpu
```

**Expected observable behavior**:
- The CPU preprocessing path runs unchanged from feature 019. `preprocess_output.json` is written into the per-document folder.
- `run_summary` stdout line ends with `schema_version: "0.1.7"` (bumped per R-020.9) and includes the four new top-level fields:
    ```json
    {
        "evidence_gate_id": "v1",
        "evidence_gate_state_counts": {"sufficient": 1, "borderline": 0, "insufficient": 0},
        "evidence_gate_documents": [
            {
                "document_id": "inv_001_easy",
                "decision": "sufficient",
                "signals": {
                    "vendor_name_candidate_count": 3,
                    "header_band_token_density": 14,
                    "ocr_detection_confidence_mean": 0.84,
                    "business_suffix_present": true,
                    "tax_id_shaped_present": false
                }
            }
        ],
        "evidence_gate_suppressed_fallback_count": 0
    }
    ```
- `evidence_gate_suppressed_fallback_count` is `0` because the CPU profile does not engage the OCR-only fast lane; the suppression is GPU-only by design (FR-007).
- Re-running the same command on the same input produces byte-identical run_summary fields (SC-001 / SC-003).
- `preprocess_output.json` shape is unchanged from a pre-feature-020 run on the same fixture (SC-006 / SC-007 / FR-019).

**Verify**:
```bash
python -m ledgerlinc_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --preprocess-profile ppstructurev3@cpu \
    | jq 'select(.kind == "run_summary") | .schema_version, .evidence_gate_id, .evidence_gate_state_counts'
```

---

## Path 2 — Default `ppstructurev3@gpu` run (no opt-in)

**Command**:
```bash
python -m ledgerlinc_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --preprocess-profile ppstructurev3@gpu
```

**Expected observable behavior**:
- The GPU preprocessing path runs unchanged from feature 019. PPStructureV3 is the active strategy (legacy default).
- `evidence_gate_suppressed_fallback_count` is `0` because `--evidence-gate-skip-fallback` is not set (default off per FR-012).
- The other three new fields are emitted as per Path 1 with values reflecting the document's gate evaluation over the PPStructureV3 output.
- `ocr_only_fallback_count` is `0` (PPStructureV3 strategy doesn't engage OCR-only).
- All feature 014–019 guarantees hold (FR-022 / SC-009).

---

## Path 3 — GPU OCR-only with skip-fallback opt-in, `sufficient` document

**Command**:
```bash
python -m ledgerlinc_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --preprocess-profile ppstructurev3@gpu \
    --preprocess-strategy ocr-only-v1 \
    --evidence-gate-skip-fallback
```

**Expected observable behavior** (assuming `inv_001_easy` is a fixture where the gate decision is `sufficient` AND feature 019's FR-005 trigger would otherwise fire):
- OCR-only preprocessing produces a candidate `preprocess_output.json`.
- Feature 019's FR-005 trigger evaluates to `True` (insufficient token count or low mean confidence).
- The gate evaluates the OCR-only candidate output and returns `sufficient`.
- The four-conjunct suppression predicate (R-020.8) returns `True`: `preprocess_strategy_id == "ocr-only-v1"` AND `fr_005_trigger_would_fire == True` AND `opt_in_active == True` AND `candidate_gate_decision == "sufficient"`.
- The fallback to PPStructureV3 is SUPPRESSED. The OCR-only candidate becomes the document's final `preprocess_output.json`.
- `run_summary` shows:
    ```json
    {
        "preprocess_strategy_id": "ocr-only-v1",
        "ocr_only_fallback_count": 0,
        "evidence_gate_id": "v1",
        "evidence_gate_state_counts": {"sufficient": 1, "borderline": 0, "insufficient": 0},
        "evidence_gate_documents": [
            {"document_id": "inv_001_easy", "decision": "sufficient", "signals": { "...": "..." }}
        ],
        "evidence_gate_suppressed_fallback_count": 1
    }
    ```

**This is the latency-harvest case** — the OCR-only output is accepted without the PPStructureV3 fallback paying its inference cost. Operator inspection of `run_summary` shows which document(s) benefited.

---

## Path 4 — GPU OCR-only with skip-fallback opt-in, `borderline` document

**Command**: (same as Path 3 but with a fixture where the gate would be `borderline` AND feature 019 FR-005 trigger fires)
```bash
python -m ledgerlinc_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_006_layout_table \
    --preprocess-profile ppstructurev3@gpu \
    --preprocess-strategy ocr-only-v1 \
    --evidence-gate-skip-fallback
```

**Expected observable behavior** (assuming `inv_006_layout_table` is a fixture where the OCR-only output has weak evidence and gate returns `borderline`):
- OCR-only preprocessing produces a candidate.
- Feature 019's FR-005 trigger evaluates to `True`.
- The gate evaluates the OCR-only candidate and returns `borderline`.
- The suppression predicate (R-020.8) returns `False` because `candidate_gate_decision != "sufficient"`.
- Feature 019's fallback to PPStructureV3 runs UNCHANGED. The OCR-only candidate is discarded; PPStructureV3 produces the final `preprocess_output.json`.
- The gate evaluates AGAIN on the post-fallback PPStructureV3 output to get the RECORDED decision (per R-020.7 — recorded decision is over the final file).
- `run_summary` shows:
    ```json
    {
        "preprocess_strategy_id": "ocr-only-v1",
        "ocr_only_fallback_count": 1,
        "evidence_gate_id": "v1",
        "evidence_gate_state_counts": {"sufficient": 0, "borderline": 1, "insufficient": 0},
        "evidence_gate_documents": [
            {"document_id": "inv_006_layout_table", "decision": "borderline", "signals": { "...": "..." }}
        ],
        "evidence_gate_suppressed_fallback_count": 0
    }
    ```
- Note `decision: "borderline"` reflects the post-fallback PPStructureV3 evaluation, not the OCR-only candidate evaluation (which was also `borderline` but on a different `preprocess_output.json`).

**This is the safety case** — weak evidence on the candidate still falls back. The gate's `borderline` and `insufficient` states never trip suppression (FR-009 / SC-011).

---

## Path 5 — CPU profile with opt-in flag set (warn-and-proceed)

**Command**:
```bash
python -m ledgerlinc_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --preprocess-profile ppstructurev3@cpu \
    --evidence-gate-skip-fallback
```

**Expected observable behavior** (FR-013 / R-020.12):
- One stderr warning line is emitted containing the literal `--evidence-gate-skip-fallback ignored: active profile is not ppstructurev3@gpu` (grep-able marker).
- The run proceeds with the CPU profile unchanged. `preprocess_output.json` is byte-identical to a Path 1 run (no opt-in flag).
- All four new `run_summary` fields are STILL emitted (FR-014 — the gate computation is CPU-safe and runs regardless of profile).
- `evidence_gate_suppressed_fallback_count` is `0` (no suppression on CPU).
- Exit code is the same as a Path 1 run.

**Verify**:
```bash
python -m ledgerlinc_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --preprocess-profile ppstructurev3@cpu \
    --evidence-gate-skip-fallback 2>&1 \
    | grep -F "--evidence-gate-skip-fallback ignored:"
```

Same result with env-var fallback:
```bash
LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK=1 python -m ledgerlinc_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --preprocess-profile ppstructurev3@cpu 2>&1 \
    | grep -F "--evidence-gate-skip-fallback ignored:"
```

CLI wins when both are set (R-020.1):
```bash
LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK=1 python -m ledgerlinc_ocr.preprocessing \
    --document-folder ... \
    --preprocess-profile ppstructurev3@gpu \
    # No --evidence-gate-skip-fallback flag, but env var is truthy
    # ⇒ opt-in is active (env-var fallback)
```

---

## Path 6 — Re-derive a gate decision from the recorded `run_summary`

This path verifies SC-002 / SC-012: the recorded signal values plus the documented `v1` decision table re-derive the recorded decision exactly, without re-running the binary.

**Step 1**: Extract one document's record from a captured `run_summary`:
```bash
RUN_SUMMARY='{"kind":"run_summary","schema_version":"0.1.7","evidence_gate_id":"v1","evidence_gate_documents":[{"document_id":"inv_001_easy","decision":"sufficient","signals":{"vendor_name_candidate_count":3,"header_band_token_density":14,"ocr_detection_confidence_mean":0.84,"business_suffix_present":true,"tax_id_shaped_present":false}}]}'

echo "$RUN_SUMMARY" | jq '.evidence_gate_documents[] | select(.document_id == "inv_001_easy")'
```

**Step 2**: Apply the v1 decision table (per `contracts/evidence-gate-rule.md`):
- `vendor_name_candidate_count >= 1` → `3 >= 1` → `True`
- `header_band_token_density >= 8` → `14 >= 8` → `True`
- `ocr_detection_confidence_mean >= 0.70` → `0.84 >= 0.70` → `True`
- `business_suffix_present` → `True`
- `tax_id_shaped_present` → `False`
- `has_suffix OR has_tax_id` → `True OR False` → `True`
- All four conjuncts of the `sufficient` rule satisfied → decision is `sufficient`.

**Step 3**: Verify the re-derived decision matches the recorded `decision: "sufficient"`. They do match. SC-012 holds.

---

## Path 7 — `python -m ledgerlinc_ocr.pipeline` warm-corpus mode

The pipeline CLI accepts the same `--evidence-gate-skip-fallback` flag and `LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK` env var as the preprocessing CLI (R-020.1). Behavior matrix is identical:

```bash
python -m ledgerlinc_ocr.pipeline \
    --documents-file <list> \
    --preprocess-profile ppstructurev3@gpu \
    --preprocess-strategy ocr-only-v1 \
    --evidence-gate-skip-fallback
```

The flag composes orthogonally with `--gpu-warmup`, `--module-set`, `--det-rec-variant`, `--raster-profile`, `--region-strategy`, and `--preprocess-strategy` exactly as features 016/017/018/019 documented.

---

## Smoke tests (CPU, no GPU required)

All seven of these MUST pass before merge per FR-024 / R-020.15:

1. **Schema version bump**: `python -m ledgerlinc_ocr.preprocessing ... 2>&1 | jq -e 'select(.kind == "run_summary") | .schema_version == "0.1.7"'` → exit 0.
2. **Four new fields always present**: stub-adapter run emits `evidence_gate_id`, `evidence_gate_state_counts`, `evidence_gate_documents`, `evidence_gate_suppressed_fallback_count` even when no documents are processed.
3. **CPU warn-and-proceed**: `--evidence-gate-skip-fallback` on `ppstructurev3@cpu` emits the grep-able marker AND the run exits with the same status as the no-flag run.
4. **Env-var precedence**: `LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK=1` with no `--evidence-gate-skip-fallback` flag activates the opt-in; with `--no-evidence-gate-skip-fallback` (or its absence treated as off), CLI wins.
5. **Signal re-derivation**: every per-document record's `decision` matches `v1_decide(record.signals)` exactly (SC-002 / SC-012).
6. **Aggregate equals per-doc count**: `evidence_gate_state_counts[s]` equals the count of `evidence_gate_documents[i].decision == s` for each `s` in `{sufficient, borderline, insufficient}`.
7. **Legacy byte-identity**: a run with NO `--evidence-gate-skip-fallback` flag produces a `preprocess_output.json` byte-identical to a pre-feature-020 run on the same fixture (SC-006 / SC-007).

---

## Appendix A — Benchmark numbers (filled at landing)

This appendix is intentionally empty in the planning phase. At landing, the FR-015 / R-020.13 benchmark — the legacy default vs. the skip-fallback opt-in candidate, on the same fixed 5-doc subset features 017 / 018 / 019 used — records:

```
| document_id | legacy elapsed (s) | candidate elapsed (s) | legacy decision | candidate decision | suppressed? |
|---|---|---|---|---|---|
| inv_001_easy | ... | ... | ... | ... | yes/no |
| inv_002_easy | ... | ... | ... | ... | yes/no |
| inv_006_layout_table | ... | ... | ... | ... | yes/no |
| (subset doc 4) | ... | ... | ... | ... | yes/no |
| (subset doc 5) | ... | ... | ... | ... | yes/no |
| TOTAL | ... | ... | sufficient: N, borderline: N, insufficient: N | sufficient: N, ... | total suppressions: N |
```

Per-document `evidence_gate_documents` records, the aggregate `evidence_gate_state_counts`, and the per-document `evidence_gate_suppressed_fallback_count` increments are captured directly from the `run_summary` line of each benchmark run.

## Appendix B — Deferred GPU verification (filled at landing or in `tasks.md`)

Per R-020.15 / FR-026, the following GPU-marked tests / benchmarks MAY be deferred if workstation GPU hardware is unavailable at landing time:

- [ ] `test_evidence_gate_skip_fallback.py @gpu` (US4 / T033) — verifies Path 3 scenario end-to-end (`sufficient` candidate → fallback suppressed, counter increments).
- [ ] `test_evidence_gate_skip_fallback_borderline.py @gpu` (US4 / T034) — verifies Path 4 scenario end-to-end (`borderline` candidate → fallback runs, counter unchanged).
- [ ] `test_evidence_gate_all_suppressed_lazy_construction.py::test_lazy_no_warmup @gpu` (US4 / T033a) — verifies the FR-007 lazy-construction clause: all-suppressed corpus + no `--gpu-warmup` ⇒ PPStructureV3 never constructed, `phase_timings.warmup` for PPStructureV3 == `0`.
- [ ] `test_evidence_gate_all_suppressed_lazy_construction.py::test_forced_construction_with_warmup @gpu` (US4 / T033a) — verifies the FR-007 `--gpu-warmup` exception clause: all-suppressed + `--gpu-warmup` ⇒ PPStructureV3 IS constructed (operator-opt-in trade-off); suppression counter still equals doc count.
- [ ] `test_evidence_gate_benchmark.py @gpu` (US7 / T053) — runs the FR-015 four-run benchmark discipline (warmup once, legacy×2 + candidate×2, discard run 1 each); produces Appendix A numbers; asserts per-key change pattern (only `per_page_inference` + `total` decrease on suppressed docs; others within jitter band).
- [ ] `test_quality_gate_two_metric_evidence_gate.py @gpu` (US7 / T054) — produces the FR-016 / R-020.14 two-metric promotion-gate verdict (aggregate vendor-identity field score + per-document pass count, both ≥ legacy on the 5-doc subset).
- [ ] FR-015 corpus benchmark run on workstation GPU.
- [ ] FR-016 quality-gate evidence in `research.md` Appendix B.

Each deferred item is captured as a checkbox in this Appendix and as a follow-up task in `tasks.md`. The deferral cannot be quietly skipped; closing each box requires the corresponding GPU run output to be attached to this feature's PR or follow-up issue.

**CPU-safe variants of GPU-deferrable tests** (MUST pass before merge — these are NOT deferrable; they live in the merge-gating floor below):

- `test_evidence_gate_skip_fallback_borderline_cpu.py` (US4 / T034a) — CPU-safe variant of T034 via the `decide_ocr_only_fallback_disposition` injection seam in `preprocessing/pipeline.py`; asserts MI-11 (gate evaluated twice — once on candidate for suppression decision, once on post-fallback output for recorded decision) without requiring GPU.
- `test_evidence_gate_all_suppressed_lazy_construction.py::test_lazy_cpu_safe` (US4 / T033a CPU variant) — CPU-safe variant; asserts the construction-decision path in `preprocessing/pipeline.py` never calls the PPStructureV3 factory when all candidates are `sufficient` AND opt-in active.
- `test_evidence_gate_recorded_over_final.py` (US4 / T035) — CPU-safe via injection; asserts MI-10 (recorded decision is over the FINAL output, not the candidate).

## Surveillance follow-up (Clarifications Session 2026-05-16 Q3 Option D — permanent deferral)

Per the Q3 clarification, **over-time regression surveillance for `evidence_gate_suppressed_fallback_count`** (recurring GPU benchmark / snapshot-diff PR gating / alerting) is **DEFERRED to a follow-up ops feature**, not feature 020 scope. T033's in-PR `>= 1` assertion is the safety net at landing; over-time drift detection belongs alongside `pipeline/corpus_run.py` infrastructure in a future feature.

- [ ] Out-of-PR surveillance: recurring GPU benchmark / snapshot-diff / alerting for `evidence_gate_suppressed_fallback_count` regression — **DEFERRED to follow-up ops feature**; T033 is the in-PR safety net at landing.

This entry persists in Appendix B even if all other GPU deferrals close — the surveillance question is a permanent follow-up, not a deferred verification.

CPU-safe floor that MUST pass before merge: items 1–7 of "Smoke tests" above plus the eight CPU-safe unit tests listed in `plan.md` § Source Code (`test_evidence_gate_signals_unit.py`, `test_evidence_gate_decision_unit.py`, `test_evidence_gate_optin_unit.py`, `test_evidence_gate_y_threshold_unit.py`, `test_cpu_warn_and_proceed_evidence_gate.py`, `test_run_summary_schema_0_1_7.py`, `test_evidence_gate_corpus_run.py`, `test_legacy_byte_identity_evidence_gate.py` CPU variant).
