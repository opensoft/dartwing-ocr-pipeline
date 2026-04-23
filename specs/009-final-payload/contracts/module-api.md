# Contract: `ledgerlinc_ocr.assembler` Python API

This document pins the importable Python surface of `src/ledgerlinc_ocr/assembler/`. Changes
to the shapes below without a policy-version bump are contract violations.

## Public surface

```python
from ledgerlinc_ocr.assembler import (
    Invocation,
    run,
    build_pipeline_version,
)
from ledgerlinc_ocr.assembler.errors import (
    AssemblerError,
    InputMissingError,
    InputUnreadableError,
    InputSchemaInvalidError,
    ContractDriftError,
    DocumentIdMismatchError,
    RoutingContradictionError,
    OutputSchemaInvalidError,
    EXIT_OK,
    EXIT_UNEXPECTED,
    EXIT_INPUT_REJECTED,
    EXIT_INTERNAL_ERROR,
)
```

## `Invocation`

```python
@dataclass(frozen=True)
class Invocation:
    document_folder: Path
    pipeline_version: str | None = None     # None → build_pipeline_version()
    now_utc: Callable[[], datetime] | None = None   # None → datetime.now(timezone.utc)
```

**Stability**:
- Fields may be added (with defaults) without a bump.
- Fields may not be removed or renamed without a `<semver>` bump.
- `frozen=True` is part of the contract; callers may rely on hashability.

## `run(invocation: Invocation) -> Path`

Reads, validates, assembles, validates, writes. Returns the absolute path of the written
`final_structured_payload.json`.

**Behavior**:
- On success: writes the file and returns its path. Exit-equivalent is `EXIT_OK`.
- On any cross-input invariant failure (see `data-model.md`): raises a specific `AssemblerError`
  subclass. No output file is written. Caller can map exception → exit code via
  `exc.exit_code`.
- On unhandled exceptions: propagates. The CLI wrapper traps and returns `EXIT_UNEXPECTED`.

**Stability**:
- Signature `(Invocation) -> Path` is pinned. Additional keyword-only parameters may be added
  with defaults without a bump.
- The returned path is always `<document_folder>/final_structured_payload.json`.

## `build_pipeline_version(semver: str = "0.1.0") -> str`

Returns `f"009-final-payload@{semver}"`. The default `semver` is the current policy version.

**Stability**:
- The format `"009-final-payload@<semver>"` is pinned by FR-007. Changing the format (e.g.,
  adding segments like the preprocessing slice's `+paddleocr…` suffix) is a contract change.
- The `semver` default bumps whenever the `overall_vendor_confidence` formula or
  `secondary_identifiers_found` ordering changes.

## Exception hierarchy

```
AssemblerError
├── InputRejectedError (exit_code = 2)
│   ├── InputMissingError
│   ├── InputUnreadableError
│   ├── InputSchemaInvalidError
│   ├── ContractDriftError
│   ├── DocumentIdMismatchError
│   └── RoutingContradictionError
└── InternalError (exit_code = 3)
    └── OutputSchemaInvalidError
```

Every subclass carries an `exit_code: int` class attribute and a `kind: str` class attribute
used for the stderr JSON `kind` field. Additional subclasses may be added without a bump; no
existing subclass may be removed or re-parented.

## Exit-code constants

```python
EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_INPUT_REJECTED = 2
EXIT_INTERNAL_ERROR = 3
```

These values are stable across the lifetime of the v1.0.0 contract set and match the
preprocessing slice's conventions.

## What is NOT part of the contract

- `assembler.flatten`, `assembler.quality`, `assembler.trace`, `assembler.validation`,
  `assembler.write` — internal helpers. Signatures may change at will.
- The in-memory dict shape of intermediate values. Only the final on-disk JSON shape is
  contracted (via `final_structured_payload.schema.json`).
- The CLI flags and stderr JSON keys — those live in `contracts/cli-contract.md`.
