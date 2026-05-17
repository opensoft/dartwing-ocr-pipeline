# Contract Checklist: Deterministic Vendor-Identity Signals And Early Accept Gate

**Purpose**: Release-gate validation that the spec pins its contract surface
(run_summary additive bump, four canonical artifact preservation, feature
014–019 surface carry-forward) with the rigor needed for downstream
consumers (evidence-packet assembler, single-voter extractor, router,
final-payload assembler, evaluator). Every item validates the
**requirements**, not the implementation.
**Created**: 2026-05-16
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + contract-set owner)

## Canonical Stage-1 Artifact Preservation

- [x] CHK001 Is the rule "no `schema_version` value, no JSON schema field, no entry in `contracts/stage1_vendor_identity/AMENDMENTS.md` is changed by this feature except for the additive operator-visible surface" stated as a hard requirement, not as guidance? [Clarity, Spec §FR-020 §US6 AC#3 §SC-010]
- [x] CHK002 Is each of the four canonical artifacts (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`) named explicitly as forbidden-to-modify, rather than referenced collectively as "the artifacts"? [Completeness, Spec §FR-020 §US6 AC#3]
- [x] CHK003 Is the rule "signal-set and gate-decision data MUST live exclusively on the operator-facing `run_summary` line" stated unambiguously, not implied? [Clarity, Spec §FR-021 §US6 §Edge Cases]
- [x] CHK004 Is the forbidden-location list complete (no per-document gate sidecar, no new file under `tests/stage1_vendor_identity/`, no contract-set amendment), or is "and equivalents" left to interpretation? [Completeness, Spec §FR-021]
- [x] CHK005 Does the spec define what "the active contract set" means at landing time (current value, source of truth, how a reviewer verifies it has not drifted)? [Clarity, Spec §FR-020 §SC-007 §SC-010]
- [x] CHK006 Is `contract_set_version` named as immutable by this feature, alongside `schema_version` and `pipeline_version`? [Completeness, Spec §FR-020 §SC-010]
- [x] CHK007 Is the rule "`pipeline_version` continues to end in `.gpu0` / `.cpu0` per profile" stated as a carry-forward invariant, not as new behavior? [Clarity, Spec §FR-022 §SC-009]

## RunSummary Codebase-Level Schema Bump

- [x] CHK008 Is the bump direction stated as `0.1.6 → 0.1.7` (patch-level) rather than as a generic "version bump"? [Clarity, Plan / R-020.9]
- [x] CHK009 Is the rationale for choosing a patch bump (additive-only) over a minor bump documented, so a future reader knows why minor was rejected? [Clarity, R-020.9]
- [x] CHK010 Does the spec or plan state that the bump is **codebase-level only** and no JSON Schema file is written? [Clarity, run-summary-schema.md / Constitution II discussion]
- [x] CHK011 Is the rule "`run_summary` is run-level observability, not a stage 1 output contract" stated so QG#2 inapplicability is auditable? [Clarity, Plan / Constitution II row]
- [x] CHK012 Is the precedent from features 014–019 (additive-only pattern across six prior bumps) referenced so the reviewer can trace the pattern? [Completeness, Plan / R-020.9]

## Four Additive `run_summary` Fields — Required Surface

- [x] CHK013 Is each of the four field names (`evidence_gate_id`, `evidence_gate_state_counts`, `evidence_gate_documents`, `evidence_gate_suppressed_fallback_count`) named explicitly in the spec, not described generically as "additive fields"? [Completeness, Spec §FR-003 §FR-006 §FR-007 §FR-010]
- [x] CHK014 Is the JSON type of every new field pinned (string / object / array / integer), not left as "appropriate type"? [Clarity, run-summary-schema.md]
- [x] CHK015 Is the default value of every new field pinned, including `evidence_gate_id="v1"`, the three default-zero counters inside `evidence_gate_state_counts`, the empty array `[]` for `evidence_gate_documents`, and `0` for `evidence_gate_suppressed_fallback_count`? [Completeness, Spec §FR-006 §FR-008 §R-020.10]
- [x] CHK016 Is the rule "`evidence_gate_state_counts` is an object with all three keys present (NOT sparse) even when every counter is zero" stated explicitly? [Clarity, R-020.10 / module-invariants.md MI-17]
- [x] CHK017 Is the per-element shape of `evidence_gate_documents` pinned (`document_id`, `decision`, `signals`) with the nested `signals` object's five field names enumerated? [Completeness, R-020.10 / data-model.md §4]
- [x] CHK018 Is the per-element `decision` value constrained to the closed three-state vocabulary (`sufficient` / `borderline` / `insufficient`) at the field level, not just at the gate-rule level? [Clarity, run-summary-schema.md / data-model.md §4]
- [x] CHK019 Is the deterministic field-emission order documented (four new fields appended AFTER feature 019's `preprocess_strategy_id` and `ocr_only_fallback_count`)? [Completeness, R-020.10 / run-summary-schema.md]

## Always-Emit Invariant

- [x] CHK020 Is the rule "all four fields MUST be emitted on EVERY run of the new binary, including `ppstructurev3@cpu` runs and stub-adapter runs" stated as a hard requirement? [Clarity, Spec §FR-008 §FR-010 §SC-003]
- [x] CHK021 Is "absence of any of these four fields on a run of the new binary is itself a regression signal" stated explicitly, rather than relying on the reader to infer it? [Clarity, Spec §SC-003 §US3 AC#3]
- [x] CHK022 Does the spec define how a stub-adapter run with zero documents emits the four fields (i.e., is the empty-array / default-zero behavior explicit for that path)? [Completeness, R-020.10 / data-model.md §5]
- [x] CHK023 Is the always-emit rule consistent across single-document runs (`runner.py`) and corpus runs (`corpus_run.py`)? [Consistency, Spec §FR-008 §FR-010]

## Aggregate-vs-Per-Document Invariant

- [x] CHK024 Is the rule "`evidence_gate_state_counts[s]` MUST equal the count of `evidence_gate_documents[i].decision == s` for each `s` in the closed vocabulary" stated as a hard invariant, not as an observable property? [Clarity, module-invariants.md MI-18]
- [x] CHK025 Is the per-document ordering invariant for `evidence_gate_documents` pinned (deterministic per `corpus_run.py` iteration, typically alphabetical by `document_id`)? [Completeness, R-020.11 / data-model.md §4]
- [x] CHK026 Is `document_id` semantics (per-document folder name relative to the corpus root) pinned so the FR-016 quality-gate join with the evaluator's `evaluation_run_summary.json` is unambiguous? [Clarity, R-020.11 / Spec §FR-016]
- [x] CHK027 Does the spec state that the `document_id` in `evidence_gate_documents` MUST match the `document_id` used by feature 007's evaluator without translation? [Completeness, R-020.11]

## Feature 014–019 Surface Carry-Forward

- [x] CHK028 Is the carry-forward rule stated as "no existing `run_summary` field, no `phase_timings.*` key, no field inside any canonical artifact, and no field introduced by features 017–019 is renamed, removed, or retyped by this feature"? [Clarity, Spec §FR-011 §FR-022 §SC-009 / MI-19]
- [x] CHK029 Is every prior-feature surface element enumerated by name (feature 017's `module_set_id` / `det_rec_variant_id` / `ppstructure_modules_invoked`; feature 018's `raster_profile_id` / `region_strategy_id` / `region_strategy_fallback_count`; feature 019's `preprocess_strategy_id` / `ocr_only_fallback_count`)? [Completeness, Spec §US3 / Spec §FR-022 / FR-011]
- [x] CHK030 Is each prior-feature invariant (PPStructureV3 constructed exactly once per process, GPU readiness probed at most once per process, single-device-per-process guard, no silent CPU fallback after `ppstructurev3@gpu`, warmup behavior unchanged) named explicitly in FR-022, not collapsed into "all guarantees continue to hold"? [Completeness, Spec §FR-022 §SC-009]
- [x] CHK031 Is the rule "feature 018's region-strategy fallback counter and feature 019's OCR-only fallback counter MUST NOT be altered, suppressed, or shadowed by this gate" stated as a hard requirement? [Clarity, Spec §FR-023 §Edge Cases]
- [x] CHK032 Does the spec define the verification mechanism for surface byte-identity (e.g., a captured pre-feature-020 run_summary fixture)? [Completeness, MI-19 / Plan test list]

## CLI Surface — Flag and Env-Var Contract

- [x] CHK033 Is the flag name `--evidence-gate-skip-fallback` pinned, not described as "a boolean opt-in flag"? [Clarity, R-020.1 / cli-contract.md]
- [x] CHK034 Is the env-var name `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK` pinned and aligned with the feature 016/017/018/019 naming convention? [Consistency, R-020.1]
- [x] CHK035 Is the precedence rule "CLI wins when both are set" stated unambiguously, with empty-string env = unset called out separately? [Clarity, R-020.1 / cli-contract.md]
- [x] CHK036 Is the truthy/falsy vocabulary (`"1"`, `"true"`, `"yes"`, `"on"` vs. `"0"`, `"false"`, `"no"`, `"off"`, `""`, unset) pinned at the contract level, not left to implementation discretion? [Completeness, R-020.1]
- [x] CHK037 Is the rejection behavior for an unrecognized env-var value pinned to the same error path the existing `_PRESET_ENV_VAR` helpers use? [Consistency, R-020.1 / cli-contract.md §Exit codes]
- [x] CHK038 Is the rule "no new exit code is introduced" stated explicitly, so a reviewer doesn't expect a `UnknownPresetError` extension? [Clarity, cli-contract.md §Exit codes / Plan]
- [x] CHK039 Is the rule "no value-bearing `--evidence-gate <id>` flag at landing because the registry has size one" documented so the future-extensibility shape is auditable? [Clarity, R-020.2 / cli-contract.md]
- [x] CHK040 Is the orthogonality contract (this flag does NOT change resolution of `--preprocess-profile` / `--gpu-warmup` / `--module-set` / `--det-rec-variant` / `--raster-profile` / `--region-strategy` / `--preprocess-strategy`) stated explicitly? [Completeness, cli-contract.md §Orthogonality]

## Forbidden Surface Changes (Closed-Form Restrictions)

- [x] CHK041 Is the rule "no gate-related field may be added inside any of the four canonical stage 1 artifacts" stated as a forbidden surface, not as a discouraged practice? [Clarity, Spec §Edge Cases / run-summary-schema.md §Forbidden]
- [x] CHK042 Is the rule "no `phase_timings.evidence_gate` or any nested `phase_timings` key for gate timing" stated so future implementers do not add gate-specific timing? [Clarity, run-summary-schema.md §Forbidden]
- [x] CHK043 Is the rule "per-document gate records MUST NOT be emitted on a separate stdout `kind:` line" stated explicitly, anchoring Clarifications Q3's single-line choice? [Clarity, run-summary-schema.md §Forbidden / Clarifications Q3]
- [x] CHK044 Is the rule "no sidecar JSON artifact for per-document gate data" stated as forbidden by FR-021, not just as out-of-scope? [Clarity, Spec §FR-021]
- [x] CHK045 Is the rule "the gate decision MUST NOT alter the `preprocess_output.json` page index, block index, or coordinate system" stated as a hard requirement, with the feature 018 `pages.length == page_count` invariant explicitly preserved? [Completeness, Spec §Edge Cases]

## Cross-Reference to Prior-Feature Contracts

- [x] CHK046 Is the additive-pattern lineage (014: 0.1.0→0.1.1, 015: 0.1.1→0.1.2, 016: 0.1.2→0.1.3, 017: 0.1.3→0.1.4, 018: 0.1.4→0.1.5, 019: 0.1.5→0.1.6) referenced so the 0.1.6→0.1.7 step is auditable as a continuation? [Traceability, Plan / R-020.9]
- [x] CHK047 Is the QG#2 inapplicability ("Changes that affect output contracts must update `docs/stage1-vendor-identity/schemas.md`") explicitly defended, mirroring features 016/017/018/019? [Completeness, Plan / Constitution II row]
- [x] CHK048 Is feature 008's deterministic routing surface called out as unchanged by this feature (no modification to `routing_decision.json` inputs, computation, or output shape)? [Consistency, Spec §FR-028 §Out of Scope]

## Verifiability of Contract Claims

- [x] CHK049 For every contract claim (no canonical-artifact diff, no `contract_set_version` diff, four new fields always present, prior-feature surface byte-identical), is there a named test or CI check that verifies it before merge? [Measurability, Plan §Testing / MI-16 / MI-19]
- [x] CHK050 Is `git diff main -- contracts/stage1_vendor_identity/` named as the verification mechanism for SC-010, so the check is reproducible by any reviewer? [Measurability, Spec §SC-010]
- [x] CHK051 Does the spec define what a reviewer should grep for to verify each of the four new fields is present (e.g., `jq -e '.evidence_gate_id'` on the `run_summary` line)? [Measurability, cli-contract.md §Verification]

## Notes

- Check items off as completed: `[x]`
- Add comments or findings inline; reference the spec/plan/research/data-model/contract line when raising a defect
- This checklist tests **requirements quality**, not implementation correctness
