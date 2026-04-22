# CLI Contract — `python -m ledgerlinc_ocr.extract`

Invocation surface for the stage 1 single-voter edge extractor. Pinned by spec FR-025 and
Clarifications Q4 (CLI signature) + Q3 (endpoint/voter-config split).

## Invocation

```text
python -m ledgerlinc_ocr.extract --folder <path> --voter <name> [--voter-config <path>]
```

### Required flags

- `--folder <path>` — absolute or relative path to a per-document folder. The folder MUST contain
  a schema-valid `preprocess_output.json` with `contract_set_version == "1.0.0"`.
- `--voter <name>` — short name selecting a shipped voter config
  (`src/ledgerlinc_ocr/extract/voters/configs/<name>.yaml`). Default ships with `gemma-edge`. The
  short name becomes part of `vote_metadata.voter_id` via the config file, NOT via the flag.

### Optional flags

- `--voter-config <path>` — explicit path to a voter config file. Overrides `--voter` resolution.
  Used for tests and for operators pinning custom config paths.
- `--log-level {DEBUG,INFO,WARNING,ERROR}` — stdlib logging level for stderr diagnostics.
  Default: `INFO`. Does not affect the artifact; `warnings` / `extraction_notes` are separate.

### Environment

- `OLLAMA_BASE_URL` — base URL for the host Ollama endpoint (e.g., `http://host.docker.internal:11434`
  inside the devcontainer, `http://localhost:11434` on the host). Required for all runs that use an
  Ollama-backed voter. Stub voters (tests) ignore this variable.
- `LEDGERLINC_VOTER_CONFIG_DIR` (optional) — override directory for voter configs; `<name>.yaml` in
  this directory takes precedence over the packaged default when `--voter <name>` is used.

## Behavior

1. Load and validate `--folder/preprocess_output.json` against the frozen preprocess schema.
   - On missing / unreadable / schema-invalid / `contract_set_version != "1.0.0"` → exit `2`, no
     artifact written, error to stderr.
2. Load the voter config.
   - On YAML parse error or pydantic validation error → exit `6`, no artifact written.
3. Render the prompt from the preprocessing packet using the voter's prompt template.
4. Call the voter adapter.
   - `OllamaVoter` POSTs to `${OLLAMA_BASE_URL}/api/generate` with `format: "json"`, the configured
     sampling options, and the configured per-request timeouts. No retries.
   - Connect refused / DNS failure / read timeout → exit `3`.
   - HTTP 404 with `"model not found"` semantics → exit `4`.
5. Parse and repair the response (R-007).
   - Unrepairable → exit `5`.
6. Run the reconciliation pipeline (see `data-model.md`).
7. Validate the assembled artifact against `edge_extraction_output.schema.json` IN-MEMORY.
   - If validation fails, exit `1` with a diagnostic — this is a programmer error (reconciliation
     produced an invalid artifact) and should never happen in practice; no file written.
8. Write `edge_extraction_output.json` atomically into `--folder`.
   - Write pattern: write-to-temp-in-same-folder + `os.replace` to final name.
   - On I/O error → exit `7`.
9. Exit `0`.

## Exit codes

| Code | Meaning |
|------|---------|
| `0`  | Artifact written; see `status` inside the file for soft-outcome detail. |
| `1`  | Unexpected / unclassified error (programmer bug, never a routine outcome). |
| `2`  | Input contract drift — preprocess packet missing, unreadable, schema-invalid, or wrong version. |
| `3`  | Ollama endpoint unreachable (connect refused, DNS failure, read timeout). |
| `4`  | Ollama model unavailable on the endpoint. |
| `5`  | Unrepairable model response. |
| `6`  | Voter configuration invalid (YAML parse or pydantic validation failure). |
| `7`  | Folder write error (cannot write `edge_extraction_output.json`). |

Codes 2-7 mean "no artifact written". Code 0 means "artifact written", which may still carry
`status="partial"` or `status="failure"` in the artifact body (R-012).

## Artifact write rules

- Writes exactly ONE file per invocation: `<folder>/edge_extraction_output.json`.
- Never modifies `preprocess_output.json`, `expected.json`, `notes.md`, `source.pdf`, or any file
  it did not create (FR-019).
- Never creates `routing_decision.json`, `final_structured_payload.json`,
  `evaluation_document.json`, `consensus_output.json`, or anything under `votes/` (FR-018).
- Second invocation against the same folder overwrites the existing `edge_extraction_output.json`
  (spec Edge Cases — version control is the history mechanism, not the extractor).

## Stderr diagnostics

- Successful runs: one INFO line summarizing the outcome — `"wrote edge_extraction_output.json
  (status=success, warnings=0)"` or similar.
- Hard failures: one ERROR line naming the cause (FR-015, US5).
- Repairs: one WARNING line per repair or drop event, plus the matching entry in the artifact's
  `warnings` array.

## Example invocations

```bash
# Normal stage 1 run against a corpus document
python -m ledgerlinc_ocr.extract \
    --folder tests/stage1_vendor_identity/inv_003_easy \
    --voter gemma-edge

# Smoke test with the stub voter (no Ollama required)
python -m ledgerlinc_ocr.extract \
    --folder tests/fixtures/extract/sample_folder \
    --voter stub

# Operator override: alternate Gemma config
LEDGERLINC_VOTER_CONFIG_DIR=/etc/ledgerlinc/voters python -m ledgerlinc_ocr.extract \
    --folder tests/stage1_vendor_identity/inv_007_medium \
    --voter gemma-edge
```
