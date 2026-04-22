# Labeling Notes — inv_015_hard

## Difficulty rationale

Classified `hard` because the vendor's company name appears **only** inside the header logo graphic. The PDF text layer contains every other vendor field (address, phone, email, EIN, website) but not the company name itself. This is the only `logo_only` fixture in the corpus and satisfies FR-015's critical tag coverage requirement.

## Key traps

- **Logo-only name.** Any pipeline that reads only the PDF text layer (pypdf, pdfminer, PaddleOCR over the text stream) will miss the company name entirely. Successful extraction requires logo / perception processing — Falcon Perception or a visual-grounding model pass.
- **`present: true` is correct despite the absence from the text layer.** The name IS explicitly displayed on the invoice; it is merely rendered as a raster graphic rather than as selectable text. `explicit_company_name` applies; `logo_only` marks the extraction-path difficulty.
- **Do not confuse with missing-name.** This is NOT a missing_name case. The name exists on the page — it is just gated behind image-perception. `inferred: false` must remain.

## Labeler decisions

- `company_name.value = "Northwind Forge"`, `present: true`, `inferred: false`.
- Document is a synthetic leak-free fixture (source: `tests/sample_invoices/_reserved_synthetic/logo_only_03_northwind_forge.pdf`), substituted in during this labeling pass because none of the original candidate PDFs satisfied `logo_only`. See `specs/006-corpus-labeling/candidates.md` SYN-1 for provenance.
- EIN, website, address, phone, email all taken directly from the text layer.
