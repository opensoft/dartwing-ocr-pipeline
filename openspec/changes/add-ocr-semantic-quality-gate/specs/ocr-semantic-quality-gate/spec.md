## ADDED Requirements

### Requirement: Semantic table truth sidecar
The system SHALL support an optional authored `semantic_table_truth.json` file for a per-document fixture. The sidecar SHALL be separate from `expected.json`, SHALL identify the same `document_id` as the folder, and SHALL define the table/body row truth needed by the semantic OCR quality gate.

#### Scenario: Semantic sidecar is present
- **WHEN** a per-document folder contains `semantic_table_truth.json`
- **THEN** the validator accepts the file only if its `document_id` matches the folder and its rows follow the semantic table truth contract

#### Scenario: Semantic sidecar is absent
- **WHEN** a per-document folder does not contain `semantic_table_truth.json`
- **THEN** vendor-identity validation and evaluation continue under the existing `expected.json` contract without requiring table/body truth

### Requirement: Deterministic semantic quality evaluation
The system SHALL evaluate semantic table quality deterministically from `preprocess_output.json` and `semantic_table_truth.json` when the sidecar is present. The semantic gate SHALL NOT call a model, perform network I/O, or use OCR confidence as proof of correctness.

#### Scenario: High-confidence OCR contains malformed money
- **WHEN** an expected table row contains decimal currency such as `$21.00` and the observed OCR body text contains a malformed value such as `$21:00`
- **THEN** the semantic quality result records a failed currency-shape check even if OCR confidence is high

#### Scenario: Required row value is missing
- **WHEN** an expected row declares required quantity, description, unit price, or amount content that cannot be found in the observed body OCR evidence
- **THEN** the semantic quality result records a failed missing-content check for that row

#### Scenario: OCR confidence is high
- **WHEN** OCR confidence is high but row content checks fail
- **THEN** the semantic quality verdict remains failed and records OCR confidence only as supporting evidence

### Requirement: Semantic quality report surface
The evaluator SHALL expose semantic table quality separately from vendor-identity scoring. Per-document evaluation SHALL include semantic quality details when the gate runs, and corpus evaluation SHALL aggregate semantic quality status without changing the meaning of existing vendor-identity metrics.

#### Scenario: Document has semantic truth
- **WHEN** the evaluator processes a document with `semantic_table_truth.json`
- **THEN** `evaluation_document.json` includes the semantic table quality status, failed checks, and row-level reasons

#### Scenario: Corpus mixes semantic and vendor-only documents
- **WHEN** the evaluator processes a corpus where only some documents have semantic table truth
- **THEN** `evaluation_run_summary.json` reports semantic quality metrics for applicable documents and leaves vendor-identity pass rates comparable to prior runs

### Requirement: Vendor-identity behavior remains unchanged
The semantic quality gate SHALL NOT change feature 019 OCR-only fallback behavior, feature 020 vendor-identity evidence-gate behavior, feature 021 GPU MVP promotion criteria, or `document_pass_fail.vendor_identity_passed`.

#### Scenario: Header passes and body fails
- **WHEN** a document has sufficient vendor-identity evidence but fails semantic table quality
- **THEN** vendor-identity evaluation may still pass while semantic table quality fails independently

#### Scenario: Feature 020 skip-fallback is evaluated
- **WHEN** the existing feature 020 vendor-identity evidence gate computes a `sufficient` decision
- **THEN** the semantic table quality gate does not alter that decision or its existing run-summary fields

### Requirement: Whole-invoice claim requires semantic quality
The system SHALL prevent evaluator/reporting surfaces from treating vendor-identity sufficiency as a whole-invoice or table-quality claim. When semantic truth is present, any whole-invoice/table-quality pass claim SHALL depend on the semantic quality verdict.

#### Scenario: Whole-invoice claim with failed semantic quality
- **WHEN** semantic table truth is present and the semantic quality verdict is failed
- **THEN** the evaluator reports that whole-invoice/table-quality has not passed even if vendor identity passed

#### Scenario: Vendor-identity-only document
- **WHEN** semantic table truth is absent
- **THEN** the evaluator reports semantic table quality as not applicable rather than inferring a pass from vendor-identity metrics

### Requirement: Corpus promotion follows dataset governance
The system SHALL add degraded-body fixtures to committed corpus data only through the normal dataset and schema amendment path. Noncanonical calibration samples SHALL NOT be treated as scored corpus fixtures until they satisfy folder naming, labeling, source PDF, and truth-contract validation.

#### Scenario: Noncanonical degraded sample exists
- **WHEN** a sample is named with a noncanonical suffix such as `inv_024_hard_degraded_body`
- **THEN** the validator and docs treat it as calibration or test-fixture material, not as a scored stage 1 corpus folder

#### Scenario: Degraded fixture is promoted
- **WHEN** a degraded-body sample is promoted to committed scored corpus data
- **THEN** the same change includes the folder contract, truth contract, labeling guide, and evaluator updates required to validate and score it
