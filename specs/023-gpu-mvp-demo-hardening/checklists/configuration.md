# Configuration Requirements Quality Checklist: GPU MVP Demo Hardening

**Purpose**: Release-gate audit of the configuration surface — CLI flags, environment variables, defaults, override precedences, and the runbook-documented operator knobs.
**Created**: 2026-05-24
**Feature**: [spec.md](../spec.md)

## CLI Flag Inventory

- [ ] CHK001 Are all CLI flags enumerated in one canonical list (`--check-only`, `--document-folder`, `--voter-config`, `--preset`, `--with-evaluator`), with each tied to a specific FR? [Completeness, Spec §FR-005/FR-011/FR-018/FR-022/FR-027]
- [ ] CHK002 Is the spec explicit about any *not-permitted* flags — e.g., no `--force`, no `--clean`, no `--no-readiness`, so the operator surface is closed? [Completeness, Gap]
- [ ] CHK003 Is the short-form vs long-form convention specified (e.g., no `-c` for `--check-only`), so the runbook can teach a single form? [Coverage, Gap]
- [ ] CHK004 Are flag names case-sensitive vs case-insensitive specified, so `--Check-Only` either works or is rejected with a clear error? [Clarity, Gap]

## Flag Defaults

- [ ] CHK005 Is the default value of `--document-folder` specified as a concrete path (`tests/stage1_vendor_identity/inv_001_easy/`)? [Clarity, Spec §FR-027]
- [ ] CHK006 Is the default value of `--preset` specified as `header-first-v1`? [Clarity, Spec §FR-011]
- [ ] CHK007 Is the default value of `--voter-config` specified as "feature 005/021 auto-discovery"? [Clarity, Spec §FR-005]
- [ ] CHK008 Are the defaults of `--with-evaluator` (off) and `--check-only` (off) explicit, so operators know that the bare command runs the full pipeline against the canonical fixture? [Completeness, Spec §FR-018/FR-022]

## Flag Interactions

- [ ] CHK009 Is the interaction between `--check-only` and `--document-folder` defined (per round-3, `--check-only` ignores the folder)? [Clarity, Spec §Round-3 Q2 implicit]
- [ ] CHK010 Is the interaction between `--check-only` and `--with-evaluator` defined (no pipeline = no evaluator)? [Coverage, Gap]
- [ ] CHK011 Is the interaction between `--check-only` and `--preset` defined (no pipeline = preset ignored, or still validated)? [Coverage, Gap]
- [ ] CHK012 Is the interaction between `--with-evaluator` and missing `semantic_table_truth.json` defined (warn-and-skip per FR-022)? [Clarity, Spec §FR-022]
- [ ] CHK013 Is the interaction between `--voter-config <path>` and a malformed/missing voter config defined (exit 2 per FR-005)? [Clarity, Spec §FR-005]

## Environment Variables

- [ ] CHK014 Are required environment variables enumerated — `OLLAMA_CONTEXT_LENGTH=2048`, anything else? [Completeness, Spec §FR-006]
- [ ] CHK015 Is `OLLAMA_BASE_URL` documented as a required-or-defaulted input, given that "host Ollama" implies a specific URL? [Coverage, Spec §FR-006, Gap]
- [ ] CHK016 Are Paddle ROCm environment variables (e.g., `HIP_VISIBLE_DEVICES`, `MIOPEN_FIND_MODE`) referenced via the startup script vs. set by the demo CLI? [Clarity, Spec §FR-006, Dependencies]
- [ ] CHK017 Is the precedence between CLI flag and env var defined (per round-2 Q9, CLI flag wins; env var is not the mechanism for `--voter-config`)? [Clarity, Spec §Round-2 Q9]

## Voter-Config Discovery

- [ ] CHK018 Is the auto-discovery algorithm (search paths, lookup order, package-relative defaults) referenced as feature 005/021's existing logic, unchanged? [Consistency, Spec §FR-005, §Assumptions]
- [ ] CHK019 Is the override mechanism (`--voter-config <path>`) specified to bypass auto-discovery entirely, not merge with it? [Clarity, Spec §FR-005]
- [ ] CHK020 Is the requirement to record the *actual* voter-config path used in the report explicit, so audits can verify which config was effective? [Completeness, Spec §FR-019]

## Timeout & Performance Knobs

- [ ] CHK021 Is the 600 s timeout configurable (env, flag) or pinned in code? [Completeness, Spec §FR-008, Gap]
- [ ] CHK022 Is the 10 s preflight bound configurable or pinned? [Completeness, Spec §SC-007, Gap]
- [ ] CHK023 Is the minimum Ollama version configurable, or pinned in the runbook? [Clarity, Spec §FR-023, §Assumptions]

## Per-Run vs Persistent Configuration

- [ ] CHK024 Is the spec explicit that there is no config file (TOML/YAML) at the demo level — all configuration is via CLI flags + env vars? [Completeness, Gap]
- [ ] CHK025 Is the spec explicit that the voter config (feature 005/021's YAML) is the *only* config file the demo reads? [Clarity, Spec §FR-005]

## Documentation / Runbook Configuration

- [ ] CHK026 Is the runbook required to enumerate every flag's default, override mechanism, and intended use case in one table, so the operator does not need to read the spec? [Completeness, Spec §FR-006]
- [ ] CHK027 Are configuration changes that require a runbook update specified — e.g., minimum Ollama version, OLLAMA_CONTEXT_LENGTH value? [Coverage, Spec §FR-023, §FR-006]

## Primary / Alternate / Exception / Recovery / Non-Functional Coverage

- [ ] CHK028 Are configuration requirements defined for the **primary** flow (bare command with all defaults)? [Coverage — Primary, Spec §FR-001/FR-011/FR-027]
- [ ] CHK029 Are configuration requirements defined for **alternate** flows (every combination of `--check-only`, `--document-folder`, `--voter-config`, `--preset`, `--with-evaluator`)? [Coverage — Alternate, Spec §FR-005/FR-011/FR-018/FR-022/FR-027]
- [ ] CHK030 Are configuration requirements defined for **exception** flows (invalid value for any flag — unknown preset name, non-existent path, malformed config)? [Coverage — Exception, Gap]
- [ ] CHK031 Are configuration **recovery** requirements defined (e.g., a bad flag value exits 2 with a clear "usage" diagnostic; no partial-config state)? [Coverage — Recovery, Spec §FR-021]
- [ ] CHK032 Are configuration **non-functional** properties specified (flag parsing is fast; flag help is auto-generated; configuration is auditable from the report)? [Coverage — Non-Functional, Gap]

## Ambiguities & Conflicts

- [ ] CHK033 Is the precedence between `--preset full-ocr` and the feature-018 `header-first-v1` default consistent (CLI flag overrides default) and reflected in the per-flag default table? [Consistency, Spec §FR-011]
- [ ] CHK034 Is the spec consistent on whether the `--with-evaluator` flag enables an *optional* evaluator (default off, per FR-022) or whether the spec elsewhere implies a default-on path? [Consistency, Spec §FR-022, §Assumptions]


---

**Plan coverage verification (2026-05-25):** see [plan-coverage.md](./plan-coverage.md) for the cross-reference of this checklist's items against `plan.md` / `research.md` / `data-model.md` / `contracts/` / `quickstart.md`.
