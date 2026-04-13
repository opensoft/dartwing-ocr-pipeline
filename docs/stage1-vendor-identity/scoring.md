# Stage 1 Scoring

## Goal

The scoring system should tell us whether the edge pipeline is useful, where it fails, and whether changes improve or regress quality.

Stage 1 scoring operates at three levels:

- per-field
- per-document
- per-run

The scoring system should remain valid both for a single-voter baseline and for the later three-vote ensemble architecture.

## Per-Field Result Types

Each scored field gets one of these result labels:

- `match`
- `partial_match`
- `mismatch`
- `missing_prediction`
- `unexpected_prediction`
- `not_applicable`

Recommended numeric values:

- `match = 1.0`
- `partial_match = 0.5`
- `mismatch = 0.0`
- `missing_prediction = 0.0`
- `unexpected_prediction = 0.0`

## Fields To Score

Vendor identity fields:

- `company_name.value`
- `company_name.present`
- `company_name.inferred`
- `address.street_1`
- `address.street_2`
- `address.city`
- `address.state`
- `address.postal_code`
- `address.country`
- `tax_ids.ein`
- `tax_ids.state_tax_id`
- `tax_ids.vat_id`
- `tax_ids.other_tax_id`
- `website`
- `phone`
- `email`

Routing fields:

- `manual_review_required`
- `review_reason`

## Normalization Rules

Before comparison, normalize fields where formatting differences should not count as errors.

Recommended normalization:

- company name
  - lowercase
  - trim
  - collapse whitespace
  - strip punctuation where reasonable
- street
  - normalize common suffixes such as `st/street`, `rd/road`, `ave/avenue`
- state
  - treat full name and 2-letter abbreviation as equal
- postal code
  - trim spaces
  - allow ZIP+4 to compare to ZIP when needed
- website
  - remove scheme
  - remove trailing slash
  - optionally remove `www.`
- phone
  - digits only
- email
  - lowercase
- tax IDs
  - strip spaces and punctuation

## Partial Match Policy

Use `partial_match` sparingly.

Appropriate cases:

- company name is clearly the same entity but not the exact legal rendering
- address has correct city, state, and postal code but imperfect street normalization
- postal code matches at 5 digits but not ZIP+4
- phone matches except extension
- inferred company is directionally correct but not exact

Do not use `partial_match` for:

- booleans
- review reason
- tax IDs when normalization already handles formatting differences

## Field Weights

Not all fields should count equally.

Recommended weights:

- `company_name.value = 20`
- `company_name.present = 8`
- `company_name.inferred = 8`
- address total `= 20`
- tax ID total `= 16`
- `website = 6`
- `phone = 4`
- `email = 6`
- `manual_review_required = 8`
- `review_reason = 4`

Address split:

- `street_1 = 8`
- `street_2 = 1`
- `city = 4`
- `state = 3`
- `postal_code = 3`
- `country = 1`

Tax ID split:

- `ein = 8`
- `state_tax_id = 3`
- `vat_id = 3`
- `other_tax_id = 2`

## Document Score

Formula:

- `document_score = sum(field_result_value * field_weight) / sum(applicable_field_weights)`

Only applicable fields should count in the denominator.

## Hard Pass Gates

The weighted score alone is not enough. A document should also pass required gates.

### `vendor_identity_passed`

`vendor_identity_passed = true` only if:

- `company_name.value` is a `match` or acceptable `partial_match`
- `company_name.present` matches expected
- `company_name.inferred` matches expected
- at least 2 secondary vendor identifiers match from:
  - address
  - any tax ID
  - website
  - phone
  - email

### `review_routing_passed`

`review_routing_passed = true` only if:

- `manual_review_required` matches expected
- `review_reason` matches expected

### `overall_document_passed`

`overall_document_passed = true` only if:

- `vendor_identity_passed == true`
- `review_routing_passed == true`
- `document_score >= 0.85`

## Missing-Name Rules

All missing-name documents must satisfy:

- `company_name.present == false`
- `company_name.inferred == true`
- `manual_review_required == true`
- `review_reason == "company_name_inferred"`

Even if the inferred name is strong, stage 1 does not auto-accept those documents.

## Confidence Tracking

Confidence should not be scored as truth.

Instead, track calibration metrics separately:

- average confidence for correct fields
- average confidence for incorrect fields
- inferred-name confidence distribution

This will help detect overconfidence.

## Failure Categories

Every mismatch should be assigned a failure category when possible.

Recommended categories:

- `ocr_miss`
- `layout_miss`
- `normalization_gap`
- `wrong_entity_selected`
- `hallucinated_value`
- `inference_error`
- `routing_error`

These categories are often more useful than the raw numeric score when improving the pipeline.

## Run-Level Metrics

For the full 20-document suite, report:

- overall weighted field accuracy
- overall document pass rate
- vendor identity pass rate
- review routing pass rate
- by difficulty bucket
- by field type
- missing-name subset metrics

When ensemble mode is enabled, also report:

- unanimous field rate
- 2-of-3 majority rate
- split-decision rate
- disagreement frequency by field type

## Headline Metrics

Recommended headline metrics for stage 1:

- `document_score`
- `vendor_identity_passed`
- `review_routing_passed`
- `overall_document_passed`

This allows a document to score reasonably well but still fail because routing was wrong, which is the desired behavior.
