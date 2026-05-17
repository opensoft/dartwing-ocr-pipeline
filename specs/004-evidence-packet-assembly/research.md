# Phase 0 Research: Evidence Packet Assembly

**Feature**: 004-evidence-packet-assembly
**Date**: 2026-04-20
**Status**: Complete — all Technical Context unknowns resolved.

All five /speckit.clarify Q&A are already baked into the spec. This document
resolves the remaining technical-design choices needed before Phase 1.

---

## Decision 1 — Contract-set version bump: `1.1.0` (MINOR, additive)

**Decision**: The new contract version is `1.1.0`. Create
`contracts/stage1_vendor_identity/v1.1.0/` by copying `v1.0.0/` verbatim,
then apply the delta (add `evidence_packet.schema.json`; edit
`folder.schema.json` to list `evidence_packet.json` as an **optional**
reserved generated filename; edit `contract_set.json` to register the new
artifact). Append the entry to `AMENDMENTS.md`.

**Rationale**: `AMENDMENTS.md` step 1 classifies bumps as MAJOR (breaking),
MINOR (additive), or PATCH (non-behavioral). Legalizing a **new optional
generated file** and registering **one new artifact schema** is purely
additive — no existing artifact is invalidated, no enum narrowed, no field
removed. MINOR is the correct tier. All previously valid v1.0.0 folders and
artifacts remain valid under v1.1.0. The `preprocess_output.json` written by
003 (with `contract_set_version: "1.0.0"`) will continue to validate at
read-time inside the assembler, because the assembler loads its input
schema from either `v1.0.0/preprocess_output.schema.json` or
`v1.1.0/preprocess_output.schema.json` — their byte content is identical.

**Alternatives considered**:
- **PATCH (`1.0.1`)**: rejected. Adding a new artifact schema is a behavior
  change for consumers (`folder.schema.json` now permits an extra file), not
  a typo fix.
- **MAJOR (`2.0.0`)**: rejected. No breaking change; existing artifacts
  remain valid; the new file is optional.
- **Leave contracts at `1.0.0` and house the new schema elsewhere**:
  rejected. The constitution requires stable JSON contracts for stage 1
  artifacts; keeping the packet schema outside the versioned contract set
  would split the contract surface and violate §II.

**Implementation impact**: see FR-013, FR-015c, and the new version directory
in the Project Structure section of `plan.md`.

---

## Decision 2 — `line_index` semantics for regex-hint source references

**Problem**: Q5 clarified that each hint carries
`{document_text_offset, document_text_length, page_index, block_index,
line_index}`, all non-null. But `preprocess_output.json` stores per-page
`raw_ocr_lines[]` and per-page `blocks[]` as **siblings** — there is no
explicit block→line mapping in the v1.0.0 schema, and `document_text` is
built from `block.text` (not from `raw_ocr_line.text`). So "line_index"
cannot mean "index into `raw_ocr_lines`" without introducing a new
block↔line correlation step. We need a definition that is (a) deterministic,
(b) derivable purely from what the reading-order join already consumes, and
(c) useful to downstream voters.

**Decision**: `line_index` is the 0-based index of the newline-separated
sub-line **within the originating block's `text`** where the match starts.
Formally:

```
# Given a match at document_text offset D:
# 1. reverse-map D to (page_index, block_index) via the join bookkeeping.
# 2. compute the offset within block.text: B = D - block_start_offset.
# 3. line_index = block.text[:B].count("\n").
```

If `block.text` has no newlines (common for single-line layout blocks),
`line_index == 0`. This is a well-defined function of the preprocess output
alone and requires no new mapping tables.

**Rationale**: The join is the single source of truth for offsets; deriving
`line_index` from block-internal newlines keeps the reverse-mapping pure
and deterministic. Downstream voters that want to cross-reference against
`raw_ocr_lines[]` still have full `bbox` information via `block.bbox` plus
the match's character-range inside `block.text`; the assembler does not
have to invent a correlation that the v1.0.0 schema did not establish.

**Alternatives considered**:
- **Map to `raw_ocr_lines[]` by bbox intersection**: rejected. Requires
  synthetic geometry reasoning; non-deterministic when bboxes overlap;
  adds code complexity for no voter benefit this slice.
- **Set `line_index` to `null` when the block has no newlines**: rejected.
  Q5 explicitly requires all four source-reference fields to be non-null.
- **Define `line_index` as the 1-based ordinal across the whole page**:
  rejected. Less portable for voters reading block-scoped excerpts.

**Implementation impact**: `src/dartwing_ocr/evidence_packet/offset_mapping.py`
owns the reverse-mapping. The `evidence_packet.schema.json` makes
`line_index` `{"type": "integer", "minimum": 0}`.

---

## Decision 3 — Regex pattern choices

**Decision**: Ship exactly four named patterns, compiled once at import time:

| Field | Pattern | Notes |
|---|---|---|
| `email` | `[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}` | ASCII-only local + domain; no IDN, no quoted-local. Liberal enough for stage 1 corpus. |
| `website` (URL) | `\bhttps?://[A-Za-z0-9.\-]+(?:\.[A-Za-z]{2,})(?:/[\w\-./%?=&#]*)?\b` | Must start with `http(s)://`. Bare domains (`acme.com`) are **not** surfaced at this stage — domain-only detection is deferred to a later slice because it produces too many false positives on invoice numbers. |
| `us_phone` | `\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}` | North-American 10-digit. Optional parens around area code, optional `+1` prefix allowed via a leading optional group `(?:\+1[\s\-.]?)?`. |
| `ein` | `\b\d{2}-\d{7}\b` | US Employer ID strict 9-digit hyphenated form. Non-hyphenated 9-digits are rejected to avoid false positives on ZIP+4 and generic IDs. |

All four patterns are compiled with `re.IGNORECASE` where sensible (email,
URL) and used via `re.finditer` over `document_text`. Matches are emitted in
document order (ascending start offset); duplicates are preserved (Q4).

**Rationale**: Liberal but bounded. SC-009 grades recall on the easy bucket
with false positives explicitly allowed; each hint is stamped `unverified`
so the downstream voter confirms. Keeping the patterns small and
well-documented means they can be iterated on in a later slice without
touching the packet contract.

**Alternatives considered**:
- **Use a third-party library** (e.g. `phonenumbers`, `validators`):
  rejected. New dependency, nondeterministic locale behavior in some cases,
  and overkill for stage 1 hint surfacing.
- **International phone numbers**: deferred. The stage 1 corpus is US-invoice
  focused; adding E.164 handling is a premature generalization.
- **Bare-domain URL detection**: deferred (see above).
- **Regex for tax IDs beyond EIN (VAT, state tax ID)**: deferred. The
  `challenge_tags` vocabulary lists these but stage 1 corpus coverage
  doesn't require them; adding them here would inflate false-positive rate.

**Implementation impact**: `src/dartwing_ocr/evidence_packet/regex_hints.py`.

---

## Decision 4 — Reverse-mapping from `document_text` offsets to
(`page_index`, `block_index`, `line_index`)

**Decision**: Build an **offset index** alongside the reading-order join —
not a post-hoc re-parse. The assembler's `offset_mapping.py` rebuilds
`document_text` using the same algorithm as
`src/dartwing_ocr/preprocessing/document_text.py::join_document_text`
(pages sorted by `page_number`, blocks within each page sorted by
`reading_order`, joined with `"\n"` intra-page and `"\n\n"` inter-page),
while simultaneously recording a sorted list of `(block_start_offset,
block_end_offset, page_index, block_index)` tuples. Reverse mapping for a
regex match at offset `D` is a `bisect.bisect_right` lookup into the sorted
list.

**Invariant**: the rebuilt `document_text` MUST equal
`preprocess_output["document_text"]` byte-for-byte. The assembler asserts
this invariant before emitting any hint; mismatch raises
`PacketAssemblyError` (indicates that 003's `join_document_text` algorithm
drifted from this assembler's copy — a contract bug to be fixed in lockstep).

**Rationale**: Bisection keeps per-match lookup O(log N) in block count;
hints never exceed hundreds per document, so total overhead is trivial.
Rebuilding in-process instead of importing `join_document_text` directly
lets us record offsets without modifying 003's code (which treats the join
as an opaque string op). The byte-equality assertion is a cheap sentinel
that catches the one way this could silently go wrong — 003 changing its
separator constants without updating this slice.

**Alternatives considered**:
- **Import and monkey-patch `join_document_text`**: rejected. Violates
  module encapsulation; fragile across 003 refactors.
- **Refactor `join_document_text` in 003 to emit an offset index**:
  rejected. Cross-slice change for this slice's convenience; 003 is
  already shipped; the contract between slices is the JSON artifact, not
  Python helpers.
- **Linear scan per hint**: rejected. Simpler but wastes time for
  documents with many matches; bisect is a trivial stdlib import.

**Implementation impact**: `src/dartwing_ocr/evidence_packet/offset_mapping.py`.

---

## Decision 5 — Logging configuration and CLI verbosity mapping

**Decision**: The `dartwing_ocr.evidence_packet` module uses `logging.getLogger(__name__)`
(which resolves to the `dartwing_ocr` logger via namespace hierarchy).
The CLI at `cli.py`:

- accepts `-v/--verbose` (may be stacked, `-vv`, etc., but only the first
  `-v` matters for persistence — persistence is a boolean trigger, not a
  dial);
- when at least one `-v` is passed, calls `logging.getLogger("dartwing_ocr").setLevel(logging.DEBUG)`;
- otherwise leaves the logger at its inherited level (typically `WARNING`).

The assembler's persistence decision (`should_persist`) is evaluated **at
invocation time** by checking
`logging.getLogger("dartwing_ocr").isEnabledFor(logging.DEBUG)`. Library
callers that configure the logger to `DEBUG` themselves (e.g. via
`logging.basicConfig(level=logging.DEBUG)`) get identical behavior to the
CLI's `-v` — which is the whole point of Q1's answer.

**Rationale**: One source of truth (Python logging), predictable and
testable behavior, matches 003's CLI shape. No dedicated `--persist-packet`
flag, no env var.

**Alternatives considered**:
- **`--log-level DEBUG` flag instead of `-v`**: functionally equivalent;
  `-v` is more idiomatic for CLIs and shorter to type. Both could coexist
  but only one is needed for SC-007 testability.
- **Check `logging.DEBUG` against the **root** logger**: rejected. The
  `dartwing_ocr` namespace logger is the correct scope — testing
  fixtures can toggle just our logger without affecting pytest's global
  log capture.

**Implementation impact**: `src/dartwing_ocr/evidence_packet/cli.py` and
`assembler.py`.

---

## Decision 6 — Packet key ordering (canonical form)

**Decision**: Keys are inserted in a **fixed, documented order** at every
nesting level. Top-level order:

```
contract_set_version, document_id, source_file, page_count,
pages, reading_order, document_text, tables,
ingestion_sources, perceptual_observations, candidate_vendor_signals
```

Per-section key orders are declared in `data-model.md`. No `sort_keys=True`
normalization is applied — Q2's answer pins the serializer on
`sort_keys=False`, so the assembler owns ordering.

**Rationale**: Dict insertion order is stable in Python 3.7+; combined with
`sort_keys=False`, a single well-defined assembly path yields
byte-identical output across runs. `sort_keys=True` would also work for
determinism but would scramble human-readable order (e.g. putting
`candidate_vendor_signals` near the top because `c` < `d`), hurting
reviewability. Q2 explicitly chose the reviewability path.

**Alternatives considered**:
- `sort_keys=True`: rejected (Q2).
- JSON Canonical Form (RFC 8785): rejected. Overkill; no canonicalization
  consumer exists downstream; reviewability suffers.

**Implementation impact**: `src/dartwing_ocr/evidence_packet/assembler.py`
and its `sections/` helpers return ordered `dict` literals.

---

## Decision 7 — Reuse of 003's `write_atomic`

**Decision**: The evidence-packet persistence path **imports and reuses**
`dartwing_ocr.preprocessing.artifact.write_atomic` rather than duplicating
it. The only packet-specific wrapping is around schema validation (different
schema, different artifact filename).

**Rationale**: One serializer, one atomic-write strategy, one canonical
form across all stage 1 persisted artifacts. Any future tweak (e.g. switch
to `os.fdatasync`) happens in one place. Q2 explicitly anchored on 003's
convention.

**Alternatives considered**:
- Copy-paste `write_atomic` into `evidence_packet/serialization.py`:
  rejected. Two copies drift.
- Extract `write_atomic` into a shared `dartwing_ocr/io.py`: deferred.
  A larger refactor; we can do it if/when a third slice needs it. For now
  importing from the sibling module is the lowest-friction path and does
  not create a circular dependency (the evidence-packet module depends on
  the preprocessing module, not the other way round).

**Implementation impact**: `src/dartwing_ocr/evidence_packet/serialization.py`.

---

## Decision 8 — Assembler input surface: folder path vs. loaded dict

**Decision**: Ship **two** public functions, both in `evidence_packet/__init__.py`:

```python
def assemble_from_folder(folder: Path) -> dict: ...
def assemble_from_preprocess(preprocess_output: dict, *, document_id: str | None = None) -> dict: ...
```

`assemble_from_folder` is the CLI path and the primary public entry. It
validates the folder, reads `preprocess_output.json`, validates the input
against `v1.x.y/preprocess_output.schema.json`, calls
`assemble_from_preprocess`, and then persists if the logger is at DEBUG.

`assemble_from_preprocess` is the library path for 005's voter (and for
testing). It expects a dict that has already been loaded; it still
validates against the input schema and still validates the output packet,
but does no I/O.

**Rationale**: 005's single-voter slice will want to call this in-process
without an extra file read. Splitting the entry points keeps each one
small and testable in isolation. Both funnel through the same
`assembler.py` core.

**Alternatives considered**:
- Single `assemble(source)` taking `Path | dict`: rejected. Type ambiguity
  hurts both type checkers and readers.
- Expose only `assemble_from_folder`: rejected. 005's voter would need to
  re-read the file it already has in memory.

**Implementation impact**: `src/dartwing_ocr/evidence_packet/__init__.py`
and `assembler.py`.

---

## Decision 9 — Error taxonomy

**Decision**: Three typed errors, all subclasses of `PacketAssemblyError`:

- `PreprocessInputMissing` — `preprocess_output.json` not found / unreadable / not JSON (CLI exit 2).
- `PreprocessInputInvalid` — file parses but fails `preprocess_output.schema.json` validation (CLI exit 3).
- `PacketInvalid` — the *assembled* packet fails `evidence_packet.schema.json` validation. This is a programmer bug; exits 4; should never happen in shipped code. Tests assert it CAN be raised for a deliberately corrupted assembler path.

Folder-level issues (missing folder, DEBUG-mode write to a read-only
folder) are raised as `OSError`/`FileNotFoundError` bubbling up — matched
by the CLI's top-level handler and mapped to exit 2 (input side) or
exit 5 (persistence side).

**Rationale**: Mirrors 003's error philosophy (typed pipeline errors, CLI
maps them to stable exit codes). Keeps library callers' `try/except`
narrow.

**Alternatives considered**:
- One blanket `PacketAssemblyError`: rejected. Callers can't distinguish
  input bugs from assembler bugs without parsing messages.
- Reuse 003's error classes directly: rejected. Different semantic layer;
  shared exit-code discipline is enough.

**Implementation impact**: `src/dartwing_ocr/evidence_packet/errors.py`;
CLI exit-code table in `contracts/cli-contract.md`.

---

## Open questions: none

All Technical Context fields in `plan.md` are resolved. `/speckit.plan` may
proceed to Phase 1.
