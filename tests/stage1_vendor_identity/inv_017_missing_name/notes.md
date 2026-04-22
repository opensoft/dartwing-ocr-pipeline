# Labeling Notes — inv_017_missing_name

## Why no explicit company name was findable

No header letterhead, no footer legal name, no logo, no "from" block, no Bill-From section. The invoice shows only an address, phone, email, and an unrelated customer Bill-To. The only identifier that hints at vendor identity is the email domain `billing@desertflowplumb.example.com`.

## What was inferred as best-guess vendor

**Desert Flow Plumbing**, inferred from the email domain's local part. This follows the corpus convention of accepting a domain-derived best-guess when (a) the local part maps cleanly to a human-readable name in natural case and (b) the address/phone area code are consistent with the inferred identity (NV phone `(702) 555-0143`, Las Vegas NV address). `present: false`, `inferred: true`, `manual_review_required: true`.

## Alternative entities rejected

- **Bill-To.** Customer, not vendor. Rejected.
- **Remit-to.** The invoice shows a distinct remit-to line that differs from the inferred physical address — captured by the `remit_to_differs_from_vendor` tag. The physical operating address is used for the vendor `address`; the remit-to PO Box is not promoted into the primary address.
- **Contractor license number.** A plumbing contractor license appears on the invoice. This is a **regulatory professional license**, not a tax registration. Excluded from `tax_ids` (same screening logic applied to DUNS and ACH Company ID elsewhere in the corpus).

## Labeler decisions

- Tags: `missing_company_name`, `email_domain_present`, `remit_to_differs_from_vendor`. `explicit_company_name` correctly absent.
- `tax_ids` all null — contractor license is not a tax ID.
