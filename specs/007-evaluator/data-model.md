# Phase 1 Data Model: Evaluator & Reporting

**Feature**: 007-evaluator
**Date**: 2026-04-21

This document specifies the runtime data model for the evaluator — the in-memory dataclasses that move between modules. The persisted JSON artifacts (`evaluation_document.json`, `evaluation_run_summary.json`) are governed by the frozen schemas under `contracts/stage1_vendor_identity/v1.1.0/` (older MINORs within the same major are accepted at ingress per FR-013); this file describes the Python surface that produces those artifacts.

All dataclasses live under `src/ledgerlinc_ocr/evaluator/` and are `@dataclass(frozen=True, slots=True)` unless noted. All enums are Python `enum.Enum` subclasses. Every type is pickle-free and JSON-serializable via `io.to_dict`.

---

## 1. Enums and constants

```python
# scoring.py
class ResultLabel(str, Enum):
    MATCH = "match"
    PARTIAL_MATCH = "partial_match"
    MISMATCH = "mismatch"
    MISSING_PREDICTION = "missing_prediction"
    UNEXPECTED_PREDICTION = "unexpected_prediction"
    NOT_APPLICABLE = "not_applicable"

RESULT_VALUES: dict[ResultLabel, float] = {
    ResultLabel.MATCH: 1.0,
    ResultLabel.PARTIAL_MATCH: 0.5,
    ResultLabel.MISMATCH: 0.0,
    ResultLabel.MISSING_PREDICTION: 0.0,
    ResultLabel.UNEXPECTED_PREDICTION: 0.0,
}  # NOT_APPLICABLE is excluded from the denominator

SCORED_FIELDS: tuple[str, ...] = (
    "company_name.value", "company_name.present", "company_name.inferred",
    "address.street_1", "address.street_2", "address.city",
    "address.state", "address.postal_code", "address.country",
    "tax_ids.ein", "tax_ids.state_tax_id", "tax_ids.vat_id", "tax_ids.other_tax_id",
    "website", "phone", "email",
    "manual_review_required", "review_reason",
)

FIELD_WEIGHTS: dict[str, int] = {
    "company_name.value": 20, "company_name.present": 8, "company_name.inferred": 8,
    "address.street_1": 8, "address.street_2": 1, "address.city": 4,
    "address.state": 3, "address.postal_code": 3, "address.country": 1,
    "tax_ids.ein": 8, "tax_ids.state_tax_id": 3,
    "tax_ids.vat_id": 3, "tax_ids.other_tax_id": 2,
    "website": 6, "phone": 4, "email": 6,
    "manual_review_required": 8, "review_reason": 4,
}  # Sum = 100. Address sub-sum = 20. Tax-ID sub-sum = 16.

CONTRACT_SET_VERSION: str = "1.1.0"  # pinned; MINOR-forward compat per FR-013
GATE_THRESHOLD: float = 0.85
GATE_EPSILON: float = 1e-9
```

**Invariants**:
- `set(FIELD_WEIGHTS) == set(SCORED_FIELDS)` (enforced by a startup assert in `scoring.py`).
- `sum(FIELD_WEIGHTS.values()) == 100`.
- `SCORED_FIELDS` order is the canonical `field_results` key order (FR-018 / research.md §11).

---

## 2. `FieldResult`

One scored-field outcome, ready to serialize into `evaluation_document.json:field_results[<field>]`.

```python
@dataclass(frozen=True, slots=True)
class FieldResult:
    field_name: str           # Must be in SCORED_FIELDS
    expected: Any             # Raw expected value (after structural access, before normalization)
    actual: Any               # Raw actual value (after structural access, before normalization)
    result: ResultLabel
```

**Validation rules**:
- `field_name in SCORED_FIELDS`.
- `result in ResultLabel`.
- If `expected is None and actual is None`, `result` MUST be `NOT_APPLICABLE`.
- If `expected is not None and actual is None`, `result` MUST be `MISSING_PREDICTION`.
- If `expected is None and actual is not None`, `result` MUST be `UNEXPECTED_PREDICTION`.
- Booleans (`company_name.present`, `company_name.inferred`, `manual_review_required`) and `review_reason` MUST NOT produce `PARTIAL_MATCH` (FR-006).
- Tax-ID fields MUST NOT produce `PARTIAL_MATCH` (FR-006).

---

## 3. `ComparisonSummary`

Mirrors the `comparison_summary` object in `evaluation_document.schema.json` (strict schema, no `partial_match_count`; Q1 clarification).

```python
@dataclass(frozen=True, slots=True)
class ComparisonSummary:
    applicable_field_count: int
    matched_field_count: int          # strict matches only
    mismatched_field_count: int
    missing_prediction_count: int
    unexpected_prediction_count: int
    field_accuracy: float             # (match + 0.5 * partial) / applicable
```

**Invariants** (FR-011 Q1 integration):
- `partial_count = applicable - (matched + mismatched + missing_pred + unexpected_pred)` — derived, never stored.
- `partial_count >= 0`.
- `field_accuracy == round((matched + 0.5 * partial_count) / applicable, 6)` when `applicable > 0`, else `0.0`.
- `matched + mismatched + missing_pred + unexpected_pred + partial_count == applicable`.

---

## 4. `DocumentPassFail`

Mirrors `document_pass_fail` in the schema.

```python
@dataclass(frozen=True, slots=True)
class DocumentPassFail:
    vendor_identity_passed: bool
    review_routing_passed: bool
    overall_passed: bool
```

**Invariants** (FR-008–FR-010, FR-012):
- `overall_passed` iff `vendor_identity_passed` AND `review_routing_passed` AND `document_score + GATE_EPSILON >= GATE_THRESHOLD`.
- On a `missing_name` bucket document, `review_routing_passed` is `False` unless all four missing-name invariants hold in the prediction (FR-012).

---

## 5. `DocumentEvaluation`

Full in-memory representation of one document's evaluation, serialized into `evaluation_document.json` via `io.write_document_evaluation`.

```python
@dataclass(frozen=True, slots=True)
class DocumentEvaluation:
    contract_set_version: str         # Pinned version; default "1.1.0" (FR-002)
    document_id: str
    difficulty: Literal["easy", "medium", "hard", "missing_name"]
    challenge_tags: tuple[str, ...]
    comparison_summary: ComparisonSummary
    document_pass_fail: DocumentPassFail
    field_results: tuple[FieldResult, ...]  # Ordered by SCORED_FIELDS
    notes: tuple[str, ...]
    # Internal, not persisted — used by the corpus aggregator:
    document_score: float             # Weighted score used for overall_passed
    folder_path: Path                 # Path the evaluation_document.json was written to
```

**Invariants**:
- `contract_set_version` on the persisted `DocumentEvaluation` equals the **effective pinned version** — that is, `CONTRACT_SET_VERSION` by default, or whatever value the caller passes via the CLI `--contract-set-version` flag or the Python API `contract_set_version=` kwarg. The evaluator stamps this effective pinned version (not strictly `CONTRACT_SET_VERSION`) into its own output. Input artifacts (`expected.json`, `final_structured_payload.json`) are pre-validated under the FR-013 MINOR-forward compat rule (same major, artifact minor ≤ pinned minor) and are NOT required to match the persisted value.
- `len(field_results) == len(SCORED_FIELDS)` and `tuple(f.field_name for f in field_results) == SCORED_FIELDS`.
- `document_id`, `difficulty`, `challenge_tags` propagated verbatim from `expected.json` (FR-003).
- `notes` is always an empty tuple in stage 1. Any future advisory/warning content flows through `DocumentEvaluationOutcome.warnings` (data-model §11), not through the persisted `notes` array, so that the machine artifact's content stays purely a function of the inputs (FR-018 determinism).

**Serialization**: The persisted JSON omits `document_score` and `folder_path`.

---

## 6. `DifficultyStats`

Mirrors `evaluation_run_summary.schema.json#/$defs/difficulty_stats`.

```python
@dataclass(frozen=True, slots=True)
class DifficultyStats:
    document_count: int
    field_accuracy: float
    overall_document_pass_rate: float
```

---

## 7. `OverallMetrics`

Mirrors `overall_metrics` in the run-summary schema.

```python
@dataclass(frozen=True, slots=True)
class OverallMetrics:
    field_accuracy: float
    vendor_identity_pass_rate: float
    review_routing_pass_rate: float
    overall_document_pass_rate: float
```

All values are rounded to 6 decimals at construction time (research.md §10).

---

## 8. `ConsensusMetrics`

Mirrors `consensus_metrics`.

```python
@dataclass(frozen=True, slots=True)
class ConsensusMetrics:
    single_voter_baseline_runs: int
    majority_vote_documents: int           # Stage 1 always 0
    split_decision_documents: int          # Stage 1 always 0
    unanimous_field_rate: float | None = None
    two_of_three_majority_rate: float | None = None
    split_decision_rate: float | None = None
```

**Stage 1 rule** (FR-016): `single_voter_baseline_runs == document_count`; the three "rate" optionals are either `None` (omitted from JSON) or trivially `0.0`. Default: omit them.

---

## 9. `DocumentListEntry`

Mirrors `documents[]` in the run-summary schema.

```python
@dataclass(frozen=True, slots=True)
class DocumentListEntry:
    document_id: str
    overall_passed: bool
    field_accuracy: float
```

**Ordering** (FR-017): The `documents[]` array is sorted by `document_id` ascending.

---

## 10. `RunSummary`

Full in-memory representation of a corpus-level run, serialized into `evaluation_run_summary.json` via `io.write_run_summary`.

```python
@dataclass(frozen=True, slots=True)
class RunSummary:
    contract_set_version: str
    run_id: str
    pipeline_version: str | None
    policy_version: str | None
    document_count: int
    overall_metrics: OverallMetrics
    consensus_metrics: ConsensusMetrics
    by_difficulty: dict[str, DifficultyStats]   # Keys: easy, medium, hard, missing_name
    by_field: dict[str, float]                  # Keys: SCORED_FIELDS (dotted)
    documents: tuple[DocumentListEntry, ...]
```

**Invariants**:
- `by_difficulty` keys == `{"easy", "medium", "hard", "missing_name"}` exactly.
- Sum of `by_difficulty[k].document_count` == `document_count` (SC-006).
- `len(documents) == document_count`, sorted by `document_id` ascending.
- `by_field` keys == `set(SCORED_FIELDS)`, values in `[0.0, 1.0]` rounded to 6 decimals.

---

## 11. CLI results (Pydantic for parity with `validator`)

The CLI returns a `DocumentEvaluationOutcome` or `RunSummaryOutcome` from the module-level public API. These are `pydantic.BaseModel` subclasses so they can be pretty-printed and compared in tests.

```python
class DocumentEvaluationOutcome(BaseModel):
    ok: bool                       # True iff no hard error; low-scoring doc is still ok=True
    evaluation: DocumentEvaluation | None
    errors: list[str] = []
    warnings: list[str] = []
    output_path: Path | None       # Path to written evaluation_document.json

class RunSummaryOutcome(BaseModel):
    ok: bool
    summary: RunSummary | None
    per_document: list[DocumentEvaluationOutcome]
    errors: list[str] = []
    warnings: list[str] = []
    json_output_path: Path | None  # evaluation_run_summary.json
    md_output_path: Path | None    # evaluation_run_summary.md
```

**Contract** (with FR-023): `ok` reflects clean execution, not document pass/fail.

---

## 12. Relationships

```text
Corpus root
└── per-document folder
    ├── expected.json                  ─┐
    ├── final_structured_payload.json  ─┤ → DocumentEvaluation → evaluation_document.json
    └── (other pipeline artifacts)     ─┘

Corpus root
└── {N per-document folders}           ─→ {N DocumentEvaluation}
                                        ↓ aggregate
                                        RunSummary
                                        ├─→ evaluation_run_summary.json
                                        └─→ evaluation_run_summary.md  (+ stdout)
```

No state is shared across documents during evaluation — each `DocumentEvaluation` is computed independently. Aggregation is a pure fold over the set.

---

## 13. Lifecycle

A `DocumentEvaluation` is:
1. constructed by `document.evaluate(folder)` from two JSON inputs;
2. validated against the frozen schema by `io.write_document_evaluation`;
3. persisted as JSON into the folder;
4. returned to the caller (tests, or the corpus aggregator).

A `RunSummary` is:
1. constructed by `corpus.evaluate(root)` from a tuple of `DocumentEvaluation`s;
2. validated against the frozen run-summary schema;
3. persisted as JSON + rendered Markdown at the corpus root;
4. echoed to stdout as the same Markdown content.

Neither object is mutated after construction (`frozen=True`).

---

## 14. Not modeled

The following spec concepts are deliberately NOT given dedicated dataclasses:
- **Failure categories** (`ocr_miss`, etc.) — out of scope per spec Assumptions.
- **Confidence-calibration metrics** — out of scope per spec Assumptions.
- **Weighted `document_score`** — computed transiently in `scoring.evaluate_document_score`; the result is used to decide `overall_passed` and then discarded. Not persisted (per Key Entities in `spec.md`).
- **Secondary-identifier slot tallies** — computed transiently in `gates.vendor_identity_passed`; booleans flow into the final pass gate only.
