# Validator Module-API Delta

**Feature**: 006-corpus-labeling
**Phase**: 1 (Design & Contracts)
**Date**: 2026-04-20
**Stability**: Minor version bump (addition only, no rename/remove).

This is the sole contract change introduced by this feature. It is a **module-API delta**, not a JSON Schema change — no file under `contracts/stage1_vendor_identity/v1.0.0/` is touched, and `contract_set_version` stays at `"1.0.0"`. Per `contracts/stage1_vendor_identity/AMENDMENTS.md`, adding a new `ViolationCode` is not a contract-set amendment.

---

## What changes

One new value is added to `ViolationCode` in `src/ledgerlinc_ocr/validator/report.py`:

```python
class ViolationCode:
    ...
    # Folder
    FOLDER_MISSING_REQUIRED_FILE = "FOLDER_MISSING_REQUIRED_FILE"
    FOLDER_NOTES_MISSING_SOFT = "FOLDER_NOTES_MISSING_SOFT"
    FOLDER_NAME_INVALID = "FOLDER_NAME_INVALID"
    FOLDER_RESERVED_FILENAME_COLLISION = "FOLDER_RESERVED_FILENAME_COLLISION"
    FOLDER_SOURCE_PDF_UNREADABLE = "FOLDER_SOURCE_PDF_UNREADABLE"   # NEW
```

And `validate_folder()` in `src/ledgerlinc_ocr/validator/folder.py` gains one additional check: after the unconditional-files loop, for each present `source.pdf`, the file is opened with `pypdf.PdfReader(path, strict=False)` and `len(reader.pages)` is evaluated inside a try/except. Any exception → `Severity.ERROR` emission with the new code.

---

## ViolationCode reference

### `FOLDER_SOURCE_PDF_UNREADABLE`

- **When emitted**: `<folder>/source.pdf` exists as a file but either (a) has zero bytes, or (b) fails to parse with `pypdf.PdfReader(path, strict=False)` (including any exception raised while forcing `len(reader.pages)`).
- **Severity**: `Severity.ERROR`.
- **Emitted by**: `validate_folder()` in `folder.py`. Bubbles through `validate_corpus()` as a sub-report finding.
- **Not emitted when**: `source.pdf` is absent — in that case the existing `FOLDER_MISSING_REQUIRED_FILE` code fires once and the readability check is skipped to avoid duplicate findings for the same underlying issue.

### Violation fields (contract)

| Field | Value |
|-------|-------|
| `severity` | `"error"` |
| `target` | the folder path as a string (same convention as other folder-level violations) |
| `field_path` | `"/source.pdf"` |
| `violation_code` | `"FOLDER_SOURCE_PDF_UNREADABLE"` |
| `reason` | Human-readable, e.g. `"source.pdf is empty (0 bytes)."` or `"source.pdf failed structural parse: <pypdf error summary>."` |
| `expected` | `"FR-003 readable source.pdf"` |
| `source_file` | the file path as a string, matching existing folder-artifact violation conventions |

---

## Stability implications

Per the module-API stability contract at `specs/001-freeze-schemas-folder-contracts/contracts/module-api.md`:

> Adding a new code is a minor version bump. Renaming or removing requires major.

Therefore:

- This delta is a **minor** addition. It does not break any existing caller. Callers that check for specific `violation_code` values will simply not match this new one unless they opt in.
- The `_ALL_VIOLATION_CODES` frozenset (used by `is_known_violation_code()`) automatically includes the new code because it is collected via `vars(ViolationCode).items()`.
- No changes to `Severity`, `ArtifactName`, `Violation`, `ValidationOutcome`, or any schema file.
- No changes to `contract_set_version` (remains `"1.0.0"`).

---

## Backward compatibility

- **Existing `validate_folder()` callers**: unchanged call signature. Existing callers that ignored non-matched violation codes see no difference. Existing callers that allow-list codes must add `FOLDER_SOURCE_PDF_UNREADABLE` if they want to treat it as non-fatal — but that would conflict with FR-003, so it is not recommended.
- **Existing test fixtures**: every existing fixture with a valid `source.pdf` passes. Fixtures whose `source.pdf` was a placeholder (zero-byte or renamed-text-file) will now fail — these should be replaced with real minimal PDFs (the test-file fixture ecosystem already has small PDF samples).
- **Existing `validate_corpus()` behavior**: unchanged, except that a previously-passing corpus with a corrupt `source.pdf` now fails. This matches the stated intent of SC-001.

---

## Related test additions

`tests/contract_tests/test_folder_source_pdf_readability.py` — new file, ≥5 cases:

1. Folder with a real, minimal, well-formed PDF → no `FOLDER_SOURCE_PDF_UNREADABLE` emitted.
2. Folder with `source.pdf` missing entirely → `FOLDER_MISSING_REQUIRED_FILE` emitted; `FOLDER_SOURCE_PDF_UNREADABLE` **not** emitted (avoid duplicate).
3. Folder with `source.pdf` existing but zero bytes → `FOLDER_SOURCE_PDF_UNREADABLE` emitted.
4. Folder with `source.pdf` being a text file renamed `.pdf` → `FOLDER_SOURCE_PDF_UNREADABLE` emitted.
5. Folder with a truncated PDF (valid `%PDF-` header, missing xref/trailer) → `FOLDER_SOURCE_PDF_UNREADABLE` emitted.

Each test asserts the emitted `Violation.violation_code`, `Violation.severity`, and `Violation.field_path` match this contract.

---

## Amendment trail

If a future feature needs to remove or rename `FOLDER_SOURCE_PDF_UNREADABLE`, that requires a major version bump per `module-api.md` and an entry in `AMENDMENTS.md`. Adding more folder-level codes (e.g., `FOLDER_SOURCE_PDF_TOO_LARGE`) is another minor addition and follows the same pattern.
