# Feature Specification: Freeze Schemas & Folder Contracts

**Feature Branch**: `001-freeze-schemas-folder-contracts`
**Created**: 2026-04-12
**Status**: Draft
**Input**: User description: "read all the files in the docs folder. understand the architecture and the implementation-plan. then we will work off the implementation plan. our first task is freeze schemas and folder contracts. generate the spec for this."

## Context

The stage 1 vendor-identity pipeline and its evaluation harness will be built as a set of cooperating components: preprocessing, evidence assembly, edge-model extraction, deterministic routing, final payload assembly, per-document evaluation, and run-level reporting. Those components pass information to each other exclusively through JSON artifacts persisted in per-document folders. Until those JSON shapes and the folder they live in are frozen, every downstream component is building against a moving target — and hand-labeled truth cannot be collected reliably.

This feature is the first item on the stage 1 implementation-plan critical path: **freeze the artifact schemas and the per-document folder layout, and provide a way for any component to machine-validate an artifact against the frozen contract.** No extraction, routing, or evaluation behavior is delivered by this slice. The deliverable is stable, validatable contracts that everything else in stage 1 can be built against.

## Clarifications

### Session 2026-04-12

- Q: Where does the frozen, authoritative contract set live, and in what form? → A: The contract set lives in two co-versioned layers inside this repo. (1) Human-facing canonical documentation: `docs/stage1-vendor-identity/schemas.md`, `docs/stage1-vendor-identity/dataset-layout.md`, `docs/stage1-vendor-identity/scoring.md`, `docs/stage1-vendor-identity/architecture.md`, and `.specify/memory/constitution.md`. (2) A co-located machine-readable contract layer (e.g., `contracts/`) with one schema per artifact plus the folder contract and contract-set version metadata. The docs are canonical for meaning and shape; the machine-readable layer is the executable representation used by validators and code. Both layers are updated together through the amendment path, versioned as one contract set, and kept in lockstep.
- Q: What scheme does the contract-set version use, and is it stamped onto every persisted artifact? → A: Semver (`MAJOR.MINOR.PATCH`), starting at `1.0.0`. Every persisted artifact carries a dedicated `contract_set_version` field, distinct from `pipeline_version` and `policy_version`. `contract_set_version` describes the schema/folder/evaluation contract set; `pipeline_version` describes the pipeline build/release; `policy_version` describes the routing/consensus policy. The `contract_set_version` field applies to all seven persisted artifacts: `preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`, `expected.json`, `evaluation_document.json`, `evaluation_run_summary.json`. Rationale: contract shape, pipeline implementation, and routing policy evolve independently, so validators and historical-result interpretation need them tracked separately.
- Q: What form does the validator's output take when an artifact or folder fails validation? → A: Both a canonical machine-readable structured report and a human-readable CLI rendering of that same report, plus a process exit code for pass/fail. The structured report is the single source of truth for tooling (harness aggregation across the 20-document corpus, CI, regression gates); the CLI renders a human view of it for developers and labelers. Minimum structured fields per violation: `target` (artifact name or folder), `field_path`, `violation_code`, `reason` (human-readable), and `expected` (rule or contract name) where relevant. Rationale: the harness needs to aggregate failures across documents without scraping text; labelers still need readable output without learning a report schema.
- Q: Is the challenge-tag vocabulary frozen or extensible? → A: Frozen closed set at contract-set version `1.0.0`. The authoritative list is the vocabulary in `docs/stage1-vendor-identity/dataset-layout.md`. The validator rejects any `challenge_tags` value not on the list. New tags require the amendment path and a contract-set version bump. Rationale: run summaries and bucketed comparisons stay stable; labelers can work in parallel without inventing incompatible categories; later additions still have a clean governed path.
- Q: Is `notes.md` a hard requirement, a soft requirement, or conditional? → A: Conditional on difficulty. Hard requirement (folder validator fails) for `hard` and `missing_name` documents; soft requirement (warning only, folder passes) for `easy` and `medium` documents. Rationale: hard and missing-name documents carry the traps reviewers and investigators most need explained (remit-to mismatches, inferred-name reasoning, dense headers, portal cover pages); easy/medium documents are largely self-explanatory and their `challenge_tags` already carry the signal, so requiring `notes.md` there would slow parallel labeling without adding information.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pipeline Developer Codes Against a Frozen Artifact Shape (Priority: P1)

A pipeline developer is about to implement one of the stage 1 components (preprocessing, extraction, routing, or final payload assembly). They need a single authoritative definition of the artifact that component produces, so that the shape of the output is decided before code is written and does not drift as other components come online.

**Why this priority**: Every stage 1 pipeline component reads or writes one of the four core artifacts. Without a frozen shape, components cannot be implemented in parallel, integration breaks silently, and rework dominates the schedule. This is the single largest unblocker on the stage 1 critical path.

**Independent Test**: A developer can, without writing any pipeline code, pick any one of the core artifacts (for example `edge_extraction_output`), read the frozen contract, produce a hand-written sample JSON file that satisfies it, run the validator, and see the file accepted. A developer can also introduce a deliberate deviation (missing required field, wrong type, empty string instead of `null`) and see the validator reject it with a clear error.

**Acceptance Scenarios**:

1. **Given** a developer needs to know the shape of `preprocess_output`, **When** they consult the frozen contract, **Then** they find every required field, its type, its nullability, and the meaning of each section, including `ingestion_sources` flags for the three Trijunction contributors.
2. **Given** a developer has produced a sample `edge_extraction_output` document, **When** they run it through the validator, **Then** they receive either a pass result or a list of specific violations (missing fields, wrong types, disallowed empty strings).
3. **Given** a developer is preparing for multi-voter extraction, **When** they inspect `edge_extraction_output`, **Then** the contract already carries voter-identity metadata and per-field evidence references so a later ensemble can be added without breaking the shape.
4. **Given** a developer is writing routing code, **When** they write a `routing_decision` artifact, **Then** the contract enforces that `decision` is drawn from the stage 1 allowed set and that `review_status.manual_review_required` and `review_status.review_reason` are both present.
5. **Given** a developer writes a `final_structured_payload`, **When** they validate it, **Then** the contract rejects payloads that report `company_name.present = false` without `company_name.inferred = true` and `review_status.manual_review_required = true`.

---

### User Story 2 - Human Labeler Produces Truth Against a Frozen Folder Layout (Priority: P1)

A human labeler is hand-labeling one of the 20 stage 1 test invoices. They need to know exactly which folder to create, which files belong in that folder, what `expected.json` must contain, and what "missing company name" means at the field level. They must be able to complete labeling without reading any pipeline code.

**Why this priority**: Label quality is explicitly called out as the biggest evaluation risk. Labeling can proceed in parallel with pipeline development, but only if the labeler has a frozen folder layout and a frozen `expected.json` shape. Without this, labels collected now will have to be redone.

**Independent Test**: A labeler can create a new folder `tests/stage1_vendor_identity/inv_001_easy/`, drop a PDF in as `source.pdf`, write an `expected.json` using only the documented contract, author `notes.md`, and validate the folder against the layout rules — all without any pipeline component being built.

**Acceptance Scenarios**:

1. **Given** the stage 1 corpus root exists, **When** a labeler creates a new per-document folder, **Then** the required file set (`source.pdf`, `expected.json`, `notes.md`) and the reserved names for generated artifacts (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`, `evaluation_document.json`) are documented in one place.
2. **Given** a labeler writes an `expected.json`, **When** they run it through the validator, **Then** it is accepted if and only if `document_id`, `difficulty`, `challenge_tags`, `expected_review`, and `expected_vendor_candidate` are all present with valid values.
3. **Given** the document is a missing-name case, **When** the labeler writes `expected.json`, **Then** the contract requires `expected_vendor_candidate.company_name.present = false`, `expected_vendor_candidate.company_name.inferred = true`, `expected_review.manual_review_required = true`, and `expected_review.review_reason = "company_name_inferred"`.
4. **Given** a labeler is choosing challenge tags, **When** they consult the contract, **Then** they find the allowed tag vocabulary (including `explicit_company_name`, `missing_company_name`, `logo_only`, `remit_to_differs_from_vendor`, `low_quality_scan`, and the remaining documented tags).
5. **Given** a labeler writes confidence values or predicted fields into `expected.json`, **When** they validate, **Then** the contract rejects the file because `expected.json` must contain only truth, not predictions, confidence, or evaluation outcomes.

---

### User Story 3 - Evaluator Compares Outputs to Truth Against Frozen Evaluation Contracts (Priority: P1)

An evaluator developer is implementing per-document and per-run evaluation. They need a frozen shape for `evaluation_document.json` and `evaluation_run_summary.json` so the evaluator can write those files, and so humans and downstream tooling can read them, without either side reverse-engineering the other's expectations.

**Why this priority**: Evaluation is the end of the stage 1 loop. If `evaluation_document.json` or `evaluation_run_summary.json` change shape after they are in use, every stored historical result becomes incomparable. Freezing these two contracts alongside the pipeline artifacts keeps quality comparisons honest across iterations.

**Independent Test**: An evaluator developer can, before any real evaluator code exists, hand-write a pass/fail `evaluation_document.json` for one document and a `evaluation_run_summary.json` for a fake 20-document run, validate both, and confirm the shapes line up with the fields listed in the scoring rubric.

**Acceptance Scenarios**:

1. **Given** a developer writes an `evaluation_document.json`, **When** they validate it, **Then** it must include a per-field result map using the fixed result vocabulary (`match`, `partial_match`, `mismatch`, `missing_prediction`, `unexpected_prediction`, `not_applicable`) and the three document-level pass gates (`vendor_identity_passed`, `review_routing_passed`, `overall_passed`).
2. **Given** a developer writes an `evaluation_run_summary.json`, **When** they validate it, **Then** the contract requires overall metrics (`field_accuracy`, `vendor_identity_pass_rate`, `review_routing_pass_rate`, `overall_document_pass_rate`), per-difficulty breakdowns, per-field breakdowns, and consensus metrics placeholders even when only a single-voter baseline has been run.
3. **Given** an evaluator run was performed in single-voter mode, **When** the summary is validated, **Then** the consensus metrics section accepts `single_voter_baseline_runs` with zero majority or split documents without failing validation.

---

### User Story 4 - Contributor Changes a Contract Through a Governed Path (Priority: P2)

A contributor needs to add, remove, or change a field in one of the frozen artifacts (for example, adding a new tax-ID type or a new routing decision value). They need an unambiguous process that updates the contract, the validator, and any downstream rules in lockstep and records the change.

**Why this priority**: The contracts are going to change. Without a governance path, contract drift happens silently through hand-edits and the "frozen" state stops being real. This is P2 because it only matters once contracts are actually in use — a small window after P1 is delivered.

**Independent Test**: A contributor can take a proposed contract change, follow the documented amendment path, and produce a version-stamped new contract plus a note describing the change. An unchanged validator run against a pre-change artifact should still pass; a new validator run against a post-change artifact should pass only if it satisfies the new rules.

**Acceptance Scenarios**:

1. **Given** a contributor proposes adding a new field to `edge_extraction_output`, **When** they complete the documented amendment steps, **Then** the contract's version identifier is incremented, the change is described in the repo, and the validator enforces the new shape.
2. **Given** the routing decision vocabulary changes, **When** the contract is amended, **Then** previously valid artifacts continue to validate under the prior version if the prior version is retained, and the harness clearly identifies which version an artifact was written against.

---

### Edge Cases

- A pipeline component writes an artifact with `"value": ""` for an absent field instead of `"value": null`. The validator must reject this, because the contract requires `null` for missing fields.
- A pipeline run produces a `final_structured_payload` claiming an explicit company name but `routing_decision` claims `manual_review_required = true` for reason `company_name_inferred`. The cross-artifact contract must flag this as inconsistent.
- A labeler invents a new `challenge_tag` not on the closed vocabulary listed in `dataset-layout.md` at contract-set version `1.0.0`. The validator must reject this with a pointer to the allowed vocabulary and a hint that new tags require the amendment path.
- A `final_structured_payload` is produced on a document where no explicit company name was found. The contract requires `company_name.present = false`, `company_name.inferred = true`, and `review_status.manual_review_required = true`; any other combination must fail validation.
- An `expected.json` includes a `confidence` value or a `predicted` block. The validator must reject it, because truth files are not allowed to carry predictions or confidence.
- A per-document folder is missing either `source.pdf` or `expected.json`. The folder-layout validator must report it as incomplete. A folder missing `notes.md` must fail validation when `difficulty` is `hard` or `missing_name`, and must emit a warning (but pass) when `difficulty` is `easy` or `medium`.
- A `tax_ids` block contains a tax ID type that is not one of the four documented types (`ein`, `state_tax_id`, `vat_id`, `other_tax_id`). The validator must reject the artifact.
- An `edge_extraction_output` omits the `vote_metadata` block. Even in single-voter mode, the contract requires `vote_metadata` with `consensus_mode = "single_voter_baseline"` so ensemble mode can be added later without a breaking change.
- An `evaluation_run_summary.json` reports a `document_count` that does not match the length of the per-document results list. The validator must flag this.

## Requirements *(mandatory)*

### Functional Requirements

**Artifact contracts — general**

- **FR-001**: The system MUST provide a frozen, authoritative contract for each of the following seven artifacts: `preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`, `expected`, `evaluation_document`, `evaluation_run_summary`.
- **FR-002**: Each artifact contract MUST define, for every field, its name, type, nullability, allowed-value set where applicable, and whether the field is required, optional, or conditionally required.
- **FR-003**: The system MUST represent absent values as `null` and MUST NOT permit empty strings as substitutes for missing values in any artifact that carries extracted values.
- **FR-004**: Every persisted artifact MUST carry a `document_id`, and every pipeline-produced artifact MUST carry a `pipeline_version` identifier describing the pipeline build/release.
- **FR-005**: Every routing-layer artifact MUST additionally carry a `policy_version` identifier describing the routing/consensus policy, so routing-rule changes can be traced independently from pipeline changes.
- **FR-005a**: Every persisted artifact in the contract set (all seven: `preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`, `expected`, `evaluation_document`, `evaluation_run_summary`) MUST carry a dedicated `contract_set_version` field, distinct from `pipeline_version` and `policy_version`, identifying the contract-set version the artifact was written against.

**`preprocess_output` contract**

- **FR-006**: The `preprocess_output` contract MUST define page-level structure including page number, dimensions, detected rotation, blocks, raw OCR lines, consolidated document text, tables (allowed to be empty), quality indicators, and `ingestion_sources` status flags for `paddleocr_vl`, `falcon_ocr`, and `falcon_perception`.
- **FR-007**: The `preprocess_output` contract MUST allow `falcon_ocr` and `falcon_perception` to be marked `not_implemented` without invalidating the artifact, so stage 1 can ship with Paddle only.
- **FR-008**: Every block and every raw OCR line MUST carry a stable identifier usable as an evidence reference from later artifacts.

**`edge_extraction_output` contract**

- **FR-009**: The `edge_extraction_output` contract MUST represent each extracted vendor-identity field as an object containing `value`, `confidence`, and `evidence` (a list of preprocess-level evidence identifiers), plus `present` and `inferred` flags for `company_name`.
- **FR-010**: The `edge_extraction_output` contract MUST include `model_runtime` metadata (provider, model name, version, runtime path) and `vote_metadata` (voter identifier, voter role, consensus mode) on every artifact, even when only one voter runs.
- **FR-011**: The `edge_extraction_output` contract MUST decompose postal address into `street_1`, `street_2`, `city`, `state`, `postal_code`, `country`.
- **FR-012**: The `edge_extraction_output` contract MUST type tax IDs as `ein`, `state_tax_id`, `vat_id`, `other_tax_id` and MUST NOT allow free-form tax-ID types.
- **FR-013**: The `edge_extraction_output` contract MUST include invoice header fields (`invoice_number`, `invoice_date`, `total_amount` with currency) even though stage 1 is not evaluated on them.

**`routing_decision` contract**

- **FR-014**: The `routing_decision` contract MUST constrain `decision` to the stage 1 vocabulary `edge_accept` or `edge_review_required`, and MUST keep the door open for later ensemble decisions without requiring a breaking change.
- **FR-015**: The `routing_decision` contract MUST carry a `consensus_summary` block, even in single-voter mode, with a `mode` of `single_voter_baseline` and an `agreement_level` of `not_applicable`.
- **FR-016**: The `routing_decision` contract MUST include deterministic `scores` (company, address, tax ID, contact, overall vendor identity) and a `checks` block covering the stage 1 deterministic gates.
- **FR-017**: The `routing_decision` contract MUST include `review_status` with both `manual_review_required` (boolean) and `review_reason` (nullable string), and MUST require `review_reason` to be non-null whenever `manual_review_required` is true.

**`final_structured_payload` contract**

- **FR-018**: The `final_structured_payload` contract MUST present vendor-identity fields as flattened `value` + `confidence` pairs (no evidence references), preserve `company_name.present` and `company_name.inferred`, carry a top-level `review_status`, a `quality_summary`, and a `trace` block pointing at the other three pipeline artifacts.
- **FR-019**: The `final_structured_payload` contract MUST reject any payload where `company_name.present = false` and either `company_name.inferred = false` or `review_status.manual_review_required = false`.

**`expected` contract**

- **FR-020**: The `expected` contract MUST require `document_id`, `difficulty`, `challenge_tags`, `expected_review`, and `expected_vendor_candidate`, and MUST permit an optional `notes` field.
- **FR-021**: The `expected` contract MUST constrain `difficulty` to `easy`, `medium`, `hard`, or `missing_name`.
- **FR-022**: The `expected` contract MUST constrain `challenge_tags` to the closed vocabulary listed in `docs/stage1-vendor-identity/dataset-layout.md` at contract-set version `1.0.0`. The validator MUST reject any tag value not on that list. New tags are introduced only through the amendment path with a contract-set version bump.
- **FR-023**: The `expected` contract MUST forbid predicted values, confidence numbers, evaluation outcomes, and any pipeline-generated metadata.
- **FR-024**: When `difficulty` is `missing_name`, the `expected` contract MUST require `expected_vendor_candidate.company_name.present = false`, `expected_vendor_candidate.company_name.inferred = true`, `expected_review.manual_review_required = true`, and `expected_review.review_reason = "company_name_inferred"`.

**Evaluation contracts**

- **FR-025**: The `evaluation_document` contract MUST include a comparison summary, a per-field result map keyed by dotted field path, and document-level pass gates (`vendor_identity_passed`, `review_routing_passed`, `overall_passed`).
- **FR-026**: The per-field result map MUST use only the result vocabulary `match`, `partial_match`, `mismatch`, `missing_prediction`, `unexpected_prediction`, `not_applicable`.
- **FR-027**: The `evaluation_run_summary` contract MUST include overall metrics (`field_accuracy`, `vendor_identity_pass_rate`, `review_routing_pass_rate`, `overall_document_pass_rate`), per-difficulty breakdowns for `easy`, `medium`, `hard`, and `missing_name`, per-field breakdowns at minimum for the fields listed in the stage 1 scoring rubric, and a consensus-metrics block that accepts single-voter-baseline runs.

**Folder contract**

- **FR-028**: The system MUST define a single authoritative corpus root path (`tests/stage1_vendor_identity/`) and MUST define the per-document folder naming convention (`inv_<NNN>_<difficulty>/`).
- **FR-029**: The folder contract MUST list the input files per document and their strictness: `source.pdf` is unconditionally required; `expected.json` is unconditionally required; `notes.md` is conditionally required — a hard requirement (folder validator fails) for documents with `difficulty` of `hard` or `missing_name`, and a soft requirement (folder validator emits a warning but passes) for documents with `difficulty` of `easy` or `medium`. The folder contract MUST also list the reserved filenames for generated artifacts (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`, `evaluation_document.json`).
- **FR-030**: The folder contract MUST reserve (without yet requiring) a `votes/` subfolder and a `consensus_output.json` filename so the future ensemble mode fits into the same layout without a breaking change.
- **FR-031**: The folder contract MUST define a single top-level evaluation file name `evaluation_run_summary.json` and its location at the corpus root.
- **FR-032**: The folder contract MUST treat a document folder as incomplete if any required input file is absent and MUST treat reserved generated filenames as off-limits for anything other than pipeline or evaluator output.

**Validation capability**

- **FR-033**: The system MUST provide a way for any contributor to take an on-disk JSON artifact and check it against its named contract, receiving either a pass or an itemized list of violations.
- **FR-034**: The system MUST provide a way to validate a per-document folder against the folder contract, reporting missing required files and unexpected files using reserved names.
- **FR-035**: The validator MUST enforce cross-artifact consistency rules at least for the company-name provenance triad across `expected`, `edge_extraction_output`, `routing_decision`, and `final_structured_payload`.
- **FR-036**: The validator MUST emit both a canonical machine-readable structured report and a human-readable CLI rendering of that same report, and MUST signal pass/fail via a process exit code. The structured report is authoritative for tooling; the CLI rendering is a view of it.
- **FR-036a**: Each entry in the structured violation report MUST include, at minimum: `target` (artifact name or folder), `field_path`, `violation_code`, `reason` (human-readable), and `expected` (the rule or contract name being violated) where relevant.
- **FR-036b**: The structured report MUST be aggregatable across multiple documents by harness tooling without requiring text parsing; the harness MUST be able to summarize validator failures across the full 20-document corpus from the structured reports alone.

**Governance**

- **FR-037**: The contract set MUST use semver (`MAJOR.MINOR.PATCH`) starting at `1.0.0`. All seven artifact contracts and the folder contract MUST advance together under a single `contract_set_version`, so a stage 1 run can declare one contract-set version and have every artifact validated against it. The validator MUST be able to reject an artifact whose stamped `contract_set_version` is incompatible with the version it is being validated against.
- **FR-038**: The system MUST define a written amendment path that requires updating the human-facing documentation layer, the co-located machine-readable contract layer, and the validator in the same change, and that bumps the contract-set version when the change alters any artifact or folder shape.
- **FR-039**: The contract set MUST live in two co-versioned layers inside this repo: (a) human-facing canonical documentation in `docs/stage1-vendor-identity/schemas.md`, `docs/stage1-vendor-identity/dataset-layout.md`, `docs/stage1-vendor-identity/scoring.md`, `docs/stage1-vendor-identity/architecture.md`, and `.specify/memory/constitution.md`; and (b) a co-located machine-readable contract layer (e.g., `contracts/`) with one schema per artifact plus the folder contract and contract-set version metadata. The documentation layer is canonical for meaning and shape; the machine-readable layer is the executable representation consumed by validators and code. The two layers MUST be updated in lockstep and MUST never contradict each other.

### Key Entities

- **Artifact Contract**: A named, versioned definition of the shape of one of the seven stage 1 JSON artifacts. Each contract specifies field names, types, nullability, allowed values, required-vs-optional status, and conditional requirements (for example, "if `manual_review_required` is true, then `review_reason` must be non-null"). Artifact contracts are consumed by pipeline code, evaluator code, human labelers, and the validator.

- **Folder Contract**: A definition of the corpus root path, the per-document folder naming convention, the required input file set per document, the reserved generated filenames per document, and the corpus-level run summary filename. Consumed by labelers, pipeline runners, and harness tooling.

- **Validator**: A component that takes (a) a JSON artifact and a contract name, or (b) a per-document folder, and returns either a pass (exit code 0) or an itemized list of violations with field-path pointers. Output is emitted in two forms that describe the same underlying result: a canonical machine-readable structured report (consumed by the harness, CI, and regression gates) and a human-readable CLI rendering (consumed by developers and labelers). Also enforces cross-artifact consistency rules where the contracts demand it.

- **Vendor-Identity Field**: A logical field describing one facet of vendor identity (company name, an address part, a typed tax ID, website, phone, or email). Every vendor-identity field appears in at least three artifacts: truth (`expected`), extraction (`edge_extraction_output`), and final payload (`final_structured_payload`). The contract set must keep these representations compatible.

- **Evidence Reference**: A stable identifier produced by preprocessing (for a block or OCR line) and later consumed by extraction artifacts. The contract set must keep these identifiers consistent across `preprocess_output` and `edge_extraction_output`.

- **Challenge Tag**: A flat-vocabulary label applied to a document in `expected.json` to describe the difficulty characteristics of that document (for example `logo_only`, `remit_to_differs_from_vendor`). The tag vocabulary is a closed set, frozen at contract-set version `1.0.0` and sourced from `docs/stage1-vendor-identity/dataset-layout.md`. Additions require the amendment path and a version bump.

- **Contract Set Version**: A semver identifier (`MAJOR.MINOR.PATCH`, starting at `1.0.0`) that covers all seven artifact contracts and the folder contract together, so a stage 1 run is either fully on version X or fully on version X+1. Stamped on every persisted artifact as `contract_set_version`, distinct from `pipeline_version` (pipeline build/release) and `policy_version` (routing/consensus policy). Advanced only through the documented amendment path.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can produce a conforming hand-written sample for any of the seven artifacts in under 30 minutes using only the frozen contract, with zero back-and-forth questions about field meaning or shape.
- **SC-002**: 100% of required fields, allowed-value enumerations, nullability rules, and cross-artifact consistency rules called out in this specification are enforced by the validator — not merely documented.
- **SC-003**: A labeler can initialize a new per-document folder, author `expected.json`, and pass the folder-contract and artifact-contract validators with no iteration beyond fixing their own labeling content.
- **SC-004**: Any violation of the company-name provenance rule (`present = false` without `inferred = true` and `manual_review_required = true`) is rejected by the validator across `expected`, `edge_extraction_output`, `routing_decision`, and `final_structured_payload`.
- **SC-005**: After this feature ships, none of the seven artifact shapes change during the remainder of stage 1 without going through the documented amendment path; any change that does ship is accompanied by a contract-set version bump.
- **SC-006**: Pipeline, harness, and labeling work can proceed in parallel after this feature ships. The critical-path components listed in the implementation plan (`CLI contract`, `PDF preprocessing`, `evidence packet`, `single-voter extraction`, `routing`, `final payload`, `evaluation`) each list this feature as a resolved dependency.
- **SC-007**: A contributor can amend a contract through the documented path end-to-end (propose, update documentation, update validator, bump contract-set version) in under one working day of focused effort, without touching any pipeline or evaluator business logic.
- **SC-008**: Switching from single-voter to three-voter ensemble mode in a future stage does not require changes to `preprocess_output`, `routing_decision` (beyond the decision vocabulary), `final_structured_payload`, `expected`, or the folder layout — this must be demonstrable by forward-compatible example artifacts that validate under the stage 1 contract set.

## Assumptions

- The contract content is anchored by the existing documentation in `docs/stage1-vendor-identity/schemas.md`, `dataset-layout.md`, `scoring.md`, `architecture.md`, and `.specify/memory/constitution.md`. This feature converts that documentation into an authoritative, versioned, machine-validatable contract set; it does not renegotiate the field-level decisions already captured there.
- Stage 1 is PDF-only and vendor-identity-only. The contracts carry invoice header fields but are not required to support line-item extraction. Line-item contracts are out of scope.
- Stage 1 runs in single-voter-baseline mode only. Ensemble-mode fields (`vote_metadata`, `consensus_summary`, `votes/` subfolder, `consensus_output.json`) are present in the contracts so the shape does not have to change when ensemble mode is turned on later, but no ensemble behavior is delivered here.
- The challenge-tag vocabulary is the one listed in `docs/stage1-vendor-identity/dataset-layout.md`. Additional tags will be added through the governance path, not ad hoc.
- The stage 1 test corpus is 20 documents (5 easy, 5 medium, 5 hard, 5 missing name) and the folder contract is sized for that scale. Corpus growth beyond 20 documents is a later concern and does not require a contract change.
- Human labelers work from the documented contract without needing to read pipeline code. Validator error messages therefore have to be readable by non-implementers.
- The contracts are owned by the repo (not an external registry). Versioning is captured in the repo alongside the contract documentation.
