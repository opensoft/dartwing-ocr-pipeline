# Implementation Plan: GPU MVP Promotion

**Branch**: `021-gpu-mvp-promotion` | **Date**: 2026-05-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/021-gpu-mvp-promotion/spec.md`

## Summary

Close the GPU-deferred proof points from feature 020 and make the MVP demo GPU-required without breaking CPU-safe CI. The work is a **validation, promotion, and documentation slice** — no schema changes, no new product behavior in `dartwing_ocr` except a single conditional inverted default (the FR-028 explicit-off legacy path, only if the team chooses promote-to-default after a PASS verdict).

Six concrete deliverables: (1) an Ollama `/api/ps` readiness shell helper under `scripts/` that asserts the active voter-config model is fully GPU-placed (`size_vram > 0 AND size_vram == size`); (2) conversion of the **five** feature-020 GPU placeholder tests — the four under `tests/pipeline_tests/` plus `tests/unit/preprocessing/test_warmup_skip_fallback_exception.py` — from `@pytest.mark.skip(reason="R-020.15")` to real GPU-asserting tests (preserving the `pytest.mark.gpu` collection marker so CPU CI continues to skip them); (3) the four-run benchmark numbers recorded in `specs/020-vendor-evidence-gate/quickstart.md` Appendix A using the FR-015 jitter formula `max(|legacy_run2 − legacy_run1|, |candidate_run2 − candidate_run1|)`; (4) the two-metric quality-gate verdict (PASS / FAIL / BLOCKED) recorded in Appendix B; (5) a new demo runbook at `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` that starts with readiness checks, uses `ppstructurev3@gpu` + `ollama@gpu` only, and surfaces the seven feature-020 `run_summary` observability fields; (6) the recorded binary promotion decision (stay-opt-in / promote-to-default) in Appendix B and the runbook.

Implementation order respects the user-story priorities (P1 readiness gate → P2 deferred verification → P3 benchmark, quality gate, runbook, promotion decision). The order is also dependency-driven: readiness gate is the precondition for trusting every later proof point.

## Technical Context

**Language/Version**: Python 3.12 (matches `.devcontainer/Dockerfile` and `pyproject.toml requires-python = ">=3.12"`; consistent with features 001–020).
**Primary Dependencies**: Existing only — `pytest>=8` (test framework, already declared), `PyYAML>=6` (voter-config parsing, already declared by feature 005), `paddleocr>=3.5,<4`, `paddlepaddle-dcu` (workstation-only optional install, already proven by features 014–019), `httpx>=0.27,<1` (used by feature 005 extractor, available to tests). **No new pinned dependency.** The Ollama readiness shell helper uses `curl` + `jq` + `yq` (system tools, not Python packages). ROCm runtime is a workstation system dependency, not a Python package.
**Storage**: Filesystem only. Reads `voter_config.yaml` (path supplied by runbook); reads host Ollama `/api/ps` at `http://localhost:11434/api/ps`; reads benchmark scratch outputs from `/tmp/021-bench/<lane>/run<N>/inv_XXX_<difficulty>/...`. Writes the four-run benchmark scratch outputs into that same `/tmp/021-bench/` tree (mirrors the corpus per-document folder contract). Writes recorded evidence into `specs/020-vendor-evidence-gate/quickstart.md` Appendix A and Appendix B, and into the new `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`. Writes no new canonical artifact, no new `run_summary` field (FR-031, FR-032).
**Testing**: pytest with the existing `pytest.mark.gpu` collection marker (used by the four placeholder tests). GPU tests are collected only when running explicitly opt-in (e.g., `pytest -m gpu`); CPU CI continues to use `pytest -m 'not gpu'` or equivalent. CPU-safe twins (`*_cpu.py`) preserve the existing fast-CI coverage of the same invariants. Where the promotion-to-default branch is chosen at landing time, one additional CPU test exercises the FR-028 explicit-off legacy path.
**Target Platform**: AMD ROCm workstation (WSL or native Linux) with `paddlepaddle-dcu` installed in `.venv-paddle-rocm`, plus host Ollama started via `scripts/start-host-ollama-rocm-wsl.sh`. CPU/stub paths continue to work in the standard `.venv` and in CI without GPU.
**Project Type**: CLI + library — already established by features 001–020. This feature does NOT add a new package layout; it appends to `scripts/`, `tests/pipeline_tests/` (conversion in place), `docs/stage1-vendor-identity/` (new runbook), and edits `specs/020-vendor-evidence-gate/quickstart.md` (Appendix A + B).
**Performance Goals**: No fixed absolute latency target (FR-015 anchors "material change" to the per-document, per-phase-key jitter band, not an absolute threshold). The promotion gate is *non-regression*: candidate run-2 must be within or below the jitter band of legacy run-2 on every recorded `phase_timings.*` key except `per_page_inference` and `total`, which are *permitted* to materially decrease on suppressed documents (FR-016).
**Constraints**: (a) **FR-031** — no canonical artifact schema, filename, or folder-contract change; (b) **FR-032** — no new product behavior in `dartwing_ocr` except the conditional FR-028 explicit-off legacy path; no new persisted artifact; no new `run_summary` field beyond feature 020's set; no remote cloud; no Jetson; no over-time surveillance; (c) **FR-033** — no regeneration of committed corpus baselines from GPU output; (d) Constitution §III — readiness gate, jitter formula, verdict logic, and promotion-permission logic are deterministic code; (e) Constitution §V — Appendix A is sufficient for third-party verdict re-derivation (SC-005); (f) **FR-008 lazy-construction key-absence semantics are inherited, not redefined here**: the FR-008 assertion that `phase_timings.engine_init` and `phase_timings.warmup` are *absent* from the per-document `run_summary` line on lazy paths depends on feature 015 (engine-init amortization once per process) and feature 016 (warmup absence on cache-hot paths) emission contracts. This feature consumes those contracts and does not define new key-emission semantics; if a future feature changes those, FR-008's test bodies (T011, T012) must be revisited.
**Scale/Scope**: 1 shell helper (~50 lines, `scripts/check-ollama-gpu-readiness.sh`). 4 placeholder-test conversions (one decorator line + body per file). 1 new doc (~150 lines, demo runbook). 2 appendix sections filled (Appendix A: 5 documents × 2 lanes × phase-key tables; Appendix B: quality-gate verdict + per-doc score/pass tables). 1 promotion decision record (binary, with rationale). **25 benchmark records per sequence** (5 warmup + 10 legacy + 10 candidate per `data-model.md §2 Benchmark Run Record`); only the 10 run-2 records (5 docs × 2 lanes, legacy and candidate) feed Appendix A's comparison tables — the 5 warmup records and the 10 run-1 records are forensic only. Optionally 1 inverted-default code line + 1 CPU test if promote-to-default is chosen.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

This feature is a validation/promotion/documentation slice — the most failure-prone constitution dimension is preserving the **runtime boundary** (Constitution §I) between pipeline code, harness code, and the model runtime. The plan keeps that boundary intact by routing the Ollama readiness check through a **shell helper outside `dartwing_ocr`** (per the Q2 clarification and FR-002's explicit "no new module in the package" carve-out). Below each principle is evaluated.

### I. One Repo, Clear Runtime Boundaries — PASS

The pipeline code (`src/dartwing_ocr/`) is unchanged except for one conditional line if promotion-to-default is chosen. The Ollama readiness check is a `scripts/` shell helper, not a pipeline module. The harness (`tests/`) gains test-body content but no new boundary. The model runtime (host Ollama) is unchanged. The cloud-class workstation validation lane is exercised in place, exactly as Constitution §I and Stage 1 Scope Constraint #5 permit.

### II. Evidence-First, Schema-First Design — PASS

FR-031 enforces the four canonical artifact schemas (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`) are unchanged. FR-032 forbids new persisted artifacts and new `run_summary` fields beyond feature 020's set. The plan's documentation deliverables (Appendix A, Appendix B, runbook) do not alter `docs/stage1-vendor-identity/schemas.md`.

### III. Deterministic Control Over Model Output — PASS

The readiness gate (Paddle preflight literal + Ollama `size_vram == size` check), the jitter formula (`max(|legacy_run2 − legacy_run1|, |candidate_run2 − candidate_run1|)`), the material-change rule (`|candidate_run2 − legacy_run2| > threshold`), the two-metric verdict (PASS iff candidate ≥ legacy on BOTH metrics), and the promotion permission (PASS *permits* but never *performs* promotion — FR-029) are all deterministic code. No model output participates in any decision.

### IV. Provenance and Review Safety — PASS

Vendor-identity provenance (`company_name.present`, `company_name.inferred`, `manual_review_required`) is preserved by FR-031. This feature does not modify the provenance surface; it only validates that the GPU lane reproduces the same provenance behavior as the CPU lane.

### V. Benchmarkable and Reproducible Delivery — PASS

The four-run discipline, the FR-015 jitter formula, the fixed five-document subset (`inv_001_easy`, `inv_002_easy`, `inv_006_medium`, `inv_011_hard`, `inv_012_hard`), and SC-005's "sufficient for a third party to re-derive the promotion verdict without re-running" are all explicitly reproducibility constraints. Per-document, per-phase-key recording in Appendix A is the audit trail.

### Stage 1 Scope Constraints — PASS

PDF input only ✓. Vendor identity only ✓. No line items ✓. No remote cloud (workstation GPU validation is explicitly permitted by Scope Constraint #5: "local cloud-class workstation validation is allowed when it uses the same artifact contracts and keeps remote deployment concerns out of the pipeline") ✓. No new latency release gate (FR-016 is a non-regression gate, not an absolute target) ✓. No Jetson ✓. Minimal review output preserved ✓.

### Quality Gates — PASS

QG #1 (pipeline/harness boundary): preserved. QG #2 (output contracts): schemas unchanged (FR-031). QG #3 (runtime behavior): the new demo runbook + appendix entries update `docs/stage1-vendor-identity/` consistently with `architecture.md` and `ollama-runtime.md`. QG #4 (concrete local execution path): the GPU lane is the concrete path; CPU lane remains for fallback. QG #5 (container vs. native Linux distinction): the runbook explicitly names `scripts/start-host-ollama-rocm-wsl.sh` for WSL and references `docker/compose.ollama-rocm-linux.yml` only as the production-style native Linux comparison; WSL behavior is not represented as production. QG #6 (`expected.json` comparison): preserved — the two-metric quality gate uses the existing feature-007 evaluator unchanged. QG #7 (consistency with `architecture.md`): preserved — this feature does not amend `architecture.md`.

**Verdict (pre-Phase-0)**: All gates PASS. No violations to record. The Complexity Tracking table is intentionally empty.

### Post-Phase-1 Re-evaluation

After generating [research.md](./research.md), [data-model.md](./data-model.md), the four files under [contracts/](./contracts/), and [quickstart.md](./quickstart.md), the Constitution Check is re-evaluated:

- **§I Boundary**: Phase 1 confirmed the Ollama readiness check is `scripts/check-ollama-gpu-readiness.sh` (POSIX shell, outside `dartwing_ocr`). The new `configs/voter/ollama-gpu.yaml` is a configuration file, not pipeline code. **`configs/voter/` is a new top-level directory introduced by this feature; it is intentionally additive and bounded to voter-config YAMLs only — it is NOT a general config dump.** Future features that need a different class of configuration (model registries, runtime presets, etc.) MUST justify a sibling directory rather than extending `configs/voter/`, and any change to that boundary requires its own constitution check. The new `tests/contract_tests/test_promotion_decision_sync.py` and `tests/contract_tests/test_ollama_readiness_helper_contract.py` are harness-layer tests, not pipeline modules. The four converted GPU tests under `tests/pipeline_tests/` stay in the harness layer. Pipeline / harness / model-runtime boundary intact. **PASS**.
- **§II Schema-first**: data-model.md defines six conceptual entities, none of which persist as a new JSON file. FR-031 schema-preservation is upheld throughout the contracts. **PASS**.
- **§III Determinism**: Every decision in research.md (jitter formula derivation, exit-code taxonomy, status mapping, recording rules, FR-020 strict conjunction, FR-029 no-auto-promotion) is deterministic code or specification. No model output participates in any verdict. **PASS**.
- **§IV Provenance**: Feature 020's vendor-identity provenance surface is preserved (FR-031). **PASS**.
- **§V Reproducibility**: appendix-recording.md's required tables and re-derivability discipline directly satisfy SC-005 ("sufficient for a third party to re-derive the promotion verdict without re-running"). **PASS**.
- **Stage 1 Scope Constraints**: PDF input only ✓, vendor identity only ✓, no line items ✓, no remote cloud (workstation GPU validation is the explicitly permitted lane per Scope Constraint #5) ✓, no Jetson ✓, no new absolute latency gate ✓. **PASS**.
- **Quality Gates 1–7**: All gates remain green. No change to `schemas.md` (QG #2). The new runbook is consistent with `architecture.md` and `ollama-runtime.md` (QG #3). The GPU lane is the concrete execution path (QG #4). WSL vs. native Linux distinction preserved in the runbook prerequisites (QG #5). Feature-007 evaluator reused unchanged (QG #6). Consistency with `architecture.md` preserved (QG #7). **PASS**.

**Verdict (post-Phase-1)**: All gates PASS. No new violations introduced by Phase 1 design. The Complexity Tracking table remains intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/021-gpu-mvp-promotion/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output — R-021.1 through R-021.14 decisions
├── data-model.md        # Phase 1 output — entities for readiness verdict, run record, jitter, verdicts
├── quickstart.md        # Phase 1 output — end-to-end GPU validation walk-through
├── contracts/           # Phase 1 output — shell helper invocation contract, test marker contract, appendix-recording contract, runbook contract
│   ├── ollama-readiness-helper.md
│   ├── gpu-test-marker.md
│   ├── appendix-recording.md
│   └── runbook.md
├── checklists/          # /speckit.checklist output (already populated by deep-rigor run)
│   ├── requirements.md
│   ├── scope.md
│   ├── gpu-readiness.md
│   ├── benchmark.md
│   ├── quality-gate.md
│   ├── runbook.md
│   ├── promotion.md
│   └── failure-handling.md
├── spec.md              # /speckit.specify + /speckit.clarify output
└── tasks.md             # Phase 2 output (/speckit.tasks command — NOT created by /speckit.plan)
```

### Source Code (repository root)

This feature does NOT introduce a new package layout. It appends to existing locations:

```text
scripts/
└── check-ollama-gpu-readiness.sh           # NEW — FR-002 readiness helper (curl + jq + yq, ≤80 lines)

src/dartwing_ocr/
├── preprocessing/
│   ├── preflight.py                        # EXISTING (feature 014/015) — invoked by readiness gate, unchanged
│   ├── preflight_cli.py                    # EXISTING — `python -m dartwing_ocr.preprocessing.preflight`
│   └── evidence_gate_optin.py              # EXISTING (feature 020) — touched ONLY if promote-to-default is chosen (one default flip)
└── extract/
    └── config.py                           # EXISTING (feature 005) — voter-config loader, unchanged

tests/
├── pipeline_tests/
│   ├── test_evidence_gate_skip_fallback.py                       # CONVERT — `@pytest.mark.skip` → real GPU assertions (US2-1)
│   ├── test_evidence_gate_skip_fallback_borderline.py            # CONVERT — `@pytest.mark.skip` → real GPU assertions (US2-2)
│   ├── test_evidence_gate_all_suppressed_lazy_construction.py    # CONVERT — `@pytest.mark.skip` → real GPU assertions (US2-3 + US2-4)
│   └── test_quality_gate_two_metric_evidence_gate.py             # CONVERT — `@pytest.mark.skip` → real GPU assertions wired to feature-007 evaluator (US4)
└── unit/
    └── preprocessing/
        └── test_warmup_skip_fallback_exception.py                # CONVERT — `@pytest.mark.skip` → real `--gpu-warmup` exception assertion (US2-4)

# Conditional (only if promote-to-default is the recorded decision):
tests/unit/preprocessing/
└── test_skip_fallback_explicit_off_legacy.py                     # NEW — FR-028 explicit-off legacy-path test (CPU-safe)

docs/stage1-vendor-identity/
└── runbook-gpu-mvp-demo.md                 # NEW — FR-025 demo runbook (≤200 lines)

specs/020-vendor-evidence-gate/
└── quickstart.md                           # EDIT — Appendix A filled (5 docs × 2 lanes × phase-keys); Appendix B filled (PASS/FAIL/BLOCKED verdict + per-doc scores)
```

**Structure Decision**: Single-project layout, additive only. No new top-level directory. No new package under `src/dartwing_ocr/`. The Ollama check lives under `scripts/` per FR-002's explicit "outside the package" carve-out (Q2 clarification, 2026-05-18). The four GPU-deferred test conversions edit the existing files in place — they preserve the `pytestmark = pytest.mark.gpu` collection marker (CPU CI continues to skip them) and replace the per-test `@pytest.mark.skip(reason="R-020.15")` decorator with real assertion bodies. The demo runbook lands at `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` per R-021.5 (closes the runbook canonical-path gap surfaced by the checklist).

## Phase 0 → Phase 1 Handoff

Phase 0 (research.md) resolves 14 planning decisions surfaced by the checklist gap-flag review, this plan's structural choices, and the post-/speckit.analyze CLI-surface verification:

- **R-021.1** Scratch-copy directory layout under `/tmp/021-bench/`
- **R-021.2** Timing unit + numeric formatting for Appendix A
- **R-021.3** Threshold-zero jitter edge case (`run1 == run2` on both lanes)
- **R-021.4** Direction symmetry for "material change" (FR-016 increases on suppressed docs are also findings)
- **R-021.5** Canonical demo-runbook file path
- **R-021.6** Handling when Ollama is up but the extraction model is not yet loaded
- **R-021.7** Active voter-config path resolution (which YAML the readiness helper reads)
- **R-021.8** pytest mark + GPU gating mechanism (preserve existing `pytest.mark.gpu`)
- **R-021.9** Ollama readiness shell helper invocation contract (flags, exit codes)
- **R-021.10** Stderr/stdout split for fail-fast error messages
- **R-021.11** Promotion-decision recording artifact (the team-decision medium)
- **R-021.12** Partial-progress benchmark recording (3 of 5 documents succeed)
- **R-021.13** Aggregate vendor-identity score formula (which feature-007 evaluator output is the source of truth)
- **R-021.14** Warm-corpus output semantics — `--output-dir` is NOT honored in `--documents-file` mode; outputs land back in each per-doc folder, so scratch-copy mirroring is the only way to keep committed corpus clean (added 2026-05-18 during analyze remediation)

Phase 1 produces:

- `data-model.md` — six entities: GPU Readiness Verdict, Benchmark Run Record, Jitter Band, Quality-Gate Verdict, Promotion Decision Record, Ollama Readiness Probe Result.
- `contracts/ollama-readiness-helper.md` — shell helper CLI contract (flags, exit codes, stdout/stderr discipline).
- `contracts/gpu-test-marker.md` — pytest marker + selection contract; how `pytest.mark.gpu` interacts with `@pytest.mark.skip` removals.
- `contracts/appendix-recording.md` — Appendix A + B table shapes, ordering, and re-derivability contract.
- `contracts/runbook.md` — runbook structural contract (sections, order, exact-command discipline, observability-field walkthrough).
- `quickstart.md` — end-to-end GPU validation walk-through covering readiness → deferred-test conversion → four-run benchmark → quality gate → appendices → runbook + promotion decision.

Phase 1 ends with `update-agent-context.sh` updating CLAUDE.md's "Active Technologies" and "Recent Changes" lines for feature 021.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_  | _(none)_   | _(none)_ — All Constitution principles and Quality Gates PASS without exception. |
