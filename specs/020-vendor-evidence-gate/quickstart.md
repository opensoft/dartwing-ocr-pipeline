# Quickstart: Vendor-Identity Evidence Gate

End-to-end walkthrough for feature 020 — the deterministic vendor-identity evidence gate over `preprocess_output.json`. Seven representative paths cover the FR-007 shape (b) skip-fallback behavioral surface, the FR-013 CPU/stub warn-and-proceed surface, and the FR-001 / FR-006 always-emit observability surface. Run from the worktree root.

---

> **Implementation status (stacked-PR delivery)**: PR #38 (MVP) implements **Paths 1 + 2 + 6 + 7** (the always-emit observability surface + the v1 re-derivation walkthrough + the warm-corpus pipeline mode). **Paths 3, 4, and 5** exercise the `--evidence-gate-skip-fallback` flag + `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK` env var, which land on stacked PR #40 (US4); running those commands against PR #38's tip will exit with `argparse: unknown argument --evidence-gate-skip-fallback`. The Appendix A FR-015 benchmark numbers and Appendix B FR-016 quality-gate numbers will be filled in by the US7 stacked PR.

Prerequisites:
- Devcontainer is built (`pip install -r requirements.txt` already ran on `postCreateCommand`), OR you have a host Python 3.12 venv with `pip install -e ".[dev]"`.
- For GPU paths: `paddlepaddle-dcu` installed in `.venv-paddle-rocm` and `scripts/start-host-ollama-rocm-wsl.sh` is the canonical Ollama startup (per feature 016 / 019 quickstart).
- For CPU paths: no GPU prerequisites; the gate is CPU-safe.

---

## Path 1 — Default `ppstructurev3@cpu` run (no opt-in, no GPU)

**Command**:
```bash
python -m dartwing_ocr.preprocessing \
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
python -m dartwing_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --preprocess-profile ppstructurev3@cpu \
    | jq 'select(.kind == "run_summary") | .schema_version, .evidence_gate_id, .evidence_gate_state_counts'
```

---

## Path 2 — Default `ppstructurev3@gpu` run (no opt-in)

**Command**:
```bash
python -m dartwing_ocr.preprocessing \
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
python -m dartwing_ocr.preprocessing \
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
python -m dartwing_ocr.preprocessing \
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
python -m dartwing_ocr.preprocessing \
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
python -m dartwing_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --preprocess-profile ppstructurev3@cpu \
    --evidence-gate-skip-fallback 2>&1 \
    | grep -F "--evidence-gate-skip-fallback ignored:"
```

Same result with env-var fallback:
```bash
DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=1 python -m dartwing_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --preprocess-profile ppstructurev3@cpu 2>&1 \
    | grep -F "--evidence-gate-skip-fallback ignored:"
```

CLI wins when both are set (R-020.1):
```bash
DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=1 python -m dartwing_ocr.preprocessing \
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

## Path 7 — `python -m dartwing_ocr.pipeline` warm-corpus mode

The pipeline CLI accepts the same `--evidence-gate-skip-fallback` flag and `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK` env var as the preprocessing CLI (R-020.1). Behavior matrix is identical:

```bash
python -m dartwing_ocr.pipeline \
    --documents-file <list> \
    --preprocess-profile ppstructurev3@gpu \
    --preprocess-strategy ocr-only-v1 \
    --evidence-gate-skip-fallback
```

The flag composes orthogonally with `--gpu-warmup`, `--module-set`, `--det-rec-variant`, `--raster-profile`, `--region-strategy`, and `--preprocess-strategy` exactly as features 016/017/018/019 documented.

---

## Smoke tests (CPU, no GPU required)

All seven of these MUST pass before merge per FR-024 / R-020.15:

1. **Schema version bump**: `python -m dartwing_ocr.preprocessing ... 2>&1 | jq -e 'select(.kind == "run_summary") | .schema_version == "0.1.7"'` → exit 0.
2. **Four new fields always present**: stub-adapter run emits `evidence_gate_id`, `evidence_gate_state_counts`, `evidence_gate_documents`, `evidence_gate_suppressed_fallback_count` even when no documents are processed.
3. **CPU warn-and-proceed**: `--evidence-gate-skip-fallback` on `ppstructurev3@cpu` emits the grep-able marker AND the run exits with the same status as the no-flag run.
4. **Env-var precedence**: `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=1` with no `--evidence-gate-skip-fallback` flag activates the opt-in; with `--no-evidence-gate-skip-fallback` (or its absence treated as off), CLI wins.
5. **Signal re-derivation**: every per-document record's `decision` matches `v1_decide(record.signals)` exactly (SC-002 / SC-012).
6. **Aggregate equals per-doc count**: `evidence_gate_state_counts[s]` equals the count of `evidence_gate_documents[i].decision == s` for each `s` in `{sufficient, borderline, insufficient}`.
7. **Legacy byte-identity**: a run with NO `--evidence-gate-skip-fallback` flag produces a `preprocess_output.json` byte-identical to a pre-feature-020 run on the same fixture (SC-006 / SC-007).

---

## Appendix A — Benchmark numbers (skeleton; filled by feature 021 / T013–T018 operator runs)

Feature 021 (`specs/021-gpu-mvp-promotion/`) is the landing slice for this Appendix. The skeleton below follows the structural contract pinned in [feature-021 `contracts/appendix-recording.md` §Appendix A](../021-gpu-mvp-promotion/contracts/appendix-recording.md) — six required subsections in fixed order. The operator runs the four-run benchmark (warmup ×1, legacy ×2, candidate ×2) per [feature-021 `quickstart.md` Path 3](../021-gpu-mvp-promotion/quickstart.md) and transcribes the run-2 values from each lane's stdout `run_summary` JSON line into the tables below.

Each Appendix-A entry is appended as a new dated subsection (`### Run YYYY-MM-DD (operator: <handle>)`); prior entries are preserved in chronological order. Partial runs (R-021.12) are prefixed `### Partial Run YYYY-MM-DD (K/5 documents — blocker: <named cause>)` and excluded from verdict computation. Invalidation rules (`### Invalidation rules` in the contract): if any field in §1 Environment fingerprint differs between two entries, the prior entry is no longer comparison-valid; a fresh four-run sequence is required.

The numbers in Appendix A are produced for the **promotion-decision reviewer audience** (internal pipeline engineers + reviewers). They are NOT marketing latency claims.

---

### Run YYYY-MM-DD (operator: <handle>) — SKELETON

#### §1. Environment fingerprint

Recorded once per benchmark sequence. All fields MUST be the actual runtime values (no operator-typed approximations).

- **GPU readiness verdict**: PASS / FAIL / BLOCKED — composed of:
  - Paddle preflight state: `ppstructurev3_init_succeeded` (or named failure)
  - Ollama readiness: PASS JSON from `scripts/check-ollama-gpu-readiness.sh` (model entry, `size_vram`, `size`)
- **Interpreter path** (FR-003 forensic): `.venv-paddle-rocm/bin/python` (or equivalent)
- **ROCm version**: `<rocm-smi --version output>`
- **Paddle wheel version**: `<pip show paddlepaddle-dcu | grep Version>`
- **Ollama version**: `<ollama --version>`
- **Voter-config path + model_name**: `configs/voter/ollama-gpu.yaml` → `model_name: "<name>"`
- **Workstation host fingerprint**: `<uname -a output>`

#### §2. Document subset confirmation

The fixed FR-011 subset (re-confirmed at the start of every run):

- `inv_001_easy`
- `inv_002_easy`
- `inv_006_medium`
- `inv_011_hard`
- `inv_012_hard`

If any document was relabeled or removed since a prior entry, the comparison against that prior entry is invalid (see Invalidation rules).

#### §3. Four-run timeline

| Lane      | Run index | Start (UTC)         | End (UTC)           | Exit | Scratch path                          |
|-----------|-----------|---------------------|---------------------|-----:|---------------------------------------|
| warmup    | 1         | YYYY-MM-DDThh:mm:ssZ | YYYY-MM-DDThh:mm:ssZ |    0 | `/tmp/021-bench/warmup/run1/`         |
| legacy    | 1         | YYYY-MM-DDThh:mm:ssZ | YYYY-MM-DDThh:mm:ssZ |    0 | `/tmp/021-bench/legacy/run1/`         |
| legacy    | 2         | YYYY-MM-DDThh:mm:ssZ | YYYY-MM-DDThh:mm:ssZ |    0 | `/tmp/021-bench/legacy/run2/`         |
| candidate | 1         | YYYY-MM-DDThh:mm:ssZ | YYYY-MM-DDThh:mm:ssZ |    0 | `/tmp/021-bench/candidate/run1/`      |
| candidate | 2         | YYYY-MM-DDThh:mm:ssZ | YYYY-MM-DDThh:mm:ssZ |    0 | `/tmp/021-bench/candidate/run2/`      |

#### §4. Per-document phase-key tables

One table per document. Threshold formula: `max(|legacy_run2 − legacy_run1|, |candidate_run2 − candidate_run1|)` (Q1 clarification 2026-05-18 / FR-015). Material rule: `|candidate_run2 − legacy_run2| > threshold` (strict greater-than; direction-symmetric per R-021.4). Values in seconds, 3 decimals (R-021.2). When `threshold == 0`, append inline note "threshold=0 (no measured jitter); any delta material" (R-021.3).

##### `inv_001_easy`

| Phase key            | legacy run1 | legacy run2 | candidate run1 | candidate run2 | legacy spread | candidate spread | threshold | Δ (cand_run2 − leg_run2) | Material? |
|----------------------|------------:|------------:|---------------:|---------------:|--------------:|-----------------:|----------:|--------------------------:|:---------:|
| `paddle_import`      |             |             |                |                |               |                  |           |                           |           |
| `gpu_bind_probe`     |             |             |                |                |               |                  |           |                           |           |
| `engine_init`        |             |             |                |                |               |                  |           |                           |           |
| `warmup`             |             |             |                |                |               |                  |           |                           |           |
| `rasterization`      |             |             |                |                |               |                  |           |                           |           |
| `per_page_inference` |             |             |                |                |               |                  |           |                           |           |
| `artifact_write`     |             |             |                |                |               |                  |           |                           |           |
| `total`              |             |             |                |                |               |                  |           |                           |           |

`Material?` vocabulary (closed set): `YES` / `NO` / `YES ↓ ✓` (permitted material decrease on `per_page_inference` or `total` for suppressed docs per FR-016) / `YES ↑ ⚠` (material increase, a finding) / `LAZY` (phase key absent — lazy construction confirmed for that lane).

##### `inv_002_easy`

(same column structure as above)

##### `inv_006_medium`

(same)

##### `inv_011_hard`

(same)

##### `inv_012_hard`

(same)

#### §5. Per-document `run_summary` observability table (run-2 values only)

| Document         | Lane      | gate_decision | evidence_gate_state_counts                  | evidence_gate_suppressed_fallback_count | ocr_only_fallback_count | preprocess_strategy_id |
|------------------|-----------|---------------|----------------------------------------------|----------------------------------------:|------------------------:|------------------------|
| `inv_001_easy`   | legacy    |               |                                              |                                         |                         | `ppstructurev3@gpu`    |
| `inv_001_easy`   | candidate |               |                                              |                                         |                         | `ppstructurev3@gpu`    |
| `inv_002_easy`   | legacy    |               |                                              |                                         |                         | `ppstructurev3@gpu`    |
| `inv_002_easy`   | candidate |               |                                              |                                         |                         | `ppstructurev3@gpu`    |
| `inv_006_medium` | legacy    |               |                                              |                                         |                         | `ppstructurev3@gpu`    |
| `inv_006_medium` | candidate |               |                                              |                                         |                         | `ppstructurev3@gpu`    |
| `inv_011_hard`   | legacy    |               |                                              |                                         |                         | `ppstructurev3@gpu`    |
| `inv_011_hard`   | candidate |               |                                              |                                         |                         | `ppstructurev3@gpu`    |
| `inv_012_hard`   | legacy    |               |                                              |                                         |                         | `ppstructurev3@gpu`    |
| `inv_012_hard`   | candidate |               |                                              |                                         |                         | `ppstructurev3@gpu`    |

#### §6. Findings

Bulleted list of every cell marked `YES ↑ ⚠` (material increase, regardless of phase key) and every `YES` cell on a non-permitted phase key (FR-016 finding). Also: any other anomaly (lane lengths differ, document missing from one lane, recorded value out of unit range). Each finding cites the (document, phase_key, lane) triple.

- _(none recorded yet; this list grows as the operator transcribes T016/T018 values)_

## Appendix B — Quality-Gate Verdict + Promotion Decision (skeleton; filled by feature 021 / T019–T030)

Feature 021 lands this appendix's evidence: the two-metric quality-gate verdict (T022) and the binary promotion decision (T028). The skeleton below follows the structural contract pinned in [feature-021 `contracts/appendix-recording.md` §Appendix B](../021-gpu-mvp-promotion/contracts/appendix-recording.md) — two required subsections (Quality-Gate Verdict, Promotion Decision), each appended as a new dated entry; prior entries are preserved as history.

The legacy section "Deferred GPU verification (filled at landing or in `tasks.md`)" follows after the new feature-021 subsections — it is preserved for historical context (feature-020 R-020.15 deferrals) and the checkbox states are updated as the corresponding feature-021 tasks land.

---

### Quality-Gate Verdict (YYYY-MM-DD) — SKELETON

**Verdict literal**: `PASS` / `FAIL` / `BLOCKED` (single value, no compound)

**Underlying inputs**: see Appendix A `### Run YYYY-MM-DD` subsection that produced these numbers.

#### Per-document field-accuracy + pass table (run-2 only)

| Document         | legacy field_accuracy | candidate field_accuracy | legacy passed? | candidate passed? |
|------------------|----------------------:|-------------------------:|:--------------:|:-----------------:|
| `inv_001_easy`   |                       |                          |                |                   |
| `inv_002_easy`   |                       |                          |                |                   |
| `inv_006_medium` |                       |                          |                |                   |
| `inv_011_hard`   |                       |                          |                |                   |
| `inv_012_hard`   |                       |                          |                |                   |

(`field_accuracy` columns transcribe each lane's `documents[i].field_accuracy` from `evaluation_run_summary.json`. `passed?` columns transcribe each lane's `documents[i].document_pass_fail.vendor_identity_passed` boolean from the per-doc `evaluation_document.json`.)

#### Aggregate metrics (feature-021 R-021.13 verification-round revision)

- **Metric (a) — `overall_metrics.vendor_identity_pass_rate`** (boolean-aggregated, vendor-identity-only signal):
  - legacy: _<float 0.0–1.0>_
  - candidate: _<float 0.0–1.0>_
  - Δ (candidate − legacy): _<signed float>_
  - non-regression: candidate ≥ legacy → ✓ / ✗

- **Metric (b) — `overall_metrics.field_accuracy`** (continuous, mean per-document field-level match rate; independent of Metric A per R-021.13):
  - legacy: _<float 0.0–1.0>_
  - candidate: _<float 0.0–1.0>_
  - Δ (candidate − legacy): _<signed float>_
  - non-regression: candidate ≥ legacy → ✓ / ✗

#### Verdict-specific content (populate one block only, per the verdict literal above)

- **PASS** (both metrics non-regressing): the verdict permits — but does NOT perform — promote-to-default (FR-029). The team's recorded Promotion Decision below cites this verdict.
- **FAIL** (at least one metric regresses):
  - regressing_metric: `pass_rate` / `field_accuracy` / `both`
  - regression_magnitude (pass_rate Δ): _<signed float>_
  - regression_magnitude (field_accuracy Δ): _<signed float>_
  - Skip-fallback MUST remain opt-in (FR-021 / FR-027). Promotion is not a permitted option.
- **BLOCKED** (verdict could not be computed):
  - blocked_cause: _<named hardware/runtime cause, e.g., "missing expected.json for inv_006_medium" (R-021.16), "ROCm SDMA path unavailable on this kernel" (R-021.6)>_
  - Skip-fallback MUST remain opt-in (FR-022 / FR-027). Promotion is not a permitted option.

---

### Promotion Decision (YYYY-MM-DD) — SKELETON

**Decision**: _(placeholder — populate with `stay opt-in` or `promote to default` per FR-026; binary, no third option. Default at landing: `stay opt-in`.)_

**Gating verdict**: see §Quality-Gate Verdict YYYY-MM-DD (`PASS` / `FAIL` / `BLOCKED`) above. FR-027 — if the gating verdict is FAIL or BLOCKED, the decision MUST be `stay opt-in`; promotion is not a permitted option.

**Decided by**: _<team identifier, e.g., "Dartwing OCR pipeline team">_

**Decided at**: YYYY-MM-DD

**Rationale**: _<2–4 sentences. For `stay opt-in`: why the team is keeping current posture (e.g., insufficient runtime evidence, fragility concerns, ops-readiness). For `promote to default`: why the team is changing the default (e.g., consistent PASS over multiple runs, operator-time savings rationale, validated rollback path).>_

**Promotion artifacts** (populate ONLY if Decision is `promote to default`; leave blank / "null" for `stay opt-in`):

- **Inverted default location**: `<file:lineref>` (e.g., `src/dartwing_ocr/preprocessing/evidence_gate_optin.py:42`) — the single line where the `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK` env-var default is flipped from OFF to ON. Same env var, same CLI flag — only the default changes.
- **Explicit-off CLI flag**: `--evidence-gate-skip-fallback` remains the explicit-on flag; the absence-of-flag path becomes the new ON default. (No new CLI flag introduced.)
- **Explicit-off env var**: `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=0` becomes the legacy-on path (was: unset/`""`/`0` = OFF). Same name; inverted default.
- **Legacy-path test**: `tests/unit/preprocessing/test_skip_fallback_explicit_off_legacy.py` (created by feature-021 T030; CPU-safe; MUST pass deterministically per SC-009).

The Promotion Decision is mirrored in [`docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`](../../docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md) `## Promotion Decision` section per R-021.11. Synchronization is verified by the CPU-safe contract test at `tests/contract_tests/test_promotion_decision_sync.py` (also a feature-021 deliverable).

A future demotion (promote-to-default → stay-opt-in) appends a NEW dated Promotion Decision subsection; the prior promote-to-default entry is retained as history (data-model.md §5 Demotion path). The inverted-default code change is reverted atomically with the demotion record (same PR).

---

### Deferred GPU verification — feature-020 R-020.15 carry-forward

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

CPU-safe floor that MUST pass before merge of PR #38 (MVP):
- items 1–7 of "Smoke tests" above
- the CPU-safe unit tests under `tests/unit/preprocessing/test_evidence_gate_*.py` (signals, decision, malformed-input, NFKC, rederivability, regex-negatives, registry, strategy-uniformity, y-threshold, module-safety, A-fixes)
- the pipeline-level coverage under `tests/pipeline_tests/test_evidence_gate_*.py` (runsummary-aggregation, field-order, pipeline-integration, callsite-regression)
- the schema-bump test `tests/pipeline_tests/test_run_summary_schema_0_1_7.py`

CPU-safe floor that MUST pass before merge of the stacked PRs:
- **PR #40 (US4 — skip-fallback opt-in)**: `tests/unit/preprocessing/test_evidence_gate_optin_unit.py` (CLI/env-var resolution; landing on #40 not in PR #38) + `tests/pipeline_tests/test_cpu_warn_and_proceed_evidence_gate.py` (CPU warn-and-proceed marker; landing on #40 not in PR #38)
- **PR #39 (US6 — schema-preservation regressions)**: `tests/pipeline_tests/test_legacy_byte_identity_evidence_gate.py` CPU variant (landing on #39 not in PR #38).
