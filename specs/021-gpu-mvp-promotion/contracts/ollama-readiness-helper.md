# Contract: Ollama Readiness Helper (FR-002)

**Path**: `scripts/check-ollama-gpu-readiness.sh`
**Spec refs**: [spec.md §FR-002](../spec.md), [research.md §R-021.9](../research.md), [data-model.md §6](../data-model.md)
**Constitution refs**: §I (boundary — outside `dartwing_ocr`), §III (deterministic check)

This contract defines the shell helper invoked by the readiness gate (FR-001 covers Paddle preflight; this helper covers FR-002 Ollama placement). The helper is implemented in POSIX-compatible shell using `curl` + `jq` + `yq` (system tools), with no Python dependency.

**Tool prerequisites**: `curl`, `jq`, and `mikefarah/yq v4+` (Go binary; the apt-packaged kislyuk/python-yq variant works for the simple `.model_name` expression the helper uses, but the Go binary is what the workstation host and devcontainer install). The devcontainer Dockerfile installs all three; on bare-metal workstations operators must ensure they are on `$PATH`. Missing prereqs exit `3` (curl/jq) or `4` (yq) with a named-cause stderr line.

## Invocation

```bash
scripts/check-ollama-gpu-readiness.sh \
    --voter-config <PATH> \
    [--base-url <URL>]
```

### Required flags

- `--voter-config <PATH>` — Path to a YAML file containing a top-level `model_name: string` key (feature 005 voter-config schema). The helper extracts `model_name` and uses it as the lookup key into `/api/ps`.

### Optional flags

- `--base-url <URL>` — Ollama base URL. Default `http://localhost:11434`. The helper appends `/api/ps`.

### Disallowed surfaces

- No interactive prompts.
- No model loading (`POST /api/generate`, `POST /api/pull`, etc.) — strictly read-only against Ollama (R-021.6).
- No persistent writes to disk. The helper creates exactly one ephemeral file via `mktemp(1)` to hold the HTTP response body for `jq` parsing; the file is unlinked on EXIT/INT/TERM via a `trap` cleanup handler. No user-visible state survives the process. (This is the only filesystem side effect; the surrounding contract continues to treat the helper as read-only with respect to persistent state.)
- No retries or wait loops.

## Exit codes

| Code | Class                  | Condition                                                                                         |
|-----:|------------------------|---------------------------------------------------------------------------------------------------|
| `0`  | PASS                   | `/api/ps` returned 200; matched-model entry has `size_vram > 0 AND size_vram == size`             |
| `1`  | FAIL — partial GPU     | Matched-model entry has `size_vram == 0` OR `0 < size_vram < size`                                |
| `2`  | FAIL — not loaded      | `/api/ps` returned 200 but the matched-model name is absent from `models[]`                       |
| `3`  | FAIL — unreachable     | Curl non-zero, network error, non-200 HTTP response, or unparseable JSON                          |
| `4`  | FAIL — config          | `--voter-config` PATH missing, not readable, not valid YAML, or lacks a non-empty `model_name`    |

No other exit codes are defined. The runbook and any wrapper scripts MUST treat unknown exit codes as FAIL of an unspecified class.

## Output streams

### Stdout (PASS only — exit 0)

A single JSON object on a single line:

```json
{"status":"pass","model_name":"<name>","size":<bytes>,"size_vram":<bytes>,"base_url":"<url>","voter_config_path":"<path>","timestamp_utc":"<iso8601>"}
```

The line MUST be JSON-valid (suitable for `| jq`). No additional stdout content is emitted on PASS.

### Stderr (FAIL — exit ≥ 1)

A single human-readable line beginning with `FAIL:` followed by the named cause:

| Exit | Stderr template                                                                                                            |
|-----:|----------------------------------------------------------------------------------------------------------------------------|
| `1`  | `FAIL: extraction model "<name>" partially on GPU at <base_url>/api/ps (size_vram=<n>, size=<m>)`                          |
| `2`  | `FAIL: extraction model "<name>" not loaded in Ollama at <base_url>/api/ps`                                                |
| `3`  | `FAIL: Ollama unreachable at <base_url>/api/ps (<error-detail>)`                                                           |
| `4`  | `FAIL: voter-config <path> missing or malformed (<reason>)`                                                                |

No stdout is emitted on FAIL. Stderr templates MUST name the unmet prerequisite per FR-004 / SC-002.

## Behavior contract

1. **Argument parsing**: missing or unrecognized flags → exit `4` with stderr template `FAIL: voter-config <path> missing or malformed (usage error)`. The helper does NOT print a usage banner to stderr beyond the FAIL line.
2. **Voter-config read**: read `--voter-config` PATH; parse as YAML via `yq -r '.model_name'`; require non-empty string; on any failure → exit `4`.
3. **HTTP fetch**: `curl --silent --show-error --fail --max-time 10 <base_url>/api/ps`; on curl non-zero or non-200 → exit `3`.
4. **JSON parse**: pipe response through `jq -e --arg n "<model_name>" '.models[] | select(.name == $n)'`; on no match → exit `2`.
5. **Placement check**: extract `size` and `size_vram` from the matched entry; if `size_vram == 0 || size_vram < size` → exit `1`; else → exit `0`.
6. **Stdout emission**: on exit `0` only, emit the PASS JSON line (above).
7. **Determinism**: given identical voter-config + identical `/api/ps` response, the helper MUST produce an identical exit code and an identical structural stdout JSON (same keys, same values) on PASS, or an identical stderr line on FAIL (Constitution §III). The `timestamp_utc` field in the PASS JSON is provenance metadata captured at invocation time (`date -u +%Y-%m-%dT%H:%M:%SZ`) and is the only field that varies across otherwise-identical invocations — it is NOT part of the placement-check determinism contract, only of the audit trail. Callers MUST NOT key cache lookups, signature checks, or equality assertions on `timestamp_utc`.

## Integration contract

- The helper is invoked by the demo runbook directly (operator runs it as the second readiness step after `python -m dartwing_ocr.preprocessing.preflight`).
- The helper is also invoked by the four-run benchmark wrapper (called from the runbook) before each lane's first run; failure aborts the benchmark sequence per FR-004.
- The helper does NOT call `python -m dartwing_ocr.preprocessing.preflight`; the runbook orders the two checks sequentially.

## Testability

- **Unit-ish coverage** (CPU-safe, no live Ollama required): a CPU-safe contract test under `tests/contract_tests/` MAY mock the helper's invocation environment using a captured `/api/ps` response fixture and verify each exit-code path. Not required for landing — the helper's deterministic shell logic is small enough that the contract above is the verification surface.
- **Integration coverage** (GPU-only): the demo runbook's readiness step exercises the helper end-to-end on the workstation Ollama.

## What this contract does NOT cover

- It does not define how Ollama is started (see `scripts/start-host-ollama-rocm-wsl.sh`).
- It does not define how the extraction model is loaded into Ollama (operator runs `ollama run <model_name> ""` or waits for the demo's first extraction call; R-021.6).
- It does not implement retries or wait loops; the runbook tells the operator to re-run the helper after remediation.
