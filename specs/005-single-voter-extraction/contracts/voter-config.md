# Voter Configuration Contract

YAML file selected by `--voter <name>` or `--voter-config <path>` (see `cli-contract.md`).
Pinned by spec Clarifications Q3 and research.md §R-005.

## Resolution order

1. `--voter-config <path>` (absolute or relative path) — wins if present.
2. `$LEDGERLINC_VOTER_CONFIG_DIR/<name>.yaml` — operator override directory.
3. `src/ledgerlinc_ocr/extract/voters/configs/<name>.yaml` — packaged default.

## Schema (pydantic-validated)

```yaml
# Required top-level keys
voter_id: string (non-empty)               # → vote_metadata.voter_id
voter_role: "primary_extractor"            # stage 1 only; other enum values reserved
consensus_mode: "single_voter_baseline"    # stage 1 only

# Copied verbatim into edge_extraction_output.model_runtime
model_runtime:
  provider: string (non-empty)
  model_name: string (non-empty)
  model_version: string (non-empty)
  runtime: string (non-empty)

# Ollama HTTP call configuration
ollama:
  model_tag: string (non-empty)            # e.g., "gemma4:e4b"
  timeout_seconds: float > 0                # default 180.0 if absent
  connect_timeout_seconds: float > 0        # default 10.0 if absent

# Model sampling
sampling:
  temperature: float in [0.0, 2.0]          # default 0.0
  seed: integer | null                      # default 42; null if model does not accept seed
  top_p: float in [0.0, 1.0] | null         # default null
  top_k: integer > 0 | null                 # default null

# Prompt
prompt:
  template_path: string                     # path to prompt file, relative to THIS config file
  max_output_tokens: integer > 0            # default 2048
  format: "json" | null                     # Ollama structured-output directive; default "json"

# Reconciliation knobs (affect extractor behavior, not Ollama)
reconciliation:
  ungrounded_confidence_cap: float in [0.0, 1.0]   # default 0.30 — FR-011 / R-003
```

## Stage 1 default: `gemma-edge.yaml`

```yaml
voter_id: "gemma-4-e4b-edge@2026-04"
voter_role: "primary_extractor"
consensus_mode: "single_voter_baseline"

model_runtime:
  provider: "host_ollama"
  model_name: "gemma-4-e4b"
  model_version: "2026-04-14-rocm"
  runtime: "ollama-rocm-linux-host"

ollama:
  model_tag: "gemma4:e4b"
  timeout_seconds: 180.0
  connect_timeout_seconds: 10.0

sampling:
  temperature: 0.0
  seed: 42
  top_p: null
  top_k: null

prompt:
  template_path: "prompts/gemma_edge_extractor.md"
  max_output_tokens: 2048
  format: "json"

reconciliation:
  ungrounded_confidence_cap: 0.30
```

## Stub / fixture voter: `stub.yaml`

Used by `tests/integration/extract/` to prove the pluggable-voter seam (US4 / SC-004). The
stub voter does not call Ollama; it reads a canned fixture JSON whose path comes from the
config.

```yaml
voter_id: "stub@test"
voter_role: "primary_extractor"
consensus_mode: "single_voter_baseline"

model_runtime:
  provider: "stub"
  model_name: "stub-voter"
  model_version: "0"
  runtime: "in-process-fixture"

# Stub voter does not use the ollama block, but the schema requires it for uniformity.
ollama:
  model_tag: "unused"
  timeout_seconds: 1.0
  connect_timeout_seconds: 1.0

sampling:
  temperature: 0.0
  seed: 0
  top_p: null
  top_k: null

prompt:
  template_path: "prompts/stub_noop.md"
  max_output_tokens: 1
  format: null

reconciliation:
  ungrounded_confidence_cap: 0.30
```

The stub voter additionally reads a fixture-path override via a synthetic extension key that is
handled outside the pydantic model (so swapping fixtures in tests does not require a schema
change). This escape hatch lives in `voters/stub.py` and is not part of the shared contract.

## Unknown keys

Pydantic is configured with `extra = "forbid"`. An unknown top-level or nested key fails
validation at load time with exit code `6` — catches typos like `voter_rol:` or
`reconcilation:` before they cause downstream confusion.
