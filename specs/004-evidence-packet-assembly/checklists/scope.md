# Scope Boundary Checklist: Evidence Packet Assembly

**Purpose**: Release-gate validation that the spec's in-scope / out-of-scope
boundaries are crisply drawn, so reviewers can reject implementations that
drift into neighboring slices (003 preprocessing, 005 single-voter
extraction, harness, Falcon sources, Q1 deferred decisions). Items test
requirements clarity around scope, not the implementation.
**Created**: 2026-04-20
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + slice owner)

## Positive Scope (What This Slice IS)

- [ ] CHK160 Is the sole responsibility stated clearly — "produce a deterministic, voter-ready, Trijunction-shaped data structure from `preprocess_output.json`"? [Clarity, Spec §Summary]
- [ ] CHK161 Is the per-document-folder unit of work stated as the one and only unit this slice processes? [Clarity, Spec §FR-001]
- [ ] CHK162 Is the single-source-of-input rule stated (read only `preprocess_output.json`, no other artifact)? [Clarity, Spec §FR-002]
- [ ] CHK163 Is the packet shape's forward-compat commitment stated (slots for Falcon OCR and Falcon Perception even though they are `not_implemented`)? [Clarity, Spec §FR-004 §Assumptions]
- [ ] CHK164 Is the regex-hint field set enumerated exactly (emails, URLs, US phones, EIN-shaped IDs) so the "four hint categories" boundary is unambiguous? [Clarity, Spec §FR-008 §Clarifications Q2]

## Negative Scope (What This Slice IS NOT)

- [ ] CHK165 Is calling any model (PaddleOCR-VL, Falcon OCR, Falcon Perception, any LLM voter) explicitly out of scope? [Clarity, Spec §Out of Scope]
- [ ] CHK166 Are `edge_extraction_output.json`, `routing_decision.json`, and `final_structured_payload.json` explicitly not produced or modified by this slice? [Clarity, Spec §Out of Scope §FR-016]
- [ ] CHK167 Is logo/stamp/header/footer detection explicitly deferred to when Falcon Perception lands? [Clarity, Spec §Out of Scope]
- [ ] CHK168 Are company-name and address candidate slots explicitly left empty/`null` in stage 1 (deferred to layout-aware heuristics in a later slice)? [Clarity, Spec §FR-008 §Clarifications Q2]
- [ ] CHK169 Are business decisions (vendor identity acceptance, review routing) explicitly outside the packet's responsibility? [Clarity, Spec §Summary §FR-010]
- [ ] CHK170 Is multi-document / batch / corpus-loop orchestration explicitly out of scope (single document per invocation only)? [Clarity, Spec §Out of Scope §Assumptions]

## Boundary with 003 (Preprocessing)

- [ ] CHK171 Is the rule "do not re-run OCR / layout / table extraction" stated explicitly? [Consistency, Spec §Out of Scope §FR-006]
- [ ] CHK172 Is the rule "do not modify, re-write, or re-interpret any field from `preprocess_output.json`" stated? [Consistency, Spec §FR-016]
- [ ] CHK173 Is the `document_text` passthrough (not re-computed) specified as a byte-equality contract? [Consistency, Spec §Data Model Invariants]
- [ ] CHK174 Is the passthrough of `pages[]` and `tables[]` specified as verbatim (no filtering, no re-indexing)? [Consistency, Spec §FR-006]
- [ ] CHK175 Is the rule "no changes to 003's code or schema" stated so reviewers reject PRs that silently touch preprocessing internals? [Gap — implicit but worth making explicit]

## Boundary with 005 (Single-Voter Extraction)

- [ ] CHK176 Is the rule "no voter-specific projection, no model-specific token budgets, no prompt fragments in the packet" stated? [Clarity, Spec §FR-009 §US3]
- [ ] CHK177 Is the rule "no per-field confidence or evidence from extraction inside the packet" stated (those live in `edge_extraction_output.json`)? [Clarity, Spec §FR-010]
- [ ] CHK178 Is the API-stability commitment to 005 stated (the two entry points are the contract 005 will program against)? [Completeness, Spec §Dependencies §FR-019]
- [ ] CHK179 Is the provenance stamp "unverified" specified as the stage-1 value so 005 knows what it is receiving? [Clarity, Spec §FR-008]

## Boundary with the Harness

- [ ] CHK180 Is harness / evaluation wiring explicitly out of scope? [Clarity, Spec §Out of Scope]
- [ ] CHK181 Is the rule "this slice does not modify `expected.json`, `evaluation_document.json`, or `evaluation_run_summary.json`" stated (or derivable from FR-016's "four existing artifacts" list)? [Consistency, Spec §FR-016 §CLI Contract]
- [ ] CHK182 Is the rule "no new corpus documents added by this slice" stated? [Clarity, Spec §Assumptions]

## Boundary with the Falcon Sources (Future Slices)

- [ ] CHK183 Is the rule "Falcon OCR / Falcon Perception are shape-only placeholders in stage 1" stated? [Clarity, Spec §FR-007 §Assumptions]
- [ ] CHK184 Is the extension path (flip `status` to `success`, populate `payload`) stated so a future slice does not feel entitled to re-shape the packet? [Completeness, Spec §US2 AC#2 §SC-005]
- [ ] CHK185 Is the rule "any future Falcon integration is a new slice, not part of 004" stated? [Clarity, Spec §Out of Scope]

## Deferred Decisions

- [ ] CHK186 Are deferred decisions labeled as deferred with a pointer to the slice / decision that resolves them (e.g. company-name inference → layout-aware heuristics slice)? [Traceability, Spec §FR-008 §Clarifications Q2]
- [ ] CHK187 Is the rule "no `--persist-packet` flag, no persistence env var" stated so a future contributor does not sneak one in? [Consistency, Spec §Clarifications Q1 §FR-020]
- [ ] CHK188 Is any future CLI verb addition (e.g. `ledgerlinc-evidence-packet --validate`) explicitly an amendment to the CLI contract, not part of 004? [Clarity, Spec §CLI Contract Forward-Compat]

## Constitution Alignment

- [ ] CHK189 Does the spec restate the constitution's pipeline-vs-harness boundary (pipeline owns preprocessing, extraction orchestration, consensus, routing, final payload; harness owns corpus, expected truth, evaluation, reporting)? [Consistency, Spec §Constitution Check]
- [ ] CHK190 Does the spec restate the stage-1 scope constraints (PDF input only, vendor identity only, no line items, no cloud, no latency gate) and affirm this slice honors them? [Consistency, Spec §Constitution Check]
- [ ] CHK191 Does the spec identify which Quality Gate (from the constitution) governs the amendment introduced here (Gate 2: output contracts)? [Traceability, Spec §Constitution Check]
- [ ] CHK192 Is the rule "runtime boundaries are not collapsed by this slice" stated (no embedding of model runtime, no merging of harness concerns)? [Consistency, Spec §Constitution Check]

## Notes

- Check items off as completed: `[x]`
- Flag unresolved `[Gap]` / `[Ambiguity]` / `[Conflict]` items for spec amendment before implementation begins
- If a reviewer or implementer feels the slice "needs" to touch an out-of-scope area, raise it as a scope amendment on the spec **before** writing code; do not silently expand scope during implementation
