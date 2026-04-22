# Failure Handling Checklist: Evidence Packet Assembly

**Purpose**: Release-gate validation that the spec defines every failure
path the assembler can encounter — input missing, input invalid, source
sub-source failures, read-only folders, assembler bugs — with unambiguous,
measurable behavior. Items validate the requirements, not the
implementation.
**Created**: 2026-04-20
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + contract owner)

## Input Absence

- [x] CHK078 Is the behavior specified when `<folder>` does not exist? [Completeness, Spec §FR-017]
- [x] CHK079 Is the behavior specified when `<folder>` exists but has no `preprocess_output.json`? [Completeness, Spec §FR-017 §Edge Cases]
- [x] CHK080 Is the behavior specified when `preprocess_output.json` exists but is unreadable (permission / I/O error)? [Gap — spec currently implies but does not spell out this sub-case]
- [x] CHK081 Is the CLI exit code mapped for all three input-absence variants (single `input_missing` kind with exit 2)? [Clarity, Spec §CLI Contract Exit Codes]
- [x] CHK082 Is the library behavior specified for the same three variants (typed exception: `PreprocessInputMissing`)? [Clarity, Spec §Research Decision 9]

## Input Malformation / Schema Invalidity

- [x] CHK083 Is the behavior specified when `preprocess_output.json` is not valid JSON? [Completeness, Spec §FR-017]
- [x] CHK084 Is the behavior specified when `preprocess_output.json` parses but fails schema validation? [Completeness, Spec §FR-003 §FR-017]
- [x] CHK085 Is the CLI exit code mapped for schema-invalid input (`input_invalid`, exit 3)? [Clarity, Spec §CLI Contract]
- [x] CHK086 Is the rule "do NOT produce a packet on schema-invalid input, even a best-effort one" stated? [Completeness, Spec §FR-017 §Edge Cases]
- [x] CHK087 Are the error-message requirements stated (identify which precondition failed) so operators can act without reading tracebacks? [Clarity, Spec §FR-017]

## Valid Input, Degraded Sub-Sources

- [x] CHK088 Is the behavior specified when `ingestion_sources.paddleocr_vl.status == "failure"` but the file is otherwise valid (assembler MUST still produce a packet; slot carries the failure status)? [Completeness, Spec §FR-018 §Edge Cases]
- [x] CHK089 Is the behavior specified when multiple sub-sources are in mixed states (one success, one failure, one not_implemented)? [Completeness, Spec §FR-018]
- [x] CHK090 Is the rule "affected sections carry the failure status, never fabricated data, never missing keys" stated? [Clarity, Spec §FR-018 §Edge Cases]
- [x] CHK091 Is the `perceptual_observations.status` mapping rule (mirror `falcon_perception.status`) stated unambiguously for the stage-1 case AND the future-populated case? [Clarity, Spec §Data Model]

## Zero / Empty Edge Cases

- [x] CHK092 Is the behavior specified for a zero-page document (all top-level slots present, `pages == []`, `reading_order == []`, `document_text == ""`, all signal lists `[]`)? [Completeness, Spec §Edge Cases]
- [x] CHK093 Is the behavior specified when `document_text` is empty but `pages[].blocks` has content (assembler preserves both as-is; regex signals yield empty lists)? [Completeness, Spec §Edge Cases]
- [x] CHK094 Is the behavior specified for a fully-blank document (quality flags + empty sections; downstream voters detect via empty arrays, not missing keys)? [Clarity, Spec §Edge Cases]
- [x] CHK095 Is the behavior specified when tables are malformed/partial in the input (passthrough, no re-interpretation)? [Consistency, Spec §Edge Cases §FR-006]

## Persistence Path Failures

- [x] CHK096 Is the behavior specified when the logger is at DEBUG but the folder is read-only (emit clear error, non-zero exit; in-memory packet is still valid and returned to library callers)? [Completeness, Spec §Edge Cases]
- [x] CHK097 Is the CLI exit code mapped for persistence failure (`persistence_failed`, exit 5)? [Clarity, Spec §CLI Contract]
- [x] CHK098 Is the behavior specified when disk is full / atomic rename fails mid-write (no partial file on disk; original file — if any — is preserved)? [Completeness, Spec §FR-015b §Research Decision 7]
- [x] CHK099 Is the rule "library callers still receive the validated packet even when persistence fails" stated (persistence failure is not an assembly failure)? [Clarity, Spec §Edge Cases]

## Assembler / Output-Validation Failures

- [x] CHK100 Is the behavior specified when the assembled packet fails its own output schema (a programmer bug)? [Completeness, Spec §FR-015a §Research Decision 9]
- [x] CHK101 Is the CLI exit code mapped for output-validation failure (`packet_invalid`, exit 4)? [Clarity, Spec §CLI Contract]
- [x] CHK102 Is the rule "no partial / schema-invalid packet is returned to library callers OR written to disk" stated? [Completeness, Spec §FR-015a §Clarifications Q3]
- [x] CHK103 Is the `PacketInvalid` exception taxonomy placement (subclass of `PacketAssemblyError`) specified so callers can catch the family? [Clarity, Spec §Research Decision 9]

## Re-run / Overwrite Semantics

- [x] CHK104 Is the behavior specified for re-running with a pre-existing `evidence_packet.json` in the folder (overwrite with byte-identical content)? [Completeness, Spec §Edge Cases]
- [x] CHK105 Is the behavior specified for re-running at a different logger level (DEBUG → default: file persists from prior run, nothing is deleted; default → DEBUG: file is created)? [Gap — implicit; worth stating so future tooling does not "clean up" stale files]
- [x] CHK106 Is the atomic-write guarantee stated so a crash mid-rename never leaves a truncated `evidence_packet.json`? [Completeness, Spec §Research Decision 7]

## Read-Side Tolerances

- [x] CHK107 Is the behavior specified when `preprocess_output.json` declares `contract_set_version: "1.0.0"` but the assembler runs under `v1.1.0` (accepted — schemas are byte-identical for `preprocess_output`)? [Clarity, Spec §Research Decision 1]
- [x] CHK108 Is the behavior specified if a future `preprocess_output.json` declares a contract version the assembler does not recognize? [Gap — should the assembler warn / fail fast / pass through?]
- [x] CHK109 Is the behavior specified when the input `document_id` does not match the folder basename (respect input, or fail, or normalize)? [Gap — affects `assemble_from_preprocess`'s `document_id` parameter]

## Observability of Failures

- [x] CHK110 Does the spec require that every error path emit a structured JSON object on stdout (matching 003's CLI shape) so orchestrators can parse outcomes without regex? [Completeness, Spec §CLI Contract §FR-017]
- [x] CHK111 Does the spec distinguish between operator-actionable errors (input missing/invalid, folder read-only) and programmer-actionable errors (packet_invalid)? [Clarity, Spec §Research Decision 9]
- [x] CHK112 Is the `kind` discriminator vocabulary closed (`ok` / `input_missing` / `input_invalid` / `packet_invalid` / `persistence_failed` / `unexpected`) with no silent introduction of new kinds? [Consistency, Spec §CLI Contract]

## Notes

- Check items off as completed: `[x]`
- Flag unresolved `[Gap]` / `[Ambiguity]` / `[Conflict]` items for spec amendment before implementation begins
- Any `[Gap]` item here should either be filled in the spec or consciously deferred with a pointer to the follow-up slice
