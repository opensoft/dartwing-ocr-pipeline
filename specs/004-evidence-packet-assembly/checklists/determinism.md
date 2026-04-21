# Determinism Checklist: Evidence Packet Assembly

**Purpose**: Release-gate validation that every source of nondeterminism
is either eliminated by spec requirement or explicitly out of scope. Every
item validates that the requirements themselves pin down deterministic
behavior; nothing here tests the implementation.
**Created**: 2026-04-20
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + contract owner)

## Byte-Identical Output

- [x] CHK045 Is byte-identical re-assembly specified as a hard requirement, not a soft goal? [Completeness, Spec §FR-011 §SC-002]
- [x] CHK046 Is the number of repeated runs that must produce identical output quantified (e.g. ≥10 consecutive)? [Measurability, Spec §SC-002]
- [x] CHK047 Is the canonical serialization form pinned (`json.dump(..., ensure_ascii=False, indent=2, sort_keys=False)`, no trailing newline, atomic rename)? [Clarity, Spec §FR-011 §Clarifications Q2]
- [x] CHK048 Is the rule "reuse 003's `write_atomic` helper" stated so two incompatible serializers cannot coexist? [Consistency, Spec §Research Decision 7]
- [x] CHK049 Is the key-ordering strategy specified as deterministic insertion order (not alphabetical / not `sort_keys=True`)? [Clarity, Spec §Research Decision 6]

## Forbidden Nondeterministic Content

- [x] CHK050 Does the spec forbid wall-clock timestamps inside the packet payload? [Completeness, Spec §FR-012]
- [x] CHK051 Does the spec forbid run IDs / UUIDs inside the packet payload? [Completeness, Spec §FR-012]
- [x] CHK052 Does the spec forbid process-state values (PID, hostname, cwd) inside the packet payload? [Completeness, Spec §FR-012]
- [x] CHK053 Does the spec forbid randomness (`random.*`, `os.urandom`, etc.) in assembly? [Gap — implicit in FR-011/FR-012; make explicit]
- [x] CHK054 Is the rule "any such metadata — if needed at all — lives in CLI logs, not the artifact payload" stated? [Clarity, Spec §FR-012]

## Deterministic Input Handling

- [x] CHK055 Is the input-loading path specified as "read `preprocess_output.json` from `<folder>`" with no filesystem ordering dependency? [Clarity, Spec §FR-002 §FR-019]
- [x] CHK056 Is the `pages[]` ordering strategy specified (sort by `page_number` ascending, independent of source-file order)? [Clarity, Spec §Data Model]
- [x] CHK057 Is the within-page `blocks[]` ordering strategy specified (sort by `reading_order` ascending)? [Clarity, Spec §Data Model]
- [x] CHK058 Is the `tables[]` ordering strategy specified (passthrough of 003's order, not re-sorted)? [Consistency, Spec §FR-006]

## Deterministic Derivations

- [x] CHK059 Is the `reading_order[]` top-level list's construction algorithm spelled out (pages ascending by `page_number`; within-page blocks ascending by `reading_order`; flattened; `block_id` strings)? [Clarity, Spec §Data Model]
- [x] CHK060 Is the `document_text` source specified as a byte-for-byte copy of `preprocess_output["document_text"]` (not a fresh re-join)? [Clarity, Spec §Data Model Invariants]
- [x] CHK061 Is the offset-index algorithm (rebuild `document_text` alongside a `(block_start, block_end, page_index, block_index)` list) specified with the equality check against the passthrough? [Clarity, Spec §Research Decision 4]
- [x] CHK062 Is the reverse-mapping's bisect strategy (or equivalent O(log N) lookup) specified so large documents do not silently fall back to nondeterministic tie-breakers? [Measurability, Spec §Research Decision 4]

## Regex-Hint Determinism

- [x] CHK063 Is the regex-match iteration strategy specified as "in document order, ascending start offset" (rules out nondeterministic iterator orderings)? [Clarity, Spec §FR-008 §Clarifications Q4]
- [x] CHK064 Is the duplicate-handling rule pinned ("one entry per occurrence, no dedup, no sort")? [Clarity, Spec §Clarifications Q4]
- [x] CHK065 Are the four regex patterns defined as frozen string literals (no external pattern loading, no runtime composition)? [Clarity, Spec §Research Decision 3]
- [x] CHK066 Are regex flags (e.g. `IGNORECASE`) explicitly stated per pattern, not "compiler default"? [Clarity, Spec §Research Decision 3]
- [x] CHK067 Is the rule "the assembler does not adjudicate false positives" stated so determinism is not broken by post-filters that depend on content heuristics? [Consistency, Spec §FR-008 §Edge Cases]

## Logging & Persistence Determinism

- [x] CHK068 Is the persistence trigger specified as a single predicate (`ledgerlinc_ocr` logger at `DEBUG`)? [Clarity, Spec §Clarifications Q1 §FR-015b]
- [x] CHK069 Is the rule "repeated DEBUG-level runs produce byte-identical `evidence_packet.json` on disk" stated, even though mtime may differ? [Clarity, Spec §CLI Contract §Determinism]
- [x] CHK070 Is the rule "re-running overwrites the file with identical bytes" stated (vs. appending, vs. failing on exist)? [Clarity, Spec §Edge Cases]
- [x] CHK071 Is there a rule against logging values that are themselves written into the packet (e.g. timing values leaking from logs into payload)? [Gap — implicit in FR-012; make explicit]

## Environmental Independence

- [x] CHK072 Is the spec explicit that assembly output does not depend on Python hash randomization, locale, or filesystem case-sensitivity? [Gap; Measurability]
- [x] CHK073 Is the spec explicit that assembly does not depend on network state, host clock, or any env var? [Completeness, Spec §FR-011 §Dependencies]
- [x] CHK074 Is the spec explicit that assembly output does not depend on GPU availability, Ollama reachability, or any external service? [Consistency, Spec §Dependencies §Out of Scope]

## Measurability

- [x] CHK075 Is the success criterion "ten consecutive runs produce ten byte-identical outputs" stated as a testable SC? [Measurability, Spec §SC-002]
- [x] CHK076 Is the criterion "four existing artifacts remain byte-identical before and after" stated as a testable SC? [Measurability, Spec §SC-006]
- [x] CHK077 Is the criterion "zero files written at default logger level; exactly one at DEBUG" stated as a testable SC? [Measurability, Spec §SC-007]

## Notes

- Check items off as completed: `[x]`
- Flag unresolved `[Gap]` / `[Ambiguity]` / `[Conflict]` items for spec amendment before implementation begins
- Determinism is a **hard** requirement; any item here left ambiguous must be resolved before merging the feature PR
