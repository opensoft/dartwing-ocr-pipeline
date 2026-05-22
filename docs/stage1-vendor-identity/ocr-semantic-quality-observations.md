# OCR Semantic Quality Observations

## Purpose

This note records the degraded-body OCR finding that motivated the follow-up OCR semantic quality gate. It is evidence for a future feature, not a change to the current stage 1 vendor-identity MVP boundary.

## Candidate Fixture

Observed local calibration candidate:

- `inv_024_hard_degraded_body/ocr_stress_test_invoice.pdf`

The candidate folder is not a canonical corpus folder because the active folder contract requires names like `inv_024_hard`. The PDF is calibration evidence for this as-built boundary amendment, not committed scored corpus data. Before this candidate becomes committed corpus data, it must pass the labeling-guide pre-inclusion checklist and be promoted through the normal dataset amendment flow.

Scratch run used during calibration:

- source copied to `/tmp/021-bench/nano-024/inv_024_hard/source.pdf`
- preprocessing profile: `ppstructurev3@gpu`
- extraction profile: `stub`
- host Ollama not required for this observation

## Summary Finding

Paddle OCR returned high confidence on table-body text that was visibly degraded and materially wrong.

Run-level body OCR metadata:

| Metric | Value |
|---|---:|
| All OCR lines | 44 |
| All token count | 77 |
| All confidence mean | 0.9813 |
| All confidence min | 0.9205 |
| Body lines | 28 |
| Body token count | 48 |
| Body confidence mean | 0.9727 |
| Body confidence min | 0.9205 |

The confidence values explain why feature 019 FR-005 did not trigger fallback. The output had enough tokens and high enough mean detector confidence. The problem is not sparse OCR; the problem is confidently wrong OCR.

## Row-Level Comparison

This table compares the human-provided ground truth against the observed OCR body text. Confidence is the mean of the observed OCR line confidences available for that row's body values.

| Row | Ground truth | Observed OCR | Approx. mean confidence | Assessment |
|---:|---|---|---:|---|
| 1 | `Qty 1`, `Brand Wax Proper sead Table`, `$21.00`, `$100.00` | `Brand Wax Proper sead Table:`, `$21:00`, `$100:00`; quantity missing | 0.986 | Description mostly preserved, quantity missing, currency punctuation wrong |
| 2 | `Qty 2`, `Adgisted porinter lowrrer' Text`, `$10.00`, `$70.00` | `Adgisted porinter lowrrert`, `Text`, `$10:00`, `$70:00`; quantity missing | 0.966 | Description changed, quantity missing, currency punctuation wrong |
| 3 | `Qty 7`, `Turna'lone energry Table (left hands so mash)`, `$42.00`, `$55.00` | `Turnalone energiy Table`, `(deft hands: so: mash`, `$42:00`, `$55:00`; quantity missing | 0.959 | Multiple text substitutions, quantity missing, currency punctuation wrong |
| 4 | `Qty 8`, `Crmar Tone strang Table`, `$15.00`, `$125.00` | `Crmar`, `Tone`, `strang Table`, `$15:00`, `$125:00`; quantity missing | 0.970 | Description split, quantity missing, currency punctuation wrong |
| 5 | `Qty 9`, `Cotton romped vecan Task`, `$10.00`, `$50.00` | `Cotton:romped vecan Task`, `$10:00`, `$50:00`; quantity missing | 0.972 | Description punctuation wrong, quantity missing, currency punctuation wrong |
| 6 | `Qty 10`, `Tone and these year Tasle`, `$22.00`, `$75.00` | `Tone and these year Tasle`, `$22:`, `$75:00`; quantity missing | 0.972 | Description preserved, quantity missing, incomplete currency value |
| 7 | `Qty 11`, `Renamignation scard Table`, `$10.00`, `$20.00` | `Renamignation scard: Table`, `$10:00`, `$20:00`; quantity missing | 0.966 | Description punctuation wrong, quantity missing, currency punctuation wrong |
| 8 | `Qty 12`, `ACME TEST SUPPLY LLC`, `$100.00`, `$29.00` | `ACMETESTSUPPL`, `$100:00`, `$29:00`; quantity missing | 0.987 | Entity text truncated/collapsed, quantity missing, currency punctuation wrong |

## Product Interpretation

The current gates answer two narrower questions:

- Feature 019 FR-005: Is the OCR-only output sparse or low confidence enough to require PPStructureV3 fallback?
- Feature 020: Is there enough page-1 header-band evidence to trust vendor identity for the skip-fallback decision?

The candidate invoice shows a third question that is not yet covered:

- Is the table/body OCR semantically usable for whole-invoice extraction?

That third question needs its own deterministic quality gate. It should not be inferred from Paddle confidence alone and should not be mixed into the vendor-identity gate without a new feature.

## Follow-Up Requirements Seed

A future feature should add deterministic checks for:

- missing quantity cells when a row is expected to have quantities
- malformed currency punctuation such as `$21:00` where a decimal money value is expected
- row-alignment gaps where cells are missing, shifted, or split
- table-column coverage for quantity, description, unit price, and amount
- body-text mismatch categories separate from vendor-identity mismatch categories

Vendor-identity-only runs may keep accepting sufficient header evidence. Whole-invoice or table-quality claims should fail, fall back, or require review when these semantic checks fail.
