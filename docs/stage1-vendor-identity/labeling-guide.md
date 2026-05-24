# Stage 1 Vendor-Identity Labeling Guide

**Contract set**: `1.3.0` (active per feature 022; v1.0.0 was the initial ratification — see `contracts/stage1_vendor_identity/AMENDMENTS.md` for the v1.0.0 → v1.1.0 → v1.2.0 → v1.3.0 trail) · **Applies to**: `tests/stage1_vendor_identity/inv_XXX_*/expected.json` and `notes.md`, AND every committed fixture under `tests/stage1_semantic_quality/inv_XXX_*/` (added by feature 022 — see §2.1).

---

## 1. Purpose and audience

This guide is the authoritative reference for humans authoring or auditing labels in the stage 1 vendor-identity corpus AND in the feature 022 semantic-quality fixture corpus. It captures the conventions that every `expected.json` file and every `notes.md` file in `tests/stage1_vendor_identity/` must follow, and — per Clarifications Q44 / FR-026 — extends the §2 pre-inclusion screening checklist verbatim to every committed fixture under `tests/stage1_semantic_quality/`.

Audience: labelers and auditors. Not a model-development document — model developers should read `prd-model-pipeline.md` and `architecture.md` instead.

Machine authorities are the JSON Schemas in `contracts/stage1_vendor_identity/v1.0.0/` and the validator in `src/dartwing_ocr/validator/`. When this guide and a schema disagree, the schema wins; this guide is updated to match.

---

## 2. Pre-inclusion screening checklist

Apply this checklist **before** a PDF is placed in the corpus. A document is included **only if every item below is YES**. On any NO, exclude the document — **do not redact**.

- [ ] **No individual's residential address** printed as the vendor's or remit-to address.
- [ ] **No full bank account number** (IBAN, ACH routing + account, etc.) on the page.
- [ ] **No full payment card number** (PAN).
- [ ] **No Social Security Numbers or national ID numbers** in any field.
- [ ] **No handwritten signatures of identifiable individuals**.
- [ ] **Licensing** — the source PDF's license either (a) explicitly permits redistribution, (b) is team-owned material the team has authority to publish, or (c) is the team's own receipt/invoice that the team has the right to share.
- [ ] **No confidentiality markings** (e.g., "CONFIDENTIAL", "INTERNAL ONLY", NDA watermarks).
- [ ] **No medical/health information** (HIPAA-sensitive fields).
- [ ] **No minors' data** (COPPA-sensitive fields).

This is the only gate. There is no separate reviewer sign-off per document.

### 2.1 Scope: which corpus roots does this checklist apply to?

The §2 checklist is the same for both stage 1 corpus roots:

| Corpus root | Purpose | Screening applies? |
|---|---|---|
| `tests/stage1_vendor_identity/` | Stable 20-document vendor-identity MVP baseline. | Yes — every PDF added here. |
| `tests/stage1_semantic_quality/` | Semantic / table-quality gate fixtures (feature 022, Clarifications Q15 / FR-026). | Yes — every committed fixture, identical screening (Clarifications Q44). |

**Note on the Q25 synthetic US2 fixture** (`tests/stage1_semantic_quality/inv_001_hard/`): the committed fixture is hand-authored and contains no `source.pdf`. It carries no real PII by construction — the body OCR lines, currency strings, and row text were synthesized to reproduce the degraded-body failure pattern from calibration evidence. The §2 checklist is therefore vacuously satisfied for the Q25 fixture, but every FUTURE committed fixture under `tests/stage1_semantic_quality/` — whether or not it includes a `source.pdf` — MUST pass the same §2 screening before landing. This is non-negotiable (Q44 / FR-026 / MI-25).

The `tests/stage1_semantic_quality/` root follows the same canonical subfolder pattern `^inv_\d{3}_(easy|medium|hard)$` (Clarifications Q40), and the same `validate corpus` partitioned reporting block (validator-cli-contract.md §`validate corpus`) recognizes noncanonical names as calibration material per the default-exclude rule (Q23 / MI-21).

---

## 3. Folder layout and naming

Each document lives in its own folder under `tests/stage1_vendor_identity/`:

```
tests/stage1_vendor_identity/
  inv_001_easy/
    source.pdf        (unconditional)
    expected.json     (unconditional)
    notes.md          (required for hard / missing_name; optional for easy / medium)
```

Folder name pattern: `^inv_\d{3}_(easy|medium|hard|missing_name)$`. Folder names and required files are enforced by `contracts/stage1_vendor_identity/v1.0.0/folder.schema.json`. Reserved filenames (pipeline/evaluator output, not authored by labelers) are documented in `tests/stage1_vendor_identity/README.md` and enforced by the validator.

---

## 4. Difficulty bucket definitions

The `inv_NNN_<difficulty>` suffix is prescriptive — it declares up front what kind of document a reader should expect. The **`hard` vs `missing_name` dividing line is non-negotiable**:

| Bucket | Definition |
|---|---|
| `easy` | Clean, printed, single-entity invoice. Vendor name and address extractable from the text layer without ambiguity. No low-quality scan, no logo-only branding, no conflicting entities. |
| `medium` | Printed, legible, but with at least one non-trivial element: a remit-to that differs from the vendor's operating address, a domain/email to cross-check, or a slightly complex layout. Text layer is usable. |
| `hard` | At least one of: low-quality scan, faint text, rotated scan, multi-entity page, logo-only company name, parent/subsidiary ambiguity, or bank/financial-services statement with non-tax identifiers that look tax-ID-like. Name **is present** on the page in some form — just difficult to extract. |
| `missing_name` | **No explicit company name** anywhere on the document — no header, no footer, no letterhead, no logo, no Bill-From block. Faint-but-present is `hard`, not `missing_name`. |

---

## 5. `expected.json` — field-by-field walk-through

All rules below are normative. Missing scalars are `null`, never `""`.

### `contract_set_version` (required)
Always `"1.0.0"` in this release. Bumps require a contract amendment under `contracts/stage1_vendor_identity/AMENDMENTS.md`.

### `document_id` (required)
Verbatim equals the folder name (e.g., `"inv_015_hard"`). The validator rejects mismatches.

### `difficulty` (required)
One of `"easy" | "medium" | "hard" | "missing_name"`. Must match the folder-name suffix.

### `challenge_tags` (required, array)
Closed vocabulary — see `docs/stage1-vendor-identity/dataset-layout.md` for the full list. Unknown tags fail validation. Pairing rules (§6):
- `explicit_company_name` — on every non-missing-name doc; never on a missing-name doc.
- `missing_company_name` — on every missing-name doc; never on a non-missing-name doc.

### `expected_review` (required)
```json
{ "manual_review_required": <bool>, "review_reason": <string|null> }
```
For `missing_name` docs the missing-name triad is mandatory (§6). For non-missing docs, `manual_review_required` is typically `false` — set to `true` only when the labeler identifies a genuinely review-worthy ambiguity, and record the reason.

### `expected_vendor_candidate.company_name` (required)
```json
{ "value": <string|null>, "present": <bool>, "inferred": <bool> }
```
Governed by the provenance decision tree (§6).

### `expected_vendor_candidate.address` (required)
All six sub-fields must exist; each is `string` or `null`. Use the **physical / sold-from / operating address** as the primary address when one is present. A remit-to PO Box or lockbox is **never** promoted to the primary address when a physical address is also shown — the remit-to difference is instead recorded via the `remit_to_differs_from_vendor` tag (§7).

When only a PO Box is printed (utility statements, financial institutions without a published physical address), the PO Box **becomes** `street_1` — capture the address that IS on the page.

`country` is populated when inferable from state/postal conventions (e.g., US state code + ZIP → `"US"`).

### `expected_vendor_candidate.tax_ids` (required)
Four sub-fields: `ein`, `state_tax_id`, `vat_id`, `other_tax_id`. Each `string` or `null`.

**Populate only legitimate tax registrations.** Do **not** populate `tax_ids` with any of the following (these are all excluded in the shipped corpus):

| Identifier | Why excluded |
|---|---|
| DUNS number | D&B business identifier, not a tax registration. |
| ACH Company ID | NACHA ACH originator identifier. |
| Contractor license number | Regulatory professional license. |
| Rate case docket | Regulatory filing reference. |
| Phrases like "Federal Tax ID on file with PUCN" | A *reference*, not a *value*. |

**Do** populate `state_tax_id` with legitimate state sales-tax registrations such as the NV Seller's Permit (e.g., `1020-44781`) or the CA Resale Permit (e.g., `SR-AS 102-884721`).

### `expected_vendor_candidate.website` (required)
Normalize to bare lowercase domain: strip the `http(s)://` scheme and any leading `www.`. Example: `www.highdesert-power.example.com` → `"highdesert-power.example.com"`.

### `expected_vendor_candidate.phone` (required)
Normalized `(NXX) NXX-NNNN` for US numbers. Toll-free rendered as `(888) 555-0142` (strip leading `1-`). `null` if absent. Fax numbers are **not** phone.

### `expected_vendor_candidate.email` (required)
Case **preserved** from the document (do not lowercase the local part). `null` if absent.

### Optional `notes` field (inside `expected.json`)
Short free-text scalar. Does **not** replace `notes.md`. In the current corpus this is unused; `notes.md` is the only notes surface.

---

## 6. Company-name provenance decision tree

```
Q1. Is there an explicit company-name STRING on the document
    (header, footer, letterhead, body text, or Bill-From block)?

  YES → present = true
        inferred = false
        value    = verbatim reading (natural case; expand the fuller legal form
                   when header + footer combine — e.g., "L.A. Grinding Company")
        tag      = challenge_tags includes "explicit_company_name"

  NO  → Q2. Is the company name rendered ONLY inside a logo graphic
             (not present anywhere in the text layer)?

        YES → present = true   (logo counts as explicit)
              inferred = false
              value    = the recognizable name
              tags     = "explicit_company_name" AND "logo_only"

        NO  → Q3. Is there a domain/website/email whose local part
                   maps cleanly to a human-readable candidate, AND
                   is that candidate consistent with the address / area code?

              YES → present = false
                    inferred = true
                    value    = the best-guess name in natural case
                    review   = manual_review_required = true
                               review_reason = "company_name_inferred"
                    tags     = "missing_company_name" (and typically
                               "email_domain_present")

              NO  → present = false
                    inferred = true
                    value    = null
                    review   = manual_review_required = true
                               review_reason = "company_name_inferred"
                    tag      = "missing_company_name"
```

**Missing-name invariant (non-negotiable)**: when the document is in the `missing_name` bucket, **all four** of the following MUST hold simultaneously:

1. `company_name.present == false`
2. `company_name.inferred == true`
3. `expected_review.manual_review_required == true`
4. `expected_review.review_reason == "company_name_inferred"`
5. `challenge_tags` includes `"missing_company_name"`
6. `challenge_tags` does NOT include `"explicit_company_name"`

The validator enforces (1)–(4) as `MISSING_NAME_TRIAD_VIOLATION`. Pairing rules (5)–(6) are audit-only in this feature — see `tasks.md` T052.

---

## 7. Remit-to vs vendor selection

The vendor is the **issuer** of the invoice — the entity the Bill-To owes money to. The vendor is never the Bill-To, never the parent holding company (unless the parent IS the legal invoicing entity printed on the invoice), and never a shipping carrier mentioned in the body.

When the document prints two or more addresses:

- **Physical / office / warehouse address** → primary address (`expected_vendor_candidate.address`).
- **Remit-to / lockbox / PO Box for payment** → recorded ONLY via the `remit_to_differs_from_vendor` tag. Do **not** promote it to the primary address.
- If only one address appears (utility PO Box cases), that address becomes primary. `remit_to_differs_from_vendor` is absent because there is no separate vendor address to differ from.

If two distinct legal entities appear on the page, add `multi_entity_page` to `challenge_tags`.

---

## 8. DBA vs legal name selection

Write the string **as it appears on the document**. Normalization for scoring is the evaluator's job, not the labeler's. Specifically:

- If the header reads "L.A. Grinding" and the footer fine print reads "LA Grinding Company", use the combined fuller form that best matches the legal name (`"L.A. Grinding Company"` in that example). Keep punctuation from the header brand when present.
- If the invoice prints "Acme Industries, a division of Globex Corp", the vendor is `"Acme Industries"` (the division is the invoicing entity). Do not substitute the parent name.
- When a product brand name appears alongside the vendor letterhead (co-marketing fixtures), the vendor is the **invoice issuer** in the header, not the brand.

---

## 9. Null handling

Use `null`, never `""`. Applies to every optional scalar in `expected.json` — all address sub-fields, all `tax_ids` sub-fields, `website`, `phone`, `email`, and `company_name.value` (when no best-guess is possible).

| Correct | Wrong |
|---|---|
| `"street_2": null` | `"street_2": ""` |
| `"vat_id": null` | `"vat_id": ""` |
| `"review_reason": null` | `"review_reason": ""` |

The validator rejects empty strings in these positions.

---

## 10. Labeling workflow

For a new document:

1. Apply the §2 screening checklist. On any NO, exclude — do not redact.
2. Place the PDF at `tests/stage1_vendor_identity/inv_NNN_<difficulty>/source.pdf` (next available `NNN`, correct difficulty suffix).
3. Author `expected.json` using the rules in §5–§9.
4. Author `notes.md` if `difficulty` is `hard` or `missing_name` (required); optional otherwise.
5. Run `python -m dartwing_ocr.validator validate folder tests/stage1_vendor_identity/inv_NNN_*` — fix any reported errors.
6. Run `python -m dartwing_ocr.validator validate corpus tests/stage1_vendor_identity` — confirm corpus-wide coverage still holds (§11).

For a correction to an existing document: same loop, starting from step 3. If the correction changes the `difficulty` bucket, rename the folder (and update `document_id` in `expected.json` to match).

---

## 11. Dispute resolution

Cite the rule. Two labelers disagreeing should re-read the relevant section of this guide. Common anchors:

- Physical vs remit address → §7.
- Legal name vs brand name → §8.
- Whether a number is a tax ID → §5, `tax_ids` table.
- Whether a document is `hard` or `missing_name` → §4.
- Whether a best-guess inferred name is warranted → §6, Q3.

If the guide is **silent** on the disagreement, escalate the disagreement into an amendment (§12) rather than setting a silent precedent.

---

## 12. Amendment process

Semantic changes to this guide use the same amendment path as the contracts:

1. Propose the change in `contracts/stage1_vendor_identity/AMENDMENTS.md` with rationale.
2. On approval, edit this guide.
3. If the change requires a validator-level enforcement update (new `ViolationCode`, new schema constraint), bundle the schema change into the same amendment; otherwise the change is documentation-only.
4. Retroactively audit existing labels in `tests/stage1_vendor_identity/` against the new rule and correct them in the same PR.

---

## See also

- `dataset-layout.md` — folder contract, difficulty definitions, closed challenge-tag vocabulary.
- `schemas.md` — human-readable `expected.json` shape (authoritative machine layer is `expected.schema.json`).
- `scoring.md` — evaluator rubric.
- `contracts/stage1_vendor_identity/v1.0.0/expected.schema.json` — the schema the validator actually enforces.
- `contracts/stage1_vendor_identity/AMENDMENTS.md` — amendment checklist and changelog.
