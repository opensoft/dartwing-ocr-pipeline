# CLI Contract Delta: `dartwing-preprocess` (010-pp-structurev3-preprocessing)

This document captures **only what changes** in the CLI contract vs. the 003-era CLI defined in `specs/003-pdf-preprocessing/contracts/cli-contract.md`. Anything not mentioned here is unchanged.

The persisted artifact shape (`preprocess_output.json`) is defined by the active JSON Schema at `contracts/stage1_vendor_identity/v1.2.0/preprocess_output.schema.json`. This slice's only schema change is the nullable-confidence widening recorded in `contracts/stage1_vendor_identity/AMENDMENTS.md`; generated preprocessing artifacts emit `contract_set_version = "1.2.0"`.

## Invocation (unchanged)

```bash
dartwing-preprocess \
    --document-folder <PATH> \
    [--source-file <NAME>] \
    [--write-page-images] \
    [--pipeline-version <STRING>]

# Also invocable as:
python -m dartwing_ocr.preprocessing \
    --document-folder <PATH> \
    [--source-file <NAME>] \
    [--write-page-images] \
    [--pipeline-version <STRING>]
```

Flags, defaults, and semantics match 003. `--pipeline-version` continues to accept an override, but the built-in default now assembles to `"stage1-preprocess-v0.2.0+paddleocr3.5.0.0000000.dpi300"` (was `"stage1-preprocess-v0.1.0+paddleocr2.10.0.0000000.dpi300"`). See FR-008 / R-007.

## Exit codes (delta)

| Exit | Name | 003 meaning | 010 meaning |
|------|------|-------------|-------------|
| `0` | `EXIT_OK` | artifact written + validated | unchanged |
| `1` | `EXIT_UNEXPECTED` | unexpected exception | unchanged |
| `2` | `EXIT_INPUT_REJECTED` | malformed PDF, encrypted, zero pages, missing file | unchanged |
| `3` | `EXIT_INTERNAL_ERROR` | assembled artifact failed contract validation | **expanded**: also used for FR-016 engine-init failure (new `EngineInitError`) |

Engine initialization failure (weight download, paddle runtime exception, import error, or any exception during `PPStructureV3()` construction) now triggers `EXIT_INTERNAL_ERROR` (`3`) and writes **no** artifact — not even a `status="failure"` stub. This is the FR-016 hard-fail behavior and is the only new exit-code semantic in this slice.

## Stdout (unchanged)

On success, stdout remains a single JSON line:

```json
{"status": "ok", "document_id": "inv_001", "artifact": "/path/to/preprocess_output.json", "warnings": 0}
```

## Stderr (delta)

On FR-016 engine-init failure, stderr emits a single-line JSON envelope (new `kind` value `"engine_init_failed"`):

```json
{
  "status": "error",
  "kind": "engine_init_failed",
  "cause_class": "FileNotFoundError",
  "cause_module": "paddlex.utils.download",
  "message": "Unable to fetch model file: PP-DocBlockLayout_infer.tar from https://paddle-model-ecology.bj.bcebos.com/...",
  "missing_weight": "PP-DocBlockLayout_infer.tar",
  "weight_hoster_url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_models/..."
}
```

Field rules:

- `status`: always `"error"`.
- `kind`: one of `"input_rejected"` (unchanged), `"artifact_invalid"` (unchanged), `"engine_init_failed"` (NEW — FR-016), `"unexpected"` (unchanged).
- `cause_class`: Python class name of the root exception (`type(exc).__name__`).
- `cause_module`: dotted module path (`type(exc).__module__`).
- `message`: `str(exc)`; preserved verbatim.
- `missing_weight`: model artifact filename (e.g., `"PP-DocBlockLayout_infer.tar"`). **Present only** when the exception is classified as a weight-download failure; omitted otherwise.
- `weight_hoster_url`: upstream URL. **Present only** when `missing_weight` is present.

Classification rule for "weight-download failure" (matches R-008):
- `exc.__module__` starts with `"paddlex"` or `"paddleocr"`, AND
- `str(exc)` matches a loose regex on `(model|weight|download|fetch)`.

If either check fails, the envelope omits the weight fields and the exception is treated as a generic engine-init failure.

Other error kinds (`input_rejected`, `artifact_invalid`, `unexpected`) retain their 003-era stderr shape — this slice does not touch them.

## Artifact location (unchanged)

Artifact is still written atomically to `<document-folder>/preprocess_output.json`. Optional debug page images (`--write-page-images`) still land at `<document-folder>/page_{N}.png` and are NOT part of the contract.

FR-022 (new in 010) formalizes that behavior: `--write-page-images` is the opt-in for debug PNG emission, PNGs are never committed to the corpus, and PNG output is explicitly OUTSIDE FR-004 byte-identical determinism. The flag itself is unchanged from 003.

## In-artifact behavior deltas that are NOT CLI-surface changes

For clarity — these are persisted-artifact rules that clarified in 010 but don't show up as a CLI contract change:

- **FR-004 / R-013 confidence handling**: every block and every OCR line in `preprocess_output.json` carries an in-range engine-emitted `confidence` float or `null` when the score is missing, non-finite, or outside the contract's `[0.0, 1.0]` domain. The V2-era clamp is retired; invalid values are not fabricated into range.
- **FR-007 / R-012 OCR recognition threshold**: PP-OCRv5's engine default is used with no project override; `len(raw_ocr_lines)` reflects native engine filtering only.
- **FR-021 / R-014 `tables[]` projection**: `tables[]` is populated from V3's `table_res_list`, projected into the frozen v1.0.0 shape; richer V3 HTML / cell metadata is discarded at the persistence boundary.

None of these change the CLI's invocation shape, exit codes, stdout, or stderr — they show up only in artifact content.

## First-run behavior (informational, not a contract change)

The CLI will block on first invocation to download ~500 MB of model weights (PP-DocBlockLayout, PP-DocLayout_plus-L, PP-OCRv5 server det/rec, SLANeXt_wired, SLANet_plus, RT-DETR-L cell detectors) from the paddlex / paddle-model-ecology hosters into `~/.paddlex/official_models/`. This is not a CLI-surface change — it was already true for PaddleOCR-VL in 003 — but the total download size is larger. See `specs/010-pp-structurev3-preprocessing/quickstart.md` for the warm-up walk-through.

After the first-run download, subsequent invocations run network-free (FR-015).

## Inputs and invariants preserved from 003

Repeated here as a checklist, not as new contract:

- `--document-folder` must be a directory; its basename must match `inv_\d{3}(?:_.*)?` (folder name → `document_id`).
- The folder must contain `source.pdf` (or the file named by `--source-file`).
- Output is deterministic byte-for-byte across reruns with the same code + deps (FR-004, SC-003).
- No network after weight warm-up (FR-015).
- CPU-only (FR-005); no GPU code path.
