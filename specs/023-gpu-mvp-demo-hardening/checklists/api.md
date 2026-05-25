# API / External Interface Requirements Quality Checklist: GPU MVP Demo Hardening

**Purpose**: Release-gate audit of requirements covering this feature's external/internal API surfaces: host Ollama HTTP, voter-config schema interactions, and the sub-module CLI integrations the demo composes.
**Created**: 2026-05-24
**Feature**: [spec.md](../spec.md)

## Host Ollama HTTP Surface

- [ ] CHK001 Is the Ollama endpoint path (`/api/ps`) and base URL discovery (`OLLAMA_BASE_URL`?) explicitly specified so the demo cannot accidentally probe a different endpoint? [Completeness, Spec §FR-005]
- [ ] CHK002 Are the exact `/api/ps` response fields the demo depends on (`name`, `size`, `size_vram`, context length) enumerated, and is each marked required vs. optional? [Completeness, Spec §FR-005/§OllamaModelStatus entity]
- [ ] CHK003 Is the comparison rule for "fully GPU-placed" — `size_vram > 0 AND size_vram == size` — pinned to specific arithmetic, or left to interpretation (e.g., approximate equality)? [Clarity, Spec §FR-005]
- [ ] CHK004 Are requirements specified for the case where `/api/ps` returns multiple entries matching the configured model name (e.g., variant tags, multiple loaded models)? [Coverage — Edge Case, Gap]
- [ ] CHK005 Are requirements specified for HTTP failure modes (5xx response, connection refused, slow response, TLS error, malformed JSON) on the readiness path? [Coverage — Exception, Spec §FR-007/Edge Cases]
- [ ] CHK006 Is the HTTP timeout for the readiness `/api/ps` call specified, or only implied by the 10-second preflight bound? [Clarity, Spec §FR-018/SC-007]
- [ ] CHK007 Are requirements specified for the post-run `/api/ps` re-query that detects silent CPU fallback (FR-012) — same endpoint, different failure semantics? [Completeness, Spec §FR-012]

## Ollama Version Probe

- [ ] CHK008 Is the Ollama version-discovery endpoint specified (e.g., `/api/version`) or left as "the runbook documents a minimum version"? [Completeness, Spec §FR-023]
- [ ] CHK009 Is the comparison rule for "below minimum version" specified (semver comparison, string compare, prefix match)? [Clarity, Spec §FR-023]
- [ ] CHK010 Is the behavior specified when the version probe itself fails (network error vs missing endpoint vs malformed response)? [Coverage, Gap]

## Ollama Context-Length Probe

- [ ] CHK011 Is it specified *where* in `/api/ps` the context length is read from (top-level field, per-model field, response header), so authors don't pick the wrong key? [Clarity, Spec §FR-006]
- [ ] CHK012 Is the behavior specified when `/api/ps` does not expose context length — the FR-006 fallback says "still catch downstream context-window errors", but is the fallback path's error-detection criterion specified? [Coverage, Spec §FR-006]

## Voter-Config Schema Interactions

- [ ] CHK013 Are the voter-config fields this feature reads (model name, anything else?) listed explicitly, so a future voter-config schema change can be impact-assessed? [Completeness, Spec §FR-005, §VoterConfig entity]
- [ ] CHK014 Is "active voter config" defined identically to feature 005's definition (so the demo and the extractor see the same config)? [Consistency, Spec §FR-005, §Assumptions]
- [ ] CHK015 Is the failure behavior specified when the voter config file exists but is malformed YAML / missing required fields (vs. simply absent)? [Coverage — Exception, Gap]
- [ ] CHK016 Is the precedence rule between `--voter-config <path>` and the auto-discovery path spelled out (CLI flag wins / auto-discovery wins / merge), so authors don't pick arbitrarily? [Clarity, Spec §FR-005]

## Internal Sub-Module CLI Integrations

- [ ] CHK017 Is the call shape (subprocess vs in-process function call vs library import) for invoking feature 003 preprocessing specified, or deferred to planning? [Completeness, Spec §Dependencies]
- [ ] CHK018 Are translation rules specified for sub-module exit codes (feature 005's 0/1/2/3/4, feature 008's 0/1/2/3) → the demo's closed exit-code table (0/1/2/3/4/5)? [Completeness, Spec §FR-021, Dependencies]
- [ ] CHK019 Are sub-module output side-channels (stdout, stderr, `kind: "run_summary"` JSON lines from features 014–020) specified as composable with the demo's stdout-JSON-only policy? [Consistency, Spec §FR-019, Dependencies]
- [ ] CHK020 Is it specified whether the demo command consumes the sub-modules' run_summary JSON or only their on-disk artifacts? [Clarity, Spec §FR-009/Dependencies]
- [ ] CHK021 Is the failure-classification mapping specified — e.g., feature 005's hard-fail JSON-repair failure → which `runtime_outcome` value? [Completeness, Spec §FR-020, Dependencies]

## Protocol / Versioning Assumptions

- [ ] CHK022 Is the minimum supported Ollama version pinned somewhere with a concrete value, or left as "planning will pick"? [Clarity, Spec §FR-023, §Assumptions]
- [ ] CHK023 Are forward-compatibility rules for `/api/ps` response fields specified — e.g., if Ollama adds a new field, must readiness silently tolerate it? [Coverage — Non-Functional, Gap]
- [ ] CHK024 Is the contract_set_version interaction (this feature is bound to v1.3.0) explicitly stated as unchanged by this feature (FR-014), so contract reviewers don't need to re-check? [Traceability, Spec §FR-014]
- [ ] CHK025 Is the `OLLAMA_BASE_URL` environment-variable contract referenced as input to the demo, or left implicit through "host Ollama"? [Completeness, Gap]

## Primary / Alternate / Exception / Recovery / Non-Functional Coverage

- [ ] CHK026 Are API requirements defined for the **primary** flow (Ollama up + GPU placed + voter config valid)? [Coverage — Primary, Spec §FR-005]
- [ ] CHK027 Are API requirements defined for **alternate** flows (Ollama up + multiple variants of the same model loaded; `/api/ps` exposing extra/new fields)? [Coverage — Alternate, Gap]
- [ ] CHK028 Are API requirements defined for **exception** flows (every Ollama HTTP failure mode)? [Coverage — Exception, Spec §FR-007, Edge Cases]
- [ ] CHK029 Are API **recovery** requirements defined (e.g., the demo never retries `/api/ps`; the operator restarts Ollama)? [Coverage — Recovery, Spec §Assumptions]
- [ ] CHK030 Are API **non-functional** requirements quantified (readiness HTTP call latency budget, retry policy = none)? [Coverage — Non-Functional, Gap]

## Ambiguities & Conflicts

- [ ] CHK031 Is the precedence between FR-005 (`size_vram > 0 AND size_vram == size`) and FR-023 (named `ollama-version` check when `size_vram` is absent) clearly ordered, or could a check both pass and fail? [Conflict, Spec §FR-005/FR-023]
- [ ] CHK032 Is the use of `OLLAMA_BASE_URL` (or similar env var) as the discovery mechanism for "host Ollama" stated, given that Docker-container Ollama and host Ollama have different URLs? [Ambiguity, Spec §Edge Cases]


---

**Plan coverage verification (2026-05-25):** see [plan-coverage.md](./plan-coverage.md) for the cross-reference of this checklist's items against `plan.md` / `research.md` / `data-model.md` / `contracts/` / `quickstart.md`.
