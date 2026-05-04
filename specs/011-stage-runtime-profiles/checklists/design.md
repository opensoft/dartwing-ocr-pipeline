# Design-Quality Checklist: Stage Runtime Profiles / Root Master Controller (011)

**Purpose**: Validate the **quality** of the controller plan, CLI contract, runtime-boundary decisions, warm-corpus behavior, and explicit deferrals as design artifacts - before `/speckit.tasks` consumes them. Items here are "unit tests for the requirements writing", not for the eventual implementation.
**Created**: 2026-05-04
**Feature**: [spec.md](../spec.md), [plan.md](../plan.md), [research.md](../research.md), [data-model.md](../data-model.md), [contracts/cli-contract.md](../contracts/cli-contract.md), [quickstart.md](../quickstart.md)
**Scope notes**: This checklist excludes implementation correctness, performance benchmarking, and code-style review. It tests whether the design artifacts are well-written, complete, unambiguous, internally consistent, and ready for task breakdown.

## Controller Plan & Scope

- [ ] CHK001 Are the controller's owned responsibilities and disowned responsibilities each enumerated as discrete bullets that a future reader can match against a candidate task without subjective judgment? [Clarity, Spec Section"Controller Scope And Boundary With The Harness", Plan SectionSummary]
- [ ] CHK002 Is the implementation sequencing in FR-034 ordered without gaps and aligned to the user-story priorities (P1 vs P2 vs P3) so a reader can derive the milestone plan without re-reading the user stories? [Consistency, Spec SectionFR-034, Spec Section"User Scenarios & Testing"]
- [ ] CHK003 Are the four "MUST NOT" non-goals in FR-036 each accompanied by enough context that a reviewer can decide if a future request violates them? [Completeness, Spec SectionFR-036]
- [ ] CHK004 Does the plan name the existing per-stage modules that act as adapter targets (preprocessing/, extract/, router/, assembler/) so a reader can cross-reference without searching the source tree? [Traceability, Plan Section"Project Structure", Research SectionR-014]
- [ ] CHK005 Are the new pipeline submodules (`profiles.py`, `slice_control.py`, `corpus.py`, `timing.py`, `ollama_lanes.py`, `failure_policy.py`) each justified by a specific FR they cover? [Completeness, Plan Section"Project Structure"]
- [ ] CHK006 Is the relationship between the controller and the harness specified in terms a reviewer can apply when scoping a borderline request (e.g., is "corpus selection" the harness's job or the controller's)? [Clarity, Spec SectionFR-033]
- [ ] CHK007 Does the plan call out which constitution gates produce normal deliverables vs. blocking violations, so a downstream task list can include the documentation work without confusion? [Clarity, Plan Section"Constitution Check" Q-Gate 3]

## CLI Contract: Argument Surface

- [ ] CHK008 Are all five new flag groups (per-stage profile, stack-preset, slice control, documents-file, on-failure, Ollama lane URLs) documented with type, default, validation rule, and originating FR? [Completeness, Contract SectionArguments]
- [ ] CHK009 Is the closed-set profile vocabulary specified once, with the same enumeration appearing in every artifact that mentions it (spec FR-006, contract Closed-set vocabulary, research R-001, data-model `StageProfile`)? [Consistency, Spec SectionFR-006 / Contract Section"Closed-set vocabulary" / Research SectionR-001]
- [ ] CHK010 Are the rejection rules for `stub@<lane>`, unsupported `<impl>@<lane>` combinations, and unknown implementations covered as discrete cases in the contract - not blended into a generic "invalid value" sentence? [Clarity, Contract Section"Rejection rules", Research SectionR-002]
- [ ] CHK011 Is the `--stack-preset` expansion table identical across spec FR-004A, contract Section"`--stack-preset` expansion table", research R-003, and the data-model overrides note, with no field-level drift? [Consistency, Spec SectionFR-004A / Contract SectionStack-preset / Research SectionR-003 / Data-model SectionStackPreset]
- [ ] CHK012 Are the per-stage `--<stage>-profile` override semantics specified explicitly enough that a reader can determine whether a partial preset+override combination is accepted or rejected? [Clarity, Spec SectionFR-004A, Contract SectionStack-preset, Research SectionR-003]
- [ ] CHK013 Are the prerequisite-artifact requirements for each `--start-at` value tabulated as an exhaustive function (start stage -> required artifacts) so no reader needs to derive them from prose? [Completeness, Contract Section"Prerequisite-artifact validation"]
- [ ] CHK014 Is the overwrite-scoping rule stated as a positive contract ("guard checks slice outputs only") and a negative contract ("prerequisites and untouched artifacts NEVER trigger OUTPUT_IN_USE") so both directions are testable? [Clarity, Spec SectionFR-011, Contract Section"Overwrite scoping", Research SectionR-006]
- [ ] CHK015 Is the mutual-exclusion matrix between `--input` / `--document-folder` / `--documents-file` written without ambiguity about what counts as "providing" a flag (presence of the flag vs. presence of a non-empty value)? [Clarity, Contract Section"Input selector"]
- [ ] CHK016 Are exit codes for new failure stages (`prerequisite_validation`, `corpus_validation`, deferred-stack errors) mapped to existing `ExitCode` enum values with no invented codes? [Consistency, Contract Section"Exit codes", Spec SectionEdge Cases]
- [ ] CHK017 Is the cold-mode vs. warm-corpus-mode stdout/stderr behavior described as separate, comparable specs so a reviewer can confirm the cold path is byte-identical to `002-cli-contract` v1.0.0? [Clarity, Contract Section"Output behavior", Research SectionR-010]

## CLI Contract: Run Summary Schema

- [ ] CHK018 Is the run-summary JSON shape specified as a closed schema (every field's name, type, and presence rule pinned), not as a free-form example? [Completeness, Contract Section"Run summary schema", Research SectionR-009]
- [ ] CHK019 Is the run-summary `schema_version` field's bump rule documented (when does it change, who owns the bump) so future amendments do not silently drift? [Clarity, Contract Section"Run summary schema"]
- [ ] CHK020 Is the per-document `stages.<stage>.<phase>_seconds` key vocabulary pinned per stage so a reader knows which phase keys to expect for `preprocess` vs. `extract` vs. `routing` vs. `final_payload`? [Clarity, Data-model Section`StageTiming`, Research SectionR-009]
- [ ] CHK021 Is the policy for missing or partial phase keys (e.g., a stage that failed mid-phase) specified, including whether absent phase keys imply zero or "not measured"? [Coverage, Edge Case, Research SectionR-009 / R-015]
- [ ] CHK022 Is the requirement that the run-summary line is the **last** stdout line stated unambiguously enough that a streaming consumer can implement an "end-of-run sentinel" without speculation? [Clarity, Contract Section"Output behavior" / Research SectionR-009]
- [ ] CHK023 Are the run-summary counts (`documents_total`, `documents_succeeded`, `documents_failed`) defined in terms of when they are incremented (post-attempt? post-skipped-by-fail-fast?) so a reviewer can write assertions for the fail-fast path? [Clarity, Coverage, Research SectionR-008]

## Runtime-Boundary Decisions

- [ ] CHK024 Is the constraint that adapter-target functions live in existing per-stage modules (not in `pipeline/`) stated as a design rule with a stated reason (constitution Q-Gate 1 + FR-033), so future PRs can be reviewed against it? [Clarity, Research SectionR-014, Plan Section"Project Structure"]
- [ ] CHK025 Are the existing module entry points (`preprocessing.pipeline.run_preprocessing`, `extract.pipeline.run_extraction`, `router.pipeline.route`, `assembler.pipeline.assemble`) named explicitly so a reader does not have to pattern-match to find them? [Traceability, Research SectionR-014]
- [ ] CHK026 Is the `WarmProfileRegistry` lifecycle (per-process, stage-scoped, not module-global) specified in a way that makes the SC-009 invariant ("exactly once per process") falsifiable by a single assertion in the integration test design? [Measurability, Research SectionR-011, Data-model Section`WarmProfileRegistry`]
- [ ] CHK027 Is the host-Ollama vs. WSL-CPU-container vs. Jetson-edge distinction documented consistently across `ollama-runtime.md` (referenced), research R-012, and contract Ollama-lane table - without one saying the WSL container is GPU-capable while another says it is not? [Consistency, Research SectionR-012, Constitution SectionV]
- [ ] CHK028 Is the deterministic-routing/final-payload property (only `@cpu` profiles, no model-driven decisions) reasserted in research/contract terms even though it is already in the constitution, so the design layer cannot drift? [Coverage, Constitution SectionIII, Spec SectionFR-018, Research SectionR-014]
- [ ] CHK029 Are the lane semantics for "what changes vs. what must not change between `ollama@gpu` and `ollama@cpu`" stated as a positive list (artifact metadata fields the schema permits to vary) AND a negative list (filenames, schemas, success/failure record shapes)? [Clarity, Spec SectionFR-014]
- [ ] CHK030 Is the timing capture method (`time.monotonic_ns`) specified with the rationale (clock-adjustment immunity), so a future PR cannot silently swap to `time.time()` without surfacing the regression? [Traceability, Research SectionR-015]

## Warm-Corpus Behavior

- [ ] CHK031 Is the `--documents-file` parsing behavior specified as a function (input bytes -> list of resolved paths) with all four edge cases pinned (blank lines, `#`-comments, missing file, empty after strip)? [Completeness, Spec Section"Edge Cases", Contract Section"Input selector", Research SectionR-007]
- [ ] CHK032 Is the path-resolution rule for entries inside the documents file (relative to the file's parent dir, not the caller's cwd) stated unambiguously? [Clarity, Research SectionR-007]
- [ ] CHK033 Are the default-failure-policy semantics defined separately for cold (no-op) and warm-corpus (continue) modes, with the reason for the asymmetry given so a reviewer can defend the design? [Clarity, Spec SectionFR-028, Research SectionR-008 / R-010]
- [ ] CHK034 Are the per-document failure record shape and the run-summary `per_document` failure entry shape consistent so a harness can correlate stderr lines to summary entries by `document_id` + `failed_stage`? [Consistency, Data-model Section`DocumentOutcome` / Section`RunSummaryDocument`]
- [ ] CHK035 Is the warm-corpus exit-code rule ("highest-severity per-document exit code observed") specified with reference to the existing `ExitCode` enum ordering, so the severity ranking is not subjectively interpreted? [Clarity, Measurability, Research SectionR-008]
- [ ] CHK036 Is the SC-009 invariant ("PPStructureV3 initialized exactly once per process") expressed as something a single test assertion can verify (e.g., `len(profile_initialization_seconds) == 1` regardless of N)? [Measurability, Spec SectionSC-009, Quickstart Section6]
- [ ] CHK037 Are the warm-corpus mode's interactions with `--overwrite` defined for both the slice-output case and the prerequisite-input case, since warm corpus runs typically run the full pipeline against many folders that may or may not already have prior artifacts? [Coverage, Edge Case, Spec SectionFR-011]
- [ ] CHK038 Is the order-preservation guarantee for `per_document` (matches `--documents-file` order after comment-strip) stated explicitly so an assertion can be written against duplicate or out-of-order entries? [Clarity, Research SectionR-007 / R-009]

## Explicit Deferrals & Non-Goals

- [ ] CHK039 Is each deferred item (`ensemble@workstation` endpoint config, live `edge-ocr@jetson` adapter, live `ollama@jetson` adapter, `cloud-workstation` voter-set artifact metadata, doc updates for architecture/ollama-runtime) listed in exactly one canonical place with a forward reference to where it lands (FR-034 step 4 or tasks)? [Completeness, Research Section"Open follow-ups", Spec SectionFR-022A / FR-035]
- [ ] CHK040 For `ensemble@workstation`, are the three behaviors required in this slice each spelled out (validation accepts the value, preset can expand to it, selection inside the slice fails fast with named missing-endpoint error)? [Completeness, Spec SectionFR-022A, Research SectionR-013]
- [ ] CHK041 Is the missing-endpoint error message content specified (must name the deferral to FR-034 step 4) so a reviewer can verify the error meets FR-031's "operator can tell which stage and profile" bar? [Clarity, Research SectionR-013, Spec SectionFR-031]
- [ ] CHK042 Is the deferral worded as a hard contract ("MUST NOT freeze flag names") rather than a soft preference, so a future PR cannot pre-bake `--ensemble-voter-*-url` flags ahead of the secondary-lane slice? [Clarity, Spec SectionFR-022A]
- [ ] CHK043 Is the non-goal "no remote cloud calls or credential handling" specified with examples of what would violate it (provider SDK imports, credential env vars, network egress to non-localhost in the cloud-workstation path) so reviewers have a checkable list? [Coverage, Spec SectionFR-021 / FR-036]
- [ ] CHK044 Is the non-goal "no new persisted benchmark artifact" stated alongside the positive equivalent ("run summary on stdout only") so a reader cannot accidentally read the run summary as a license to add a side file? [Consistency, Spec SectionFR-030 / FR-036, Research SectionR-009]
- [ ] CHK045 Are the "edge OCR scanner stays in this repository" and "no second repository" non-goals worded so the reader knows whether moving the scanner to a sibling package within the same repo is allowed or also forbidden? [Clarity, Spec SectionFR-036]

## Acceptance Criteria Quality

- [ ] CHK046 Are SC-001 through SC-011 each phrased as objectively measurable predicates (Boolean or numeric) that can be evaluated with a single command or assertion? [Measurability, Spec Section"Success Criteria"]
- [ ] CHK047 Does SC-005's "100% of tested cases" success criterion specify the test population (which invalid-profile combinations are in the rejection test set) so the percentage is auditable? [Clarity, Spec SectionSC-005]
- [ ] CHK048 Does SC-009's "exactly once per process" criterion specify how to count initializations (registry's `initialization_timings_ns` cardinality? log lines? metric counter?) so the test design is unambiguous? [Measurability, Spec SectionSC-009, Data-model Section`WarmProfileRegistry`]
- [ ] CHK049 Are SC-007 and SC-008's "run metadata distinguishes it from other stacks" criteria specified by referencing the run-summary `stack_preset` field and `resolved_profiles` map, not just prose? [Traceability, Spec SectionSC-007 / SC-008, Research SectionR-009]
- [ ] CHK050 Does SC-011's "harness/corpus live preprocessing runs can execute without launching one fresh live preprocessing process per document" criterion translate into a testable invariant given the `WarmProfileRegistry` model (e.g., `len(registry.instances)` is constant across documents)? [Measurability, Spec SectionSC-011, Research SectionR-011]

## Edge Case & Scenario Coverage

- [ ] CHK051 Are all 17 edge cases enumerated in spec Section"Edge Cases" each mapped to either an existing FR or a new edge-case behavior so none floats orphan? [Coverage, Spec Section"Edge Cases"]
- [ ] CHK052 Is there a documented requirement for the case where `--documents-file` lists the same folder twice (dedup vs. preserve duplicates)? [Coverage, Edge Case, Research SectionR-007]
- [ ] CHK053 Is there a documented requirement for the case where `--start-at extract --stop-after preprocess` (start later than stop) - is the failure stage `arguments` or `prerequisite_validation`? [Coverage, Edge Case, Research SectionR-004]
- [ ] CHK054 Is there a documented requirement for warm-corpus runs whose slice excludes preprocessing entirely (e.g., `--start-at routing` over a documents-file) - does any live preprocessing profile get warmed? [Coverage, Spec Section"Edge Cases" warm-corpus deterministic-only-stages bullet]
- [ ] CHK055 Is the behavior for a `--stack-preset cloud-workstation --extract-profile ollama@gpu` override (preset selects ensemble, override selects gpu) defined explicitly so a reviewer knows whether the deferral fail-fast still triggers? [Coverage, Edge Case, Research SectionR-003 / R-013]
- [ ] CHK056 Are the four canonical stages' phase-key vocabularies internally consistent - does every stage that writes an artifact have a `write` phase, every stage that infers have an `infer` phase, etc., or is the omission documented? [Consistency, Data-model Section`StageTiming`]
- [ ] CHK057 Are the requirements for a malformed prerequisite artifact (e.g., truncated JSON) vs. a schema-invalid prerequisite artifact (e.g., wrong type) distinguished, and do they map to the two different exit codes in the contract? [Coverage, Edge Case, Contract Section"Prerequisite-artifact validation"]

## Ambiguities, Conflicts, Traceability

- [ ] CHK058 Is the term "stage profile" used consistently across spec/plan/research/data-model/contract - or does any artifact use synonyms ("stage runtime", "profile spec") that could create grep gaps? [Consistency]
- [ ] CHK059 Is every research decision R-001 ... R-015 referenced from at least one downstream artifact (plan, data-model, contract, or quickstart) so no decision is orphaned? [Traceability, Research Section"Summary"]
- [ ] CHK060 Are FR references in the plan, contract, and quickstart kept up to date with the renumbering after FR-022A was inserted (no off-by-one references to old FR-022/FR-023 numbering)? [Consistency]
- [ ] CHK061 Is the assumption "the optional WSL Ollama container is CPU-only and not GPU-capable" cited where R-012's CPU lane default port is justified, so a future doc cleanup doesn't strip the rationale? [Traceability, Research SectionR-012, Constitution SectionV]
- [ ] CHK062 Are the 5 clarification answers (Q1-Q5) each reflected in at least one binding requirement or research decision, with no stranded "we agreed but didn't document it" items? [Completeness, Spec SectionClarifications, Research SectionR-007 through SectionR-013]
- [ ] CHK063 Is the boundary between "this slice's contract surface" and "this slice's live implementation" stated explicitly enough that a reviewer can answer "does this PR ship live behavior or only contract acceptance?" without reading the implementation? [Clarity, Spec SectionFR-035, Research SectionR-013 / R-014]

## Dependencies & Assumptions

- [ ] CHK064 Are all third-party dependencies the controller relies on (`jsonschema`, `pydantic`, `httpx`, `PyYAML`, stdlib) listed in the plan with their existing versions, so a reviewer can confirm "no new dep" claim? [Completeness, Plan Section"Primary Dependencies"]
- [ ] CHK065 Are the per-stage modules' existing public entry points listed as a dependency surface so a refactor of any one of them flags as a controller-level concern? [Traceability, Research SectionR-014]
- [ ] CHK066 Is the assumption that `validate_artifact(...)` returns a structured outcome with violation details (used by R-005) documented as a dependency on the validator module's public API? [Dependency, Research SectionR-005]
- [ ] CHK067 Is the assumption that the existing `StructuredFailureRecord` shape can carry the new `failed_stage` and `exit_code` fields without modification verified, or is a small extension implied? [Assumption, Research SectionR-008]
- [ ] CHK068 Are the documentation-update dependencies (architecture.md, ollama-runtime.md per Q-Gate 3) tracked as deliverables of this feature so they are not deferred to a later cleanup PR by accident? [Coverage, Plan Section"Constitution Check" Q-Gate 3]

## Notes

- Check items off as completed: `[x]`.
- Items tagged `[Gap]` represent design-quality holes that should be filled before `/speckit.tasks`. Items tagged `[Ambiguity]` or `[Conflict]` should be resolved by editing the corresponding artifact, not by adding code.
- The existing `requirements.md` checklist covered spec-quality (content quality, requirement completeness, feature readiness). This `design.md` checklist covers Phase-0/Phase-1 design-artifact quality (research decisions, plan structure, contract schema, data model, runtime-boundary decisions, deferrals).
- Add follow-up findings inline beneath each item rather than in a separate document so the resolution stays adjacent to the question.
