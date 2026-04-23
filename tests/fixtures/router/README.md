# Router fixtures

Hand-authored minimal `edge_extraction_output.json` samples for the stage 1
deterministic router (feature 008-routing). **Not** the output of real model
runs — each fixture is the smallest schema-valid shape that exercises one
specific rule path.

All fixtures set `contract_set_version = "1.0.0"` and validate against
`contracts/stage1_vendor_identity/v1.0.0/edge_extraction_output.schema.json`.

## Expected fixtures

| Fixture | Task | Purpose |
|---|---|---|
| `clean_explicit_name_full_identity.json` | T009 | Green path: explicit grounded company_name + full address + one tax_id + website + email. Every downstream rule resolves to "passed" so US1 asserts the deterministic schema-valid artifact. |
| `missing_name_inferred.json` | T026 | `company_name.present == false` AND `.inferred == true`. Forces `review_reason == "company_name_inferred"`. |
| `missing_name_with_strong_secondaries.json` | T027 | Missing name + overwhelming secondary evidence. Asserts strong secondaries do NOT override the Principle IV invariant. |
| `explicit_name_zero_secondaries.json` | T032 | Explicit name, zero grounded secondary slots. Secondary-floor reason fires. |
| `explicit_name_one_secondary.json` | T033 | Explicit name, exactly one grounded secondary slot. Floor still not met. |
| `explicit_name_two_secondaries.json` | T034 | Explicit name, exactly two grounded secondary slots. `edge_accept`. |
| `all_null_spam.json` | T040 | Every structural vendor_candidate field null. Spam gate fires. |
| `partial_upstream.json` | T045 | Green shape but input `status == "partial"`. |
| `failure_upstream.json` | T046 | Input `status == "failure"`. |
| `version_drift.json` | T047 | Otherwise-valid but `contract_set_version == "0.9.0"`. Hard error. |
| `forbidden_present_true_inferred_true.json` | T048 | Contract violation (FR-024). |

Fixtures live here rather than under `tests/stage1_vendor_identity/inv_*/`
because they are router-internal unit material, not labeled corpus documents.
