# Labeling Notes — inv_013_hard

## Difficulty rationale

Classified `hard` because the document is a banking/credit statement from a regulated financial institution and contains several identifier strings that look tax-ID-like but are **not** tax IDs. The labeler must make a deliberate screening decision to exclude them.

## Key traps

- **ACH Company ID ≠ tax ID.** The statement prints an "ACH Company ID" (an originator identifier used in NACHA ACH transactions). This is NOT a federal EIN, state tax ID, VAT, or other tax registration. It must be excluded from `tax_ids`. All four `tax_ids` fields are therefore null.
- **Bank / financial-services vocabulary.** Terms like "routing number", "BIN", "ACH Company ID" can trick a model into populating EIN or other_tax_id. The correct behavior is to leave the field null when no legitimate tax registration appears on the page.

## Labeler decisions

- `company_name` taken from the letterhead exactly as printed.
- No EIN visible on the invoice (the financial institution's tax ID is not disclosed on a customer-facing credit statement); all `tax_ids` null.
- No remit-to differential — the statement is informational and does not request payment to a separate lockbox.
