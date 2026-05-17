# Feature Specification: Evidence Packet Assembly (Trijunction-Ready)

**Feature Branch**: `004-evidence-packet-assembly`
**Created**: 2026-04-20
**Status**: Draft
**Input**: User description: "look in the docs for 004 — Evidence packet assembly (Trijunction-ready shape, feeds all downstream voters)"

## Clarifications

### Session 2026-04-20

- Q: How does the assembler decide to persist `evidence_packet.json` — Python logger level, dedicated CLI flag, both, or env var? → A: Python logger level only. Persist iff the `dartwing_ocr` (or equivalent) Python logger's effective level is `DEBUG` or lower. CLI `-v/--verbose` sets that logger level; no separate persistence flag.
- Q: What JSON canonical form makes packet output byte-identical across runs? → A: Reuse 003's existing `write_atomic` convention: `json.dump(packet, f, ensure_ascii=False, indent=2, sort_keys=False)`, atomic rename, no trailing newline. Key order = assembler's deterministic insertion order.
- Q: Is the packet validated against `evidence_packet.schema.json` when returned in-memory (default path), or only when persisted? → A: Always validate. The assembler validates the packet against `evidence_packet.schema.json` before returning it, regardless of logging level; validation failure raises and no file is written.
- Q: How are duplicate/ordered regex hints represented in `candidate_vendor_signals`? → A: Emit matches in document order (offset ascending), one entry per occurrence with its own source line/offset reference. No deduplication, no sorting. Downstream voters dedupe if they need to.
- Q: What source-reference fields are required on each regex hint? → A: All four: `document_text` character offset + length, plus `{page_index, block_index, line_index}` derived from `preprocess_output`'s reading-order join. All four fields are non-null in stage 1 (the assembler owns the reverse-mapping).

## Summary

Stage 1 already produces `preprocess_output.json` (003) — page images, OCR lines, layout blocks, tables, document text, quality, ingestion-source flags. The next slice on the critical path (`docs/stage1-vendor-identity/implementation-plan.md` step 4) is **evidence packet assembly**: take that preprocess artifact and assemble the **shared evidence packet** that downstream model voters will reason over. The packet must reflect the long-term Trijunction shape (PaddleOCR-VL + Falcon OCR + Falcon Perception) so additional ingestion sources and additional model voters can be slotted in without re-shaping the contract that voters consume.

This slice does **not** call any model, does **not** make business decisions about vendor identity, and does **not** change the four existing persisted artifacts. Its single responsibility is to produce a deterministic, voter-ready, Trijunction-shaped data structure from preprocess output.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Voter-Ready Packet From Preprocess Output (Priority: P1)

A pipeline developer working on the next slice (single-voter edge extraction) needs to feed model voters something richer than raw OCR text. They want a single, well-shaped object that contains all the structural and perceptual evidence the eventual three-voter ensemble will reason over, so that the voter prompt and parser can be built once against a stable shape — even though only PaddleOCR is wired in today.

**Why this priority**: This is the hard prerequisite for User Story 5 of the implementation plan (single-voter extraction). Without a stable evidence packet shape, every downstream voter has to be re-plumbed when the second and third ingestion sources or voters arrive. This is the entire reason the slice exists.

**Independent Test**: Run the assembly entry point on a per-document folder that already contains `preprocess_output.json`. Assert the returned packet contains all required Trijunction sections (OCR text + reading order, layout blocks, table snippets, ingestion-source status, perceptual observations slot, header/footer candidates, candidate vendor signals with deterministic regex hints) and that re-running on the same input yields a byte-identical packet.

**Acceptance Scenarios**:

1. **Given** a per-document folder with a valid `preprocess_output.json` from 003, **When** the assembler runs, **Then** it returns an evidence packet whose structural sections (pages, blocks, reading order, document text, tables) are derived faithfully from the preprocess artifact with no business inference added.
2. **Given** the same input folder, **When** the assembler runs twice in succession, **Then** the two packet outputs are byte-for-byte identical (deterministic assembly, no timestamps in payload, no random ordering).
3. **Given** a `preprocess_output.json` whose `ingestion_sources.falcon_ocr.status` is `not_implemented` and `falcon_perception.status` is `not_implemented`, **When** the assembler runs, **Then** the resulting packet preserves those status flags and exposes empty-but-typed slots for Falcon OCR text and Falcon Perception observations (no fabricated data, no missing keys).
4. **Given** a `document_text` containing visible email addresses, URLs, US phone numbers, and an EIN-shaped string, **When** the assembler runs, **Then** the packet's `candidate_vendor_signals` section contains those values surfaced as deterministic regex hints (with source line/offset references when available); the company-name and address candidate slots remain empty/`null`.
5. **Given** the assembler is invoked with logging set to debug/verbose level, **When** it runs against a per-document folder, **Then** an `evidence_packet.json` file is written into that folder; **Given** logging is at the default level, **When** the assembler runs, **Then** no file is written and the four existing artifacts are byte-identical before and after.

---

### User Story 2 - Pluggable Trijunction Sources (Priority: P2)

A future implementer wiring in Falcon OCR or Falcon Perception needs the evidence packet to already have the right slot for their output. They should be able to add a new source without changing the packet contract or disrupting existing consumers.

**Why this priority**: The architecture's central commitment is that the Trijunction layer is composed of three pluggable sources. Stage 1 ships only PaddleOCR, but the packet shape is the forward-compatibility seam. P2 because the absence of slots wouldn't block the immediate next slice (single voter), but their absence would force a contract break later.

**Independent Test**: Inspect the packet schema/dataclass and verify it has explicit, named slots for each Trijunction source (PaddleOCR layout/text, Falcon OCR text + spam-gate signal, Falcon Perception observations such as logos and stamps), each with a status enum. Adding a Falcon adapter in the future must be a matter of populating an existing slot, not extending the schema.

**Acceptance Scenarios**:

1. **Given** the packet contract, **When** any reviewer reads it, **Then** each of the three Trijunction sources has a named, typed section even when only one source is implemented.
2. **Given** PaddleOCR is the only enabled source, **When** the assembler runs, **Then** Falcon OCR and Falcon Perception sections exist with explicit `not_implemented` status and empty payloads, and consumers can detect availability via the status flags rather than via key presence.

---

### User Story 3 - Voter-Independent Shape (Priority: P2)

A future implementer adding the second or third model voter (Gemma, Phi-4 Mini) needs the packet to be voter-agnostic — every voter reads from the same shape. The packet must carry no voter-specific projection, no model-specific token budgets, and no prompt fragments.

**Why this priority**: The constitution's runtime boundary rule says the pipeline owns extraction orchestration and consensus over a shared evidence packet. If the packet bakes in voter-specific assumptions, consensus comparison breaks down. P2 because stage 1 only ships one voter, but the shape choice now binds all future voters.

**Independent Test**: Read the packet contract and verify it contains no voter-named sections, no prompt strings, and no per-voter scoring. Three voter implementations should be able to consume the same packet object via the same accessor without modification.

**Acceptance Scenarios**:

1. **Given** the packet, **When** any voter implementation consumes it, **Then** the voter receives identical structural and perceptual data regardless of which model it wraps.
2. **Given** a future change to add a second voter, **When** the developer wires it in, **Then** they do not need to change the packet shape, only the voter adapter.

---

### User Story 4 - Per-Document Folder Integration (Priority: P3)

A pipeline operator running stage 1 against a corpus document expects evidence packet assembly to slot into the existing per-document folder convention used by all other stage 1 artifacts (`tests/stage1_vendor_identity/inv_XXX_<difficulty>/`). They should not need to invent a new I/O path.

**Why this priority**: Consistency with the existing folder contract (003) reduces cognitive load for harness authors and CLI users. P3 because the packet's existence is the load-bearing thing; whether it sits next to the four existing artifacts or stays in-memory is a contract decision (Q1 below) rather than a UX must-have.

**Independent Test**: Run the assembler against an existing per-document folder with logging set to debug; verify the read path is the document folder's `preprocess_output.json` and that the persisted `evidence_packet.json` lands in the same folder, leaving the four existing artifact files unchanged.

**Acceptance Scenarios**:

1. **Given** a per-document folder containing only `source.pdf` and `preprocess_output.json`, **When** the assembler runs at default logging level, **Then** it reads only from that folder and writes nothing.
2. **Given** the same folder and the assembler invoked at debug logging level, **When** it runs, **Then** `evidence_packet.json` is written into that folder under a stable filename and validates against the new `evidence_packet.schema.json`.
3. **Given** the existing folder contract `contracts/stage1_vendor_identity/v1.0.0/folder.schema.json`, **When** this slice ships, **Then** the contract set is amended (via `AMENDMENTS.md`) to legalize `evidence_packet.json` as an optional generated file in the per-document folder.

---

### Edge Cases

- **Preprocess output marked partial-failure or step-failure** (003 supports these states): the assembler must still produce a packet; sections corresponding to failed steps are typed-empty with a status flag, never silently dropped.
- **Zero-page or fully-blank document**: the packet has zero pages but all top-level slots still present; downstream voters can detect "nothing to extract" via empty pages plus quality flags rather than via missing keys.
- **`document_text` empty but `pages[].blocks` present**: the packet preserves both as-is; the assembler does not synthesize text from blocks. Candidate vendor signal regex hints simply yield empty results.
- **`preprocess_output.json` missing or schema-invalid**: the assembler refuses to produce a packet (clear error, non-zero exit when invoked via CLI), rather than emitting a packet with fabricated defaults.
- **Tables present but malformed/partial** (003 normalizes tables): table snippets in the packet mirror what 003 emitted, with no re-interpretation.
- **`ingestion_sources.paddleocr_vl.status` is `failure`** but the file is otherwise valid: the packet exposes the PaddleOCR slot with that failure status; downstream voters decide whether to proceed with degraded evidence.
- **Re-running the assembler over an existing packet output**: deterministic re-assembly produces a byte-identical packet; if logging is set, the on-disk `evidence_packet.json` is overwritten with an identical byte sequence.
- **Logging set but the per-document folder is read-only**: the assembler emits a clear error identifying the folder as unwritable and exits non-zero (CLI mode); the in-memory packet is otherwise valid and is still returned to library callers.
- **Regex hint candidates contain spurious matches** (e.g., a phone-shaped string that's actually a tracking number): the packet surfaces what regex finds, with each hint marked as `unverified` so downstream voters know to confirm; the assembler does not adjudicate.

## Requirements *(mandatory)*

### Functional Requirements

**Inputs and pre-conditions:**

- **FR-001**: System MUST accept a per-document folder path (matching `tests/stage1_vendor_identity/inv_XXX_<difficulty>/`) as the unit of work.
- **FR-002**: System MUST read `preprocess_output.json` from that folder as the sole structural data source for stage 1.
- **FR-003**: System MUST validate the input `preprocess_output.json` against the frozen schema (`contracts/stage1_vendor_identity/v1.0.0/preprocess_output.schema.json`) before proceeding, and refuse to assemble a packet when validation fails.

**Packet shape:**

- **FR-004**: System MUST assemble an evidence packet with explicit, named sections for each Trijunction ingestion source: PaddleOCR-VL layout/text, Falcon OCR text + spam-gate signal, Falcon Perception observations.
- **FR-005**: Each Trijunction section MUST carry a status flag (`success`, `failure`, `not_implemented`, mirroring `preprocess_output.ingestion_sources`) so downstream consumers detect availability without inspecting key presence.
- **FR-006**: System MUST include in the packet: page-level OCR (lines + blocks), reading order, layout blocks with bounding boxes, document text in reading order, table snippets when present.
- **FR-007**: System MUST include in the packet a section for **perceptual observations** (logos, stamps, header/footer candidates) populated by Falcon Perception when available; for stage 1 this section is structurally present but empty with `not_implemented` status.
- **FR-008**: System MUST include in the packet a section for **candidate vendor signals** (company-name candidate, address candidates, tax-ID candidates, website, email, phone) shaped to match the fields the eventual `edge_extraction_output` voter will produce. Stage 1 population: deterministic regex hints over `document_text` for **email addresses, URLs/website, US phone numbers, and EIN-shaped tax IDs**. URL hints match only strings prefixed by `http://` or `https://`; bare-domain matches (e.g. `acme.com` without a scheme) are out of scope in stage 1 and are deferred to a later slice that can bring layout context. The **company-name** and **address** candidate slots remain empty/`null` in stage 1 (they require Falcon Perception / layout-aware heuristics that arrive in a later slice). Each populated hint MUST be marked as `unverified` provenance so downstream voters know to confirm. Ordering and duplicates: matches MUST be emitted in document order (ascending offset within `document_text`), with one entry per occurrence — no deduplication, no sorting. Voters may dedupe downstream if they wish. Source-reference fields on each hint: every hint MUST carry (a) `document_text` character offset and length of the match and (b) `{page_index, block_index, line_index}` derived from 003's reading-order join used to build `document_text`. All four fields are non-null in stage 1; the assembler owns the reverse-mapping from `document_text` offsets back to the originating line.
- **FR-009**: System MUST NOT include any section, key, or value that would make the packet voter-specific, model-specific, or prompt-specific.
- **FR-010**: System MUST NOT include the four existing persisted artifacts' decision content (no `routing_decision` content, no `final_structured_payload` content, no per-field `confidence`/`evidence` from extraction). The packet is upstream of voting and routing.

**Determinism and provenance:**

- **FR-011**: System MUST produce a byte-identical packet on repeated runs over the same input. Canonical serialization reuses 003's `write_atomic` helper (or equivalent): `json.dump(packet, f, ensure_ascii=False, indent=2, sort_keys=False)` with atomic rename and no trailing newline. Key order is the assembler's deterministic insertion order; there is no `sort_keys=True` normalization, so the assembler is responsible for inserting keys in a fixed order.
- **FR-012**: The packet MUST NOT contain wall-clock timestamps, run IDs, or other non-input-derived values inside its payload (such metadata, if needed at all, lives outside the packet body — for example, in a sidecar or in CLI logs).
- **FR-013**: System MUST stamp the packet with a `contract_set_version` field aligned to the stage 1 contract set. This slice bumps the contract set from `1.0.0` to `1.1.0` (MINOR, additive) via `AMENDMENTS.md`; the packet carries `"1.1.0"`. Consumers use this field to detect contract drift.
- **FR-014**: System MUST use `null` for missing scalar fields and empty arrays for missing list fields — never empty strings, never absent keys.

**Persistence and folder contract:**

- **FR-015a**: Default persistence is **in-memory only** — the assembler returns the packet to the caller and writes nothing to disk. The in-memory packet MUST be validated against `evidence_packet.schema.json` before being returned to the caller; validation failure raises and no file is written. Validation is unconditional on logging level.
- **FR-015b**: When the `dartwing_ocr` (or equivalent) Python logger's effective level is `DEBUG` or lower at invocation time, the assembler MUST also persist the packet as `evidence_packet.json` into the same per-document folder it read from. The persisted file MUST validate against a new `evidence_packet.schema.json` to be added under `contracts/stage1_vendor_identity/v1.1.0/` (the MINOR-bump directory created by this slice's amendment; see FR-015c). There is no dedicated `--persist-packet` flag and no environment-variable trigger; CLI verbosity flags work by configuring the logger.
- **FR-015c**: This slice MUST file an amendment via `contracts/stage1_vendor_identity/AMENDMENTS.md` adding `evidence_packet.json` to `folder.schema.json` as an **optional** generated file (so the folder validator accepts its presence at debug-logging level and its absence at default level). The contract-set version is bumped accordingly per the amendment policy.
- **FR-016**: System MUST NOT modify, re-write, or invalidate the four existing per-document artifacts (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`).

**Failure handling:**

- **FR-017**: When `preprocess_output.json` is missing, unreadable, or schema-invalid, System MUST emit a clear error identifying which precondition failed and exit with a non-zero status if invoked via CLI. The closed exit-code and `kind`-discriminator vocabulary is defined in `specs/004-evidence-packet-assembly/contracts/cli-contract.md`.
- **FR-018**: When `preprocess_output.json` is valid but reports a partial-failure or step-failure state (per 003 semantics), System MUST still produce a packet whose affected sections carry the corresponding failure status flag rather than fabricating data or omitting keys.

**API surface:**

- **FR-019**: System MUST expose an importable Python function (assemble-from-folder and/or assemble-from-loaded-artifact) so the next-slice voter code and the eventual extraction CLI can reuse the same assembly path. The exact function signature is an implementation concern.
- **FR-020**: System MUST ship a new console script `dartwing-evidence-packet <folder>` (mirroring 003's `dartwing-preprocess`), wired through `[project.scripts]` in `pyproject.toml`. The CLI MUST accept a verbosity flag (e.g. `-v/--verbose`) whose sole effect relevant to persistence is to set the `dartwing_ocr` (or equivalent) Python logger level to `DEBUG`, thereby satisfying the trigger condition in FR-015b. No separate `--persist-packet` flag is added.

### Key Entities

- **Evidence Packet**: A voter-agnostic, Trijunction-shaped data structure built from one document's preprocess output. Carries structural evidence (OCR, layout, reading order, tables), perceptual evidence (logos, stamps — empty in stage 1), candidate vendor signals (depth per Q2), per-source status flags, and a contract-set version. Does not carry voter outputs, routing decisions, or final payload content.
- **Trijunction Source Section**: A named slot within the packet for one of three ingestion sources (PaddleOCR-VL, Falcon OCR, Falcon Perception). Always present; populated when the source is enabled and successful, otherwise carries an explicit status flag with a typed-empty payload.
- **Candidate Vendor Signal**: A pre-extraction hint about a vendor identity field (company name, address parts, tax IDs, website, phone, email) that downstream voters can confirm, ignore, or override. Whether stage 1 populates these deterministically or leaves them empty is governed by Q2.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** (soft, non-gating): Given any document folder in the existing 20-document corpus that has a valid `preprocess_output.json`, the assembler produces an evidence packet in well under one second on the devcontainer reference profile. This is a reviewer-observed sanity check captured by the corpus run in Phase 7 polish (tasks.md T081); it is not a release gate (per constitution §"Stage 1 Scope Constraints" — no latency target as a release gate).
- **SC-002**: Re-running the assembler on the same input folder ten times in a row produces ten byte-identical packet outputs.
- **SC-003**: 100% of valid `preprocess_output.json` inputs (including partial-failure and step-failure states) yield a packet whose required sections are all present; 0% of invalid inputs yield a packet at all.
- **SC-004**: A reviewer reading only the packet contract (schema or dataclass docstring) can identify the slot for each of the three Trijunction sources without reading any prose documentation.
- **SC-005**: Adding a hypothetical Falcon OCR adapter in a future slice requires zero changes to the packet contract — only the population logic for the existing Falcon OCR slot.
- **SC-006**: The four existing per-document artifact files remain byte-identical before and after running the assembler over a folder, regardless of logging level.
- **SC-007**: At default logging level the assembler writes zero files; at debug/verbose logging level it writes exactly one file (`evidence_packet.json`) into the per-document folder.
- **SC-008**: A persisted `evidence_packet.json` validates against the new `evidence_packet.schema.json`, and the per-document folder still validates against the amended `folder.schema.json` whether the file is present or absent.
- **SC-009**: For every `tests/stage1_vendor_identity/inv_*_easy/preprocess_output.json` present on disk, deterministic regex hints in `candidate_vendor_signals` achieve 100% recall on every literally-visible email address, `http(s)://` URL, US phone number, and EIN-shaped tax ID present in `document_text`. Precision is NOT gated — false positives are explicitly allowed and are flagged `unverified` so downstream voters can confirm.

## Assumptions

- The 003 preprocessing slice is merged on `main` and produces `preprocess_output.json` per the frozen v1.0.0 schema. (Confirmed: 003 PR #2 merged into `origin/main` on 2026-04-20.)
- The five-reserved-filename folder contract (`folder.schema.json`) is the current source of truth for what generated files belong in a per-document folder. This slice extends it via the `AMENDMENTS.md` process to legalize an optional sixth file (`evidence_packet.json`) written only at debug/verbose logging level.
- Stage 1 remains PDF-only, vendor-identity-only, edge-only, single-voter — this slice does not introduce model calls, cloud paths, or new corpus documents.
- Host Ollama and PyTorch are not required for this slice; assembly is deterministic Python over JSON, in line with the schemas/CLI/preprocessing slices already shipped.
- "Trijunction-ready" means **shape-ready**, not behavior-ready: stage 1 only wires PaddleOCR, but the packet exposes named slots for Falcon OCR and Falcon Perception so a future slice can populate them without breaking consumers.
- The packet is always assembled from one preprocess output at a time; multi-document or batch assembly is out of scope.
- "Logging set" in FR-015b is specifically the `dartwing_ocr` Python logger's effective level being `DEBUG` or lower. Library callers configure the logger directly; the CLI's `-v/--verbose` flag is just a shortcut that sets that logger level. No dedicated persistence flag, no persistence env var.

## Dependencies

- Hard upstream dependency: 003 (`preprocess_output.json` shape and per-document folder location).
- Hard upstream dependency: the frozen contract set at `contracts/stage1_vendor_identity/v1.0.0/`. Adding a new persisted artifact is a MINOR amendment (per `AMENDMENTS.md`); this slice bumps the contract set to `1.1.0` and places the new `evidence_packet.schema.json` plus the amended `folder.schema.json` under `contracts/stage1_vendor_identity/v1.1.0/`.
- Soft downstream dependency: 005 (single-voter edge extraction) will consume the packet; the API surface defined here is the contract that slice will program against.
- No new external libraries beyond what 001/002/003 already pulled in; assembly is JSON-in / JSON-or-Python-out.

## Out of Scope

- Calling any model (PaddleOCR-VL invocation already lives in 003; Falcon OCR/Perception are placeholder slots only).
- Producing or modifying `edge_extraction_output.json`, `routing_decision.json`, or `final_structured_payload.json`.
- Implementing actual logo/stamp/header/footer detection (that requires Falcon Perception, deferred).
- Changing the existing per-document folder layout for any artifact other than potentially adding the packet itself (governed by Q1).
- Multi-document orchestration, corpus-loop CLI behavior, or evaluation harness wiring.

## Resolved Clarifications

These three decisions were posed during /speckit.specify and answered before this draft was finalized. They are recorded here so /speckit.plan can pick up the rationale.

### Q1 — Persistence model: logging-triggered persistence *(scope/contract)*

**Decision**: In-memory by default; persist `evidence_packet.json` to the per-document folder only when the assembler is invoked at debug/verbose logging level. Implemented via a new `evidence_packet.schema.json` and an amendment to `folder.schema.json` that makes the file an **optional** generated artifact.

**Rationale**: Default-in-memory matches the documented intent that preprocess_output "provides the basis for a future Trijunction evidence packet" (`docs/.../schemas.md`) and avoids inflating the corpus folder for normal runs. The logging-triggered persistence path gives operators a way to reproduce voter inputs when debugging without making the file mandatory in CI or the harness's normal flow.

**Implementation impact**: see FR-015a/b/c above.

### Q2 — Candidate vendor signal depth: regex hints *(scope)*

**Decision**: Stage 1 surfaces deterministic regex hints for **email addresses, URLs, US phone numbers, and EIN-shaped tax IDs** in the `candidate_vendor_signals` section. Company-name and address candidate slots remain empty/`null`; those require Falcon Perception / layout heuristics that arrive in a later slice. Each populated hint is marked `unverified` so downstream voters know to confirm.

**Rationale**: Lightweight regex over `document_text` is essentially free, gives the stage 1 voter useful anchors to confirm, and stays out of the "wrong entity selection" failure category by deferring company-name and address inference (which need spatial reasoning).

**Implementation impact**: see FR-008 above.

### Q3 — CLI surface: new console script *(scope/UX)*

**Decision**: Ship a new console script `dartwing-evidence-packet <folder>` mirroring 003's `dartwing-preprocess`. Wired via `[project.scripts]` in `pyproject.toml`.

**Rationale**: Consistency with the established 003 CLI pattern, easy to script and test in isolation, and gives harness operators a clean "run just this stage" affordance.

**Implementation impact**: see FR-020 above.
