# Data Model: Evidence Packet

**Feature**: 004-evidence-packet-assembly
**Contract version**: `1.1.0` (pending amendment; see `contracts/stage1_vendor_identity/AMENDMENTS.md`)
**Schema**: `contracts/stage1_vendor_identity/v1.1.0/evidence_packet.schema.json` (delivered in Phase 2)

This document is the narrative counterpart to the machine-readable schema.
It describes every top-level section of the packet, the key order, the
empty/present semantics, and the relationship to `preprocess_output.json`.
It is authoritative for the Python dict shape the assembler emits; the
JSON Schema in Phase 2 is generated to match.

---

## Packet root (fixed key order)

```json
{
  "contract_set_version": "1.1.0",
  "document_id": "inv_001",
  "source_file": "source.pdf",
  "page_count": 1,
  "pages": [ /* passthrough — see below */ ],
  "reading_order": [ /* flattened block_id list */ ],
  "document_text": "…",
  "tables": [ /* passthrough */ ],
  "ingestion_sources": { /* three typed slots */ },
  "perceptual_observations": { /* stage 1 = empty, not_implemented */ },
  "candidate_vendor_signals": { /* regex hints + null company/address */ }
}
```

### `contract_set_version`
- Type: `string` matching `^\d+\.\d+\.\d+$`.
- Value in stage 1: `"1.1.0"`. Not inherited from the input — the packet
  stamps the **contract set it belongs to**, not the one the input declared.
  See FR-013.

### `document_id`, `source_file`, `page_count`
- Passthrough from `preprocess_output.json`. Same types, same validation
  rules as v1.0.0 `preprocess_output.schema.json`.

### `pages[]`
- Passthrough. Each page is the exact `page` object from
  `preprocess_output.json` — `page_number`, `width`, `height`,
  `rotation_detected`, `blocks[]`, `raw_ocr_lines[]`. The assembler does
  not re-order, re-index, or enrich these. Reason: voters must see the
  same layout 003 emitted; any filtering would be a business decision.

### `reading_order[]`
- Type: flat array of `block_id` strings (e.g. `["p1_b1","p1_b2","p2_b1"]`).
- Order: pages ascending by `page_number`; within a page, blocks ascending
  by `reading_order`. Identical ordering to the `document_text` join.
- Purpose: gives voters a single linear sequence they can consult without
  re-implementing the join. SC-004 expects a reviewer to read the packet
  contract and identify "which block comes next" without prose docs.
- Empty list permitted (zero-page documents). Never `null`.

### `document_text`
- Byte-identical to `preprocess_output["document_text"]`. Passthrough.
- Rationale for carrying it explicitly (not just computing from `pages[]`):
  it is the canonical anchor for `document_text_offset` references in
  `candidate_vendor_signals`. Voters consuming a subset of the packet
  must not have to re-join.

### `tables[]`
- Passthrough. No re-interpretation (FR-010, FR-018).

### `ingestion_sources` (Trijunction slot block)

```json
{
  "paddleocr_vl": { "enabled": true,  "status": "success",         "payload": { "kind": "structural" } },
  "falcon_ocr":   { "enabled": false, "status": "not_implemented", "payload": null },
  "falcon_perception": { "enabled": false, "status": "not_implemented", "payload": null }
}
```

- All three keys are **always present** (US2 AC#1).
- `enabled` and `status` mirror `preprocess_output.ingestion_sources[*].enabled/status`.
- `payload` is typed:
  - For `paddleocr_vl`: `{"kind": "structural"}` when `status == "success"` — a sentinel object. The actual PaddleOCR data is already surfaced via `pages[]`, `reading_order`, `document_text`, and `tables[]` above; `payload` here is the forward-compat shape where future PaddleOCR-specific data (e.g. raw layout predictions) could live.
  - For `falcon_ocr`: `null` in stage 1. Future payload shape: `{"kind": "text_plus_spam_gate", "text": "...", "spam_gate": {"flagged": bool, "reason": string|null}}`.
  - For `falcon_perception`: `null` in stage 1. Future payload shape: `{"kind": "perceptual", "logos": [...], "stamps": [...], "header_candidates": [...], "footer_candidates": [...]}`.
- When `status` is `failure` or `not_implemented`, `payload` MUST be `null` (FR-014 null discipline). When `status` is `success` and the source is `paddleocr_vl`, `payload` is the sentinel `{"kind": "structural"}`.

### `perceptual_observations` (single section, not per-source)

```json
{
  "status": "not_implemented",
  "logos": [],
  "stamps": [],
  "header_candidates": [],
  "footer_candidates": []
}
```

- Status mirrors `ingestion_sources.falcon_perception.status` (i.e. the
  Trijunction source that would populate this section). Stage 1:
  `not_implemented`.
- All four arrays are empty `[]` in stage 1, never `null`, never missing
  (FR-014).
- Rationale: voters that gate on "are there logos?" check array length;
  forward-compatibility means the gate code does not need to change when
  Falcon Perception ships.

### `candidate_vendor_signals`

```json
{
  "company_name": null,
  "addresses": [],
  "emails": [ /* hint objects */ ],
  "websites": [ /* hint objects */ ],
  "phones": [ /* hint objects */ ],
  "tax_ids": [ /* hint objects; only EIN-shaped hits in stage 1 */ ]
}
```

- `company_name` is `null` in stage 1 (Q2; FR-008). The key is ALWAYS
  present. Future slices may replace `null` with a candidate object.
- `addresses[]` is `[]` in stage 1. Never `null`, never missing. Future
  slices may populate.
- `emails`, `websites`, `phones`, `tax_ids` are lists of **hint objects**
  (shape below). Matches are emitted in **document order** (ascending
  `document_text_offset`), duplicates preserved, no dedup, no sorting.
- Each hint object:

  ```json
  {
    "value": "accounts@acme.com",
    "document_text_offset": 123,
    "document_text_length": 19,
    "page_index": 0,
    "block_index": 2,
    "line_index": 0,
    "provenance": "unverified"
  }
  ```

  - `value`: the exact substring from `document_text` at `[offset, offset+length)`. The assembler MUST assert `document_text[offset:offset+length] == value` before emitting.
  - `document_text_offset`, `document_text_length`: integers ≥ 0.
  - `page_index`: **0-based** index into the sorted `pages[]` array (i.e. `pages[page_index].page_number` may not equal `page_index + 1` if the input is non-contiguous, though 003 always emits contiguous 1-based `page_number`). Non-null.
  - `block_index`: 0-based index into that page's `blocks[]` (sorted by `reading_order`). Non-null.
  - `line_index`: 0-based line within the originating block's `text`, computed as `block_text_before_match.count("\n")`. Non-null. Always `0` when the block has no newlines.
  - `provenance`: literal string `"unverified"` in stage 1. Future values might include `"voter_confirmed"` or `"layout_confirmed"`; the enum is **open** at the schema level (`string`) to avoid breaking changes when new values land, but stage 1 writers only ever emit `"unverified"`.

---

## Invariants (enforced by the assembler)

1. **Byte-identical `document_text`**: `packet["document_text"] == preprocess_output["document_text"]`. Raises `PacketAssemblyError` on mismatch.
2. **Regex hint offset correctness**: for every hint, `packet["document_text"][offset:offset+length] == value`. Raises `PacketAssemblyError` on mismatch.
3. **Reading-order faithfulness**: `reading_order` is exactly the flattened `block_id` sequence from the join. Raises `PacketAssemblyError` on mismatch.
4. **Key ordering**: every dict literal inserts keys in the documented order. Tests use `list(d.keys()) == [...]` rather than set comparisons.
5. **Null discipline** (FR-014): scalars that can be absent are `null`; lists that can be absent are `[]`; empty strings are never used as a null sentinel.
6. **No voter/model/prompt strings**: the packet contains no key or value that names a specific model, voter, prompt template, or token budget (FR-009). Lint test: recursively scan the assembled dict for banned substrings (`"prompt"`, `"voter_"`, model names).
7. **No wall-clock content** (FR-012): the packet payload contains no value derived from `datetime.now()`, `time.time()`, `uuid.uuid4()`, or any process-state source. Lint test: the recursive scan also rejects ISO-8601 timestamps and UUID-shaped strings.
8. **Schema validation always** (FR-015a, Q3): both the input (`preprocess_output.schema.json`) and the output (`evidence_packet.schema.json`) are validated. Validation happens on the fully-assembled dict; failure raises `PacketInvalid`.

---

## Relationship to `preprocess_output.json`

Every field in the packet is either (a) a passthrough from preprocess
output, (b) a passthrough with a fixed wrapper (ingestion_sources), (c) a
deterministic derivation from preprocess output (reading_order, candidate
regex hints, offset mappings), or (d) a constant ("not_implemented"
slots). The packet never introduces information not present in the input.
This is the structural guarantee behind the "no business inference" rule
in FR-002 and SC-003.

---

## Forward-compatibility strategy

When Falcon OCR and Falcon Perception land:

- Their `ingestion_sources.<source>.status` flips from `not_implemented` to `success`/`failure`. Their `payload` becomes non-null.
- `perceptual_observations.status` flips from `not_implemented` to mirror `falcon_perception.status`; the four arrays get populated.
- `candidate_vendor_signals.company_name` and `addresses` become non-`null`/non-empty when the layout-aware heuristics land.

**None of those landing events require changing the packet key set, key
order, or types.** They flip flags and populate previously-empty slots.
That is the entire rationale for the shape locked in this slice (US2 AC#2,
SC-005).

---

## State transitions

The packet itself is a stateless snapshot — there are no transitions on an
individual packet object. The only "state" is which Trijunction sources
are populated, and that is a function of the input `preprocess_output.json`,
not of the packet's age.
