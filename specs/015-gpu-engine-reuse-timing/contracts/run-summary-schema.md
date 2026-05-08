# Contract: `kind: "run_summary"` Schema 0.1.2 (Additive Patch)

This contract documents the additive shape changes to the existing `kind: "run_summary"` stdout JSON line emitted by the documents-file driver (`pipeline/corpus_run.py`) and, after this feature, also by the single-document CLI (`preprocessing/cli.py`). The legacy 0.1.1 fields are **not removed**; consumers built against 0.1.1 continue to parse 0.1.2 output unchanged.

## Schema version

`schema_version` MUST be the string `"0.1.2"` for any output emitted by this feature.

## Top-level fields

Unchanged from 0.1.1:

```json
{
  "kind": "run_summary",
  "schema_version": "0.1.2",
  "stack_preset": "<str|null>",
  "resolved_profiles": { "<stage>": "<profile-string>" },
  "execution_slice": { "start_at": "<stage>", "stop_after": "<stage>" },
  "on_failure": "continue|fail-fast",
  "documents_total": <int>,
  "documents_succeeded": <int>,
  "documents_failed": <int>,
  "profile_initialization_seconds": { "<stage>": <float> },
  "per_document": [ … ],
  "preprocess_lane": "cpu|gpu0"
}
```

## `per_document[*]` shape

The legacy 0.1.1 fields stay:

```json
{
  "document_id": "<str>",
  "folder": "<str>",
  "status": "success|failure",
  "stages": { "<stage>": { "<phase>_seconds": <float>, "total_seconds": <float> } },
  // success-only:
  // none (artifacts list is emitted separately on stdout via _emit_stdout_summary)
  // failure-only:
  "failed_stage": "<str>",
  "exit_code": <int>,
  "message": "<str>",
  "gpu_lane_forced_abort": true   // optional, present only when GPU-lane forced
}
```

**New additive keys** (R-015.4):

```json
{
  "phase_timings": { "<phase-name>": { "seconds": <float> } },
  "per_page_inference": [ { "page": <int 1-based>, "seconds": <float> } ]
}
```

### `phase_timings` keys

> Canonical vocabulary is defined in `spec.md §FR-013`. The table below is derived from that list and is non-normative if it ever drifts.

| Phase | Type | Required when |
|---|---|---|
| `paddle_import` | `{seconds: float}` | First successful per_document entry only, GPU lane only. |
| `gpu_bind_probe` | `{seconds: float}` | First successful per_document entry only, GPU lane only. |
| `engine_init` | `{seconds: float}` | First successful per_document entry only, GPU lane only. |
| `warmup` | `{seconds: float}` | **Optional / reserved**: present only if some code path actually performs warmup. Omitted by default in feature 015 (Clarification Q2). |
| `rasterization` | `{seconds: float}` | Every per_document entry where rasterization started. May be partial (timing of the failed page accumulates inside `total`, not `rasterization`). |
| `artifact_write` | `{seconds: float}` | Every successful per_document entry. Omitted on failure entries that aborted before artifact write. |
| `total` | `{seconds: float}` | Every per_document entry — success or failure. |

Phases that did NOT run on a given document MUST be **absent from the dict** (no `null`, no `0.0`). This matches FR-016 / R-009 absence policy.

CPU lane: `paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup` MUST be absent (FR-017).

### `per_page_inference` array

```json
[ { "page": 1, "seconds": 8.43 }, { "page": 2, "seconds": 7.91 } ]
```

- `page`: integer ≥ 1, matches `preprocess_output.json[*].pages[*].page_number` for that document.
- `seconds`: six-decimal-rounded `time.perf_counter()` delta around the single `engine.predict(np_img)` call for that page.
- Order: ascending by `page`.
- Pages whose rasterization or inference failed before timing could be captured are **absent** (the consumer can detect a gap by comparing to `preprocess_output.json` page list).
- CPU lane: array MUST be absent (FR-017). Per-page CPU inference time is collapsed into `total_seconds` on the legacy `stages.preprocess` form.

### Failure semantics (Clarification Q5)

A `per_document` entry with `status: "failure"` MAY carry a partial `phase_timings` and partial `per_page_inference`:

```json
{
  "document_id": "inv_005_hard",
  "folder": "tests/stage1_vendor_identity/inv_005_hard",
  "status": "failure",
  "failed_stage": "preprocess",
  "exit_code": 30,
  "message": "...",
  "phase_timings": {
    "rasterization": { "seconds": 1.04 },
    "total":         { "seconds": 9.32 }
  },
  "per_page_inference": [
    { "page": 1, "seconds": 8.21 }
  ]
}
```

Here the doc rasterized OK, processed page 1 inference, then page 2 raised — page 2 has no entry, no `artifact_write` was performed, the `engine_init` family is absent because this is not the first successful entry. `total` is always present (outer measure_total fires in the `finally` clause).

## Validation

A consumer-side schema fragment in JSON-Schema-2020-12 form (informal — actual implementation lives in pipeline/timing.py and is exercised by unit tests, not via a separate `.json` schema file, since the run_summary line is internal pipeline metadata and not part of the stage 1 contract set):

```json
{
  "$id": "run_summary_per_document_phase_timings_v0_1_2",
  "type": "object",
  "additionalProperties": true,
  "properties": {
    "phase_timings": {
      "type": "object",
      "additionalProperties": false,
      "patternProperties": {
        "^(paddle_import|gpu_bind_probe|engine_init|warmup|rasterization|artifact_write|total)$": {
          "type": "object",
          "required": ["seconds"],
          "additionalProperties": false,
          "properties": { "seconds": { "type": "number", "minimum": 0 } }
        }
      }
    },
    "per_page_inference": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["page", "seconds"],
        "additionalProperties": false,
        "properties": {
          "page":    { "type": "integer", "minimum": 1 },
          "seconds": { "type": "number",  "minimum": 0 }
        }
      }
    }
  }
}
```

## Backward compatibility

- All 0.1.1 consumers continue to parse 0.1.2 output. The legacy `stages.preprocess.{total_seconds, gpu_init_seconds, gpu_inference_seconds, …}` flat keys are preserved.
- A future feature MAY remove the legacy flat keys with an accompanying minor or major schema bump. That removal is out of scope for feature 015.
