# Quickstart: Stage 1 Pipeline Controller (Feature 011)

**Branch**: `011-stage-runtime-profiles`
**Audience**: pipeline + harness developers running the controller in the devcontainer or on a native Linux ROCm host.
**Prerequisites**: `pip install -e ".[dev]"` from the repo root inside the devcontainer (or any env with Python 3.12 and the dependencies pinned in `pyproject.toml`).

This walk-through shows the four execution shapes feature 011 enables, in priority order from FR-034:

1. Stub-only contract verification (no Ollama, no Paddle).
2. Single-stage execution slice (cold debugging).
3. Warm-corpus run with `ppstructurev3@cpu` over multiple documents.
4. Real default profile run end-to-end.

Replace `<repo>` with your absolute repo root and `<corpus>` with `<repo>/tests/stage1_vendor_identity` unless stated otherwise.

---

## 0. Verify the install

```bash
python -m ledgerlinc_ocr.pipeline run --help | head -40
```

You should see the new flags listed: `--preprocess-profile`, `--extract-profile`, `--routing-profile`, `--final-payload-profile`, `--stack-preset`, `--start-at`, `--stop-after`, `--documents-file`, `--on-failure`, `--ollama-cpu-url`, `--ollama-jetson-url`. If any are missing, the install is stale; re-run `pip install -e ".[dev]"`.

---

## 1. Stub-only run (network-free, model-free)

Verifies the controller foundation slice (FR-034 step 1) without touching Paddle or Ollama. Useful in CI and for quick contract sanity-checks.

```bash
mkdir -p /tmp/stub-run && cp tests/stage1_vendor_identity/inv_001_easy/source.pdf /tmp/stub-run/

python -m ledgerlinc_ocr.pipeline run \
    --document-folder /tmp/stub-run \
    --preprocess-profile stub \
    --extract-profile stub \
    --routing-profile stub \
    --final-payload-profile stub \
    --document-id inv_001
```

Expected:

- Exit code `0`.
- Four files written into `/tmp/stub-run/`: `preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`.
- One JSON line on stdout matching the existing `002-cli-contract` success summary (no `kind` field).

Validate the artifacts against the installed contract set:

```bash
python -m ledgerlinc_ocr.validator validate folder /tmp/stub-run
```

---

## 2. Single-stage slice (cold debugging)

Use case: re-run only extraction against an already-preprocessed folder without reprocessing the PDF.

### 2a. Produce a `preprocess_output.json` first

```bash
python -m ledgerlinc_ocr.pipeline run \
    --document-folder /tmp/stub-run \
    --preprocess-profile stub \
    --stop-after preprocess \
    --overwrite
```

Only `preprocess_output.json` is rewritten; the other three artifacts (if present from step 1) are untouched. The overwrite guard is scoped to the slice (FR-011, R-006).

### 2b. Re-run only the extract stage

```bash
python -m ledgerlinc_ocr.pipeline run \
    --document-folder /tmp/stub-run \
    --start-at extract \
    --stop-after extract \
    --extract-profile stub \
    --overwrite
```

The runner validates the upstream `preprocess_output.json` against the installed contract set (FR-010, R-005) before running extract; any mismatch fails fast with stage `prerequisite_validation` and no downstream write.

### 2c. Hard-fail when prerequisites are missing

```bash
rm /tmp/stub-run/preprocess_output.json
python -m ledgerlinc_ocr.pipeline run \
    --document-folder /tmp/stub-run \
    --start-at routing \
    --stop-after routing \
    --routing-profile stub
```

Expected exit code `11` (`INPUT_NOT_FOUND`) when the prerequisite is missing, or `30` (`SCHEMA_VALIDATION_FAILURE`) when it exists but does not validate against the installed contract set; stderr carries a structured failure record with stage `prerequisite_validation` naming `preprocess_output.json` (or `edge_extraction_output.json`, depending on which is missing first) as the unmet prerequisite.

---

## 3. Warm-corpus run with `ppstructurev3@cpu`

Use case: harness-driven multi-document run that initializes PPStructureV3 exactly once per process. This is the slice the controller exists to deliver (FR-034 step 2, SC-009).

### 3a. Prepare a documents file

```bash
cat > /tmp/corpus.txt <<EOF
# stage 1 vendor-identity smoke set
$PWD/tests/stage1_vendor_identity/inv_001_easy
$PWD/tests/stage1_vendor_identity/inv_002_easy
$PWD/tests/stage1_vendor_identity/inv_003_easy
EOF
```

The file is UTF-8, one folder per line, blank/`#`-comment lines ignored after stripping. Paths inside the file resolve relative to the file's parent directory (R-007), so this example writes absolute paths with `$PWD` because the file itself lives under `/tmp`. Edit the list to point at any subset of the 20-document corpus.

### 3b. Run with stub profiles first (Paddle-free smoke test)

```bash
python -m ledgerlinc_ocr.pipeline run \
    --documents-file /tmp/corpus.txt \
    --preprocess-profile stub \
    --extract-profile stub \
    --routing-profile stub \
    --final-payload-profile stub
```

Expected:

- Exit code `0`.
- Three per-document success records on stdout (one JSON line each, existing `002` shape).
- One `kind: "run_summary"` JSON line as the **last** stdout line, with `documents_total: 3`, `documents_succeeded: 3`, `documents_failed: 0`, and `profile_initialization_seconds: {}` (no live profile was warmed).

### 3c. Run with `ppstructurev3@cpu` (the real warm path)

```bash
python -m ledgerlinc_ocr.pipeline run \
    --documents-file /tmp/corpus.txt \
    --preprocess-profile ppstructurev3@cpu \
    --extract-profile stub \
    --routing-profile stub \
    --final-payload-profile stub
```

Expected:

- Exit code `0`.
- Three per-document success records on stdout.
- One `kind: "run_summary"` line with `profile_initialization_seconds.preprocess` approx 8-15 seconds on a typical workstation (the one-time PPStructureV3 init), and per-document `stages.preprocess` totals well below the initialization time. SC-009 is satisfied when `profile_initialization_seconds.preprocess` appears exactly once in the summary regardless of how many documents the file lists.
- Each document folder receives its full set of four canonical artifacts (the trailing stages used `stub` profiles to keep the test self-contained). The artifacts validate against the installed contract set.

### 3d. Continue-through-failures (default)

Add a deliberately-broken folder to the file and rerun:

```bash
mkdir -p /tmp/inv_999_easy && echo "not a pdf" > /tmp/inv_999_easy/source.pdf
echo "/tmp/inv_999_easy" >> /tmp/corpus.txt

python -m ledgerlinc_ocr.pipeline run \
    --documents-file /tmp/corpus.txt \
    --preprocess-profile ppstructurev3@cpu \
    --extract-profile stub \
    --routing-profile stub \
    --final-payload-profile stub
```

Expected:

- Three per-document success records on stdout, one structured failure record on stderr for `/tmp/inv_999_easy`.
- One `kind: "run_summary"` line with `documents_total: 4`, `documents_succeeded: 3`, `documents_failed: 1`, and a `per_document` entry of status `failure` for the broken folder naming the failed stage and exit code.
- Process exit code: the highest-severity per-document exit code observed (non-zero), per R-008.

To switch to fail-fast, append `--on-failure fail-fast`. The first failure aborts the run; documents listed after the failed entry are not attempted and do not appear in `per_document`.

---

## 4. Real default profile run end-to-end

Use case: top-level harness invocation that exercises the real preprocessing -> extraction -> routing -> final payload chain on the workstation. Lands after FR-034 step 3.

```bash
# Single document, defaults (ppstructurev3@cpu / ollama@gpu / rules@cpu / assembler@cpu)
python -m ledgerlinc_ocr.pipeline run \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --overwrite
```

Or, equivalently, with the preset:

```bash
python -m ledgerlinc_ocr.pipeline run \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --stack-preset full-workstation \
    --overwrite
```

Or, for the multi-document harness path:

```bash
python -m ledgerlinc_ocr.pipeline run \
    --documents-file /tmp/corpus.txt \
    --stack-preset full-workstation
```

Expected on the workstation with host Ollama running on `:11434`:

- Each document gets all four real artifacts.
- The run summary shows `profile_initialization_seconds.preprocess` once, and each per-document `stages.extract.infer_seconds` reflects the real Ollama call.
- `resolved_profiles` in the run summary echoes the preset's expansion, with `stack_preset: "full-workstation"`.

To switch to the optional CPU Ollama lane (the WSL CPU container, default `:11435`):

```bash
docker compose -f .devcontainer/docker-compose.yml --profile ollama up -d
python -m ledgerlinc_ocr.pipeline run \
    --documents-file /tmp/corpus.txt \
    --preprocess-profile ppstructurev3@cpu \
    --extract-profile ollama@cpu \
    --routing-profile rules@cpu \
    --final-payload-profile assembler@cpu
```

The artifact filenames and schemas are byte-identical between the two extraction lanes (FR-014); only metadata fields the schema already permits to vary may differ.

---

## 5. `cloud-workstation` selection: name-only in this slice

`cloud-workstation` and `ensemble@workstation` are accepted by argument validation in this feature but the live implementation is deferred to FR-034 step 4. Selecting them produces a deterministic fail-fast:

```bash
python -m ledgerlinc_ocr.pipeline run \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --stack-preset cloud-workstation \
    --overwrite
```

Expected exit code `10` (`USAGE_ERROR`); stderr's structured failure record uses the canonical stage name (`extraction` for `ensemble@workstation` / `ollama@jetson`, `preprocess` for `edge-ocr@jetson`) and the message names the offending profile and the FR-034 step 4 deferral. No artifacts are written. The same fail-fast applies to `--extract-profile ensemble@workstation` directly.

---

## 6. Verifying SC-009 (warm initialization happens exactly once)

After running step 3c, inspect the run summary line:

```bash
python -m ledgerlinc_ocr.pipeline run \
    --documents-file /tmp/corpus.txt \
    --preprocess-profile ppstructurev3@cpu \
    --extract-profile stub \
    --routing-profile stub \
    --final-payload-profile stub \
    | tail -1 \
    | python -c 'import sys, json; s = json.loads(sys.stdin.read()); print({"kind": s["kind"], "init": s["profile_initialization_seconds"], "per_doc_count": len(s["per_document"])})'
```

A successful warm corpus run prints exactly one entry under `init` (keyed by `preprocess`) regardless of how many documents the corpus file listed. If any document re-warmed PPStructureV3, the controller has regressed and the warm-corpus integration test should fail.

---

## 7. Common failure modes & their stderr stages

| Symptom | Likely stage in failure record | Likely exit code |
|---|---|---|
| `--input` and `--documents-file` both passed | `arguments` | `10` `USAGE_ERROR` |
| `--documents-file` points at a missing path | `corpus_validation` | `10` `USAGE_ERROR` |
| `--documents-file` parses to zero documents | `corpus_validation` | `10` `USAGE_ERROR` |
| `--start-at extract` but no `preprocess_output.json` in folder | `prerequisite_validation` | `11` `INPUT_NOT_FOUND` |
| `--start-at routing` and `edge_extraction_output.json` is malformed | `prerequisite_validation` | `30` `SCHEMA_VALIDATION_FAILURE` |
| `--extract-profile gemma` (unknown implementation) | `arguments` | `10` `USAGE_ERROR` |
| `--routing-profile rules@gpu` (unsupported lane) | `arguments` | `10` `USAGE_ERROR` |
| `--extract-profile ensemble@workstation` inside the slice | `extraction` (canonical stage name) | `10` `USAGE_ERROR` |
| `--extract-profile ollama@jetson` inside the slice | `extraction` | `10` `USAGE_ERROR` |
| `--preprocess-profile edge-ocr@jetson` inside the slice | `preprocess` | `10` `USAGE_ERROR` |
| Reserved artifact already present without `--overwrite`, inside slice | `input_validation` | `13` `OUTPUT_IN_USE` |

For continue-through-failures runs in warm-corpus mode, each per-document failure produces a `StructuredFailureRecord` line on stderr; the process exit code reflects the highest-severity per-document failure.

---

## What this feature does NOT do (worth re-reading before /speckit.tasks)

- It does **not** change any of the four canonical artifact schemas (FR-029).
- It does **not** introduce a new persisted benchmark file (FR-030, FR-036).
- It does **not** add CLI flags, env vars, or config files for `ensemble@workstation` voter endpoints - that surface lives in the secondary-lane slice (R-013).
- It does **not** include live `edge-ocr@jetson` or `ollama@jetson` adapters - recognition only in this slice (R-014).
- It does **not** call any external cloud-provider API or accept cloud credentials (FR-021, FR-036).

If you find yourself reaching for one of these in /speckit.tasks, stop and check whether the work belongs in FR-034 step 4 instead.
