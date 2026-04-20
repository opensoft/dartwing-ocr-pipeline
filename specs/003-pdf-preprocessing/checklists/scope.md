# Scope-Boundary Checklist: PDF Preprocessing (Stage 1)

**Purpose**: Release-gate validation that the spec makes the "out of scope"
surface explicit. This slice is preprocessing only — no business extraction,
no routing, no cloud, no other artifacts, no line-item interpretation. Every
item validates the requirements, not the implementation.
**Created**: 2026-04-20
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + architecture owner)

## Business-Field Exclusions

- [ ] CHK001 Is the exclusion of all vendor-identity fields (`company_name`, `address`, `tax_ids`, `website`, `phone`, `email`) explicit? [Completeness, Spec §FR-021]
- [ ] CHK002 Is the exclusion of invoice-header fields (`invoice_number`, `invoice_date`, `total_amount`) explicit? [Completeness, Spec §FR-021]
- [ ] CHK003 Is the rule "later slices own business extraction" stated, not merely implied? [Clarity, Spec §FR-021]
- [ ] CHK004 Does the spec forbid any schema-prohibited keys (e.g., business vendor fields) from appearing anywhere in the artifact? [Consistency, Spec §FR-020]
- [ ] CHK005 Is the provenance concept (`present`, `inferred`, `manual_review_required`) marked as out-of-scope for this slice? [Clarity, Spec §FR-021]

## Other-Artifact Exclusions

- [ ] CHK006 Is the exclusion of `edge_extraction_output.json` from this slice explicit? [Completeness, Spec §FR-017 §FR-022]
- [ ] CHK007 Is the exclusion of `routing_decision.json` from this slice explicit? [Completeness, Spec §FR-017 §FR-022]
- [ ] CHK008 Is the exclusion of `final_structured_payload.json` from this slice explicit? [Completeness, Spec §FR-017 §FR-022]
- [x] CHK009 Is the exclusion of any evaluation artifacts (`evaluation_document.json`, `evaluation_run_summary.json`) explicit, given the harness is a separate concern? [Resolved — Spec §FR-017: evaluation artifacts belong to the harness, not this slice]
- [x] CHK010 Is the exclusion of any per-voter artifacts under `votes/` stated? [Resolved — Spec §FR-017: `votes/` subfolder explicitly out of scope]

## Model / Runtime Exclusions

- [ ] CHK011 Is the exclusion of any model invocation for voting / consensus / routing specified? [Completeness, Spec §FR-022]
- [ ] CHK012 Is the exclusion of cloud service calls during preprocessing explicit? [Completeness, Spec §FR-023]
- [ ] CHK013 Is the exclusion of cloud escalation paths (deferred to later slices) stated? [Clarity, Spec §FR-023]
- [ ] CHK014 Is the stage-1 scope "edge path only" inherited / restated in this slice's context? [Consistency, Spec §Assumptions]
- [x] CHK015 Does the spec state that host Ollama is NOT used by preprocessing, distinguishing preprocessing from later slices that do use it? [Resolved — Spec §FR-023: preprocessing is model-free; Ollama reserved for later extraction/voting slices]

## Table Structural-Only Boundary

- [ ] CHK016 Is the tables scope stated as "structural capture only" (page reference, bbox, optionally a grid)? [Clarity, Spec §FR-011]
- [ ] CHK017 Is line-item parsing (descriptions, quantities, unit prices, line totals) explicitly excluded? [Completeness, Spec §FR-024]
- [ ] CHK018 Does the spec forbid business-field keys in any `tables[*]` record (e.g., `line_item_description`, `unit_price`)? [Clarity, Spec §US4 AC#3 §FR-024]
- [ ] CHK019 Is the case "PDF with no tables" handled — `tables == []`, no block forced to `block_type == "table"`? [Completeness, Spec §US4 AC#2]

## Debug-Output Boundary

- [ ] CHK020 Is the optionality of per-page image files (`page_{N}.png`) stated? [Clarity, Spec §FR-007]
- [ ] CHK021 Is downstream correctness required to be independent of debug image presence? [Clarity, Spec §FR-007]
- [ ] CHK022 Are debug image files excluded from the contract surface (i.e., the JSON alone is authoritative)? [Consistency, Spec §FR-007]

## Configuration Boundary

- [ ] CHK023 Is the rasterization DPI declared as a project constant, not a per-invocation flag? [Clarity, Spec §FR-004]
- [x] CHK024 Is "no cloud credentials, endpoints, or API keys accepted by this CLI" implied or stated? [Resolved — implied by Spec §FR-023 (no cloud calls) + §FR-025 (no ingestion toggles): no surface exists to accept credentials]
- [x] CHK025 Does the spec address whether any CLI flag may toggle ingestion sources on/off for this slice? [Resolved — Spec §FR-025: no ingestion-toggle flags; enablement is fixed and part of the deterministic pipeline version]

## Input Boundary

- [ ] CHK026 Is the input shape restricted to a single PDF per invocation? [Clarity, Spec §FR-001]
- [x] CHK027 Is the exclusion of batch / corpus-wide invocation from this slice stated? [Resolved — Spec §FR-001: batch invocation out of scope; multi-document runs belong to the harness calling this CLI once per document]
- [ ] CHK028 Is non-PDF input explicitly rejected, not coerced (e.g., PNG/JPG input is not silently accepted)? [Clarity, Spec §FR-001]

## Contract Stewardship Boundary

- [ ] CHK029 Is amendment of `contracts/stage1_vendor_identity/v1.0.0/*` schemas out-of-scope for this slice? [Completeness, Spec §Assumptions §FR-018]
- [ ] CHK030 Is the rule "contract changes follow the AMENDMENTS path, separately" stated? [Clarity, Spec §Assumptions]
- [x] CHK031 Is modifying the validator CLI itself out-of-scope (the validator is consumed, not edited)? [Resolved — Spec §Assumptions: validator is consumed via its module-API contract, never edited by this slice]

## Harness Separation

- [ ] CHK032 Is the rule "this slice does not own the evaluation harness / corpus / expected truth" stated? [Clarity, Spec §Assumptions]
- [ ] CHK033 Is the rule "downstream consumers can begin work on `preprocess_output.json` without asking for contract changes" stated as success criterion? [Measurability, Spec §SC-007]

## Documentation Surface

- [x] CHK034 Does the spec point to the ollama-runtime doc for the distinction between preprocessing (no Ollama) and later slices? [Resolved — Spec §FR-023 + §Assumptions cite `docs/stage1-vendor-identity/ollama-runtime.md`]
- [x] CHK035 Does the spec reconcile "edge path only" (ollama-based) with "no GPU required for preprocessing" so these do not appear to conflict? [Resolved — Spec §FR-023: "edge path only" applies to later-slice model calls; preprocessing is model-free, so no conflict with no-GPU]

## Measurable Scope-Respect

- [ ] CHK036 Is there a measurable success criterion confirming downstream compatibility without contract amendment (SC-007)? [Measurability, Spec §SC-007]
- [ ] CHK037 Is there a measurable success criterion for one-command devcontainer execution without cloud / GPU (SC-008)? [Measurability, Spec §SC-008]

## Notes

- Check items off as completed: `[x]`
- Every `[Gap]` here risks future scope creep — prefer tightening exclusions in the spec rather than arguing them later in review
- If any business-field key ever lands in `preprocess_output.json` during implementation, treat that as a scope violation, not a feature
