# Labeling Notes — inv_014_hard

## Difficulty rationale

Classified `hard` because the invoice is a multi-entity printing / supply document with several adjacent company and brand names (product brands, parent references, co-marketing logos) that can all look like candidate vendor names. The correct extraction requires disambiguating which of the printed strings is the actual billing entity.

## Key traps

- **Brand names vs. legal vendor name.** Product brand strings and co-marketing marks appear alongside the vendor letterhead. Only the name in the invoice header / billing block is the vendor — brand names and other adjacent company references must be rejected.
- **Website and email domain alignment.** `montroysupply.example.com` domain cross-checks the header name; labelers can use this as corroboration but should not promote the domain over the printed header text.

## Labeler decisions

- `company_name.value = "Montroy Supply Company"`, taken from the invoice header; `present: true`, `inferred: false`.
- Primary address = the physical warehouse/office address printed on the invoice, not any printed marketing-branch address.
- No tax IDs visible on the page; all `tax_ids` null.
