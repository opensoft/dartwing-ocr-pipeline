# Scope Checklist: Deterministic Vendor-Identity Signals And Early Accept Gate

**Purpose**: Release-gate validation that the spec draws clean boundaries
around what this feature touches and what it does NOT touch — schema
preservation, downstream-pipeline isolation, runtime-boundary preservation,
deferred-scope discipline, and explicit exclusions for ML-derived signals,
routing modification, cloud paths, and non-vendor-identity extraction.
Every item validates the **requirements**, not the implementation.
**Created**: 2026-05-16
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + scope/architecture reviewer)

## In-Scope: What This Feature SHIPS

- [x] CHK001 Is "five FR-001 signals (vendor-name-candidate, header-band token-density, OCR-detection aggregate-confidence, business-suffix-presence, tax-id-shaped-token-presence)" pinned at landing as the closed signal set, with no implicit "and possibly more"? [Clarity, Spec §FR-001 §Clarifications Q2]
- [x] CHK002 Is the v1 decision table pinned as the SOLE gate-rule body at landing (closed-vocabulary preset registry of size one) with no hidden alternate paths? [Clarity, R-020.2 / evidence-gate-rule.md]
- [x] CHK003 Is the FR-007 shape pinned as shape (b) skip-fallback at landing, with shape (a) observability-only and shape (c) routing-input explicitly named as REJECTED at `/speckit.clarify`? [Clarity, Spec §Clarifications Q1 §Assumptions §FR-007]
- [x] CHK004 Is the opt-in mechanism pinned as `--evidence-gate-skip-fallback` + `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK`, with no value-bearing preset selection axis at landing? [Clarity, R-020.1 / R-020.2 / cli-contract.md]
- [x] CHK005 Is the operator-visible surface pinned to four additive `run_summary` fields, with shape (b) per-document-stdout-line and shape (c) sidecar-JSON-artifact explicitly named as REJECTED at `/speckit.clarify`? [Clarity, Spec §Clarifications Q3 / run-summary-schema.md §Forbidden]
- [x] CHK006 Is the coordinate scope pinned to "page-1 header band only" with the y-fraction default `0.25` named, and the alternatives (page-1 header+footer, page-1 whole, hybrid per signal) explicitly named as REJECTED at `/speckit.clarify`? [Clarity, Spec §Clarifications Q4]

## Out-of-Scope: Deferred Items With Explicit Tracking

- [x] CHK007 Are telephone-shaped, email-shaped, and postal-address-shaped tokens explicitly named as deferred to a follow-on feature (and NOT computed by this feature)? [Clarity, Spec §Clarifications Q2 §Assumptions §US1]
- [x] CHK008 Is "promotion of a CPU-side default change" named as out-of-scope so the gate's CPU emission stays observability-only? [Clarity, Spec §Out of Scope]
- [x] CHK009 Is "adding a new persisted artifact" named as out-of-scope, with the escape-hatch condition (`/speckit.plan` finding the existing surface insufficient) explicitly NOT met? [Clarity, Spec §FR-021 §Out of Scope]
- [x] CHK010 Is "regenerating committed corpus baselines" named as out-of-scope, with the established dataset/baseline flow named as the only acceptable path? [Clarity, Spec §FR-019 §Out of Scope]
- [x] CHK011 Is "adding a learned or ML-derived signal" named as out-of-scope, with the boundary "every signal MUST be a deterministic function over `preprocess_output.json` text/token/geometry/confidence content" stated as a permanent closure? [Clarity, Spec §FR-027 §Out of Scope]
- [x] CHK012 Is "replacing feature 019's OCR-only fallback trigger with the gate decision" named as out-of-scope so the FR-005 trigger is preserved? [Clarity, Spec §FR-007 §Out of Scope]

## Out-of-Scope: Hard Exclusions That Affect Downstream Stages

- [x] CHK013 Is "schema or `schema_version` changes to the four canonical stage 1 artifacts" named as out-of-scope with no escape hatch? [Clarity, Spec §FR-020 §Out of Scope]
- [x] CHK014 Is "replacing deterministic routing or consensus with model judgment" named as out-of-scope, with feature 008's rules called out as unmodified? [Clarity, Spec §FR-028 §Out of Scope]
- [x] CHK015 Is "cloud / remote routing changes" named as out-of-scope (no new escalation surface, no new remote model call, no new external API)? [Clarity, Spec §Out of Scope]
- [x] CHK016 Is "non-vendor-identity extraction scope" named as out-of-scope (line items, totals, dates, all other stage 2+ surfaces are not touched)? [Clarity, Spec §Out of Scope]
- [x] CHK017 Is the rule "the gate is operator-consumed, NOT a new routing input" stated so FR-028 is auditable as a structural separation, not as a current restraint? [Clarity, Spec §FR-028 / Plan §Constitution Check row "Stage 1 Scope Constraints"]

## Pipeline-vs-Harness Boundary (Constitution I)

- [x] CHK018 Is the rule "this feature touches preprocessing + pipeline runtime only" stated so the harness (`tests/stage1_vendor_identity/`, evaluator, scoring) is auditable as untouched? [Clarity, Plan §Constitution Check row I]
- [x] CHK019 Is the model runtime (host Ollama, Jetson-local Ollama) explicitly named as unchanged by this feature? [Clarity, Plan §Constitution Check row I]
- [x] CHK020 Is the new module set (`preprocessing/evidence_gate.py`, `preprocessing/evidence_gate_optin.py`) named as scoped to the preprocessing layer, with no cross-boundary collapse into the harness or model runtime? [Completeness, Plan §Constitution Check row I / Plan §Source Code]

## Runtime-Boundary Preservation (CPU vs. GPU vs. Stub)

- [x] CHK021 Is the rule "signal-set + gate-decision computation runs on CPU profiles, stub-adapter runs, AND the GPU lane uniformly" stated explicitly, so the gate is auditable as profile-independent? [Clarity, Spec §FR-014 §US5 / Plan §Summary]
- [x] CHK022 Is the rule "any FR-007 behavioral-shape switch is GPU-only by design" stated, so the asymmetry between gate computation (profile-uniform) and gate behavior (GPU-only) is explicit? [Clarity, Spec §FR-012 §US5 / Plan §Summary]
- [x] CHK023 Is the production CI scope (CPU + stub only; GPU verification is workstation-only) called out so a reviewer knows where GPU coverage lives and where it does not? [Clarity, Plan §Technical Context]
- [x] CHK024 Is the rule "default `ppstructurev3@cpu` profile remains the default preprocessing profile after this feature" stated as a hard closure on default behavior? [Clarity, Spec §FR-012]

## Schema and Artifact Boundary

- [x] CHK025 Is the rule "the `run_summary` line is run-level observability metadata, NOT a stage 1 output contract" stated so the additive bump 0.1.6 → 0.1.7 is auditable as not affecting downstream contracts? [Clarity, Plan §Constitution Check row II]
- [x] CHK026 Is the rule "signal-set and gate-decision data MUST live exclusively on the operator-facing `run_summary` line; nothing inside any canonical artifact" stated unambiguously? [Clarity, Spec §FR-021 §US6 §Edge Cases]
- [x] CHK027 Is the four-artifact list (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`) named explicitly when stating the no-modification rule, not abbreviated to "the artifacts"? [Completeness, Spec §FR-020]

## Cross-Feature Adjacency Boundary

- [x] CHK028 Is the rule "feature 008's deterministic routing surface is unchanged by this feature" stated so the routing inputs / computation / `routing_decision.json` shape are auditable as preserved? [Clarity, Spec §FR-028]
- [x] CHK029 Is the rule "feature 019's FR-005 OCR-only fallback trigger is preserved unchanged" stated so the only interaction is the opt-in suppression on `sufficient` candidates? [Clarity, Spec §FR-007 §Out of Scope]
- [x] CHK030 Is the rule "feature 018's `region_strategy_fallback_count` and feature 019's `ocr_only_fallback_count` are independent and additive with respect to the gate" stated explicitly? [Clarity, Spec §FR-023 §Edge Cases]
- [x] CHK031 Is the rule "all feature 014/015/016/017/018/019 guarantees continue to hold" stated with each carry-forward guarantee enumerated rather than collapsed into "all guarantees"? [Completeness, Spec §FR-022 §SC-009]

## Module-Touch Boundary (Plan-Level Scope)

- [x] CHK032 Is the "two new modules" boundary pinned (`preprocessing/evidence_gate.py`, `preprocessing/evidence_gate_optin.py`) with no implicit "and possibly more"? [Clarity, Plan §Project Structure §Structure Decision]
- [x] CHK033 Is the "seven touched modules" boundary pinned (`preprocessing/pipeline.py`, `preprocessing/cli.py`, `preprocessing/identifiers.py`, `pipeline/timing.py`, `pipeline/corpus_run.py`, `pipeline/runner.py`, `pipeline/cli.py`) with each module's edit type (CHANGED additive vs. CHANGED medium vs. CHANGED small) called out? [Completeness, Plan §Source Code §Structure Decision]
- [x] CHK034 Is the list of UNCHANGED preprocessing modules (`artifact.py`, `document_text.py`, `errors.py`, `ingestion_sources.py`, `ocr.py`, `ocr_only.py`, `preflight.py`, `preflight_cli.py`, `preprocess_strategies.py`, `preprocess_strategy_optin.py`, `preset_optin.py`, `presets.py`, `quality.py`, `raster_profile_optin.py`, `raster_profiles.py`, `rasterize.py`, `region_strategies.py`, `region_strategy_optin.py`, `version.py`, `warmup.py`, `warmup_optin.py`, `warnings.py`) named so the unchanged surface is auditable? [Completeness, Plan §Source Code]
- [x] CHK035 Is the list of UNCHANGED pipeline modules (`corpus.py`, `exit_codes.py`, `failure_policy.py`, `ollama_lanes.py`, `path_resolution.py`, `pdf_check.py`, `profiles.py`, `slice_control.py`, `stages.py`) named, with `exit_codes.py` specifically called out as untouched because no new exit code is introduced? [Completeness, Plan §Source Code §Structure Decision]
- [x] CHK036 Is the "zero new exception classes" boundary stated explicitly, so no `EvidenceGateError` or similar gets added under the radar? [Clarity, Plan §Technical Context §Structure Decision]
- [x] CHK037 Is the "zero new exit codes" boundary stated explicitly, with the reason (no `--evidence-gate <id>` flag at landing because registry has size one) documented? [Clarity, Plan §Technical Context §Structure Decision / cli-contract.md §Exit codes]
- [x] CHK038 Is the "no new top-level subpackage" boundary stated, with the rationale (the evidence-gate axis fits under `preprocessing/`) called out? [Clarity, Plan §Structure Decision]

## Documentation Scope

- [x] CHK039 Is "this feature does NOT add a new operator-facing docs page" stated explicitly, with the FR-015 benchmark numbers landing in this feature's `quickstart.md` Appendix A and the FR-016 quality-gate evidence landing in `research.md` Appendix B? [Clarity, Plan §Documentation / Constitution Check row Quality Gates 1–7]
- [x] CHK040 Is the rule "Markdown benchmark/quality-gate evidence lives under `specs/020-vendor-evidence-gate/`, NOT under `contracts/` and NOT under `tests/stage1_vendor_identity/`" stated so the scope of the appendices is bounded? [Clarity, Plan §Storage]

## Cross-Reference Discipline

- [x] CHK041 Are all FR references resolved (no `[NEEDS CLARIFICATION]` markers remain on any FR-### that this feature ships)? [Completeness, Spec §Clarifications]
- [x] CHK042 Are all four `/speckit.clarify` resolutions traceable to specific FR-### items in the spec (Q1→FR-007; Q2→FR-001; Q3→FR-003/FR-006; Q4→FR-001 coordinate scope)? [Traceability, Spec §Clarifications]

## Promotion-Scope Boundary

- [x] CHK043 Is "promoting the skip-fallback default to ON" named as out-of-scope at landing, with the FR-016 quality-gate evaluation as a hard prerequisite? [Clarity, Spec §US7 §FR-012 §FR-016 / R-020.14]
- [x] CHK044 Is the rule "GPU verification of FR-015/FR-016 MAY be deferred per FR-026 without blocking CPU-safe merge" stated as a permissive scope, not as a default? [Clarity, Spec §FR-026 / R-020.15]
- [x] CHK045 Is "the candidate evaluation for promotion does NOT change the default at landing" stated so US7 is auditable as an evaluation slice and NOT a default flip? [Clarity, Spec §US7]

## Verifiability of Scope Claims

- [x] CHK046 For every out-of-scope item, is the verification mechanism named (e.g., `git diff main -- contracts/stage1_vendor_identity/` for SC-010, presence/absence of specific file paths for FR-021, source-grep for `UnknownPresetError` extension)? [Measurability, Spec §SC-006 §SC-010 §FR-021]
- [x] CHK047 Does the spec define what a reviewer should check at PR time to confirm the harness was not touched (e.g., diff scope, file ownership)? [Measurability, Plan §Constitution Check row I]

## Notes

- Check items off as completed: `[x]`
- Add comments or findings inline; reference the spec/plan/research/data-model/contract line when raising a defect
- This checklist tests **requirements quality**, not implementation correctness
