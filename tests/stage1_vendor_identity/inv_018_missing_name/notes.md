# Labeling Notes — inv_018_missing_name

## Why no explicit company name was findable

No company-name string appears in the header, footer, letterhead, logo, or Bill-From block. The invoice does, however, include a rich set of ancillary identifiers: email domain, EIN, NV Seller's Permit, phone, and a distinct remit-to address.

## What was inferred as best-guess vendor

**Office Stream Pro**, inferred from `orders@officestreampro.example.com`. Domain local part maps cleanly to a natural-case three-word name; Reno NV area code `(775)` and Reno physical address are consistent. `present: false`, `inferred: true`, `manual_review_required: true`.

## Alternative entities rejected

- **Bill-To.** Customer, not vendor. Rejected.
- **Remit-to.** A distinct remit-to address appears on the invoice (different from the Reno physical address). Per the primary-address convention, the physical operating address becomes vendor `address`; remit-to is captured only via the `remit_to_differs_from_vendor` tag.

## Labeler decisions

- **NV Seller's Permit → `state_tax_id`.** The invoice prints a Nevada Seller's Permit number `1020-44781`. This is a legitimate state sales-tax registration (issued by the NV Dept of Taxation), distinct from regulatory professional licenses. It IS a state tax ID. Populating `state_tax_id` here is the single source of `state_tax_id_present` coverage alongside inv_019 and is required for FR-015.
- **EIN 88-3142059 → `ein`.** Explicit on the page.
- Tags: `missing_company_name`, `email_domain_present`, `ein_present`, `state_tax_id_present`, `remit_to_differs_from_vendor`.
