# Quickstart — Single-Voter Edge Extraction (Stage 1)

End-to-end walk-through for running the extractor inside the devcontainer against a corpus
document with host Ollama.

## Prerequisites

- Devcontainer (`pipeline-dev`) is up: `code --folder-uri` → Reopen in Container, or
  `docker compose -f .devcontainer/docker-compose.yml up -d`.
- Package installed in the container:

  ```bash
  python3 -m venv .venv
  .venv/bin/pip install -e ".[dev]"
  ```

- Host Ollama is running (ROCm lane on native Linux for production-style, or CPU lane on WSL for
  benchmarks). Verify reachability from inside the devcontainer:

  ```bash
  curl -sf "${OLLAMA_BASE_URL:-http://host.docker.internal:11434}/api/tags" | head
  ```

- The target Gemma model is pulled on the Ollama host. For the stage 1 default:

  ```bash
  # Run on the Ollama host, not inside the devcontainer
  ollama pull gemma4:e4b
  ```

- A per-document folder exists with a schema-valid `preprocess_output.json` (produced by 003). The
  20-document corpus under `tests/stage1_vendor_identity/` is the default source.

## Run against one corpus document

```bash
.venv/bin/python -m dartwing_ocr.extract \
    --folder tests/stage1_vendor_identity/inv_003_easy \
    --voter gemma-edge
```

Expected outcome on a valid packet + reachable Ollama:

- Exit code `0`.
- `tests/stage1_vendor_identity/inv_003_easy/edge_extraction_output.json` exists.
- `status` in the artifact is `"success"` (clean run) or `"partial"` (repairs/drops/defaults).
- `contract_set_version == "1.0.0"`, `document_id` matches the preprocess packet.
- Every `evidence` ID resolves to a real `block_id` or `line_id` in `preprocess_output.json`.

## Verify the artifact with the contract validator

```bash
.venv/bin/python -m dartwing_ocr.validator validate artifact \
    --path tests/stage1_vendor_identity/inv_003_easy/edge_extraction_output.json \
    --kind edge_extraction_output
```

Expected: `OK` with `contract_set_version == "1.0.0"` reported back.

## Run against the missing-name corpus (US3 provenance check)

```bash
for folder in tests/stage1_vendor_identity/inv_*_missing_name; do
    .venv/bin/python -m dartwing_ocr.extract --folder "$folder" --voter gemma-edge
done
```

Expected: every produced `edge_extraction_output.json` has:
- `vendor_candidate.company_name.present == false`
- `vendor_candidate.company_name.inferred == true`
- Exactly one of the two invariants true (FR-013)

SC-002 is this, at 100%.

## Run with the stub voter (no Ollama required)

Useful for CI, for exercising the pluggable-voter seam, and for US4 / SC-004 verification.

```bash
.venv/bin/python -m dartwing_ocr.extract \
    --folder tests/fixtures/extract/sample_folder \
    --voter stub
```

Expected:
- No network call.
- Artifact written with `model_runtime.provider == "stub"`, `vote_metadata.voter_id == "stub@test"`.
- Artifact shape is identical to a Gemma run (only the voter-identifying metadata and the model-
  dependent scalar values differ).

## Hard-failure smoke tests (US5)

### Ollama unreachable

```bash
OLLAMA_BASE_URL=http://127.0.0.1:1 \
    .venv/bin/python -m dartwing_ocr.extract \
    --folder tests/stage1_vendor_identity/inv_003_easy \
    --voter gemma-edge
echo "exit=$?"
```

Expected: `exit=3`, no `edge_extraction_output.json` written.

### Contract drift on input

Point at a folder whose `preprocess_output.json` has a non-`1.0.0` version:

```bash
.venv/bin/python -m dartwing_ocr.extract \
    --folder tests/fixtures/extract/drift_folder \
    --voter stub
echo "exit=$?"
```

Expected: `exit=2`, stderr names the contract drift.

### Voter config invalid

Pass a broken YAML path:

```bash
.venv/bin/python -m dartwing_ocr.extract \
    --folder tests/stage1_vendor_identity/inv_003_easy \
    --voter-config /tmp/nonexistent.yaml
echo "exit=$?"
```

Expected: `exit=6`.

## Run the test suite

```bash
.venv/bin/pytest tests/unit/extract tests/integration/extract tests/contract_tests
```

The integration smoke test (`test_host_ollama_smoke.py`) auto-skips when `OLLAMA_BASE_URL` is
unreachable, so the suite passes in CI environments without Ollama.

## Typical iteration workflow

1. Edit `src/dartwing_ocr/extract/voters/configs/gemma-edge.yaml` to try a different
   `ollama.model_tag` or `sampling.*`. No code changes needed.
2. Edit `src/dartwing_ocr/extract/voters/configs/prompts/gemma_edge_extractor.md` to iterate on
   the prompt. No code changes needed.
3. Re-run the one-document invocation above.
4. Run `pytest tests/unit/extract` to verify reconciliation still matches the truth tables.
5. Spot-check `edge_extraction_output.json` against the corresponding `expected.json` by eye (the
   harness-driven evaluation lives in slice 008 — this slice intentionally stops short of that).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `exit=3` immediately | `OLLAMA_BASE_URL` wrong or Ollama down | Verify `curl ${OLLAMA_BASE_URL}/api/tags` |
| `exit=4` | Model not pulled on host | `ollama pull <model_tag>` on the Ollama host |
| `exit=5` | Gemma emitted unrepairable prose | Tighten the prompt; try `temperature: 0.0` + seed; re-run |
| `exit=6` | Voter-config YAML typo | Check the pydantic error on stderr |
| Empty `evidence` arrays everywhere | Prompt did not include the ID map | Check the prompt template; IDs must be visible to the model |
| `status: "failure"` on every doc | Probably bad prompt or wrong model | Run `--voter stub` to confirm reconciliation works |
