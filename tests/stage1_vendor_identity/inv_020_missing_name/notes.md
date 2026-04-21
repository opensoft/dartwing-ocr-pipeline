# Labeling Notes — inv_020_missing_name

## Why no explicit company name was findable

No company-name string anywhere on the invoice. The document is a utility billing statement with only a "Billing and Payments" header block, a PO Box address, customer-care phone, outage email, and a website. The phrase "Federal Tax ID on file with PUCN" appears but is a reference to a regulatory filing, not an actual EIN value.

## What was inferred as best-guess vendor

**High Desert Power**, inferred from `www.highdesert-power.example.com` and the outage email domain. Both the website and email anchor the same root domain; natural-case rendering gives a three-word name consistent with a regional NV utility. `present: false`, `inferred: true`, `manual_review_required: true`.

## Alternative entities rejected

- **Bill-To.** Customer, not vendor. Rejected.
- **PUCN.** The "Public Utilities Commission of Nevada" (the regulator) is referenced by the "Federal Tax ID on file with PUCN" and "Rate case docket 24-08022" lines. PUCN is a regulatory body, not the vendor. Rejected.
- **Remit-to.** Not applicable — the PO Box billing address IS the only address on the page. There is no separate vendor physical address to differ from. Therefore `remit_to_differs_from_vendor` is correctly **absent** from the tag list, even though the address is a PO Box.

## Labeler decisions

- **PO Box as `street_1`.** Since no physical address is printed on this utility statement, the billing PO Box (`PO Box 30150, Reno NV 89520-3150`) is used as the primary address.
- **Rate case docket `24-08022` → NOT a tax ID.** Excluded from `tax_ids`.
- **"Federal Tax ID on file with PUCN" → NOT an EIN value.** The string is a reference, not a value. `tax_ids.ein` is null.
- **Website normalized** to bare lowercase domain `highdesert-power.example.com` (stripped `www.` and scheme), consistent with corpus convention.
- **Toll-free phone normalized** to `(888) 555-0142` format.
- Tags: `missing_company_name`, `email_domain_present`, `website_present`.
