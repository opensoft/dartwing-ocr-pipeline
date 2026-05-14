# CLI Contract: `dartwing-evidence-packet`

**Feature**: 004-evidence-packet-assembly
**Artifact shape**: see `contracts/stage1_vendor_identity/v1.1.0/evidence_packet.schema.json` (delivered in Phase 2; governs both in-memory and on-disk packet).

The CLI is a thin wrapper over the library entry point. Both surfaces
(CLI + library) are part of the contract; they are versioned in lockstep
with the `evidence_packet` artifact schema.

---

## Invocation

```bash
dartwing-evidence-packet <folder> [-v | --verbose]
python -m dartwing_ocr.evidence_packet <folder> [-v | --verbose]
```

Both forms are equivalent. The console script is wired via
`[project.scripts]` in `pyproject.toml`:

```toml
dartwing-evidence-packet = "dartwing_ocr.evidence_packet.cli:main"
```

### Positional arguments

- `<folder>` — path to a per-document folder matching
  `tests/stage1_vendor_identity/inv_\d{3}_<difficulty>/`. Must contain a
  valid `preprocess_output.json`. May be absolute or relative; the CLI
  resolves to an absolute path before reading/writing.

### Optional arguments

- `-v`, `--verbose` — may be repeated (`-vv`, `-vvv`). The first `-v`
  sets the `dartwing_ocr` Python logger to `DEBUG`, which triggers
  persistence of `evidence_packet.json` into `<folder>` (FR-015b). Further
  `-v` stacks do not change persistence behavior; they may increase log
  verbosity but are out of scope for this contract.
- `--help` — prints usage and exits 0.

### Stdout / stderr

- On success: stdout emits **one** JSON object (single line, compact) describing the outcome:

  ```json
  {"status":"ok","folder":"/abs/path","persisted":false,"contract_set_version":"1.1.0"}
  ```

  `persisted` is `true` iff a file was written (i.e. logger level was at DEBUG). Logger output goes to stderr.

- On error: stdout emits a single JSON object with `status: "error"` and a `kind` discriminator (mirrors 003's CLI shape). Stderr may carry Python tracebacks at higher verbosity.

### Exit codes

| Code | Kind | Meaning |
|---|---|---|
| 0 | `ok` | Packet assembled (and persisted, if logger at DEBUG). |
| 2 | `input_missing` | `preprocess_output.json` absent / unreadable / non-JSON; folder missing. |
| 3 | `input_invalid` | `preprocess_output.json` fails `v1.1.0/preprocess_output.schema.json` validation. |
| 4 | `packet_invalid` | Assembled packet fails `v1.1.0/evidence_packet.schema.json` validation. Indicates an assembler bug; should never happen in shipped code. |
| 5 | `persistence_failed` | Logger at DEBUG, packet is valid, but writing `evidence_packet.json` failed (e.g. read-only folder, disk full). |
| 1 | `unexpected` | Anything else; Python exception type + message reported. |

---

## Library API (co-published with the CLI)

```python
from dartwing_ocr.evidence_packet import (
    assemble_from_folder,
    assemble_from_preprocess,
    PacketAssemblyError,
    PreprocessInputMissing,
    PreprocessInputInvalid,
    PacketInvalid,
)

def assemble_from_folder(folder: Path) -> dict: ...
    # Reads <folder>/preprocess_output.json, validates, assembles, validates
    # output, and — iff the dartwing_ocr logger is at DEBUG — writes
    # <folder>/evidence_packet.json. Returns the assembled dict either way.
    # Raises PreprocessInputMissing, PreprocessInputInvalid, PacketInvalid,
    # or OSError on persistence failure.

def assemble_from_preprocess(
    preprocess_output: dict,
    *,
    document_id: str | None = None,
) -> dict: ...
    # Pure library path. Validates the input dict against
    # v1.1.0/preprocess_output.schema.json, assembles, validates output.
    # Never reads or writes the filesystem. document_id defaults to
    # preprocess_output["document_id"].
```

Both entry points are stable and semver-governed by the contract set.

---

## Determinism contract

- Two invocations of `assemble_from_folder` on the same folder MUST return packets that are equal by `dict` value AND byte-identical after serialization (SC-002).
- If the logger is at DEBUG on both invocations, the resulting on-disk `evidence_packet.json` files MUST be byte-identical.
- If the logger is at DEBUG on one and not the other, the on-disk file from the first run is **overwritten** by the second run with identical bytes. The file's mtime may differ; its contents must not.

---

## Non-modification contract

- `preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`, `evaluation_document.json`, and `expected.json` in the folder MUST be byte-identical before and after invocation (SC-006). The CLI never opens them for writing.

---

## Logging

- Library default: no log handlers installed. Library callers configure logging themselves.
- CLI default: a `StreamHandler` to stderr at `WARNING` level, formatter `%(levelname)s %(name)s: %(message)s`. `-v` raises the `dartwing_ocr` logger to `DEBUG`; root logger is untouched so other libraries' output is unaffected.
- At `DEBUG` level, the assembler logs: folder being processed; input schema validation result; number of regex hits per field; output schema validation result; persistence path (if any); elapsed wall time (for diagnostics only — this number is NOT written into the packet payload).

---

## Forward-compatibility

- Future slices that add a `--persist-packet` flag, an env var, or a
  `--out` redirection would require amending this contract. None of those
  are in scope for 004.
- Future slices that introduce additional CLI verbs (e.g.
  `dartwing-evidence-packet --validate <file>` to re-validate an
  existing packet on disk) would be additive and fall under a PATCH or
  MINOR bump of the contract set, per `AMENDMENTS.md`.
