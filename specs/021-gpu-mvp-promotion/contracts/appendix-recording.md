# Contract: Appendix A & B Recording (FR-023, FR-024)

**Path**: `specs/020-vendor-evidence-gate/quickstart.md` (existing file; sections Appendix A and Appendix B already exist as banner-tagged placeholders awaiting this feature's evidence)
**Spec refs**: [spec.md §FR-023, §FR-024](../spec.md), [data-model.md §2–§5](../data-model.md), [research.md §R-021.1, §R-021.2, §R-021.13](../research.md)
**Constitution refs**: §V (reproducible delivery — SC-005 third-party re-derivability)

This contract pins the structural shape of Appendix A (benchmark numbers) and Appendix B (quality-gate verdict + promotion decision) so a third party can re-derive the promotion verdict from the appendices alone (SC-005).

## Appendix A — Benchmark Numbers

### Required subsections (in order)

1. **Environment fingerprint** — recorded once per benchmark sequence:
   - GPU readiness verdict (PASS / FAIL / BLOCKED), date/time, interpreter path, ROCm version, Paddle wheel version, Ollama version.
   - Ollama Readiness Probe Result (PASS JSON line from the helper).
   - Active voter-config path + extracted `model_name`.
   - Workstation host identifier (hostname, OS, kernel — `uname -a` output).
2. **Document subset confirmation** — the five FR-011 document IDs reproduced literally.
3. **Four-run timeline** — one row per run, in execution order:
   - `warmup`, `legacy/run1`, `legacy/run2`, `candidate/run1`, `candidate/run2`.
   - Each row: lane, run_index, start_utc, end_utc, exit code, scratch_path.
4. **Per-document phase-key tables** — five tables (one per document), each containing all emitted `phase_timings.*` keys:

   | Phase key            | legacy run1 | legacy run2 | candidate run1 | candidate run2 | legacy spread | candidate spread | threshold | Δ (cand_run2 − leg_run2) | Material? |
   |----------------------|------------:|------------:|---------------:|---------------:|--------------:|-----------------:|----------:|--------------------------:|:---------:|
   | `paddle_import`      | 0.842       | 0.840       | 0.841          | 0.843          | 0.002         | 0.002            | 0.002     | +0.003                    | YES       |
   | `gpu_bind_probe`     | …           | …           | …              | …              | …             | …                | …         | …                         | …         |
   | `engine_init`        | …           | …           | (absent)       | (absent)       | …             | n/a              | n/a       | n/a                       | LAZY      |
   | `warmup`             | …           | …           | (absent)       | (absent)       | …             | n/a              | n/a       | n/a                       | LAZY      |
   | `rasterization`      | …           | …           | …              | …              | …             | …                | …         | …                         | …         |
   | `per_page_inference` | 1.420       | 1.415       | 0.612          | 0.609          | 0.005         | 0.003            | 0.005     | −0.806                    | YES ↓ ✓   |
   | `artifact_write`     | …           | …           | …              | …              | …             | …                | …         | …                         | …         |
   | `total`              | 3.110       | 3.098       | 1.882          | 1.878          | 0.012         | 0.004            | 0.012     | −1.220                    | YES ↓ ✓   |

   - Values: seconds, 3 decimals (R-021.2).
   - `Material?` column: `YES` / `NO` / `YES ↓ ✓` (material decrease in the *permitted* direction for `per_page_inference` and `total` on suppressed documents) / `YES ↑ ⚠` (material increase, a finding regardless of phase key) / `LAZY` (phase key absent — lazy construction confirmed for that lane).
   - Threshold formula: `threshold = max(legacy spread, candidate spread)` (Q1 clarification).
   - Material rule: `|Δ| > threshold` (strict greater-than, direction-symmetric per R-021.4).
   - When `threshold == 0` AND `|Δ| > 0`, append inline note "threshold=0; any delta material" (R-021.3).

5. **Per-document `run_summary` observability table** — one row per document × lane (run-2 values only):

   | Document     | Lane      | gate_decision | evidence_gate_state_counts                  | evidence_gate_suppressed_fallback_count | ocr_only_fallback_count | preprocess_strategy_id |
   |--------------|-----------|---------------|----------------------------------------------|----------------------------------------:|------------------------:|-----------------------|
   | `inv_001_easy` | legacy   | sufficient    | {sufficient: 1}                              | 0                                       | 1                       | `ppstructurev3@gpu`   |
   | `inv_001_easy` | candidate | sufficient    | {sufficient: 1}                              | 1                                       | 1                       | `ppstructurev3@gpu`   |
   | …            | …         | …             | …                                            | …                                       | …                       | …                     |

6. **Findings** — bulleted list of every cell marked `YES ↑ ⚠` (material increase) and every other anomaly (e.g., lane lengths differ, document missing from a lane). Each finding cites the (document, phase key, lane) triple.

### Recording rules

- Appendix A entries are appended via a new dated subsection `### Run YYYY-MM-DD (operator: <handle>)`. Prior runs (e.g., earlier promotion attempts) are preserved in chronological order; no overwriting.
- If a run is partial (R-021.12), the subsection is prefixed `### Partial Run YYYY-MM-DD (K/5 documents — blocker: <named cause>)` and explicitly excluded from verdict computation.
- All timing values MUST use the R-021.2 unit/format convention.
- Tables MUST be GitHub-flavored Markdown.

## Appendix B — Quality Gate Verdict + Promotion Decision

### Required subsections (in order)

1. **Quality-Gate Verdict (YYYY-MM-DD)**:
   - Verdict literal: `PASS` / `FAIL` / `BLOCKED`.
   - Underlying inputs reference: link to the Appendix A `### Run YYYY-MM-DD` subsection that produced this verdict.
   - Per-document score + pass table (the QualityGateVerdict.per_document list shape; see data-model §4):

     | Document         | legacy score | candidate score | legacy pass | candidate pass |
     |------------------|-------------:|----------------:|:-----------:|:--------------:|
     | `inv_001_easy`   | 0.95         | 0.95            | ✓           | ✓              |
     | `inv_002_easy`   | 0.92         | 0.92            | ✓           | ✓              |
     | `inv_006_medium` | 0.81         | 0.83            | ✓           | ✓              |
     | `inv_011_hard`   | 0.67         | 0.65            | ✓           | ✓              |
     | `inv_012_hard`   | 0.58         | 0.60            | ✗           | ✓              |

   - Aggregate score: legacy `<sum>`, candidate `<sum>`, Δ = `<candidate − legacy>` (R-021.13).
   - Per-document pass count: legacy `<count>`, candidate `<count>`, Δ = `<candidate − legacy>` (R-021.13).
   - FAIL only: `regressing_metric` (`aggregate` / `pass_count` / `both`) + `regression_magnitude` numbers.
   - BLOCKED only: `blocked_cause` (named hardware/runtime cause; per FR-022, R-021.6).

2. **Promotion Decision (YYYY-MM-DD)**:
   - `Decision: stay opt-in` OR `Decision: promote to default`.
   - `Gating verdict: see §Quality-Gate Verdict YYYY-MM-DD (PASS / FAIL / BLOCKED)` (back-pointer to the §1 subsection).
   - `Decided by: <team identifier>` + `Decided at: <ISO date>`.
   - `Rationale:` 2–4 sentences.
   - If `promote to default`:
     - `Inverted default location: <file>:<line>` (colon-separated; e.g., `src/dartwing_ocr/preprocessing/evidence_gate_optin.py:42`).
     - `Explicit-off flag: <flag>` (e.g., `--no-evidence-gate-skip-fallback`).
     - `Explicit-off env var: <env var>` (e.g., `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=0`).
     - `Legacy-path test: <test path>` (the CPU-safe test exercising the inverted-default disable).

### Promotion-decision synchronization contract

The Appendix B `### Promotion Decision (YYYY-MM-DD)` subsection MUST be **mirrored** in `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` `## Promotion Decision` section. Mirror content MUST agree on:

- The binary decision literal (`stay opt-in` or `promote to default`).
- The gating-verdict reference.

A CPU-safe contract test (`tests/contract_tests/test_promotion_decision_sync.py`, new — falls under "CPU-safe contract test", not "new product behavior" per FR-032 since it tests documentation invariants) loads both files and asserts the decision literal appears identically in each. The test runs under `pytest -m 'not gpu'`.

## Re-derivability discipline (SC-005)

Appendix A + Appendix B together MUST be **sufficient for a third party to re-derive the promotion verdict without re-running**. Specifically:

- Every value in the Appendix A jitter/material tables MUST be computable from the raw `phase_timings.*` numbers in the same row (no implicit rounding, no hidden adjustment).
- The Appendix B verdict MUST be computable from the Appendix B per-document score + pass table (no implicit aggregation rule beyond R-021.13 sum/count).
- The promotion decision's gating-verdict reference MUST resolve to a verdict in the same Appendix B (no out-of-document reference).

## What this contract does NOT cover

- It does not constrain the prose between tables — operators may include free-form notes about anomalies, observations, or follow-up actions.
- It does not require Appendix C or beyond; this feature uses Appendix A + B only.
- It does not modify the feature-020 quickstart's non-appendix sections.
