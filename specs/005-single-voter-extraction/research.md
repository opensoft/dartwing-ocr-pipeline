# Phase 0 Research — Single-Voter Edge Extraction

Resolves every NEEDS CLARIFICATION item from the plan's Technical Context and pins the open
numeric defaults the spec's Clarifications section deferred here.

## R-001: Ollama HTTP client

**Decision**: Use `httpx` directly against the Ollama `/api/generate` endpoint, sync client,
single-request timeout, no retries. Do not take a dependency on the `ollama` Python SDK.

**Rationale**:
- `httpx` has explicit per-request timeout semantics (connect / read / write / pool) and cleanly
  surfaces `httpx.TimeoutException`, which maps 1:1 to FR-015's "hard failure on timeout" rule. The
  `requests` library's timeout handling is fuzzier and its retry machinery is optional-adapter-
  based, which is harder to *disable* than to *configure*.
- The `ollama` Python SDK wraps `/api/generate` plus `/api/chat` plus streaming, but adds an
  abstraction layer we'd have to peel back to enforce "one HTTP call, one bounded timeout, no
  retries" (FR-015) and to surface the `voter_role`/`voter_id` seam (FR-017). Using `httpx`
  directly keeps the adapter's responsibilities visible and the dependency surface small.
- `httpx` has no implicit retries; setting `timeout=httpx.Timeout(N)` and no transport-level retry
  config yields exactly the single-call semantics the spec mandates.

**Alternatives considered**:
- `requests` — works, but retry/timeout defaults are coarser and the type story is worse.
- `ollama` SDK — introduces an abstraction that obscures the HTTP-call-per-invocation guarantee.
- `aiohttp` / async — unnecessary; one HTTP call per invocation, no concurrency benefit.

## R-002: Ollama HTTP timeout default

**Decision**: `OLLAMA_REQUEST_TIMEOUT_SECONDS = 180.0` — the single bounded timeout for the model
call. Configurable via voter-config (`timeout_seconds`), defaulted in `gemma-edge.yaml`. Applied to
the HTTP read timeout; connect timeout is a shorter `10.0` s.

**Rationale**:
- Spec Clarifications Q2 pinned the *shape*: a single long timeout, no retries. This decision pins
  the numeric value.
- Gemma 4 E4B on a CPU Ollama (the WSL lane) can take tens of seconds to produce the structured
  JSON for a 2–3 page invoice; 120 s is sometimes tight under warm-cache cold-start conditions. 180 s
  gives headroom for the CPU-only benchmark lane without softening the hard-failure semantics on
  ROCm.
- A short connect timeout (10 s) catches the "Ollama endpoint down / wrong URL" case quickly,
  keeping US5 AC (b) fast to verify.
- The voter-config override exists so a slow-model fixture can raise the ceiling (e.g., Phi-4 Mini
  on CPU) without editing code.

**Alternatives considered**:
- `60.0` s — too tight for CPU Ollama; risks turning slow-model runs into spurious hard failures.
- `300.0` s — too slow to surface a genuinely-stuck endpoint; delays developer feedback.
- Connect + read as a single compound timeout — `httpx`'s `Timeout(connect=..., read=...)` lets us
  separate "endpoint down" from "model is slow", which matches the distinction US5 AC (b) draws.

## R-003: UNGROUNDED_CONFIDENCE_CAP

**Decision**: `UNGROUNDED_CONFIDENCE_CAP = 0.30`. Applied per-field after evidence reconciliation:
if a field's final `evidence` array is empty, `field.confidence = min(field.confidence, 0.30)`. The
model's `value` is retained; only `confidence` is clipped. Applies to every
`value_confidence_evidence` field AND to `total_amount` AND to `document_type`.

**Rationale**:
- Spec Clarifications Q1 pinned the *rule shape* (hard ceiling, not multiplicative). This decision
  pins the number.
- `0.30` lives clearly below any reasonable "grounded" threshold (routing 006 will almost certainly
  treat `< 0.5` as review-required territory) and clearly above `0.0` (which would be equivalent to
  option C — zero-out — that we rejected).
- For `company_name`, the cap is redundant with the `present=false, inferred=true` override from
  FR-012 (routing will key off the booleans, not the confidence), but applying the cap uniformly
  keeps the reconciliation function simple and keeps all fields on the same rule.

**Alternatives considered**:
- `0.20` — too aggressive; may collide with legitimate low-confidence-but-grounded readings after
  future rule refinements.
- `0.50` — too close to typical grounded confidences; fails the "clearly ungrounded" signal
  property.
- Per-field caps — unnecessary complexity; the empty-evidence condition is itself the per-field
  signal.

## R-004: Voter config file format and path convention

**Decision**: YAML (`.yaml`) for voter configs. Parsed via `PyYAML` with `safe_load`. Validated by
a pydantic model (`VoterConfig`) at load time. Resolved from a fixed search path:

1. `--voter-config <path>` CLI flag (explicit path override, wins if set).
2. Otherwise, `--voter <name>` resolves to `src/ledgerlinc_ocr/extract/voters/configs/<name>.yaml`
   (ships with the package; `gemma-edge` is the default).
3. An optional user override dir (`$LEDGERLINC_VOTER_CONFIG_DIR/<name>.yaml`) takes precedence over
   the packaged default when set. This allows operators to pin alternate Gemma tags without a
   package rebuild.

**Rationale**:
- YAML is more operator-friendly for a file that will occasionally have a long prompt string in it;
  JSON's lack of multi-line strings and comments would force either a sibling `.prompt.md` file or
  painful escaping.
- `PyYAML` is already common in Python tooling; `safe_load` avoids arbitrary-object deserialization.
- Shipping `gemma-edge.yaml` in-package makes `python -m ledgerlinc_ocr.extract --folder ... --voter
  gemma-edge` work out of the box. The env-var override path lets ops pin versions without code
  churn (US4).
- Pydantic validation catches typos at load time (e.g., `voter_role: primry_extractor`) with a
  clear error, rather than at prompt-send time.

**Alternatives considered**:
- JSON — uniform with contracts, but painful for prompt text.
- TOML — fine, but less familiar for operators in this project; no existing TOML config.
- Env-var-only — rejected by spec Clarifications Q3 (operator ergonomics + per-voter config
  cluster).

## R-005: Voter config schema (stage 1 shape)

**Decision**: Voter config file has the following keys (validated by pydantic
`VoterConfig`); details live in `contracts/voter-config.md`:

```yaml
voter_id: "gemma-4-e4b-edge@2026-04"      # non-empty string; becomes vote_metadata.voter_id
voter_role: "primary_extractor"            # stage 1 must be primary_extractor
consensus_mode: "single_voter_baseline"    # pinned in stage 1

model_runtime:
  provider: "host_ollama"                  # model_runtime.provider
  model_name: "gemma-4-e4b"                # model_runtime.model_name
  model_version: "2026-04-14-rocm"         # model_runtime.model_version
  runtime: "ollama-rocm-linux-host"        # model_runtime.runtime

ollama:
  model_tag: "gemma4:e4b"                  # Ollama model name as pulled on the host
  timeout_seconds: 180.0
  connect_timeout_seconds: 10.0

sampling:
  temperature: 0.0                         # spec Clarifications Q5
  seed: 42                                 # spec Clarifications Q5; null if model does not support
  top_p: null
  top_k: null

prompt:
  template_path: "prompts/gemma_edge_extractor.md"   # resolved relative to the voter-config file
  max_output_tokens: 2048
  format: "json"                           # Ollama structured-output directive

reconciliation:
  ungrounded_confidence_cap: 0.30          # FR-011 (R-003)
```

**Rationale**:
- The four `model_runtime` fields are copied verbatim into the artifact; making them config-driven
  lets a voter swap change identifying metadata without code changes (FR-017).
- `sampling` is split out so non-Gemma voters (Qwen, Phi-4 Mini) can override per-model without
  forking the adapter.
- The prompt lives in its own file next to the config, referenced by relative path. This keeps
  configs small and makes prompt iteration a zero-code change.
- `reconciliation.ungrounded_confidence_cap` being config-driven lets the plan default (`0.30`)
  evolve per-voter if data shows one model groundlessly over-confident and another not.

**Alternatives considered**:
- Hardcoded cap — rejected; would require a code change to tune per voter.
- Single-file prompt-plus-config — rejected; prompt diffs would pollute config diffs and vice versa.

## R-006: Prompt strategy and Ollama structured-output directive

**Decision**: Use Ollama's `format: "json"` directive on `/api/generate` to nudge the model toward
JSON output, combined with a system + user prompt pair that:
1. Names the preprocessing packet as the only source of truth.
2. Lists the exact JSON keys the voter must emit (mirroring the `edge_extraction_output.schema.json`
   shape, minus the harness-set fields like `processed_at`, `pipeline_version`, `contract_set_version`,
   `model_runtime`, `vote_metadata`, `status`, and `warnings`).
3. For every block and every raw OCR line, includes `block_id`/`line_id` alongside its text so the
   model can cite evidence by ID.
4. Gives explicit rules: "use `null` for missing fields; never empty strings"; "cite every claim
   with at least one `block_id` or `line_id` from the input"; "if no evidence supports a company
   name, return a best guess and set `company_name.present=false, company_name.inferred=true`".

**Rationale**:
- `format: "json"` significantly increases JSON-validity rate on Ollama-served models without
  guaranteeing schema compliance — the parse+repair step (R-007) handles the residual cases.
- Including the ID map in the prompt is non-negotiable; without it the model hallucinates evidence
  and US2 reconciliation has to discard everything. This is the evidence-first contract at the
  prompt layer.
- Naming the company-name invariant in the prompt pushes the rule at inference time; the
  FR-012/FR-013 code-level override is the backstop, not the only line of defense.

**Alternatives considered**:
- Full JSON-grammar constraint (llama.cpp-style GBNF) — Ollama exposes grammars for some models but
  not uniformly across Gemma/Qwen/Phi; would lock us into one inference path. Schema-nudge via the
  `format` hint is a portable baseline.
- Few-shot exemplars — deferred. Risks biasing the model toward the exemplar vendor/invoice; stage
  1 has a small corpus and contamination is a real concern.

## R-007: Model-response parsing and JSON repair

**Decision**: Two-stage parse:
1. Strict `json.loads` on the raw response body.
2. If that fails, a minimal repair pass: strip leading/trailing prose, strip Markdown code
   fences (` ```json ... ``` `), strip a single leading/trailing byte order mark. Re-attempt
   `json.loads`. If that fails, raise `UnrepairableResponse`, which the CLI translates into a
   hard failure (exit non-zero, no artifact — US5 AC "empty response, unparseable").

When repair succeeds but required modification occurred, `warnings` gets an entry (`"model
response required repair: stripped markdown fence"` or similar) and `status` is forced to
`"partial"` (FR-014, FR-016, US5 AC #2).

**Rationale**:
- The common repair cases are well-known and cheap to handle inline; pulling in a full JSON-repair
  library (`json-repair`, `demjson3`) is more surface area than this slice needs.
- Forcing `status="partial"` on repair is the mechanism that makes "did the model have a bad day?"
  visible from the artifact alone (spec §Why this priority for US5).
- Rejecting truly-unparseable responses at the parser prevents the reconciliation step from seeing
  something it wasn't written to handle.

**Alternatives considered**:
- `json-repair` package — heavier than required; we'd inherit a library's repair semantics rather
  than pinning our own.
- No repair (strict only) — too brittle; Gemma occasionally wraps JSON in prose even with
  `format: "json"`.

## R-008: Reconciliation status truth table

**Decision**: `status` is a pure function of the reconciliation outcomes, evaluated AFTER parsing
and evidence filtering. Precedence (first match wins):

| Condition | Status |
|-----------|--------|
| Parse failed unrepairably (before reconcile runs at all) | Hard failure — exit non-zero, no artifact |
| Reconciliation produced every required field grounded, no repair, no drops, no defaults | `"success"` |
| Any one of: JSON was repaired, an evidence ID was dropped, a required sub-field was defaulted to null | `"partial"` |
| Reconciliation ran but resulted in zero grounded evidence anywhere AND every `value` is null | `"failure"` |

`warnings` is the accompanying narrative: every deviation that moved status from success to partial
emits a string; `failure` emits a string explaining why (empty response, total evidence drop,
input-packet blank document, etc.).

**Rationale**:
- This ordering means a fully-null artifact cannot be `"success"` (would be surprising to a human
  reader) and a partially-damaged run cannot present as `"failure"` (would mask recoverable data).
- The table is deterministic: given a fixed parsed model response and a fixed preprocessing packet,
  status is always the same (SC-009).

**Alternatives considered**:
- Continuous "reliability score" in place of the three-value enum — would violate the frozen
  schema's enum. Rejected.
- `success` whenever any grounded field exists — too permissive; hides missing-required-field
  cases.

## R-009: pipeline_version composition

**Decision**: `pipeline_version = f"{package_version}+{short_sha}"` where:
- `package_version` comes from `importlib.metadata.version("ledgerlinc-ocr")`.
- `short_sha` is `git rev-parse --short HEAD` run at build time AND cached into
  `src/ledgerlinc_ocr/_build_sha.py` (a file written by a build step; falls back to `"unknown"` if
  the module is missing). The `version.py` module in `extract/` returns this composed string.

**Rationale**:
- Matches the convention already established by `src/ledgerlinc_ocr/preprocessing/version.py`.
- `importlib.metadata` is installed-package-aware, so edit-install dev loops get the right number.
- The cached SHA avoids a subprocess at run time on every extraction; missing-git environments
  degrade gracefully.

**Alternatives considered**:
- Pure `package_version` — loses build-identity; two different commits with the same package
  version would emit identical `pipeline_version`, making regressions ambiguous.
- Full commit SHA — too long; `short_sha` is enough.

## R-010: Seed support for Gemma on Ollama

**Decision**: Pass `seed=42` in the Ollama `/api/generate` request body under the `options` key
(`"options": {"seed": 42, "temperature": 0.0}`). Gemma models on Ollama accept `seed` as an option
but do not currently guarantee bit-exact reproducibility across Ollama restarts or different
quantizations; we pin it anyway for best-effort determinism, and the spec's Assumptions section
already scopes the determinism claim accordingly.

**Rationale**:
- Passing seed costs nothing and improves reproducibility for in-run repeats.
- Documenting that cross-run reproducibility is "best-effort" matches the spec's Assumptions
  posture.

**Alternatives considered**:
- No seed — discarded; cheap to set, non-cheap to retro-fit.
- Per-call randomized seed — explicitly counterproductive.

## R-011: Exit-code table

**Decision**: Mirror the existing `src/ledgerlinc_ocr/pipeline/exit_codes.py` convention.
Specifically:

| Code | Meaning |
|------|---------|
| `0` | Success — schema-valid artifact written, `status` one of `success`/`partial`/`failure`. |
| `2` | Input contract drift — `preprocess_output.json` missing, unreadable, schema-invalid, or `contract_set_version != "1.0.0"`. No artifact written. |
| `3` | Ollama unreachable — connect refused, DNS failure, or read timeout. No artifact written. |
| `4` | Ollama model unavailable — configured model not present on the endpoint. No artifact written. |
| `5` | Unrepairable model response — parse failed after repair attempt. No artifact written. |
| `6` | Voter configuration invalid — YAML parse error or pydantic validation failure. No artifact written. |
| `7` | Folder write error — cannot write `edge_extraction_output.json` at the target path. |
| `1` | Reserved for unexpected / unclassified errors. |

**Rationale**:
- Distinct codes per hard-failure category make US5 ACs verifiable with a single `echo $?` in
  integration tests.
- Reserving `1` for unexpected errors preserves shell-level surprise detection.

**Alternatives considered**:
- Single non-zero exit code for all hard failures — rejected; makes US5 tests lose specificity.
- Process-exits via stderr codes only (no exit-code table) — rejected; CI and harness integration
  rely on numeric codes.

## R-012: `status == "failure"` convention on "model returns no usable content"

**Decision**: Prefer the **artifact-with-failure-status path** (US5 AC #4, option a). If the
extractor reaches the point of having a parsed-but-useless response (e.g., JSON that validates as
`{}` or model explicitly refusing), it writes a schema-valid artifact with every field defaulted to
null, every confidence `0.0`, every evidence array empty, `status="failure"`, and a `warnings`
entry explaining the cause. Exit code is `0` (the artifact *was* written) — the failure is
reported *in* the artifact per the spec's "loud over silent" principle.

If the extractor cannot reach that point (unrepairable parse, Ollama unreachable, contract drift),
it exits non-zero per R-011 and writes nothing.

**Rationale**:
- Spec US5 AC #4 explicitly prefers the artifact-with-failure-status path "so downstream consumers
  can see the failure without log archaeology".
- The exit-code distinction (`0` with failure-status artifact vs. non-zero with no artifact) is the
  line between "I ran, the run failed, look at the artifact" and "I could not run at all, look at
  stderr".

**Alternatives considered**:
- Always exit non-zero on `status="failure"` — makes CI noisier without adding information; the
  harness can key off `status` just as well.
- Never write `status="failure"` (only success/partial + non-zero exits) — contradicts spec US5 AC
  #4.

## R-013: Determinism scope (cross-reference)

**Decision**: Restate the scope the spec's Assumptions section already pinned — nothing new
here, but the plan's SC-009 verification strategy needs an explicit scope table. What is
contractually deterministic (tested) vs. best-effort (not gated):

| Element | Determinism | Test strategy |
|---------|-------------|---------------|
| JSON schema shape of the artifact | Contractual | Schema validation test on every integration output |
| Reconciliation outputs given a fixed model response | Contractual | Unit tests with recorded voter responses |
| `status` derivation | Contractual | R-008 truth-table unit tests |
| `company_name.present` / `company_name.inferred` given fixed model response | Contractual | Unit tests; corpus-level SC-002 |
| Evidence-filter outcome given fixed model response | Contractual | Unit tests |
| `UNGROUNDED_CONFIDENCE_CAP` application | Contractual | Unit tests |
| Model value strings across runs | Best-effort (temp 0 + seed) | Smoke test only; explicitly not gated |
| `processed_at` | Intentionally non-deterministic | Assert format, not value |
| `pipeline_version` | Deterministic per build; varies across builds | Format assertion |

**Rationale**: Captures exactly what SC-009 is claiming so the Phase 2 test plan can target the
contractual set with unit tests and leave the best-effort set to integration smoke.
