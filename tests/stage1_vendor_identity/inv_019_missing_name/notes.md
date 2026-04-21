# Labeling Notes — inv_019_missing_name

## Why no explicit company name was findable

No company-name string anywhere on the invoice — no header, footer, letterhead, logo, or Bill-From. The invoice shows a warehouse/bay address, phone, email, EIN, a CA Resale Permit, a DUNS number, and a distinct remit-to PO Box.

## What was inferred as best-guess vendor

**Truckfleet Distributors**, inferred from `parts@truckfleet-distributors.example.com`. Domain local part maps cleanly to a natural-case two-word name; Ontario CA `(909)` area code and Ontario CA warehouse address are consistent. `present: false`, `inferred: true`, `manual_review_required: true`.

## Alternative entities rejected

- **Bill-To.** Customer, not vendor. Rejected.
- **Remit-to PO Box.** The invoice prints `PO Box 44120, Ontario CA 91764` as remit. Per the corpus convention the primary address is the **physical / warehouse** address (`880 Commerce Ct, Warehouse 3 - Bay 12`), not the PO Box. Remit difference captured via `remit_to_differs_from_vendor`.

## Labeler decisions

- **DUNS 079-882-441 → excluded from `tax_ids`.** A DUNS is a D&B business-identifier number, not a tax registration. Same screening rule applied to ACH Company ID (inv_013) and contractor license (inv_017).
- **CA Resale Permit `SR-AS 102-884721` → `state_tax_id`.** California resale permit is a legitimate state sales-tax registration (issued by CDTFA). Populated as `state_tax_id` — same convention as NV Seller's Permit in inv_018.
- **EIN 47-2209118 → `ein`.** Explicit on the page.
- `address.street_2 = "Warehouse 3 - Bay 12"` — the warehouse bay designator is captured as a proper suite-line component of the address.
- Tags: `missing_company_name`, `email_domain_present`, `ein_present`, `state_tax_id_present`, `remit_to_differs_from_vendor`.
