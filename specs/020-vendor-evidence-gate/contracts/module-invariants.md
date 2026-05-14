# Module Invariants: `preprocessing/evidence_gate.py` and `preprocessing/evidence_gate_optin.py`

Hard invariants enforced at the module-import and module-call boundaries. Each invariant maps to a specific FR / SC in `spec.md`.

---

## Pure-read invariants (FR-001 / FR-027 / Constitution III)

| # | Invariant | Enforcement |
|---|---|---|
| MI-1 | The gate computation MUST be a pure function of `preprocess_output.json` content. No global state. No file I/O outside the input dict. No network. No model call. | Unit tests pass a `dict` (not a file path); module-level imports verified by `test_evidence_gate_signals_unit.py` (no Paddle / no requests / no torch import). |
| MI-2 | The gate MUST NOT consult `edge_extraction_output.json`, `routing_decision.json`, or `final_structured_payload.json`. | The module accepts only `preprocess_output` dicts as input; type signature `evaluate_evidence_gate(preprocess_output: dict, *, gate_id: str = "v1") -> EvidenceGateResult` does not expose other artifact types. |
| MI-3 | The gate MUST NOT consult model output (extraction, classification, vendor-identity). | Same as MI-2; type signature prevents it. |
| MI-4 | Module-load is CPU-safe and Paddle-free. | `import preprocessing.evidence_gate` from a process with no Paddle installed succeeds. CI runs this import in the CPU-only suite. |
| MI-5 | Module-load is `paddleocr` / `paddlepaddle` / GPU-runtime-free. | Static analysis at PR review: no `from paddleocr import` or `import paddle` statements in either module. |

---

## Determinism invariants (FR-001 / FR-004 / FR-005 / SC-001 / SC-002 / SC-012)

| # | Invariant | Enforcement |
|---|---|---|
| MI-6 | Two invocations of `EvidenceGate.evaluate(input_dict)` on byte-identical input dicts MUST produce byte-identical `EvidenceGateResult`s on the same host AND across hosts. | `test_evidence_gate_signals_unit.py` asserts byte-equality across two invocations on the same input. |
| MI-7 | The decision `d` produced by `EvidenceGate.evaluate(input_dict)` MUST satisfy `d == EVIDENCE_GATES[gate_id].decide(result.signals)` (re-derivability). | `test_evidence_gate_decision_unit.py` asserts the invariant on a parameterized table of synthetic `FiveSignalSet` values. |
| MI-8 | `Y_THRESHOLD_FRACTION`, `DENSITY_THRESHOLD`, `CONFIDENCE_THRESHOLD`, and the regex constants MUST be `Final[...]` and immutable at module load. | Static analysis (mypy / pyright); a runtime test attempts mutation and asserts `AttributeError` / `FrozenInstanceError`. |
| MI-9 | Token extraction MUST use NFKC Unicode normalization before tokenization. | Unit test passes a string containing combining characters / fullwidth forms; asserts the normalized token list matches the expected canonical list. |

---

## Evaluation-order invariants (FR-007 / R-020.7)

| # | Invariant | Enforcement |
|---|---|---|
| MI-10 | The decision recorded in `evidence_gate_documents` for any document MUST be the gate evaluation over that document's FINAL `preprocess_output.json` (the file written to disk and accepted by downstream stages). | `test_evidence_gate_corpus_run.py` re-reads the on-disk `preprocess_output.json` for each document and reapplies the gate; asserts the recorded decision matches the recomputed decision. |
| MI-11 | When the suppression predicate (R-020.8) returns `False` and a fallback fires, the gate MUST be evaluated TWICE per document — once on the OCR-only candidate (for the predicate input) and once on the post-fallback PPStructureV3 final output (for the recorded decision). | Verified via `test_evidence_gate_skip_fallback_borderline.py @gpu` (deferred); CPU-safe variant uses an injected fake `preprocess_strategy` whose fallback path is observable. |
| MI-12 | When the suppression predicate returns `True`, the gate MUST be evaluated EXACTLY ONCE per document (on the OCR-only candidate, which is then kept as the final output). | Verified via `test_evidence_gate_skip_fallback.py @gpu` (deferred); CPU-safe variant covers this via the predicate's deterministic execution path. |

---

## Suppression invariants (FR-007 / FR-009 / R-020.8 / SC-011)

| # | Invariant | Enforcement |
|---|---|---|
| MI-13 | `should_suppress_fallback` MUST return `True` iff ALL four conjuncts hold: `preprocess_strategy_id == "ocr-only-v1"` AND `fr_005_trigger_would_fire == True` AND `opt_in_active == True` AND `candidate_gate_decision == "sufficient"`. | Unit test `test_evidence_gate_suppress_predicate.py` covers all 16 truth-table rows. |
| MI-14 | `borderline` and `insufficient` candidate gate decisions MUST NEVER trigger suppression, regardless of opt-in or strategy. | Unit test asserts `should_suppress_fallback(..., candidate_gate_decision="borderline") == False` AND `should_suppress_fallback(..., candidate_gate_decision="insufficient") == False`, both with `opt_in_active=True` and FR-005 trigger firing. |
| MI-15 | `evidence_gate_suppressed_fallback_count` MUST increment by exactly `1` per document where `should_suppress_fallback` returns `True` for that document, and MUST NOT increment otherwise. | `test_evidence_gate_skip_fallback.py @gpu` asserts increment by 1; CPU-safe variant via injection asserts the increment is exactly synchronized with the predicate's return value. |

---

## Always-emit invariants (FR-008 / FR-010 / FR-011 / R-020.10 / SC-003)

| # | Invariant | Enforcement |
|---|---|---|
| MI-16 | Every run of `python -m ledgerlinc_ocr.preprocessing` or `python -m ledgerlinc_ocr.pipeline` MUST emit a `kind: "run_summary"` stdout line that includes all four new top-level fields (`evidence_gate_id`, `evidence_gate_state_counts`, `evidence_gate_documents`, `evidence_gate_suppressed_fallback_count`). | `test_run_summary_schema_0_1_7.py` asserts via `jq -e` that all four keys are present on stub-adapter, CPU, and (deferred) GPU run outputs. |
| MI-17 | Default values when no documents reached the gate: `evidence_gate_id = "v1"`, `evidence_gate_state_counts = {"sufficient": 0, "borderline": 0, "insufficient": 0}`, `evidence_gate_documents = []`, `evidence_gate_suppressed_fallback_count = 0`. The state-counts object MUST be present with all three keys (NOT a sparse object). | `test_run_summary_schema_0_1_7.py` asserts default shape on a stub-adapter run with empty corpus. |
| MI-18 | `evidence_gate_state_counts[s]` MUST equal the count of `evidence_gate_documents[i].decision == s` for each `s` in the closed vocabulary. | `test_evidence_gate_corpus_run.py` asserts the aggregate equals the per-document count for each of the three states. |
| MI-19 | No existing `run_summary` field, no `phase_timings.*` key, no field inside any canonical artifact, and no field introduced by features 017/018/019 is renamed, removed, or retyped. | `test_run_summary_schema_0_1_7.py` reads a captured pre-feature-020 `run_summary` (from feature 019 fixtures) and asserts every key is still present in the post-bump emission with the same type. |

---

## Skip-fallback default-off invariant (FR-012 / SC-008)

| # | Invariant | Enforcement |
|---|---|---|
| MI-20 | At landing, the skip-fallback opt-in defaults to OFF on every profile (including `ppstructurev3@gpu`). A run with no `--evidence-gate-skip-fallback` flag AND no truthy `LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK` env var MUST produce identical behavior to a pre-feature-020 run on the same fixture (modulo the four additive `run_summary` fields). | `test_legacy_byte_identity_evidence_gate.py` (CPU) asserts `preprocess_output.json` byte-identity to a feature-019 baseline. |
| MI-21 | Promoting the opt-in to default-on requires passing the FR-016 quality gate (R-020.14) AND a code change to flip the default in `evidence_gate_optin.py::resolve_evidence_gate_skip_fallback`. This is explicitly out of scope for the initial landing of feature 020. | Manual review at promotion time; not enforced by CI in the current landing. |

---

## Warn-and-proceed invariants (FR-013 / R-020.12)

| # | Invariant | Enforcement |
|---|---|---|
| MI-22 | When `resolve_evidence_gate_skip_fallback(...)` returns `True` AND the active profile is not `ppstructurev3@gpu`, exactly ONE stderr line is emitted containing the literal substring `--evidence-gate-skip-fallback ignored:`. | `test_cpu_warn_and_proceed_evidence_gate.py` runs the CLI with the flag on `ppstructurev3@cpu` and asserts `grep -F` matches exactly once. |
| MI-23 | The warn-and-proceed path does NOT change the run's exit code. The same fixture, same other flags, with vs. without `--evidence-gate-skip-fallback` on a CPU profile MUST produce identical exit codes. | Same test as MI-22 asserts equal exit codes. |
| MI-24 | The warn does NOT fire when the active profile IS `ppstructurev3@gpu` even if `preprocess_strategy_id` is NOT `ocr-only-v1`. The flag is honored as a no-op in that case (no candidate to suppress); no spurious warn. | Unit test `test_evidence_gate_optin_unit.py` covers `(profile="ppstructurev3@gpu", strategy="ppstructurev3", opt_in=True)` and asserts `evidence_gate_skip_fallback_warn_message` is NOT invoked. |

---

## Closed-vocabulary invariants (FR-001 / FR-005 / R-020.2)

| # | Invariant | Enforcement |
|---|---|---|
| MI-25 | `EVIDENCE_GATES` MUST contain exactly the keys defined at landing (`"v1"` only). Mutating the registry at runtime is a developer error. | Type signature `EVIDENCE_GATES: Final[dict[str, EvidenceGate]]` plus a unit test that asserts `dict(EVIDENCE_GATES) == {"v1": ...}` at module load. |
| MI-26 | `EvidenceGate.decide` MUST return one of `{"sufficient", "borderline", "insufficient"}` and nothing else (no fourth state, no `None`, no string outside the closed vocabulary). | The return type annotation is `Literal["sufficient", "borderline", "insufficient"]`; mypy / pyright enforces. Runtime tests cover the boundary at all three thresholds and reject any non-literal return via a parameterized table. |
| MI-27 | Adding a future signal or a new state requires a code change plus a new closed-vocabulary entry; runtime parameter knobs are forbidden. | Manual review at preset-amendment time; `FiveSignalSet` is a frozen dataclass with five named fields. Adding a sixth signal is a typed dataclass change. |
