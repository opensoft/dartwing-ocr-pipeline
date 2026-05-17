# Data Model: 009-final-payload

Internal (in-memory) types used by `src/dartwing_ocr/assembler/`. These are implementation
detail; the authoritative on-disk shape is `contracts/stage1_vendor_identity/v1.0.0/
final_structured_payload.schema.json`.

## Entities

### 1. `Invocation` (`assembler/pipeline.py`)

The single struct passed into the assembler from the CLI or an importable caller.

| Field | Type | Notes |
|---|---|---|
| `document_folder` | `pathlib.Path` | Absolute or relative; both inputs and the output live here. |
| `pipeline_version` | `str \| None` | When `None`, `build_pipeline_version()` is used. Tests override. |
| `now_utc` | `Callable[[], datetime] \| None` | Injectable clock for deterministic tests. Defaults to `lambda: datetime.now(timezone.utc)`. |

### 2. `AssemblerInputs` (internal, after validation)

Produced by reading + validating `edge_extraction_output.json` and `routing_decision.json`. Never serialized.

| Field | Type |
|---|---|
| `extractor` | `dict` (schema-valid `edge_extraction_output`) |
| `routing` | `dict` (schema-valid `routing_decision`) |

### 3. `FlattenedVendorCandidate` (`assembler/flatten.py`)

Result of walking the `FIELDS_TO_FLATTEN` table. A plain `dict` with the shape the schema expects — `company_name` with `{value, present, inferred, confidence}`, each other scalar with `{value, confidence}`. The `evidence` key is never present at any nesting depth.

### 4. `QualitySummary` (`assembler/quality.py`)

Derived deterministically from `AssemblerInputs.extractor`. Shape matches the schema.

| Field | Type | Derivation |
|---|---|---|
| `overall_vendor_confidence` | `float in [0, 1]`, rounded to 4 decimals | Stage 1 policy `0.1.0`: `clip(0.5 * company_name.confidence + 0.5 * mean(secondary_confidences, default 0.0), 0.0, 1.0)` then `round(_, 4)`. |
| `explicit_name_found` | `bool` | `extractor.vendor_candidate.company_name.present AND NOT extractor.vendor_candidate.company_name.inferred`. |
| `consensus_level` | `"single_voter_baseline"` | Hard-coded (FR-017). |
| `secondary_identifiers_found` | `list[str]` | See §Secondary identifiers derivation below. |

### 5. `TraceBlock` (`assembler/trace.py`)

Four relative-path strings. Always the fixed filenames in stage 1.

| Field | Value |
|---|---|
| `source_file` | `"source.pdf"` |
| `preprocess_output_file` | `"preprocess_output.json"` |
| `edge_extraction_output_file` | `"edge_extraction_output.json"` |
| `routing_decision_file` | `"routing_decision.json"` |

### 6. `FinalPayload` (`assembler/pipeline.py`)

The assembled dict, ready to be written. Key insertion order matches the schema's declared property order:

```python
FINAL_KEY_ORDER = [
    "contract_set_version",
    "pipeline_version",
    "document_id",
    "processed_at",
    "document_type",
    "vendor_candidate",
    "review_status",
    "quality_summary",
    "trace",
]
```

| Field | Source |
|---|---|
| `contract_set_version` | Constant `"1.0.0"`. |
| `pipeline_version` | `Invocation.pipeline_version` or `build_pipeline_version()`. |
| `document_id` | Cross-input invariant — both inputs must agree; value is that agreed string. |
| `processed_at` | `Invocation.now_utc()` formatted per Decision 2. |
| `document_type` | Constant `"invoice"` (schema enum's only value). |
| `vendor_candidate` | Output of `FlattenedVendorCandidate`. |
| `review_status` | Verbatim copy of `AssemblerInputs.routing.review_status`. |
| `quality_summary` | Output of `QualitySummary` serialization. |
| `trace` | Output of `TraceBlock` serialization. |

## `FIELDS_TO_FLATTEN` Table

Drives `assembler/flatten.py`. Exhaustive; any field not listed here must NOT appear in the output.

| Extractor path | Final payload path | Kind | Output shape |
|---|---|---|---|
| `vendor_candidate.company_name` | `vendor_candidate.company_name` | `company_name` | `{value, present, inferred, confidence}` |
| `vendor_candidate.address.street_1` | `vendor_candidate.address.street_1` | `value_confidence` | `{value, confidence}` |
| `vendor_candidate.address.street_2` | `vendor_candidate.address.street_2` | `value_confidence` | `{value, confidence}` |
| `vendor_candidate.address.city` | `vendor_candidate.address.city` | `value_confidence` | `{value, confidence}` |
| `vendor_candidate.address.state` | `vendor_candidate.address.state` | `value_confidence` | `{value, confidence}` |
| `vendor_candidate.address.postal_code` | `vendor_candidate.address.postal_code` | `value_confidence` | `{value, confidence}` |
| `vendor_candidate.address.country` | `vendor_candidate.address.country` | `value_confidence` | `{value, confidence}` |
| `vendor_candidate.tax_ids.ein` | `vendor_candidate.tax_ids.ein` | `value_confidence` | `{value, confidence}` |
| `vendor_candidate.tax_ids.state_tax_id` | `vendor_candidate.tax_ids.state_tax_id` | `value_confidence` | `{value, confidence}` |
| `vendor_candidate.tax_ids.vat_id` | `vendor_candidate.tax_ids.vat_id` | `value_confidence` | `{value, confidence}` |
| `vendor_candidate.tax_ids.other_tax_id` | `vendor_candidate.tax_ids.other_tax_id` | `value_confidence` | `{value, confidence}` |
| `vendor_candidate.website` | `vendor_candidate.website` | `value_confidence` | `{value, confidence}` |
| `vendor_candidate.phone` | `vendor_candidate.phone` | `value_confidence` | `{value, confidence}` |
| `vendor_candidate.email` | `vendor_candidate.email` | `value_confidence` | `{value, confidence}` |

Explicitly NOT in the table (and therefore NOT emitted): `invoice_header_fields.*`, `document_type` (emitted separately as a bare string), `extraction_notes`, `warnings`, `status`, `model_runtime`, `vote_metadata`, any `evidence` array anywhere.

## Secondary identifiers derivation

Pseudocode for `secondary_identifiers_found`:

```python
SECONDARY_ENUM_ORDER = ["address", "ein", "state_tax_id", "vat_id", "other_tax_id", "website", "phone", "email"]

def derive_secondary_identifiers(extractor: dict) -> list[str]:
    out = []
    vc = extractor["vendor_candidate"]

    # address — city + state + postal_code all non-null with non-empty evidence (FR-020, 008 FR-010 rule)
    addr = vc["address"]
    if (
        addr["city"]["value"] is not None and len(addr["city"]["evidence"]) > 0
        and addr["state"]["value"] is not None and len(addr["state"]["evidence"]) > 0
        and addr["postal_code"]["value"] is not None and len(addr["postal_code"]["evidence"]) > 0
    ):
        out.append("address")

    # tax IDs
    for slot in ("ein", "state_tax_id", "vat_id", "other_tax_id"):
        f = vc["tax_ids"][slot]
        if f["value"] is not None and len(f["evidence"]) > 0:
            out.append(slot)

    # contacts
    for slot in ("website", "phone", "email"):
        f = vc[slot]
        if f["value"] is not None and len(f["evidence"]) > 0:
            out.append(slot)

    return [s for s in SECONDARY_ENUM_ORDER if s in out]  # pin order
```

The final comprehension enforces Clarification Q3: the schema enum's declared order is the only permitted order.

## `overall_vendor_confidence` derivation

Pseudocode:

```python
def compute_overall(extractor: dict, secondary_ids: list[str]) -> float:
    vc = extractor["vendor_candidate"]

    cn_conf = vc["company_name"]["confidence"]  # always present per upstream schema

    # Secondary confidences — one value per identifier in secondary_ids
    secondary_confs: list[float] = []
    for ident in secondary_ids:
        if ident == "address":
            secondary_confs.append(
                (
                    vc["address"]["city"]["confidence"]
                    + vc["address"]["state"]["confidence"]
                    + vc["address"]["postal_code"]["confidence"]
                )
                / 3.0
            )
        elif ident in ("ein", "state_tax_id", "vat_id", "other_tax_id"):
            secondary_confs.append(vc["tax_ids"][ident]["confidence"])
        else:  # website, phone, email
            secondary_confs.append(vc[ident]["confidence"])

    secondary_mean = (sum(secondary_confs) / len(secondary_confs)) if secondary_confs else 0.0
    raw = 0.5 * cn_conf + 0.5 * secondary_mean
    clipped = max(0.0, min(1.0, raw))
    return round(clipped, 4)  # Decision 6
```

## Cross-input invariant table

Checked in `assembler/validation.py`, in this order. First failure wins; remaining checks are skipped.

| # | Invariant | Failure → | Exit | Message kind |
|---|---|---|---|---|
| 1 | Both input files exist and are readable | `InputMissingError` / `InputUnreadableError` | 2 | `missing_input` / `unreadable_input` |
| 2 | Each input is JSON-parseable | `InputUnreadableError` | 2 | `unreadable_input` |
| 3 | Each input validates against its v1.0.0 schema | `InputSchemaInvalidError` | 2 | `schema_invalid_input` |
| 4 | `extractor.contract_set_version == "1.0.0"` AND `routing.contract_set_version == "1.0.0"` | `ContractDriftError` | 2 | `contract_drift` |
| 5 | `extractor.document_id == routing.document_id` | `DocumentIdMismatchError` | 2 | `document_id_mismatch` |
| 6 | Routing internal consistency (Decision 9) | `RoutingContradictionError` | 2 | `routing_contradiction` |
| 7 | Assembled output validates against `final_structured_payload.schema.json` | `OutputSchemaInvalidError` | 3 | `output_schema_invalid` |

Invariants 1–6 run before assembly begins; invariant 7 runs after assembly but before writing the file. No file is ever written on any invariant failure.

## State transitions

None. The assembler is stateless: every invocation reads two files, computes one in-memory payload, validates it, writes one file.
