# ocr-semantic-quality-boundary Specification

## Purpose

Records the shipped product boundary discovered after features 019/020/021 landed: OCR confidence and vendor-identity sufficiency do not certify the correctness of invoice body content (table rows, quantities, descriptions, prices, row alignment). Establishes the canonical capability that documents this limitation so it is not silently re-violated by future work, and identifies the forward path through the `ocr-semantic-quality-gate` capability that consumes this boundary.
## Requirements
### Requirement: Shipped OCR-only confidence boundary is explicit
The project SHALL document that feature 019 FR-005 token count and mean detector confidence are lightweight OCR sufficiency signals, not proof of semantic correctness for invoice body rows, table cells, quantities, prices, or row alignment.

#### Scenario: High-confidence body OCR is wrong
- **WHEN** a degraded-body fixture produces high Paddle OCR confidence but incorrect table-body text
- **THEN** the documented interpretation is that feature 019 did not detect a semantic/table-quality failure, not that the body OCR was correct

#### Scenario: Future tuning is needed
- **WHEN** the team decides to catch confidently wrong table rows
- **THEN** the work is specified as a new semantic/table OCR quality feature instead of silently changing feature 019 FR-005 semantics

### Requirement: Vendor-identity sufficiency remains scoped to vendor identity
The project SHALL document that feature 020 `sufficient` decisions certify only the configured vendor-identity evidence gate scope, currently page-1 header-band signals, and do not certify whole-invoice OCR quality.

#### Scenario: Header is sufficient and body is degraded
- **WHEN** a document has sufficient header-band vendor identity evidence but degraded table-body OCR
- **THEN** feature 020 may remain valid for vendor identity while the document is still a failure candidate for a future semantic/table quality gate

#### Scenario: Whole-invoice claim is made
- **WHEN** an operator or future feature claims table/body or whole-invoice OCR quality
- **THEN** that claim MUST depend on a separately specified semantic/table quality gate, not on feature 020 vendor-identity sufficiency alone

### Requirement: GPU MVP promotion does not broaden product behavior
The project SHALL document that feature 021 GPU promotion validates the vendor-identity MVP GPU path and does not promote table/body OCR correctness, line-item extraction, or whole-invoice quality.

#### Scenario: GPU validation passes vendor-identity gates
- **WHEN** GPU readiness, benchmark, and vendor-identity quality gates pass for feature 021
- **THEN** the project may claim GPU-backed vendor-identity MVP readiness, but MUST NOT claim semantic table/body OCR quality from that evidence alone

### Requirement: Future semantic quality fix is non-active until implemented
The project SHALL document `022-ocr-semantic-quality-gate` as a future fix seed only. The current shipped code does not implement semantic/table OCR quality detection, and this amendment SHALL NOT be interpreted as adding that behavior.

#### Scenario: Team starts semantic quality work
- **WHEN** the team begins implementation of semantic/table OCR quality checks
- **THEN** the work starts under a separate governed OpenSpec/Speckit change, not from this as-built boundary amendment

#### Scenario: Gate affects runtime fallback
- **WHEN** semantic/table OCR quality is proposed to affect runtime fallback, review routing, or skip-fallback suppression
- **THEN** the future feature MUST explicitly define that behavior and its interaction with feature 019 and feature 020 before any code or runtime contract changes land

### Requirement: Degraded table-body fixtures follow corpus governance
The project SHALL require degraded table-body candidates to pass the normal labeling, folder-contract, and schema/evaluator amendment flow before they become canonical scored corpus data.

#### Scenario: Candidate folder is not canonical
- **WHEN** a degraded invoice candidate exists in a non-canonical folder such as `inv_024_hard_degraded_body`
- **THEN** the project records it as calibration evidence only until it is promoted to a valid `inv_NNN_hard` corpus folder through the normal dataset process

#### Scenario: Table truth becomes scored data
- **WHEN** table/body truth becomes part of evaluation
- **THEN** the feature MUST define where that truth lives and update the labeling guide, schemas, or evaluator contract as needed

### Requirement: Amendment is documentation-only until follow-up implementation
This OpenSpec change SHALL NOT change runtime code, CLI behavior, environment variables, dependencies, canonical artifact schemas, or committed corpus baselines.

#### Scenario: Reviewing the amendment diff
- **WHEN** a reviewer inspects this OpenSpec amendment
- **THEN** changes are limited to OpenSpec artifacts, documentation, and shipped Speckit spec notes

#### Scenario: Runtime behavior is desired
- **WHEN** the team wants semantic/table quality to alter pipeline execution
- **THEN** that behavior MUST be implemented under a separate future OpenSpec/Speckit feature after this boundary amendment is accepted

