# Research: Corpus Scaffolding & Human Labeling

**Feature**: 006-corpus-labeling
**Phase**: 0 (Outline & Research)
**Date**: 2026-04-20

This file resolves the design questions surfaced by the plan's Technical Context and the five clarifications recorded in `spec.md` (§ Clarifications, Session 2026-04-20). Each section follows **Decision / Rationale / Alternatives**.

---

## 1. Validator-level PDF structural-integrity check (from Clarification Q4)

**Decision**: Extend `src/dartwing_ocr/validator/folder.py` so that the existing `source.pdf` presence check is augmented by (a) a non-empty file-size assertion, and (b) a structural parse using `pypdf.PdfReader(path, strict=False)` wrapped in a try/except. Any `pypdf`-raised exception on construction or on `len(reader.pages)` (which forces the xref scan) emits a new `ViolationCode.FOLDER_SOURCE_PDF_UNREADABLE` at `Severity.ERROR`. No page-rendering is attempted.

**Rationale**:
- `pypdf` is already a project dependency (`pyproject.toml` pins `pypdf >= 5.0, < 7`), used by the preprocessing slice. No new dep.
- `PdfReader(..., strict=False)` tolerates minor spec deviations common in real-world invoice PDFs while still rejecting truncated, corrupt, or non-PDF files.
- Forcing `len(reader.pages)` triggers the xref-table/cross-reference parse; without that, a pathological PDF can construct a reader without error and fail later in downstream stages.
- The check is O(pages), not O(page-render). For a 20-document corpus of ≤5 pages each, total validator overhead is measured in tens of milliseconds — well inside the "interactive" budget.
- Keeping the check at structural-parse level (Option B from the clarification) avoids dragging Poppler / pdf2image into the validator's import graph. Those belong in preprocessing.

**Alternatives considered**:
- **Stdlib-only magic byte check (`%PDF-` header + `%%EOF` trailer)**: rejected — too permissive; passes many truncated or partially-valid files that pypdf rejects immediately.
- **Render-at-least-one-page via pypdfium2**: rejected — pulls a heavyweight binding into the validator's import path for a harness-side check; preprocessing already does render-level work.
- **Passive — leave it at `is_file()`**: rejected — conflicts with FR-003 clarification and with the stated intent of "readable `source.pdf`" across US1 Scenario 3 and SC-003.

**Implementation notes**:
- New violation code: `ViolationCode.FOLDER_SOURCE_PDF_UNREADABLE`, added to `src/dartwing_ocr/validator/report.py`. Documented in `contracts/validator-delta.md`.
- `Violation.expected` field set to `"FR-003 readable source.pdf"` for consistency with existing folder-level messages.
- `Violation.field_path = "/source.pdf"`.
- The check runs only when the file exists and is not a directory; an already-missing file raises the existing `FOLDER_MISSING_REQUIRED_FILE` and this check is skipped to avoid duplicate findings.
- Tests under `tests/contract_tests/test_folder_source_pdf_readability.py` cover: valid PDF (pass), missing file (existing error; no duplicate), empty (zero-byte) file (unreadable), truncated valid PDF (unreadable), non-PDF text file renamed `.pdf` (unreadable).

---

## 2. Sourcing composition for the 20 PDFs (from Clarification Q2)

**Decision**: Compose the corpus from two buckets:

- **Team-held invoices** (primary): real invoices the team has on hand that can be committed as-is. These naturally populate `easy` and `medium` and some `hard` slots.
- **Publicly-available invoice samples** (gap-filling): public-domain or permissively-licensed invoice templates and sample PDFs used to fill sparse challenge-tag coverage (`logo_only`, `missing_company_name`, `low_quality_scan`, `rotated_scan`, `portal_cover_page`) that team-held material alone would not exercise.

Every document in both buckets must pass the labeling guide's PII/license screening checklist (from Clarification Q5) before inclusion.

**Rationale**:
- FR-015 requires specific critical-tag coverage that is unlikely to appear in a naturally-occurring set of 20 team invoices (e.g., `logo_only`, `missing_company_name`, `vat_id_present`). Fighting the distribution by picking only team invoices risks missing coverage.
- Public samples give deterministic, no-PII starting points for the awkward categories without requiring redaction.
- Mixing sources matches the constitutional principle of reproducibility — anyone can reconstruct the `logo_only` or `missing_name` documents from public pointers documented in `notes.md`.

**Alternatives considered**:
- **Team-held only**: rejected — challenge-tag coverage is unlikely to hit FR-015 without cherry-picking.
- **Public-only**: rejected — a public-only corpus may drift from the real invoice distribution the pipeline actually faces.
- **Synthetic generation**: rejected — while it would guarantee tag coverage, synthetic PDFs typically render too cleanly to exercise `low_quality_scan` or `rotated_scan`, and the corpus explicitly aims at real-world vendor-identity traps.

**Candidate public sample sources** (non-binding; the labeler makes final per-document decisions):
- Vendor invoice templates on `.gov` and `.edu` sites (explicitly public-domain).
- Archived invoices from open-source ERP demos (typically Apache-2.0 / MIT).
- Redacted examples published by compliance/training vendors whose templates are marked reusable.
- Historical invoices in digital-library collections where the license permits redistribution.

The labeling guide's PII/license checklist is the gate; it supersedes this list.

---

## 3. Challenge-tag allocation plan (FR-015 / FR-016 coverage)

**Decision**: Pre-plan which document carries which critical `challenge_tags` so the corpus is known to satisfy FR-015 before labeling begins. The plan is advisory — the labeler may move a tag between documents — but it reserves the *existence* of every critical tag in at least one document.

**Critical tags that must appear at least once** (FR-015):

| Tag | Target document(s) | Notes |
|-----|--------------------|-------|
| `explicit_company_name` | All 15 non-missing (`inv_001..015`) | Enforced by FR-016; invariant |
| `missing_company_name` | All 5 missing (`inv_016..020`) | Enforced by FR-016; invariant |
| `logo_only` | At least 1 of `inv_003`..`005` (`easy`) or `inv_011..015` (`hard`) | Logo-rendered branding |
| `remit_to_differs_from_vendor` | At least 1 of `inv_011..015` (`hard`) | Classic hard trap |
| `low_quality_scan` | At least 1 of `inv_011..015` (`hard`) | Faint text + scan artifacts |
| `ein_present` | At least 1 of `inv_006..010` (`medium`) | US invoice with explicit EIN |
| One of `{vat_id_present, state_tax_id_present, other_tax_id_present}` | At least 1 of `inv_006..015` | FR-015 "at least one non-EIN tax-ID tag" |

**Non-critical tags encouraged but not required by FR-015**: `footer_only`, `address_only`, `website_present`, `email_domain_present`, `multi_entity_page`, `rotated_scan`, `dense_header`, `portal_cover_page`, `faint_text`. The labeler aims for broad coverage but is not blocked on these.

**Rationale**:
- Tagging plan precedes labeling so we do not finish the corpus and then discover FR-015 is unmet (in which case we would have to swap in a new document and re-label).
- Mapping tags to difficulty buckets is advisory, but `remit_to_differs_from_vendor` and `low_quality_scan` are naturally `hard` signals; pinning them there is the cheapest allocation.
- `missing_company_name` / `explicit_company_name` are disjoint by FR-016 — making this invariant visible in the allocation table prevents labeler error.

**Alternatives considered**:
- **Label first, reconcile FR-015 coverage at validator time**: rejected — reactive; risks re-labeling after failed coverage audit.
- **Force every tag into at least one document**: rejected — FR-015 only mandates critical tags; exceeding that adds labeling cost without a requirement.

---

## 4. Labeling guide structure and content (from Clarification Q1 + FR-017)

**Decision**: `docs/stage1-vendor-identity/labeling-guide.md` is structured in the following sections, in order:

1. **Purpose and audience** — one paragraph. Labelers and auditors; not model developers.
2. **Pre-inclusion screening checklist** — PII/license gate (from Clarification Q5). Applied per document before the PDF is added to the corpus. Failure = exclude, do not redact.
3. **Folder layout and naming** — restates `^inv_\d{3}_(easy|medium|hard|missing_name)$` and the unconditional/conditional files. Points to `folder.schema.json` as the authority.
4. **Difficulty bucket definitions** — prescriptive rules for `easy`, `medium`, `hard`, `missing_name`. Emphasizes the `hard` vs `missing_name` dividing line (faint-but-present = `hard`; no-explicit-name-at-all = `missing_name`).
5. **`expected.json` walk-through, field by field** — for each required key:
   - `contract_set_version` → always `"1.0.0"` in this release.
   - `document_id` → derived from folder name, verbatim.
   - `difficulty` → must match folder suffix.
   - `challenge_tags` → closed vocabulary (linked to `dataset-layout.md`) + assignment rules.
   - `expected_review` → the missing-name invariants; for non-missing, `manual_review_required` is typically `false` unless the labeler identifies a review-worthy ambiguity.
   - `expected_vendor_candidate.company_name` → the present/inferred/value decision tree.
   - `expected_vendor_candidate.address` → null-vs-empty-string rule; per-field nullability.
   - `expected_vendor_candidate.tax_ids` → EIN/VAT/state/other with explicit examples.
   - `expected_vendor_candidate.{website,phone,email}` → verbatim from document; `null` if absent.
   - `notes` (optional schema field inside `expected.json`) → short free-text; does not replace `notes.md`.
6. **Company-name provenance decision tree** — the required flow:
   - Is there an explicit company name string on the document? **Yes** → `present=true`, `inferred=false`, `value=<verbatim reading>`.
   - **No**, but there is a logo with a recognizable company → `present=true` (logo counts as present), `inferred=false`, `value=<the recognizable name>`, `challenge_tags` includes `logo_only`.
   - **No** explicit string **and** no unambiguous logo → `present=false`, `inferred=true`, `value=<best guess or null>`, and the document belongs in the `missing_name` bucket with `manual_review_required=true`, `review_reason="company_name_inferred"`.
7. **Remit-to vs vendor selection** — always label the billing entity (vendor). `challenge_tags` gets `multi_entity_page` if two entities are visible and `remit_to_differs_from_vendor` if the remit-to address differs from the vendor address.
8. **DBA vs legal name selection** — write the string as it appears on the document. Normalization for scoring is evaluator-side.
9. **Null handling** — `null`, never `""`. Applies to all optional scalars. Examples.
10. **Labeling workflow** — step-by-step for adding a new document or correcting an existing one: (a) run the screening checklist; (b) place the PDF; (c) author `expected.json`; (d) author `notes.md` if required; (e) run `python -m dartwing_ocr.validator validate folder <folder>`; (f) run `validate corpus` for global coverage checks.
11. **Dispute resolution** — cite-the-rule pattern. If two labelers disagree, they re-read the guide section; if the guide is silent, the disagreement is escalated into a guide amendment.
12. **Amendment process** — changes to this guide that affect semantics require the same amendment path as the contracts (`contracts/stage1_vendor_identity/AMENDMENTS.md`).

**Rationale**:
- The order follows the labeler's actual workflow: screen the document, place it, fill out the JSON, cross-check, validate. Reference material (the per-field walk-through) sits mid-document where it is easy to find.
- Missing-name invariants and the company-name decision tree get their own dedicated section (#6) because they are the constitution-bound rules (Principle IV) most likely to be mis-applied.
- Screening checklist (#2) is hoisted to the top because it is the *first* decision a labeler makes and because it blocks inclusion.

**Alternatives considered**:
- **Pure field-reference document (schema commentary)**: rejected — does not address workflow, disputes, or the missing-name provenance rule.
- **Split into multiple files (workflow + reference + examples)**: rejected for this slice — one authoritative file is simpler to discover and easier to keep in sync with FR-017. A future slice may split if the guide grows past ~2000 lines.

---

## 5. PII/license screening checklist (from Clarification Q5)

**Decision**: Embed the following screening checklist in the labeling guide (section 2 above). A document is included **only if every item is YES**. Failure on any item → exclude the document; do not redact.

- **No individual's residential address** printed as the vendor's or remit-to address.
- **No full bank account number** (IBAN, ACH routing + account, etc.) on the page.
- **No full payment card number** (PAN).
- **No Social Security Numbers or national ID numbers** in any field.
- **No handwritten signatures of identifiable individuals**.
- **Licensing**: the source PDF's license either (a) explicitly permits redistribution, (b) is team-owned material the team has authority to publish, or (c) is the team's own receipt/invoice that the team has the right to share.
- **No confidentiality markings** (e.g., "CONFIDENTIAL", "INTERNAL ONLY", NDA watermarks).
- **No medical/health information** (HIPAA-sensitive fields).
- **No minors' data** (COPPA-sensitive fields).

**Rationale**:
- The list is intentionally short and checkbox-shaped so the labeler can apply it without cross-checking external guidelines.
- These are the eight categories that typically arise on real invoices; everything else (trade secrets, competitive pricing, etc.) is absorbed by the "licensing" and "confidentiality markings" items.
- The checklist is the only gate; there is no separate reviewer sign-off (per Clarification Q5 resolution).

**Alternatives considered**:
- **No written checklist, trust labeler judgment**: rejected by Clarification Q5 — the team wants a documented gate.
- **Second-reviewer sign-off per document**: rejected — explicitly out of scope for this feature; single-labeler assumption holds.
- **Formal compliance review (legal sign-off)**: rejected — too heavy for a 20-document test corpus with no individual PII by construction.

---

## 6. Best practices referenced

- **Folder contract consumer patterns**: the existing validator implementation in `src/dartwing_ocr/validator/folder.py` is the reference for how to add the new `source.pdf` readability check — mimic the existing `Violation` emission for `FOLDER_MISSING_REQUIRED_FILE` so the new code reuses the `Violation` schema, the `target`/`field_path` conventions, and the `expected` short-citation style.
- **Contract amendments**: per `contracts/stage1_vendor_identity/AMENDMENTS.md`, this feature does NOT touch the frozen schemas — the new `ViolationCode` is a module-API addition, not a contract change, and does not require a contract-set version bump.
- **Existing 003 preprocessing slice's corpus expectations**: `specs/003-pdf-preprocessing/quickstart.md` expects `tests/stage1_vendor_identity/inv_XXX_*/source.pdf` to exist. This feature is exactly what fills that assumption.
