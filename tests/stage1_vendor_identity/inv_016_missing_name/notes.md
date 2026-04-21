# Labeling Notes — inv_016_missing_name

## Why no explicit company name was findable

The invoice contains no company-name text anywhere: no header, no footer, no letterhead, no logo, no "from" block, no Bill-From section. The document also lacks any domain, website, phone area code, or tax identifier that would allow a downstream inference. It is the purest missing-name case in the corpus — designed to exercise the `review_reason = "company_name_inferred"` path when **no** best-guess is possible.

## What was inferred as best-guess vendor

Nothing. All vendor-candidate fields are `null`. Per the company-name provenance invariants, `company_name.value` is `null`, `present: false`, `inferred: true`, and `manual_review_required: true` with `review_reason: "company_name_inferred"`.

## Alternative entities rejected

- **Bill-To / customer.** The customer block on this invoice is for the labeling fixture's Sierra Fleet Services entity. Per the primary-address convention, the vendor is the issuer of the invoice, never the Bill-To recipient — even when it is the only legible entity on the page. Bill-To is correctly rejected as a vendor candidate.
- **Remit-to.** No distinct remit-to address block is shown.
- **Parent / holding co.** No parent reference or brand family appears.

## Labeler decisions

- `challenge_tags = ["missing_company_name"]` — only tag present. `explicit_company_name` correctly absent.
- All address, tax-id, website, phone, email fields are `null`. This is the expected fully-null reference for missing-name regression tests.
