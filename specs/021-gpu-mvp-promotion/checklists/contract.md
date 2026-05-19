# Contract Quality Checklist: GPU MVP Promotion

**Purpose**: Validate that the four Phase 1 contract documents under `contracts/` (helper invocation, GPU test marker, appendix recording, runbook structure) are written with the completeness, clarity, and consistency needed for an implementor to satisfy them without consulting source code or asking the author.
**Created**: 2026-05-18
**Feature**: [spec.md](../spec.md), [plan.md](../plan.md), [contracts/](../contracts/)

This checklist tests the *contracts as written* (requirements-quality of the contract files), not whether the implementation that satisfies them is correct. The contracts are listed and reviewed individually below.

## Cross-Contract Quality

- [X] CHK001 Is every contract file traceable to at least one spec FR or US scenario (no orphan contracts)? [Traceability, contracts/]
- [X] CHK002 Are the four contracts each named with a stable, descriptive filename (`ollama-readiness-helper.md`, `gpu-test-marker.md`, `appendix-recording.md`, `runbook.md`) so cross-references survive renames? [Traceability, contracts/]
- [X] CHK003 Are the four contracts each linked from `plan.md` §Phase 1 Handoff and from `quickstart.md` (so a reader following either entry point lands on the contract)? [Traceability, plan.md, quickstart.md]
- [X] CHK004 Is the relationship between contracts and spec FRs explicit — each contract names which FR(s) it implements at its top? [Traceability, contracts/]

## Contract 1: `ollama-readiness-helper.md` (FR-002)

### Invocation Contract

- [X] CHK005 Is the helper's path `scripts/check-ollama-gpu-readiness.sh` named identically in the contract, in the runbook contract, and in quickstart.md? [Consistency, contracts/ollama-readiness-helper.md]
- [X] CHK006 Is the `--voter-config <PATH>` flag's requiredness explicit (no default)? [Clarity, contracts/ollama-readiness-helper.md]
- [X] CHK007 Is the `--base-url <URL>` flag's optional-ness explicit with a pinned default (`http://localhost:11434`)? [Clarity, contracts/ollama-readiness-helper.md]
- [X] CHK008 Are the "disallowed surfaces" (no interactive prompts, no model loading, no PERSISTENT disk writes — an ephemeral trap-cleaned `mktemp` tmpfile for the curl response body is explicitly carved out and documented) enumerated as a closed list, so a reviewer can spot a violation? [Completeness, contracts/ollama-readiness-helper.md]

### Exit-Code Contract

- [X] CHK009 Are all five exit codes (0–4) enumerated with one-to-one mapping to status literals? [Completeness, Clarity, contracts/ollama-readiness-helper.md]
- [X] CHK010 Is the "unknown exit codes are FAIL of unspecified class" fallback rule stated, so wrappers don't accidentally treat new codes as PASS? [Coverage, contracts/ollama-readiness-helper.md]
- [X] CHK011 Are FAIL-class distinctions (partial GPU / not loaded / unreachable / config) defined operationally — a reviewer can pick the right exit code from a given `/api/ps` response shape? [Measurability, contracts/ollama-readiness-helper.md]

### Output-Stream Contract

- [X] CHK012 Is the PASS stdout JSON shape closed (status, model_name, size, size_vram, base_url, voter_config_path, timestamp_utc — exactly these keys)? [Completeness, contracts/ollama-readiness-helper.md]
- [X] CHK013 Is the FAIL stderr template for each exit code specified verbatim, so error-grepping is reproducible? [Clarity, contracts/ollama-readiness-helper.md]
- [X] CHK014 Is the contract explicit that PASS produces no stderr AND FAIL produces no stdout (mutually exclusive stream usage)? [Consistency, contracts/ollama-readiness-helper.md]

### Behavior Contract

- [X] CHK015 Are the seven behavioral steps (argument parsing → voter-config read → HTTP fetch → JSON parse → placement check → stdout emission → determinism) enumerated in execution order? [Completeness, contracts/ollama-readiness-helper.md]
- [X] CHK016 Is the curl invocation's flag list pinned (`--silent --show-error --fail --max-time 10`)? [Clarity, contracts/ollama-readiness-helper.md]
- [X] CHK017 Is the determinism guarantee stated explicitly — "given identical voter-config + identical `/api/ps` response, the helper MUST produce identical exit code AND identical structural stdout JSON keys; `timestamp_utc` is the one carved-out non-deterministic field (provenance metadata captured at invocation time) and MUST NOT be used as a cache key"? [Clarity, Determinism, contracts/ollama-readiness-helper.md]

### Integration & Testability

- [X] CHK018 Are the two callers of the helper (demo runbook, benchmark wrapper) both named, so a future change-impact analysis can find both? [Traceability, contracts/ollama-readiness-helper.md]
- [X] CHK019 Is the testability surface explicit — CPU-safe contract test (optional but allowed) + GPU integration via the runbook (required)? [Coverage, contracts/ollama-readiness-helper.md]
- [X] CHK020 Is the "what this contract does NOT cover" section complete — at least naming model-loading, Ollama startup, retries? [Completeness, contracts/ollama-readiness-helper.md]

## Contract 2: `gpu-test-marker.md` (FR-006 – FR-010, SC-004)

### File List

- [X] CHK021 Are all five files in scope (the four `pipeline_tests/` + one `unit/preprocessing/` placeholder) enumerated with their US scenario mappings? [Completeness, contracts/gpu-test-marker.md]
- [X] CHK022 Is the conditional FR-028 test file (`tests/unit/preprocessing/test_skip_fallback_explicit_off_legacy.py`) flagged as new-and-only-if-promotion, not folded into the unconditional five? [Clarity, contracts/gpu-test-marker.md]

### Marker Contract

- [X] CHK023 Is the file-level `pytestmark = pytest.mark.gpu` requirement specified verbatim (not paraphrased)? [Clarity, contracts/gpu-test-marker.md]
- [X] CHK024 Is the per-test `@pytest.mark.skip(reason="R-020.15")` removal rule stated as MUST (no allowance for keeping the decorator)? [Clarity, contracts/gpu-test-marker.md]
- [X] CHK025 Is the marker registration rule (in `pyproject.toml` `[tool.pytest.ini_options]` `markers = [...]`) explicit, with the exact entry shape and a one-line description? [Completeness, contracts/gpu-test-marker.md]

### Body Contract per Test

- [X] CHK026 Are the Given/When/Then acceptance shapes for each converted test (skip_fallback, borderline, lazy_construction, warmup-exception, quality-gate) reproduced from the spec without paraphrase-drift? [Consistency, Spec §US2, §US4, contracts/gpu-test-marker.md]
- [X] CHK027 Is the BLOCKED-via-`pytest.xfail(strict=False)` handling for the quality-gate test's BLOCKED case explicit, so a hardware blocker doesn't produce a test failure? [Clarity, contracts/gpu-test-marker.md]

### CI Behavior Contract

- [X] CHK028 Are the three CI modes (CPU CI, GPU validation, mixed) each given an expected `pytest -m` invocation and expected collection behavior? [Completeness, contracts/gpu-test-marker.md]
- [X] CHK029 Is the relationship between converted GPU tests and existing CPU-safe twins (`*_cpu.py`) explicit (twins unchanged, twins continue to cover invariants on CPU)? [Consistency, contracts/gpu-test-marker.md]

### Out-of-Scope

- [X] CHK030 Is the "does not pin pytest fixtures or assertion APIs" carve-out stated, so the contract doesn't accidentally over-constrain task-level implementation choices? [Clarity, contracts/gpu-test-marker.md]

## Contract 3: `appendix-recording.md` (FR-023 / FR-024)

### Appendix A Structure

- [X] CHK031 Are the six required Appendix A subsections enumerated in order (env fingerprint → doc subset → four-run timeline → per-doc phase tables → run_summary observability table → findings)? [Completeness, contracts/appendix-recording.md]
- [X] CHK032 Is the per-document phase-key table column set pinned (phase key, four run values, two spreads, threshold, Δ, Material?), with no implicit column? [Completeness, contracts/appendix-recording.md]
- [X] CHK033 Is the Material? column's value vocabulary closed (`YES / NO / YES ↓ ✓ / YES ↑ ⚠ / LAZY`), so a reviewer can recognize a non-conforming value? [Clarity, contracts/appendix-recording.md]
- [X] CHK034 Is the threshold=0 inline-note rule explicit (matches R-021.3), so an unfamiliar reviewer doesn't misread a `YES` with threshold 0? [Consistency, contracts/appendix-recording.md]

### Appendix B Structure

- [X] CHK035 Are the two required Appendix B subsections (Quality-Gate Verdict, Promotion Decision) enumerated with their dated-subsection naming convention `### Run YYYY-MM-DD`? [Completeness, contracts/appendix-recording.md]
- [X] CHK036 Is the per-document score+pass table column order pinned (document, legacy score, candidate score, legacy pass, candidate pass)? [Consistency, contracts/appendix-recording.md]
- [X] CHK037 Are the PASS / FAIL / BLOCKED required-content differences enumerated (PASS records the full table; FAIL adds regressing_metric + magnitude; BLOCKED records only blocked_cause)? [Completeness, contracts/appendix-recording.md]
- [X] CHK038 Is the Promotion Decision Record's field set pinned and matches data-model.md §5 (decision, gating_verdict_ref, decided_at, decided_by, rationale, promotion_artifacts)? [Consistency, contracts/appendix-recording.md, data-model.md §5]

### Synchronization Contract

- [X] CHK039 Is the Appendix B ↔ runbook mirror requirement stated as MUST, with the synchronization-test path named? [Clarity, contracts/appendix-recording.md]
- [X] CHK040 Is the synchronization test required to run under `pytest -m 'not gpu'` (CPU-safe)? [Coverage, contracts/appendix-recording.md]
- [X] CHK041 Is the synchronization test's assertion scope explicit (binary decision literal MUST agree; rationale agreement is not required)? [Clarity, contracts/appendix-recording.md]

### Re-derivability Discipline

- [X] CHK042 Is the SC-005 "sufficient for a third party to re-derive the promotion verdict" requirement reproduced verbatim in the contract, so a reviewer can hold the appendix shape to that standard? [Traceability, contracts/appendix-recording.md, Spec §SC-005]
- [X] CHK043 Are the three re-derivability rules (every value computable from raw numbers; verdict computable from per-doc table; gating reference resolves within Appendix B) enumerated? [Completeness, contracts/appendix-recording.md]

## Contract 4: `runbook.md` (FR-025)

### Section Structure

- [X] CHK044 Are the ten required runbook sections enumerated in fixed order (prereqs → readiness gate → demo command → run_summary read → suppression demo → scratch discipline → promotion decision → when-things-go-wrong → see-also)? [Completeness, contracts/runbook.md]
- [X] CHK045 Is the Step 1 readiness-first ordering pinned as MUST (Paddle preflight FIRST, then Ollama check, then demo)? [Clarity, contracts/runbook.md]
- [X] CHK046 Is the Step 2 demo command's required flag set pinned (`--preprocess-profile ppstructurev3@gpu` + `--preprocess-strategy ocr-only-v1` + `--extract-profile ollama@gpu`, per the post-/analyze C1-C4 / C6 corrections), so a reviewer can assert no CPU profile slipped in? [Clarity, contracts/runbook.md]
- [X] CHK047 Is the CLI flag-name caveat stated ("if feature 011/020's CLI surface differs at landing, re-pin from `--help`"), so the runbook stays accurate without speculative flag invention? [Coverage, contracts/runbook.md]

### Self-Sufficiency Test

- [X] CHK048 Is the SC-008 self-sufficiency rule reproduced as a testable invariant (grep for `@cpu` and `stub-voter` returns zero matches)? [Measurability, contracts/runbook.md]
- [X] CHK049 Is the "no `see the code for details` pointers in command-level instructions" rule stated explicitly? [Clarity, contracts/runbook.md]

### Promotion Decision Mirror

- [X] CHK050 Is the §Promotion Decision section's mirror-from-Appendix-B requirement stated, with the link-back direction specified (runbook links to Appendix B, not the inverse)? [Clarity, Consistency, contracts/runbook.md]

### Lifecycle

- [X] CHK051 Is the runbook update-lifecycle rule (future features changing `evidence_gate_id` or CLI flags MUST update the runbook in the same body of work) stated, so the runbook doesn't drift? [Coverage, contracts/runbook.md]

## Contract Quality Aggregate

- [X] CHK052 Are all four contracts free of `should` / `may` in normative positions (deterministic discipline, matches `determinism.md` CHK032)? [Consistency, contracts/]
- [X] CHK053 Are all four contracts free of implementation-specific language that would force one particular code structure (the contracts describe interfaces, not algorithms)? [Clarity, contracts/]
- [X] CHK054 Are all four contracts cross-linked back to the relevant FR(s), Constitution principles, and Phase 0 R-021 decisions? [Traceability, contracts/]
- [X] CHK055 Are the four contracts free of redundant duplications (e.g., the same exit-code table appearing in two contracts)? [Consistency, contracts/]

## Gaps to Flag

- [X] CHK056 Is a separate contract for the `configs/voter/ollama-gpu.yaml` file's content shape needed, or is its single key (`model_name`) trivially covered by feature 005's voter-config spec? [Gap]
- [X] CHK057 Is a contract for the CPU-safe promotion-decision-sync test (`tests/contract_tests/test_promotion_decision_sync.py`) needed, or is the synchronization rule already adequately specified in `appendix-recording.md`? [Gap]
- [X] CHK058 Are versioning / amendment expectations for these contracts specified — i.e., if a contract changes after landing, how is the change recorded? [Gap]
- [X] CHK059 Is a contract needed for the four converted GPU tests' BLOCKED-marking behavior across hardware-cause categories (kernel mismatch, paddle wheel mismatch, MIOpen state)? [Gap]

## Notes

- This checklist tests the *writing quality of the four Phase 1 contracts*. Each contract is a specification surface; the items above ensure those specifications are themselves complete, clear, consistent, and measurable.
- The principal failure mode for contract quality is silent reliance on author knowledge — a contract that "obviously means X to whoever wrote it" but doesn't say so. CHK020, CHK030, CHK053 are the defenses against that pattern.
- Items CHK056–CHK059 flag genuine gaps that may benefit from a future contract addition or research.md amendment.
