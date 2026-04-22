# Quickstart: Labeling One Document

**Feature**: 006-corpus-labeling
**Phase**: 1 (Design & Contracts)
**Audience**: Any labeler or auditor who needs to add or correct one document in the stage 1 vendor-identity corpus.

This is an end-to-end walk-through for producing `expected.json` and (where required) `notes.md` for a single invoice, from PDF screening through validator pass. The authoritative conventions live in `docs/stage1-vendor-identity/labeling-guide.md` — this quickstart is the shortest usable path, not a replacement for the guide.

---

## 0. Prerequisites

From the repo root:

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
source .venv/bin/activate
```

Verify the validator runs:

```bash
python -m ledgerlinc_ocr.validator show contract-set
```

Expected: prints `contract_set_version = "1.0.0"` with the 7 artifact schemas listed.

---

## 1. Screen the candidate PDF

Open the candidate PDF. Walk the PII/license screening checklist from the labeling guide:

- No individual's residential address used as vendor or remit-to.
- No full bank account / IBAN / ACH routing+account combination.
- No full payment card number.
- No SSN or national ID numbers.
- No handwritten signatures of identifiable individuals.
- License permits redistribution (public-domain, permissive, team-owned, or own receipt).
- No confidentiality markings ("CONFIDENTIAL", "INTERNAL", NDA watermarks).
- No health or minors' data.

If any check fails → **exclude the document**. Do not redact. Choose a different candidate.

---

## 2. Pick the difficulty bucket

Using the labeling guide's "Difficulty bucket definitions":

- **`easy`**: clear company name, clear address, typical US/EU invoice format, clean scan.
- **`medium`**: one non-trivial trap (e.g., multi-line DBA, uncommon format) but everything else is clean.
- **`hard`**: multiple traps, low-quality scan, rotated pages, dense header, faint text, remit-to mismatch — name is still present, just not easy to read cleanly.
- **`missing_name`**: **no explicit company name string anywhere on the document.** A logo with a recognizable company is NOT `missing_name` — that is `hard` with `logo_only`.

---

## 3. Place the document

Pick the next available `inv_NNN` prefix (contiguous from 001). Create the folder and copy the PDF:

```bash
mkdir -p tests/stage1_vendor_identity/inv_007_hard
cp /path/to/candidate.pdf tests/stage1_vendor_identity/inv_007_hard/source.pdf
```

For this feature, the 20 folders are pre-allocated as:

- `inv_001_easy` .. `inv_005_easy`
- `inv_006_medium` .. `inv_010_medium`
- `inv_011_hard` .. `inv_015_hard`
- `inv_016_missing_name` .. `inv_020_missing_name`

---

## 4. Author `expected.json`

Create `tests/stage1_vendor_identity/inv_007_hard/expected.json` following this skeleton (all keys required; `additionalProperties: false` rejects extras):

```json
{
  "contract_set_version": "1.0.0",
  "document_id": "inv_007",
  "difficulty": "hard",
  "challenge_tags": [
    "explicit_company_name",
    "remit_to_differs_from_vendor",
    "multi_entity_page"
  ],
  "expected_review": {
    "manual_review_required": false,
    "review_reason": null
  },
  "expected_vendor_candidate": {
    "company_name": {
      "value": "Acme Widgets Inc.",
      "present": true,
      "inferred": false
    },
    "address": {
      "street_1": "123 Main Street",
      "street_2": null,
      "city": "Columbus",
      "state": "OH",
      "postal_code": "43215",
      "country": "USA"
    },
    "tax_ids": {
      "ein": "12-3456789",
      "state_tax_id": null,
      "vat_id": null,
      "other_tax_id": null
    },
    "website": "acme-widgets.com",
    "phone": "614-555-0199",
    "email": "billing@acme-widgets.com"
  },
  "notes": null
}
```

### Field rules (summary)

- `contract_set_version`: always `"1.0.0"` in this release.
- `document_id`: equals the folder's `inv_NNN` prefix, no suffix.
- `difficulty`: equals the folder-name suffix.
- `challenge_tags`: closed vocabulary of 18 values. Include `explicit_company_name` for every non-missing doc and `missing_company_name` for every missing-name doc. Nothing else is invariant, but see FR-015 for the critical-tags coverage requirement across the corpus.
- `expected_review.manual_review_required`: `true` only for missing-name docs (or other reviewer-identified ambiguity); `review_reason` then equals `"company_name_inferred"`.
- `expected_vendor_candidate.company_name`:
  - Non-missing doc: `present=true`, `inferred=false`, `value=<verbatim reading>`.
  - Missing-name doc: `present=false`, `inferred=true`, `value=<best-guess or null>`.
- `expected_vendor_candidate.address`, `tax_ids`, `website`, `phone`, `email`: **`null` for every field absent from the document. Never empty string.**
- `notes`: optional short comment. Not a replacement for `notes.md`.

### Missing-name example

For `inv_016_missing_name/expected.json`, the company-name block looks like:

```json
{
  "company_name": {
    "value": "Best-guess Vendor Name Inc.",
    "present": false,
    "inferred": true
  }
}
```

and `expected_review` becomes:

```json
{
  "manual_review_required": true,
  "review_reason": "company_name_inferred"
}
```

and `challenge_tags` must include `missing_company_name` (and MUST NOT include `explicit_company_name`).

---

## 5. Author `notes.md` (required for `hard` and `missing_name`)

Free-form Markdown. A typical `notes.md` is 5–15 lines. Cover:

1. Why this document is in its difficulty bucket.
2. At least one concrete trap or feature that justifies the chosen `challenge_tags`.
3. (Missing-name only) why no explicit name was findable, what was inferred, which alternative entities on the page were rejected (remit-to, parent co., billing-to).

Example (`inv_011_hard/notes.md`):

```markdown
# inv_011 — hard

- Faint laser-print on a grey background; several characters in the header
  are borderline-illegible, hence `faint_text`.
- Two entities on the page: "Acme Widgets Inc." (billing) in the header and
  "Acme Payment Services LLC" in the remit-to block. We label the vendor as
  Acme Widgets Inc. and record `multi_entity_page` +
  `remit_to_differs_from_vendor`.
- No VAT / state tax ID visible; only EIN appears (`ein_present`).
```

For `easy` and `medium` docs, `notes.md` is optional — add one only if the placement is non-obvious. Absence generates a `FOLDER_NOTES_MISSING_SOFT` warning, not an error.

---

## 6. Validate

Folder-level check:

```bash
python -m ledgerlinc_ocr.validator validate folder tests/stage1_vendor_identity/inv_007_hard
```

Expected output:

```text
Target: tests/stage1_vendor_identity/inv_007_hard
Contract set: 1.0.0
Result: PASS (0 errors, 0 warnings)
```

If you see `FOLDER_SOURCE_PDF_UNREADABLE`, the PDF is truncated, empty, or not a valid PDF — re-copy it or pick a different source.

Corpus-level check (runs once all 20 folders exist):

```bash
python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity
```

This enforces the corpus-level rules: 20 folders, 5/5/5/5 distribution, contiguous `inv_001..inv_020`, reserved-filename absence, challenge-tag coverage against FR-015/FR-016, etc.

---

## 7. Commit

```bash
git add tests/stage1_vendor_identity/inv_007_hard/
git commit -m "Label inv_007 (hard) — Acme Widgets"
```

Per the project's commit conventions, include what was labeled and any reviewer-facing context that does not fit in `notes.md`.

---

## Troubleshooting

**`SCHEMA_ADDITIONAL_PROPERTIES`**: Your `expected.json` has a key the schema does not allow. Remove the extra key.

**`SCHEMA_REQUIRED_MISSING`**: A required key is missing. Compare against the skeleton in § 4.

**`MISSING_NAME_TRIAD_VIOLATION`**: On a `missing_name` document, one of `company_name.present=false`, `company_name.inferred=true`, or `manual_review_required=true` is wrong. All three are invariant together.

**`FOLDER_SOURCE_PDF_UNREADABLE`**: `source.pdf` exists but is empty or not parseable. Re-copy from the original, or open it in a PDF viewer to confirm it is a real PDF.

**`CHALLENGE_TAG_UNKNOWN`**: You used a tag outside the closed vocabulary. See `docs/stage1-vendor-identity/dataset-layout.md` for the 18 allowed values.

**`FOLDER_NAME_INVALID`**: Folder name does not match `^inv_\d{3}_(easy|medium|hard|missing_name)$`, or the `difficulty` in `expected.json` disagrees with the folder suffix.

**`FOLDER_RESERVED_FILENAME_COLLISION`**: You put a generated-artifact filename (`preprocess_output.json`, etc.) or `votes/` / `consensus_output.json` in a document folder. Remove it; the corpus is input-only at ship time.

---

## What this quickstart deliberately omits

- Per-field normalization rules for scoring (these live in evaluator code per `scoring.md`; labels are always verbatim).
- The complete closed `challenge_tags` vocabulary (see `dataset-layout.md`).
- Dispute-resolution protocol (see `labeling-guide.md` § Dispute resolution).
- Amendment process for the guide or contracts (see `AMENDMENTS.md`).

For anything not listed here, the **labeling guide is authoritative** and this quickstart is secondary.
