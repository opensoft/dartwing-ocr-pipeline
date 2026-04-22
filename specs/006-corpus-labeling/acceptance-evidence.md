# Acceptance Evidence: 006-corpus-labeling

Evidence for the nine Success Criteria (SC-001 … SC-009) in `spec.md`. Each section cites the command or artifact that establishes the pass. Captured against the state of the corpus and validator on the branch `006-corpus-labeling`.

---

## SC-001 — Validator exits with zero hard errors

**Command**:

```bash
.venv/bin/python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity
```

**Result**: exit code `0`, 0 FAIL reports, 0 hard errors across 41 sub-reports (20 folder + 20 expected + 1 corpus). Only soft warnings emitted: 10 × `FOLDER_NOTES_MISSING_SOFT` on `easy`/`medium` folders (acceptable per spec).

---

## SC-002 — 20 folders, 5/5/5/5 distribution, contiguous `inv_001…inv_020`

**Evidence**: `ls tests/stage1_vendor_identity/` shows exactly 20 `inv_NNN_<difficulty>` folders. Programmatic count:

- `easy`: 5 (`inv_001` … `inv_005`)
- `medium`: 5 (`inv_006` … `inv_010`)
- `hard`: 5 (`inv_011` … `inv_015`)
- `missing_name`: 5 (`inv_016` … `inv_020`)
- Numeric prefixes contiguous `1..20`: ✓

---

## SC-003 — All 20 documents have readable `source.pdf` and schema-valid `expected.json`

**Evidence**: Covered by SC-001's zero-error corpus run. Individually, all 20 `expected.json` artifacts report `PASS (0 errors, 0 warnings)` in the validator sub-reports, and the folder validator's `FOLDER_SOURCE_PDF_UNREADABLE` check (added in Phase 2, T004–T007) passes for every `source.pdf`. `document_id` ↔ folder name and `difficulty` ↔ folder suffix agreement is enforced by the folder schema and passes for all 20.

---

## SC-004 — All 5 `missing_name` docs satisfy the missing-name invariants

**Result**: 5/5 — `inv_016` … `inv_020` all have `company_name.present == false`, `company_name.inferred == true`, `expected_review.manual_review_required == true`, `expected_review.review_reason == "company_name_inferred"`. Validator enforces this as `MISSING_NAME_TRIAD_VIOLATION`; no such violation was emitted.

---

## SC-005 — All 10 `hard`/`missing_name` documents have non-empty `notes.md`

**Result**: 10/10 — every `hard` (inv_011…inv_015) and `missing_name` (inv_016…inv_020) folder contains a `notes.md` larger than 100 bytes, each documenting the difficulty rationale and at least one concrete trap aligned with the document's `challenge_tags`. Validator does not emit `FOLDER_MISSING_REQUIRED_FILE` for any hard/missing_name folder.

---

## SC-006 — Critical `challenge_tags` coverage (FR-015)

Tag presence across the 20-doc corpus:

| Critical tag | Present on |
|---|---|
| `explicit_company_name` | 15 docs (all non-missing) |
| `missing_company_name` | 5 docs (all missing_name) |
| `logo_only` | 1 doc (`inv_015_hard` — Northwind Forge synthetic, provenance in `candidates.md` SYN-1) |
| `remit_to_differs_from_vendor` | 7 docs |
| `low_quality_scan` | 1 doc (`inv_011_hard`) |
| `ein_present` | 5 docs |
| At least one non-EIN tax-ID tag | `state_tax_id_present` on 2 docs (`inv_018`, `inv_019`) |

All critical tags satisfied. Audit performed programmatically at T052.

---

## SC-007 — Labeling guide completeness (guide-only paper review)

**Artifact**: `docs/stage1-vendor-identity/labeling-guide.md`. Self-review at T068 confirmed:

- Every required key in `expected.schema.json` (6 top-level + all sub-field groups — `company_name` × 3, `address` × 6, `tax_ids` × 4, plus `website`, `phone`, `email`) has at least one explicit rule in guide §5–§9.
- All four difficulty buckets defined in §4.
- All six missing-name invariants stated in §6 (four validator-enforced + two audit-only tag-pairing rules).
- PII/license screening checklist in §2 matches `research.md` §5 verbatim (9 items).

Live-reviewer trial is explicitly out of scope per SC-007.

---

## SC-008 — No schema-disallowed keys, predicted values, confidence scores, or evaluator verdicts

**Evidence**: `additionalProperties: false` is set on the relevant schema objects in `expected.schema.json`. Any forbidden key would fail the artifact validation in SC-001. Zero artifact errors across the corpus → zero contamination. The governance-layer check `EXPECTED_HAS_PREDICTIONS` (validator module API) is also clean across the 20 labels.

---

## SC-009 — Corpus directly usable by downstream slices (003, future)

**Evidence**: Corpus is at `tests/stage1_vendor_identity/inv_NNN_*/`, matching the path convention that `specs/003-pdf-preprocessing/quickstart.md` already assumes. No adapter code, no copies, no renames. Future extraction and evaluation slices can read `source.pdf` and `expected.json` directly from each folder.
