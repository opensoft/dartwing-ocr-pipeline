# CLI Contract: Workstation Paddle GPU Preprocessing Validation

**Feature**: 014-paddle-gpu-preprocessing
**Date**: 2026-05-06

This feature touches three CLI surfaces. Two already exist
(`ledgerlinc-preprocess`, `ledgerlinc-pipeline`) and gain additive
behavior. One is new: the preflight CLI.

---

## 1. Preflight CLI (NEW)

### Invocation

```bash
python -m ledgerlinc_ocr.preprocessing.preflight [--no-init] [--quiet]
```

The package install (e.g. `pip install -e .`) is the only prerequisite
to discover this command. There is no console-script entry in
`pyproject.toml`.

### Flags

| Flag         | Default | Effect |
|--------------|---------|--------|
| `--no-init`  | absent  | When set, the classifier does not attempt PPStructureV3 GPU construction. Maps to `attempt_ppstructurev3_init=False`. Used in network-restricted shells where Paddle weight downloads are not possible. |
| `--quiet`    | absent  | When set, suppresses the human-readable text section. Stdout is exactly the trailing JSON line. Useful for shell pipelines. |

### Stdout shape

When `--quiet` is **absent**:

```text
[preflight] state: <state-value>
interpreter_path: <path>
interpreter_version: <version>
venv_path: <path or absent>
paddle_version: <version or absent>
paddleocr_version: <version or absent>
paddle_compiled_with_cuda: <true|false>
paddle_compiled_with_rocm: <true|false>
visible_device_count: <int>
selected_device: <gpu:0 | cpu>
runtime_device_exposure.dev_dri_present: <true|false>
runtime_device_exposure.dev_kfd_present: <true|false>
runtime_device_exposure.hip_visible_devices_set: <true|false>
runtime_device_exposure.cuda_visible_devices_set: <true|false>
runtime_device_exposure.rocm_path_set: <true|false>
runtime_device_exposure.running_in_container: <true|false>
ppstructurev3_init_seconds: <float, optional>
ppstructurev3_init_error: <string, optional>
ppstructurev3_init_skipped_reason: <string, optional>

recommendation: <one-sentence remediation>
{"kind":"preflight_readout","schema_version":"0.1.0","state":"<state>","evidence":{...},"recommendation":"<...>"}
```

Lines whose underlying field is `None` are omitted from the text
section but always appear in the JSON object as `null`.

When `--quiet` is **set**: stdout is exactly the single JSON line above,
followed by one trailing `\n`.

### Stderr usage

Stderr is reserved for **unrecoverable** classifier crashes (e.g. an
unhandled exception inside the classifier itself, not a paddle/import
error — those are recoverable and surface as FR-001 states on stdout).
A reserved internal-error format is:

```text
preflight: internal error: <exception class>: <message>
```

### Exit codes

| Exit | Meaning                                                               |
|------|-----------------------------------------------------------------------|
| `0`  | `state == ppstructurev3_init_succeeded`                                |
| `1`  | argparse / CLI usage error                                             |
| `2`  | Internal classifier error (no FR-001 state could be produced)          |
| `10` | `state == paddle_not_installed`                                        |
| `11` | `state == paddle_cpu_only`                                             |
| `12` | `state == gpu_not_exposed`                                             |
| `13` | `state == gpu_exposed_paddle_cant_bind`                                |
| `14` | `state == ppstructurev3_init_failed`                                   |

### Side-effect contract (FR-004)

The preflight CLI MUST NOT write any pipeline artifact
(`preprocess_output.json`, `routing_decision.json`, etc.). It MAY
trigger PaddleOCR's first-run weight download into
`~/.paddlex/official_models/**` (this is the only allowed disk write,
and it is preexisting paddle behavior). When `--no-init` is set, even
that write is suppressed.

### Output posture (English UTF-8, terminal-safe, dev-internal)

The preflight readout is a development-internal diagnostic. It MUST
be emitted as English UTF-8 plain text plus a single trailing JSON
line. It MUST NOT use ANSI escape sequences (no color, no cursor
control) so it remains readable when piped through `tee`, captured by
CI logs, or read on a monochrome terminal. Line widths SHOULD fit a
standard 80-column terminal; long evidence values (paths, exception
messages) MAY exceed that as a diagnostic necessity.

The readout MAY include filesystem paths, environment-variable
presence, and exception messages. **No PII redaction is required at
stage 1**: the readout is intended for the developer running it and
is not surfaced to end users. Operators sharing readouts in public
issue trackers SHOULD review the captured evidence for sensitive
host details before posting; that is an operational practice, not a
preflight responsibility.

### `pipeline_version` parsing (consumer guidance)

Consumers reading `preprocess_output.json` and parsing
`pipeline_version` SHOULD:

- Treat `pipeline_version` as opaque if they do not need profile or
  device identity (this preserves backward compatibility with
  pre-feature artifacts, which had no lane segment).
- When lane identity is needed, use the `parse_lane_segment(...)`
  helper from `preprocessing/version.py` (see `data-model.md`).
  Pre-feature artifacts (no trailing lane segment) parse as
  `("cpu", None)` per the backward-compatible default; unrecognized
  segments parse as `("unknown", None)` without raising.
- For deeper validation, the normative regex is documented in
  `research.md` R-014.2.

`contract_set_version` (currently `1.2.0`) governs JSON Schema
validation; `pipeline_version` is a producer-behavior identity
string. Consumers that gate solely on schema validity check
`contract_set_version` (or run the validator); consumers that gate
on producer behavior check `pipeline_version`. The two are
orthogonal — a `pipeline_version` lane-segment change does not
require a `contract_set_version` bump.

### `run_summary` consumer tolerance

All consumers of the `kind:"run_summary"` JSON line MUST ignore
unknown keys, including unknown nested keys under
`per_document[].stages.<stage>`. This is the additive contract that
permits patch-level `schema_version` bumps (e.g. 0.1.0 → 0.1.1 in
this feature) without breaking existing parsers. The full
versioning policy is documented in `research.md` R-014.6.

### Determinism

Two consecutive runs with the same environment MUST produce the same
`state`, `recommendation`, and `evidence` *except for*:

- `interpreter_path`, `interpreter_version` — stable.
- `venv_path` — stable.
- `paddle_version`, `paddleocr_version` — stable across the same install.
- `paddle_compiled_with_*`, `visible_device_count`, `selected_device`,
  `runtime_device_exposure.*` — stable across the same environment.
- `ppstructurev3_init_seconds` — varies; classified as a wallclock
  observation, not a determinism input.

---

## 2. `ledgerlinc-preprocess` and `ledgerlinc-pipeline` (EXTENDED)

### Profile vocabulary additions

`src/ledgerlinc_ocr/pipeline/profiles.py::SUPPORTED_PROFILES` adds:

```python
("preprocess", "ppstructurev3", "gpu"),
```

`stub@gpu` remains rejected (FR-011, edge case bullet 5).

The default preprocess profile remains `ppstructurev3@cpu` (FR-008).

### CLI flag

The existing `--preprocess-profile` flag (introduced in feature 011)
gains one new accepted value: `ppstructurev3@gpu`. No new flag is
introduced. Selecting the GPU profile in either single-document or
warm-corpus mode is identical from the CLI's perspective:

```bash
ledgerlinc-preprocess  --input <pdf> --client-id <id> \
    --preprocess-profile ppstructurev3@gpu  ...

ledgerlinc-pipeline --documents-file <file> \
    --preprocess-profile ppstructurev3@gpu  ...
```

### Pre-write GPU gate (FR-009)

Before writing the first artifact for the first document with the GPU
lane selected, the pipeline MUST call
`ledgerlinc_ocr.preprocessing.preflight.classify(attempt_ppstructurev3_init=True)`
exactly once per process and check `state ==
PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED`. On any other state:

- The pipeline writes nothing for *any* document in the run.
- The pipeline emits a single stderr error line:
  `error: --preprocess-profile=ppstructurev3@gpu: <STATE>; <recommendation>`.
- The pipeline exits with the matching preflight exit code (10–14).

The classifier output is reused throughout the rest of the process
(no re-classification per document).

### Per-document GPU failure semantics (FR-010, R-014.4)

After the gate has passed, a per-document GPU inference failure (e.g.
ROCm OOM during `_get_engine().predict(...)`):

- Records a per-document failure entry with
  `gpu_lane_forced_abort: true` (warm-corpus mode; the key is present
  only on the per-document failure record that triggered the abort
  and is always `true` when present) or surfaces the exception
  directly (single-doc mode).
- Aborts the warm-corpus run regardless of `--on-failure` value
  (R-014.4). The user's requested `--on-failure` value is preserved
  verbatim in the run-summary's top-level `on_failure` field for
  audit transparency; only the runtime control flow is overridden.
- Emits the partial `run_summary` JSON line on stdout including the
  failure record and the documents not attempted (per existing
  feature-011 conventions).
- Exits with the existing feature-011 stage-failure exit code, with
  no silent CPU fallback.

### `pipeline_version` segment (FR-016, R-014.2)

`build_pipeline_version(..., lane_segment="cpu")` and
`build_pipeline_version(..., lane_segment="gpu0")` produce trailing
`.cpu` and `.gpu0` segments. The CPU lane is the new default for the
CPU profile.

`parse_lane_segment(pipeline_version_str) -> tuple[str, Optional[int]]`
exposes the inverse parser for downstream consumers (and for
`tests/integration/test_pipeline_gpu_e2e.py`).

### `run_summary` fields (FR-022, R-014.6)

The end-of-run JSON line (`kind: "run_summary"`) gains:

```json
{
  "kind": "run_summary",
  "schema_version": "0.1.1",
  ...
  "preprocess_lane": "gpu0",
  "profile_initialization_seconds": {
    "preprocess": 8.421309,
    ...
  },
  "per_document": [
    {
      "document_id": "inv_001_easy",
      "folder": "...",
      "status": "success",
      "stages": {
        "preprocess": {
          "total_seconds": 1.234567,
          "gpu_init_seconds": 8.421309,
          "gpu_inference_seconds": 1.123456
        }
      }
    }
  ]
}
```

`gpu_init_seconds` is present only on the first document where GPU
init occurred in this process (R-009 absence policy). The value is
**per-process**, not per-document: it measures the one-time
PPStructureV3 GPU construction cost on first use, recorded once on
the first per-document entry where the singleton was constructed,
and absent from every subsequent `per_document[1..N]` entry in the
same run (analyze finding RR13 gloss). On CPU runs, `preprocess_lane`
is `"cpu"` and the `gpu_*_seconds` keys are absent.

---

## 3. Backward compatibility guarantees

- A consumer of the pre-feature `pipeline_version` that compares only
  the prefix up to and including `dpi300` continues to work. Adding
  the lane segment is strictly additive.
- A consumer of the pre-feature `run_summary` that ignores unknown
  keys continues to work. The `schema_version` patch bump (`0.1.0` →
  `0.1.1`) is the documented signal that additive fields are present.
- No breaking changes to the `--preprocess-profile` flag: `cpu` lane
  is the default, the existing `ppstructurev3@cpu` value behaves
  identically to before this feature, and the `stub` profile remains
  lane-less.
- No new `[project.scripts]` console entry; `python -m …` is the only
  preflight invocation form.
