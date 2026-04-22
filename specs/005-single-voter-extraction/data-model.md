# Phase 1 Data Model — Single-Voter Edge Extraction

Internal-only data shapes (nothing in this file amends a frozen contract). The on-disk artifact
shape is pinned by `contracts/stage1_vendor_identity/v1.0.0/edge_extraction_output.schema.json`
and is NOT redefined here — only the in-memory types the extractor uses between "read input" and
"write output", plus the reconciliation state machine.

## Entity: `PreprocessPacket` (read-only input, internal view)

Loaded from `preprocess_output.json`. Validated against
`contracts/stage1_vendor_identity/v1.0.0/preprocess_output.schema.json` before use.

**Fields the extractor consumes**:
- `document_id: str` — copied verbatim into the output (FR-004).
- `contract_set_version: str` — must be `"1.0.0"` (FR-003).
- `pages: list[Page]` where `Page` supplies `blocks: list[Block]` and `raw_ocr_lines: list[OcrLine]`.
- `ingestion_sources: IngestionSources` — surfaced into the prompt so the model knows which
  upstream signals are present vs. not-implemented.
- `warnings: list[str]` — if non-empty, the extractor records input-side partiality in its own
  `extraction_notes` (FR-023).

**Derived**: `evidence_index: set[str]` — the set of every `block_id` and `line_id` the packet
published. Used as the ground-truth filter for model-proposed evidence IDs.

## Entity: `VoterConfig` (loaded YAML → pydantic)

Fields per R-005 in research.md. Pydantic model with `extra = "forbid"` so unknown keys are loud.

```python
class OllamaCallConfig(BaseModel):
    model_tag: str
    timeout_seconds: float = 180.0
    connect_timeout_seconds: float = 10.0

class SamplingConfig(BaseModel):
    temperature: float = 0.0
    seed: int | None = 42
    top_p: float | None = None
    top_k: int | None = None

class PromptConfig(BaseModel):
    template_path: str            # relative to the voter-config file
    max_output_tokens: int = 2048
    format: Literal["json"] | None = "json"

class ReconciliationConfig(BaseModel):
    ungrounded_confidence_cap: float = 0.30  # FR-011 / R-003

class ModelRuntimeConfig(BaseModel):        # copied verbatim into artifact
    provider: str
    model_name: str
    model_version: str
    runtime: str

class VoterConfig(BaseModel):
    voter_id: str
    voter_role: Literal["primary_extractor", "secondary_extractor", "verifier"]
    consensus_mode: Literal["single_voter_baseline"]
    model_runtime: ModelRuntimeConfig
    ollama: OllamaCallConfig
    sampling: SamplingConfig
    prompt: PromptConfig
    reconciliation: ReconciliationConfig
```

**Validation rules** (beyond field types):
- In stage 1, `voter_role` MUST be `"primary_extractor"`. Other enum values are reserved but invalid
  under the current `single_voter_baseline` consensus mode (FR-006).
- `consensus_mode` MUST be `"single_voter_baseline"` (FR-006 and schema enum).
- `ungrounded_confidence_cap` MUST be in `[0.0, 1.0]`.
- `timeout_seconds` MUST be positive.

## Entity: `ModelResponse` (raw then parsed)

Two internal forms:
- `RawModelResponse`: the literal response body string from Ollama, plus metadata (`duration_ms`,
  `model` echoed by the server, `done` flag).
- `ParsedModelResponse`: a nested-dict structure produced by the parser. No schema validation yet —
  the model can return anything shaped; reconciliation is responsible for coercing it.

The parser emits a `repair_trail: list[str]` — non-empty if any repair step fired, which feeds into
`warnings` and forces `status="partial"` (R-007).

## Entity: `ExtractionArtifact` (in-memory, prior to write)

A `TypedDict` (or pydantic `BaseModel`) mirroring the frozen
`edge_extraction_output.schema.json`. Not redefined here; see the schema. The assembler in
`artifact.py` validates this dict against the JSON Schema BEFORE the file is written (FR-002).

## Reconciliation State Machine

The reconciler is a pure function:

```python
def reconcile(
    packet: PreprocessPacket,
    parsed: ParsedModelResponse,
    config: VoterConfig,
    now: datetime,
    pipeline_version: str,
    repair_trail: list[str],
) -> ExtractionArtifact:
    ...
```

No I/O, no Ollama, no file writes. Deterministic given the inputs (R-013).

### Step 1 — Metadata assembly

Populate `contract_set_version = "1.0.0"`, `document_id = packet.document_id`, `pipeline_version`,
`processed_at = now.isoformat()`, `model_runtime` from `config.model_runtime`, `vote_metadata` from
`config.{voter_id, voter_role, consensus_mode}`.

### Step 2 — Model-proposed field extraction

Walk the parsed response for every required schema field. For each:
1. If the key is absent → default to `{value: null, confidence: 0.0, evidence: []}` (or
   `{value: null, currency: null, confidence: 0.0, evidence: []}` for `total_amount`). Append
   a warning naming the defaulted field (FR-016). Mark "soft failure" bit true.
2. If the key is present → coerce types (string-or-null for scalars, number-or-null for
   `total_amount.value`, string-or-null for `total_amount.currency`). If the model emitted a type
   that cannot be coerced (e.g., an object where a string is expected), default as in (1) and warn.

### Step 3 — Evidence reconciliation

For every field's `evidence` array:
1. Check each proposed ID matches the regex `^p\d+_[bl]\d+$`. Drop non-matching and warn (FR-010).
2. Check each surviving ID is in `packet.evidence_index`. Drop unresolved and warn (FR-010). Mark
   "soft failure" bit true.
3. Deduplicate; preserve first-occurrence order for determinism.

### Step 4 — Ungrounded-confidence cap (FR-011 / R-003)

For every field where `len(evidence) == 0` after Step 3:
- `field.confidence = min(field.confidence, config.reconciliation.ungrounded_confidence_cap)`.
- Model-proposed `value` is retained. Only `confidence` is clipped.

Applied to: every `value_confidence_evidence` field in `vendor_candidate.*` and
`invoice_header_fields.*`, plus `total_amount`, plus `document_type.confidence`.

### Step 5 — Company-name provenance override (FR-012, FR-013 / US3)

If `company_name.evidence == []` after Step 3:
- Deterministically set `company_name.present = false`, `company_name.inferred = true`, regardless
  of model claim (FR-012).
- Append an `extraction_notes` entry explaining the override (US3 AC #3).

If `company_name.evidence != []` (has at least one grounded ID):
- `company_name.present = true`, `company_name.inferred = false`.

Final guard (FR-013): `(present=true, inferred=true)` and `(present=false, inferred=false)` are
both explicit programmer-check invariants. A final assertion raises an internal error if violated
(code should never produce either; the assertion is belt-and-braces).

### Step 6 — `document_type.value` coercion (FR-009)

Regardless of model claim, set `document_type.value = "invoice"` (schema enum forces it). If the
model claimed something else (e.g., `"receipt"` or `"statement"`), lower `document_type.confidence`
proportionally and append an `extraction_notes` entry describing the mismatch (spec Edge Cases).

### Step 7 — Status derivation (R-008 truth table)

Using the bits accumulated above:
- If no defaulting, no evidence drops, no repairs, and at least one grounded evidence anywhere in
  the output → `status = "success"`. `warnings` remains empty (modulo FR-023 input-side warnings).
- If any soft-failure bit is set (JSON repair, evidence drop, sub-field default) AND there IS some
  grounded evidence somewhere in the artifact → `status = "partial"`. `warnings` is non-empty.
- If the extractor reached reconciliation but every `value` is null and every `evidence` is empty →
  `status = "failure"`. `warnings` explains.

Hard-failure cases (unrepairable response, Ollama unreachable, contract drift) NEVER reach this
function; they exit non-zero upstream per R-011/R-012.

### Step 8 — Warnings + extraction_notes normalization

- Warnings: preserve first-seen order; deduplicate (drop later duplicates while keeping the first
  occurrence); ensure every entry is a non-empty string. Per FR-010, the same ordering and
  deduplication rule applies uniformly to every `evidence` array, `warnings`, and `extraction_notes`
  so SC-009's reconciliation-determinism claim holds byte-exactly modulo `processed_at` /
  `pipeline_version`.
- Extraction notes: same normalization, separate channel. Notes are descriptive (e.g., "company_name
  override: no explicit evidence in packet"); warnings are condition-signals (e.g., "sub-field
  defaulted: vendor_candidate.tax_ids.vat_id").

If `packet.warnings` was non-empty on the input side, prepend an entry to `extraction_notes`
(FR-023): `"input preprocessing was partial: {N} warnings"`.

### Post-conditions (asserted before write)

- Artifact validates against `edge_extraction_output.schema.json`.
- `status in {"success", "partial", "failure"}`.
- `company_name.present XOR company_name.inferred == True` (exactly one is true).
- Every `evidence` array contains only IDs in `packet.evidence_index`.
- No `value` is `""` (empty strings are FR-007 / FR-008 violations; use `null`).
