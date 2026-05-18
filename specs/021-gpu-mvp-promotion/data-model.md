# Data Model: GPU MVP Promotion (Feature 021)

**Date**: 2026-05-18 · **Branch**: `021-gpu-mvp-promotion` · **Spec**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

This feature persists **no new artifacts**. It does, however, define six conceptual entities whose shape is referenced by code (the Ollama readiness helper), tests (the converted GPU placeholders + quality-gate test), and documentation (Appendix A, Appendix B, the demo runbook). The entities below describe in-memory or transient-record shapes only.

For schema references to canonical artifacts (`preprocess_output.json` etc.), see `docs/stage1-vendor-identity/schemas.md` and `contracts/stage1_vendor_identity/v1.2.0/`. **No schemas change in this feature** (FR-031).

---

## 1. GPU Readiness Verdict

**Purpose**: Composite verdict gating every GPU benchmark and GPU demo run (FR-001 + FR-002 + FR-003).

**Shape** (transient, returned by a wrapper invocation that calls both checks; not persisted):

```text
GPUReadinessVerdict {
    paddle_preflight: {
        state: enum{"ppstructurev3_init_succeeded", "<named-failure>"}    # FR-001
        interpreter_path: str                                              # FR-003 (sys.executable)
    }
    ollama_placement: OllamaReadinessProbeResult                           # see §6
    verdict: enum{"PASS", "FAIL", "BLOCKED"}
    timestamp_utc: str                                                     # ISO-8601, recorded for forensics
}
```

**PASS rule** (deterministic): `verdict == "PASS"` iff `paddle_preflight.state == "ppstructurev3_init_succeeded"` AND `ollama_placement.status == "pass"`.

**FAIL rule**: at least one component fails and the failure is operator-remediable (e.g., wrong interpreter, model not loaded).

**BLOCKED rule**: at least one component fails with a hardware/runtime cause (e.g., ROCm unavailable on this kernel) that the operator cannot remediate in the moment; the named cause is captured for Appendix recording.

**Validation**:

- `paddle_preflight.state` MUST be a literal from a closed set (`ppstructurev3_init_succeeded` is the only PASS literal; failure literals are defined by feature 014's preflight).
- `interpreter_path` MUST be the value of `sys.executable` at preflight invocation time (FR-003 forensic only — never compared against an allowlist; per Q3 clarification).
- `ollama_placement` MUST follow the §6 contract.
- `verdict` MUST be one of the three literals; no fourth state.

**State transitions**: None. A verdict is a single-shot composite over a single moment; subsequent runs produce new verdicts.

**Recording**: The verdict is NOT persisted as a JSON file (FR-032 forbids new artifacts). It is logged to stderr (per R-021.10) and, for the demo run, summarized at the top of the demo's run notes. Appendix A's environment-fingerprint subsection records the verdict for the four-run benchmark.

---

## 2. Benchmark Run Record

**Purpose**: Per-document, per-lane, per-run record of the four-run benchmark discipline (FR-011 through FR-018, FR-023).

**Shape** (one record per (document × lane × run) tuple; recorded in Appendix A as a table row):

```text
BenchmarkRunRecord {
    document_id: str                          # e.g., "inv_001_easy"; one of the five FR-011 subset
    lane: enum{"warmup", "legacy", "candidate"}
    run_index: int                            # 1 or 2 (warmup only has run 1)
    phase_timings: dict<str, float>           # all emitted phase keys; values in seconds, 3 decimals (R-021.2)
    gate_decision: enum{"sufficient", "borderline", "insufficient"}    # feature 020 evidence-gate verdict
    evidence_gate_state_counts: dict<str, int>                          # feature 020 schema
    evidence_gate_suppressed_fallback_count: int                        # feature 020 schema
    ocr_only_fallback_count: int                                        # feature 020 schema
    preprocess_strategy_id: str                                         # feature 020 schema
    scratch_path: str                         # e.g., "/tmp/021-bench/legacy/run1/inv_001_easy/" (R-021.1)
}
```

**Validation**:

- `document_id` MUST be one of `{"inv_001_easy", "inv_002_easy", "inv_006_medium", "inv_011_hard", "inv_012_hard"}` (FR-011).
- `lane` ∈ `{warmup, legacy, candidate}`.
- `run_index ∈ {1, 2}`; `(lane, run_index) == ("warmup", 2)` is invalid (warmup is one run).
- `phase_timings` MUST contain all keys emitted by feature 015's `run_summary.phase_timings.*` for this run; the set is a superset, never a subset (R-021.2).
- `phase_timings[k]` MUST be a non-negative float, 3 decimals.
- The five evidence-gate fields MUST match feature 020's `RunSummary.SCHEMA_VERSION = 0.1.7` shape.
- `scratch_path` MUST match the R-021.1 layout `/tmp/021-bench/<lane>/run<N>/<document_id>/`.

**Cardinality**: 5 documents × (warmup ×1 + legacy ×2 + candidate ×2) = 25 records per benchmark sequence. Appendix A's comparison tables use only the run-2 records (10 records: 5 docs × 2 lanes). The 5 warmup records and the 10 run-1 records are forensic only.

**State transitions**: A record is immutable once recorded; a re-run produces a new (lane, run_index) tuple, never overwriting an existing one.

**Recording**: Appendix A tables. One table per phase-key family or per document; format pinned by `contracts/appendix-recording.md`.

---

## 3. Jitter Band

**Purpose**: Per-document, per-`phase_timings.*` threshold for the FR-015 / FR-016 material-change rule (Q1 clarification 2026-05-18).

**Shape** (derived, one per (document × phase_key) tuple; recorded in Appendix A inline with the benchmark tables):

```text
JitterBand {
    document_id: str
    phase_key: str                            # e.g., "per_page_inference"
    legacy_pair_spread: float                 # |legacy_run2 − legacy_run1| in seconds, 3 decimals
    candidate_pair_spread: float              # |candidate_run2 − candidate_run1| in seconds, 3 decimals
    threshold: float                          # max(legacy_pair_spread, candidate_pair_spread)
    material_delta: float                     # |candidate_run2 − legacy_run2|
    is_material: bool                         # material_delta > threshold (strict)
}
```

**Validation**:

- All spreads, threshold, and material_delta MUST be non-negative.
- `threshold == max(legacy_pair_spread, candidate_pair_spread)` (formula pinned by Q1).
- `is_material == (material_delta > threshold)` with strict greater-than (per Q1 / R-021.3).
- When `threshold == 0` AND `material_delta > 0`, `is_material == true` with an inline note "threshold=0 (no measured jitter); any delta material" (R-021.3).
- Direction-symmetric: `material_delta` is the absolute value (R-021.4).

**State transitions**: None. Derived per benchmark sequence; recomputed on a fresh four-run sequence.

**Recording**: Inline with each Benchmark Run Record's phase-key row in Appendix A — typically a one-line summary like `per_page_inference: legacy_run2=0.842s candidate_run2=0.531s | threshold=0.018s | Δ=0.311s | MATERIAL`.

---

## 4. Quality-Gate Verdict

**Purpose**: PASS / FAIL / BLOCKED verdict over the two-metric quality gate (FR-019 through FR-022).

**Shape** (one per benchmark sequence; recorded in Appendix B as a verdict block):

```text
QualityGateVerdict {
    verdict: enum{"PASS", "FAIL", "BLOCKED"}
    legacy_aggregate_score: float | null                  # sum of legacy run-2 per-doc vendor_identity_score (R-021.13)
    candidate_aggregate_score: float | null               # sum of candidate run-2 per-doc vendor_identity_score
    legacy_pass_count: int | null                         # count of legacy run-2 documents with vendor_identity_pass == true
    candidate_pass_count: int | null                      # count of candidate run-2 documents with vendor_identity_pass == true
    per_document: list<{
        document_id: str
        legacy_score: float
        candidate_score: float
        legacy_pass: bool
        candidate_pass: bool
    }>
    regressing_metric: enum{"aggregate", "pass_count", "both", "none"} | null      # populated only on FAIL
    regression_magnitude: {
        aggregate_delta: float | null                     # candidate - legacy (negative ⇒ regression)
        pass_count_delta: int | null                      # candidate - legacy (negative ⇒ regression)
    } | null                                               # populated only on FAIL
    blocked_cause: str | null                             # named cause; populated only on BLOCKED
    recorded_at: str                                       # ISO-8601 date
}
```

**Validation**:

- PASS requires `candidate_aggregate_score >= legacy_aggregate_score AND candidate_pass_count >= legacy_pass_count` (FR-020 strict conjunction).
- FAIL requires at least one metric strictly less than legacy. `regressing_metric` and `regression_magnitude` MUST be populated.
- BLOCKED requires `legacy_aggregate_score`, `candidate_aggregate_score`, `legacy_pass_count`, `candidate_pass_count`, and `per_document` to be `null`. `blocked_cause` MUST be a non-empty string naming a specific hardware/runtime cause (FR-022, R-021.6).
- `per_document` length MUST equal 5 (the FR-011 subset) on PASS / FAIL; `null` on BLOCKED.

**State transitions**: A verdict is immutable once recorded; a re-evaluation produces a new dated record.

**Recording**: Appendix B verdict block; format pinned by `contracts/appendix-recording.md`.

---

## 5. Promotion Decision Record

**Purpose**: The team's binary decision about whether OCR-only skip-fallback stays opt-in or is promoted to default (FR-026 through FR-029).

**Shape** (one per feature landing; recorded in Appendix B AND mirrored in the runbook per R-021.11):

```text
PromotionDecisionRecord {
    decision: enum{"stay opt-in", "promote to default"}
    gating_verdict_ref: str                                   # e.g., "see §Quality-Gate Verdict 2026-05-18 (PASS)"
    rationale: str                                            # 2–4 sentences
    decided_at: str                                            # ISO-8601 date
    decided_by: str                                            # team identifier (e.g., "Dartwing OCR pipeline team")
    promotion_artifacts: {                                    # populated only if decision == "promote to default"
        inverted_default_location: str                        # e.g., "src/dartwing_ocr/preprocessing/evidence_gate_optin.py L42"
        explicit_off_flag: str                                # e.g., "--no-evidence-gate-skip-fallback"
        explicit_off_env_var: str                             # e.g., "DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=0"
        legacy_path_test: str                                 # path to the CPU-safe test exercising the legacy path
    } | null
}
```

**Validation**:

- `decision == "promote to default"` MUST be consistent with `gating_verdict_ref` pointing at a PASS verdict (FR-027).
- If `decision == "promote to default"`, `promotion_artifacts` MUST be fully populated and the named `legacy_path_test` MUST exist and pass under `pytest -m 'not gpu'` (SC-009).
- If `decision == "stay opt-in"`, `promotion_artifacts` MUST be `null`.
- `gating_verdict_ref` MUST be a textual reference to a Quality-Gate Verdict subsection in Appendix B (back-pointer for traceability).

**State transitions**: A record is immutable once recorded; a future change of operational posture creates a new dated record and the prior record is retained as history.

**Recording**: Appendix B `### Promotion Decision (YYYY-MM-DD)` subsection (authoritative) + runbook `## Promotion Decision` mirror (R-021.11). Synchronization is verified by a CPU-safe contract test (see `contracts/appendix-recording.md`).

---

## 6. Ollama Readiness Probe Result

**Purpose**: Structured result of one invocation of `scripts/check-ollama-gpu-readiness.sh` (R-021.9).

**Shape** (transient; stdout-emitted JSON on PASS, stderr message on FAIL):

```text
OllamaReadinessProbeResult {
    status: enum{"pass", "fail_partial_gpu", "fail_not_loaded", "fail_unreachable", "fail_config"}
    model_name: str                                            # voter-config model_name
    size: int | null                                           # bytes; null on fail_unreachable / fail_config
    size_vram: int | null                                      # bytes; null on fail_unreachable / fail_config
    base_url: str                                              # default "http://localhost:11434"
    voter_config_path: str                                     # source of model_name
    timestamp_utc: str
}
```

**Status mapping** (one-to-one with helper exit codes per R-021.9):

| Exit code | Status                | Condition                                                            |
|----------:|-----------------------|----------------------------------------------------------------------|
| 0         | `pass`                | `size_vram > 0 AND size_vram == size`                                |
| 1         | `fail_partial_gpu`    | `size_vram == 0` OR `0 < size_vram < size`                           |
| 2         | `fail_not_loaded`     | Model name absent from `/api/ps` response                            |
| 3         | `fail_unreachable`    | Curl non-zero, network error, non-200 HTTP                           |
| 4         | `fail_config`         | Voter-config missing, not YAML, or no `model_name` key               |

**Validation**:

- `status == "pass"` requires `size_vram > 0 AND size_vram == size` (FR-002, fully-on-GPU).
- `status == "fail_partial_gpu"` covers `size_vram == 0` (CPU placement) and `0 < size_vram < size` (mixed placement).
- `model_name` MUST be non-empty; sourced from the voter-config YAML's `model_name` string (feature 005 contract).
- `size` and `size_vram` MUST be non-negative integers (bytes) when present.

**State transitions**: None — single-shot probe per invocation.

**Recording**: PASS emits a single JSON line on stdout (suitable for `| jq`). All FAIL statuses emit a single human-readable line on stderr (R-021.10). The probe result is captured into Appendix A's environment-fingerprint subsection at benchmark time.

---

## Cross-Entity Relationships

```text
GPUReadinessVerdict ─┬─ paddle_preflight (feature 014/015 surface; unchanged here)
                    └─ ollama_placement = OllamaReadinessProbeResult

Benchmark Sequence ─┬─ produces 25 BenchmarkRunRecord (5 docs × 5 (lane,run) tuples)
                   ├─ derives 10 JitterBand per phase_key from run-2 pairs (5 docs × N phase keys × 1 band)
                   ├─ feeds feature-007 evaluator → produces QualityGateVerdict
                   └─ informs PromotionDecisionRecord (rationale only; verdict alone never auto-promotes)

PromotionDecisionRecord references QualityGateVerdict by appendix subsection (back-pointer).
```

## What this feature does NOT define

- No new `*.json` artifact schema (FR-031).
- No new `run_summary` field (FR-032). Feature 020's `RunSummary.SCHEMA_VERSION = 0.1.7` is used as-is.
- No new evaluator metric (R-021.13 — feature-007 evaluator outputs reused unchanged).
- No new entity that lives inside `src/dartwing_ocr/` (FR-032). All six entities above are either documentation entries (Appendix A, B, runbook) or transient shell-helper / test-local data.

## Next

`contracts/` defines the surfaces for each entity that has a programmatic boundary (helper invocation, test marker, appendix-recording format, runbook structure).
