# Labeling Notes — inv_012_hard

## Difficulty rationale

Classified `hard` because the document carries a distinct remit-to address that differs from the vendor's primary operating address, and the vendor is a large operating subsidiary whose canonical legal form ("Veritiv Operating Company") is easy to conflate with the parent holding company name.

## Key traps

- **Remit-to divergence.** The footer remit-to block points to a lockbox address distinct from the primary vendor address printed in the header. Labelers must put the **vendor's physical / operating address** in `address`, NOT the remit-to lockbox. The `remit_to_differs_from_vendor` tag marks this explicitly.
- **Parent vs. operating-entity name.** Use the legal name exactly as it appears on the invoice header ("Veritiv Operating Company"). Do not substitute the parent holding company name from external knowledge.

## Labeler decisions

- `company_name.value` matches the header exactly. `present: true`, `inferred: false`.
- Primary address = vendor office address (physical / sold-from), consistent with the corpus-wide primary-address convention.
- No EIN or state tax ID visible on the invoice; all `tax_ids` null.
