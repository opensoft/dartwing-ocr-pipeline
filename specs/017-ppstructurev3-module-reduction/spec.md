# Feature Specification: PPStructureV3 Module And Model Reduction

**Feature Branch**: `017-ppstructurev3-module-reduction`
**Created**: 2026-05-09
**Status**: Draft
**Input**: User description: "Build the next GPU optimization slice after feature 016. Reduce GPU preprocessing cost by disabling PPStructureV3 components we do not need for stage 1 vendor identity and by evaluating lighter PaddleOCR model variants, without changing any persisted artifact schemas."

## Clarifications

### Session 2026-05-09

- Q: What is the promotion quality-gate metric for FR-015 / SC-008? → A: Two-metric gate — both (a) the per-corpus aggregate vendor-identity field score from `evaluation_run_summary.json` and (b) the per-document pass count on the same subset (per `docs/stage1-vendor-identity/scoring.md`) must be ≥ the legacy default's values on the same subset.
- Q: What shape does the configuration identifier take on `run_summary`? → A: Two separate top-level string fields on the `run_summary` line — `module_set_id` (names the active PPStructureV3 module set, e.g. `"legacy"`, `"reduced-v1"`) and `det_rec_variant_id` (names the active detection/recognition model pairing, e.g. `"legacy"`, `"ppocrv4-mobile"`). Both are human-readable strings (not hashes) and are emitted on every run including default `ppstructurev3@cpu` and stub-adapter runs (with values reflecting the active default of that profile).
- Q: Where does the FR-001 live-path module audit land? → A: Both surfaces. (1) An additive top-level list field on every `run_summary` line — `ppstructure_modules_invoked` — whose value is the list of PPStructureV3 sub-module names actually invoked on that run (empty list on the stub adapter). (2) A richer narrative + raw-trace capture in this feature's research artifact (`specs/017-ppstructurev3-module-reduction/research.md` or a sibling artifact) that records the landing audit comparing legacy and reduced module sets.
- Q: How does FR-002 select which PPStructureV3 sub-modules are enabled — named presets or per-sub-module toggles? → A: Named presets only. The feature ships with exactly two presets at landing: `legacy` (the full module set active on `main` at landing time of feature 016) and `reduced-v1` (the disable set recommended by the FR-001 audit). `module_set_id` is drawn from a closed vocabulary; new presets are added by code change plus a new `module_set_id` value, not by per-run sub-module toggling.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Audit and disable unused PPStructureV3 modules on the GPU lane (Priority: P1)

A pipeline engineer wants to know exactly which PPStructureV3 sub-modules (layout, table, formula, chart, document orientation, seal, etc.) actually execute during a live `ppstructurev3@gpu` preprocessing pass on a stage 1 vendor-identity input — not just which modules are registered at preflight. Once they have that audit, they want a single explicit configuration switch on the live `ppstructurev3@gpu` path that turns off the modules vendor identity does not need, so each subsequent GPU run pays for fewer module weights and fewer per-page operations while still emitting the same `preprocess_output.json` schema.

**Why this priority**: This is the core deliverable. Stage 1 only needs vendor-identity-relevant text and layout; every PPStructureV3 sub-module that runs but contributes nothing to vendor identity is paid GPU memory + GPU time. Without the live-path audit, "disable unused modules" is guesswork; without the configuration switch, the audit is just documentation.

**Independent Test**: Run the existing `ppstructurev3@gpu` preprocessing command on `inv_001_easy/source.pdf` once with the legacy (full) module set and once with the reduced module set. Confirm: (a) the live-path audit lists the modules actually invoked in each run; (b) the reduced run executes strictly fewer module invocations than the legacy run; (c) both runs produce a `preprocess_output.json` that validates against the same JSON schema; (d) the reduced configuration is selected via explicit configuration, not by silent default change to the GPU lane.

**Acceptance Scenarios**:

1. **Given** a `ppstructurev3@gpu` run with the legacy module set on a fixed vendor-identity fixture, **When** preprocessing completes, **Then** an audit (log, run-summary metadata, or research-artifact captured trace) lists each PPStructureV3 sub-module that ran during that live pass.
2. **Given** the same fixture and the same `ppstructurev3@gpu` profile but with the reduced module set explicitly selected, **When** preprocessing completes, **Then** the audit lists strictly fewer PPStructureV3 sub-modules than the legacy run, and the resulting `preprocess_output.json` validates against the existing schema with no field added, removed, renamed, or retyped.
3. **Given** a `ppstructurev3@gpu` run without any new switch set, **When** preprocessing completes, **Then** module-set behavior is unchanged from feature 016 — the reduced module set MUST NOT become the GPU default in this scenario unless it is explicitly promoted (US6).

---

### User Story 2 - Benchmark at least two lighter detection/recognition model configurations (Priority: P1)

An engineer wants to evaluate at least two lighter PaddleOCR detection/recognition model configurations against the same small stage 1 vendor-identity corpus, using the same GPU lane. Each configuration is selectable per-run via explicit configuration. The benchmark records, for each configuration, the per-document timing surface produced by feature 015 (`phase_timings.*`) and the vendor-identity quality numbers produced by the existing evaluator. The decision of whether to promote any of the lighter configurations to the new GPU default is made from those numbers, not from intuition.

**Why this priority**: Module reduction (US1) caps the cost of running the modules we keep, but most of the GPU time and memory in stage 1 vendor identity is currently paid in detection + recognition. Without comparing at least two lighter alternatives on the same corpus, the team has no evidence to pick one — and "we'll measure later" tends to never happen. This story turns "lighter models might help" into a decision with data attached.

**Independent Test**: Pick a fixed small subset of `tests/stage1_vendor_identity/inv_*` (the same subset for every configuration). Run the `ppstructurev3@gpu` lane on that subset under the legacy default and under each of at least two lighter detection/recognition configurations. Confirm: (a) each configuration produces `preprocess_output.json` files that validate against the existing schema; (b) the existing harness/evaluator pipeline produces vendor-identity quality numbers for each configuration; (c) per-document `phase_timings.*` is emitted for each run; (d) the configuration selection is explicit per run, not inferred.

**Acceptance Scenarios**:

1. **Given** a fixed small vendor-identity corpus subset, **When** the GPU lane is run on that subset under the legacy detection/recognition default and under each of at least two lighter configurations, **Then** every run completes successfully and emits per-document `phase_timings.*` per feature 015 plus a `preprocess_output.json` that validates against the existing schema.
2. **Given** the same set of runs, **When** the existing harness/evaluator pipeline is applied to each configuration's outputs, **Then** vendor-identity quality numbers are produced per configuration and recorded in this feature's research artifact for the promotion decision.
3. **Given** a configuration whose model weights or runtime fail to bind on GPU, **When** that configuration is selected, **Then** the run fails fast — it MUST NOT silently fall back to CPU (preserving feature 015 FR-008).

---

### User Story 3 - Selected configuration is visible in operator-facing output (Priority: P1)

An operator inspecting a `run_summary` line (or the equivalent diagnostic surface specified in feature 015) for a GPU preprocessing run can tell which PPStructureV3 module set and which detection/recognition model variant the run used, by reading a stable identifier directly from the output — without having to read source code, environment variables, or feature-flag state.

**Why this priority**: Module reduction (US1) and model variant evaluation (US2) introduce multiple possible GPU configurations on the same `ppstructurev3@gpu` profile. Without an output-visible identifier, two runs that differ only in module set or model variant look identical to operators and to anyone diagnosing a quality regression after the fact. P1 because every other story depends on operators being able to attribute observed differences to the configuration that produced them.

**Independent Test**: Run the GPU lane once under the legacy configuration and once under a clearly different configuration (different module set or different model variant). Confirm the `run_summary` line for each run carries a stable identifier (string, not just a numeric hash) that distinguishes the two configurations, and that the identifier value matches the configuration the operator actually selected.

**Acceptance Scenarios**:

1. **Given** a `ppstructurev3@gpu` run with the legacy configuration, **When** preprocessing completes, **Then** the `run_summary` (or equivalent operator-facing diagnostic) carries an additive identifier field that names the active PPStructureV3 module set and the active detection/recognition model variant.
2. **Given** the same run repeated under a different module set or different model variant, **When** preprocessing completes, **Then** the identifier in the `run_summary` line is different from the legacy run's identifier, and the new value matches the selected configuration.
3. **Given** a `ppstructurev3@cpu` run (default profile) without any new configuration switches set, **When** preprocessing completes, **Then** the `run_summary` line is unchanged from feature 016 except for an additive identifier field whose value reflects the default CPU configuration.

---

### User Story 4 - Default CPU profile and CI without GPU stay safe (Priority: P2)

An engineer running the default `ppstructurev3@cpu` profile, or the existing CI without GPU hardware, must not have their behavior changed by this feature beyond an additive identifier on `run_summary`. No CPU code path may import GPU-only module-disable or model-variant code; no CPU run may consult or mutate any GPU-only configuration switch this feature introduces.

**Why this priority**: P2 — the risk is regression, not new value. CPU and CI paths already work post-016; this story protects them. Lower than P1 only because the CPU/CI path's correctness is independently verifiable today.

**Independent Test**: Run the default `ppstructurev3@cpu` profile and the existing stub-adapter / CPU-only test suites on a host without Paddle GPU, both with and without any new GPU configuration switches set in the environment. The suites must pass in both configurations. CPU `preprocess_output.json` outputs must be byte-identical to outputs on `main` before this feature lands.

**Acceptance Scenarios**:

1. **Given** the default `ppstructurev3@cpu` profile on a host without GPU, **When** preprocessing runs, **Then** no GPU-only module-disable or model-variant code path is imported or executed.
2. **Given** the same default CPU profile with new GPU configuration switches *explicitly set* in the environment, **When** preprocessing runs, **Then** the run completes normally with no behavior change other than an additive identifier on `run_summary` that names the default CPU configuration.
3. **Given** the existing default test suite on a host without Paddle GPU, **When** the suite runs, **Then** it passes; GPU-only verification of module-disable / lighter-model behavior is skipped via `@pytest.mark.gpu` rather than failed.

---

### User Story 5 - Output schema and downstream contracts unchanged (Priority: P2)

A corpus run on the GPU lane under any configuration this feature introduces — legacy module set, reduced module set, any lighter model variant — must produce a `preprocess_output.json` that still matches the existing JSON Schema and that the downstream evidence-packet, single-voter extractor, router, and final-payload assembler accept without modification.

**Why this priority**: P2 — protects every downstream slice (004 evidence packet, 005 extraction, 008 routing, 009 final payload) from leaking a GPU-side optimization into their contract surface. Lower than the core P1 stories only because schema-conformance is mechanically checkable.

**Independent Test**: For each evaluated configuration, run a small corpus subset end-to-end through the existing pipeline (preprocess → evidence packet → extract → route → assemble → evaluate). Confirm: (a) every `preprocess_output.json` validates under `contracts/stage1_vendor_identity/*/preprocess_output.schema.json` of the active contract set; (b) each downstream stage runs to completion against those outputs; (c) `schema_version` and the four canonical artifact contracts are not modified by this feature.

**Acceptance Scenarios**:

1. **Given** a small corpus subset run end-to-end under a configuration introduced by this feature, **When** every stage completes, **Then** every emitted artifact validates against its existing schema in the active contract set.
2. **Given** the same end-to-end run, **When** the evaluator runs, **Then** it produces `evaluation_document.json` and `evaluation_run_summary.{json,md}` without contract changes.
3. **Given** the active contract set at landing time, **When** this feature lands, **Then** no `schema_version` value, no JSON schema field, and no entry in `contracts/stage1_vendor_identity/AMENDMENTS.md` is changed by this feature except for an additive identifier surface explicitly defined here.

---

### User Story 6 - Quality-gate guard before any GPU default change (Priority: P3)

If, after running US2's benchmark, the team chooses to promote a lighter detection/recognition configuration or a reduced module set to the new `ppstructurev3@gpu` default, the promotion must be gated on vendor-identity quality being preserved against the existing GPU default — measured on the same small corpus the benchmark used. Promotion that fails the gate is rejected; the legacy default stays in place.

**Why this priority**: P3 — the feature ships value at P1+P2 (audit, configurable disable, benchmark, visibility, schema preservation) without ever flipping the GPU default. Promotion is a follow-on decision. P3 because skipping the gate would convert this feature from "evaluation slice" to "silent regression vector"; promotion-gating is required only if and when the team chooses to promote.

**Independent Test**: Take a candidate lighter configuration that US2 evaluated. Compare its vendor-identity quality numbers (from the existing evaluator) against the legacy default's numbers on the same corpus. The promotion gate passes only if the candidate is at parity or better on the agreed quality metric. If the gate passes, the candidate becomes the new GPU default in this feature; if it fails, the legacy default is kept and the candidate remains an opt-in selection only.

**Acceptance Scenarios**:

1. **Given** a candidate lighter configuration evaluated under US2, **When** the team considers promoting it to the new `ppstructurev3@gpu` default, **Then** the decision references vendor-identity quality numbers produced by the existing evaluator on the same corpus the benchmark used.
2. **Given** a candidate that passes the quality gate, **When** the GPU default is changed, **Then** the change is recorded in this feature's research artifact and the new default's identifier appears in subsequent `run_summary` lines without any opt-in switch needing to be set.
3. **Given** a candidate that fails the quality gate, **When** the promotion decision is made, **Then** the legacy default remains in place and the candidate stays selectable only via explicit configuration.

---

### Edge Cases

- **Module-disable switch combined with `ppstructurev3@cpu`**: A switch that disables PPStructureV3 modules on the GPU lane is GPU-only by design. When set with the CPU profile or a stub adapter, the system MUST follow the same warn-and-proceed pattern feature 016 established for `--gpu-warmup` on CPU: emit a clear stderr warning that the switch was ignored because the active profile is not `ppstructurev3@gpu`, perform no module-disable, and proceed with the run normally. Silent ignore is NOT acceptable.
- **Model-variant switch combined with `ppstructurev3@cpu`**: Same disposition as the module-disable switch. Warn-and-proceed; no CPU model swap; the CPU run uses its existing CPU defaults.
- **Lighter configuration's model weights fail to bind on GPU**: Run MUST fail fast (preserving feature 015 FR-008 "no silent CPU fallback after `ppstructurev3@gpu` is selected"). The exit reason MUST identify the configuration that failed so operators can diagnose without re-instrumentation.
- **Disabled module is referenced by a downstream consumer**: If turning off a PPStructureV3 sub-module would remove a field downstream stages depend on, that sub-module MUST stay enabled — schema preservation (FR-003) and downstream-contract preservation (FR-019) take priority over module-disable savings.
- **Reduced module set produces an empty/blank `preprocess_output.json`**: Treated as a regression of FR-003. The reduced configuration is rejected; the legacy module set is kept as the default until the regression is resolved.
- **Lighter configuration changes per-document `phase_timings` shape**: Forbidden. Per-document `phase_timings` keys (`paddle_import`, `gpu_bind_probe`, `engine_init`, `rasterization`, `per_page_inference`, `artifact_write`, `total`, and `warmup` from feature 016) MUST NOT be renamed, removed, or have their type changed by this feature.
- **Operator overrides the new GPU default back to the legacy default**: MUST be supported by the same explicit configuration switch this feature introduces — a default change MUST NOT remove the operator's ability to select the legacy configuration.
- **GPU verification deferred to a follow-up**: When workstation GPU hardware is unavailable at landing time, GPU-marked tests (`@pytest.mark.gpu`) and benchmark verification MAY be deferred and tracked as a follow-up issue/task without blocking the CPU-safe implementation from merging (per feature 016 FR-014). The deferral MUST be captured in this feature's tasks/quickstart so the verification cannot be quietly skipped.
- **Conditions under which the legacy GPU configuration is preserved as the default** (collated for review traceability): (a) FR-015 quality-gate failure on either metric; (b) blank-output regression (this section); (c) module-dependency conflict where a downstream stage needs an output of a sub-module the reduced preset would disable (FR-004); (d) GPU bind failure on the candidate configuration (FR-007); (e) the team makes no promotion decision at landing (FR-017 / US6). In all cases the legacy configuration remains both the default and an explicitly selectable option (FR-017).

#### Out of Scope

Documented here so future failures are recognized as known gaps rather than regressions:

- **DPI reduction and region-first / header-first processing**: Reserved for feature 018. Out of scope.
- **OCR-only fast lane (skip layout entirely for vendor-identity-only paths)**: Reserved for feature 019. Out of scope.
- **Promoting a CPU-side default change**: Out of scope. This feature only considers GPU-side defaults; CPU defaults stay as they are unless an explicit follow-up amendment promotes one.
- **Adding a new persisted benchmark artifact**: Out of scope unless `/speckit.clarify` or `/speckit.plan` produces evidence that `run_summary` plus the existing harness/evaluator outputs are insufficient to record the benchmark. If introduced later, name/location/schema/lifecycle MUST be specified in `data-model.md` + `research.md` and the contract set updated under `contracts/stage1_vendor_identity/AMENDMENTS.md`.
- **Regenerating committed corpus baselines**: Out of scope. Any baseline change MUST go through the established dataset/baseline flow defined in `docs/stage1-vendor-identity/dataset-layout.md` and `labeling-guide.md`, not through this feature's PR.
- **Schema or `schema_version` changes to the four canonical stage 1 artifacts**: Out of scope. This feature is configuration-only on the runtime side and additive-only on the `run_summary` side.

## Requirements *(mandatory)*

### Functional Requirements

**Live-path audit and module configuration**

- **FR-001**: System MUST identify, by code or instrumentation on the live `ppstructurev3@gpu` runtime path (not preflight), which PPStructureV3 sub-modules execute during a stage 1 vendor-identity preprocessing pass. The audit MUST land on two surfaces: (a) an additive top-level list field on every `run_summary` line — `ppstructure_modules_invoked` — whose value is the list of PPStructureV3 sub-module names actually invoked on that run (empty list when the stub adapter is active); and (b) a richer narrative + raw-trace capture of the landing audit (legacy vs. reduced module sets on the same fixture) recorded in this feature's research artifact under `specs/017-ppstructurev3-module-reduction/`.
- **FR-002**: System MUST provide an explicit configuration mechanism on the live `ppstructurev3@gpu` path that selects a named PPStructureV3 module-set preset for a given run. Preset selection is the ONLY user-facing surface for module-set choice — the feature MUST NOT expose per-sub-module on/off toggles. The feature ships exactly two presets at landing: `legacy` (the full module set active on `main` at landing time of feature 016) and `reduced-v1` (the disable set recommended by the FR-001 audit). `module_set_id` is drawn from this closed vocabulary; adding a future preset (e.g., `reduced-v2`) is a code change plus a new `module_set_id` value, not a runtime toggle. The mechanism MUST NOT change behavior on `ppstructurev3@cpu` or any stub adapter.
- **FR-003**: A `ppstructurev3@gpu` run with the reduced PPStructureV3 module set MUST produce a `preprocess_output.json` that validates against the existing JSON Schema for that artifact in the active contract set, with no field added, removed, renamed, or retyped.
- **FR-004**: If the reduced module set would remove output fields any downstream stage (`evidence-packet`, `extract`, `router`, `assembler`, `evaluator`) depends on, the offending module MUST remain enabled. Schema and downstream-contract preservation take priority over module-disable savings.

**Detection / recognition model variants**

- **FR-005**: System MUST exercise at least two lighter PaddleOCR detection/recognition model configurations against the same small stage 1 vendor-identity corpus subset used for benchmarking the legacy default.
- **FR-006**: Each evaluated configuration (legacy plus at least two lighter ones) MUST be selectable per-run on the `ppstructurev3@gpu` profile via explicit configuration; the legacy GPU configuration MUST remain a valid selection.
- **FR-007**: Selecting a configuration whose model weights or runtime fail to bind on GPU MUST fail fast and MUST NOT silently fall back to CPU, preserving feature 015 FR-008.

**Operator-facing visibility**

- **FR-008**: The `run_summary` line MUST carry two additive top-level string fields that together identify the active configuration: `module_set_id` (names the active PPStructureV3 module set, e.g., `"legacy"`, `"reduced-v1"`) and `det_rec_variant_id` (names the active detection/recognition model pairing, e.g., `"legacy"`, `"ppocrv4-mobile"`). Both fields MUST be human-readable strings, not opaque numeric hashes.
- **FR-009**: The fields introduced by FR-008 and FR-001 (`module_set_id`, `det_rec_variant_id`, `ppstructure_modules_invoked`) MUST be additive only on `run_summary`. No existing `run_summary` field, `phase_timings.*` key, or `preprocess_output.json` field may be renamed, removed, or retyped by this feature.
- **FR-010**: Both `module_set_id` and `det_rec_variant_id` MUST be emitted on every run of the new binary, including default `ppstructurev3@cpu` runs and stub-adapter runs (so absence of either field is itself a regression signal). On those non-GPU runs the field values MUST reflect the active default configuration of that profile (e.g., `cpu-default` for both, or equivalent stable strings agreed at `/speckit.plan` time).

**Profile defaults and CPU/stub isolation**

- **FR-011**: `ppstructurev3@cpu` MUST remain the default preprocessing profile.
- **FR-012**: `ppstructurev3@gpu` MUST remain explicit / opt-in.
- **FR-013**: When any GPU-only configuration switch this feature introduces is set on `ppstructurev3@cpu` or a stub adapter, the system MUST: (a) emit a clear stderr warning that the switch was ignored because the active profile is not `ppstructurev3@gpu`; (b) perform no module-disable and no model swap; (c) proceed with the run normally and exit with the same status it would have produced without the switch. Silent ignore and rejection are both NOT acceptable. (Mirrors feature 016 FR-010 for `--gpu-warmup`.)
- **FR-014**: CPU and stub adapter execution paths MUST NOT import, reference, or trigger any GPU-only module-disable or model-variant code path this feature introduces. Imports MUST be guarded so a host without Paddle GPU can run the default suite.

**Quality-gate before promotion**

- **FR-015**: A lighter PPStructureV3 module set or detection/recognition model variant MUST NOT be promoted to the new `ppstructurev3@gpu` default until BOTH of the following quality-gate metrics, computed on the same small corpus subset used for benchmarking, are at parity with or better than the legacy default's values on the same subset: (1) the per-corpus aggregate vendor-identity field score read from `evaluation_run_summary.json`, and (2) the per-document pass count on that subset (per the pass criterion in `docs/stage1-vendor-identity/scoring.md`). "Parity" means `candidate_metric >= legacy_metric` for each of (1) and (2). Both metrics MUST come from the existing evaluator outputs; no new metric is introduced by this feature.
- **FR-016**: Quality-gate evidence MUST be recorded in this feature's research artifact alongside the configuration identifier, so a future reader can re-derive the promotion decision from documented numbers.
- **FR-017**: Promotion of a new GPU default MUST NOT remove the legacy configuration as a selectable option; the operator MUST still be able to invoke the legacy configuration by explicit selection.

**Non-regression and contract preservation**

- **FR-018**: This feature MUST NOT regenerate any committed corpus baseline (`tests/stage1_vendor_identity/*/preprocess_output.json`, `expected.json`, evaluator outputs, etc.). Any baseline regeneration MUST go through the established dataset/baseline flow defined in `docs/stage1-vendor-identity/dataset-layout.md` and `labeling-guide.md`, not through this feature's PR.
- **FR-019**: The four canonical stage 1 artifact schemas (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`), the active `contract_set_version`, and `pipeline_version` shape established in features 014/015/016 MUST NOT be changed by this feature.
- **FR-020**: This feature MUST NOT introduce a new persisted benchmark artifact unless `/speckit.clarify` or `/speckit.plan` produces evidence that the existing `kind: "run_summary"` stdout shape plus the existing harness/evaluator outputs are insufficient. If introduced, its name, location, schema, and lifecycle MUST be specified in `data-model.md` + `research.md` and the contract set updated under `contracts/stage1_vendor_identity/AMENDMENTS.md`.
- **FR-021**: All feature 014 / 015 / 016 guarantees MUST continue to hold: PPStructureV3 constructed exactly once per process (015 FR-001), GPU readiness probed at most once per process (015 FR-004), single-device-per-process guard (015 FR-006), no silent CPU fallback after `ppstructurev3@gpu` is selected (015 FR-008), `pipeline_version` continues to end in `.gpu0` for GPU runs / `.cpu0` for CPU runs, warmup behavior unchanged (016 FR-001 through FR-020).

**CI safety and verification gating**

- **FR-022**: All tests that require Paddle GPU, ROCm, specific PaddleOCR detection/recognition model weights, or live `ppstructurev3@gpu` runtime introspection MUST be marked `@pytest.mark.gpu` so they are deselected in the default CI configuration.
- **FR-023**: The default test suite MUST pass on a host without Paddle GPU and without ROCm. CPU profile and stub adapter coverage MUST exercise the warn-and-proceed path from FR-013.
- **FR-024**: If workstation GPU verification cannot be performed before merge, GPU-marked tests, the live-path audit (FR-001), and the benchmark (FR-005) MAY be deferred and tracked as a follow-up issue or task per feature 016 FR-014. Deferral MUST NOT block landing the CPU-safe implementation; the deferred items MUST be captured in this feature's tasks and quickstart so the verification cannot be quietly skipped.

**Boundary with features 018 and 019**

- **FR-025**: This feature MUST NOT change rasterization DPI and MUST NOT introduce region-first or header-first processing (reserved for feature 018).
- **FR-026**: This feature MUST NOT introduce an OCR-only fast lane that bypasses layout for vendor-identity-only paths (reserved for feature 019).

### Key Entities

- **PPStructureV3 module set**: A named preset that fixes which PPStructureV3 sub-modules (layout, table, formula, chart, document orientation, seal, etc.) execute during a live `ppstructurev3@gpu` preprocessing pass. The feature ships exactly two presets at landing — `legacy` (full module set active on `main` at landing time of feature 016) and `reduced-v1` (the legacy set minus the sub-modules the FR-001 audit confirms vendor identity does not depend on). Selection is by preset name only; per-sub-module toggling is not exposed. New presets are added by code change plus a new `module_set_id` value.
- **Detection / recognition model variant**: A specific pairing of PaddleOCR detection model weights and recognition model weights selectable on the `ppstructurev3@gpu` profile. "Legacy" = the variant active on `main` at landing time of feature 016. "Lighter" = a variant whose detection and/or recognition weights are smaller, faster, or lower-precision than the legacy variant, evaluated under FR-005.
- **Configuration identifier**: A pair of additive, human-readable string fields emitted on every `run_summary` line — `module_set_id` for the active PPStructureV3 module set and `det_rec_variant_id` for the active detection/recognition model pairing. Operators attribute observed runtime / quality differences to the configuration that produced them by reading these two fields. Both are stable across runs of the same configuration on that axis; either changes when its axis changes.
- **Live-path audit record**: The output of FR-001 — a list of PPStructureV3 sub-modules that executed during a specific live preprocessing pass. Surfaced two ways: (1) a per-run `ppstructure_modules_invoked` list field on the `run_summary` line, so the "which modules ran" question is answerable on every future run from output alone; and (2) a richer narrative + raw-trace capture of the landing-time legacy-vs-reduced audit in this feature's research artifact under `specs/017-ppstructurev3-module-reduction/`.
- **Quality-gate evidence**: Vendor-identity quality numbers (per the existing evaluator) for each evaluated configuration on the same small corpus subset, recorded in this feature's research artifact, used as the gating evidence for any GPU-default promotion under FR-015.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a fixed vendor-identity fixture, a `ppstructurev3@gpu` run with the reduced PPStructureV3 module set produces a `preprocess_output.json` that validates against the same JSON Schema as a run with the legacy module set, with no schema-level diff between the two outputs.
- **SC-002**: At least two distinct lighter detection/recognition model configurations are evaluated against the same small stage 1 vendor-identity corpus subset. Each configuration's per-document `phase_timings.*` and the existing evaluator's vendor-identity quality numbers are recorded in this feature's research artifact, alongside the configuration's identifier.
- **SC-003**: Every `run_summary` line emitted by the new binary carries both additive string fields `module_set_id` and `det_rec_variant_id` per FR-008 / FR-010. Two runs that differ on the module set have different `module_set_id` values; two runs that differ on the detection/recognition variant have different `det_rec_variant_id` values; two runs with the same configuration on both axes have identical values for both fields.
- **SC-004**: A `ppstructurev3@cpu` run with any GPU-only configuration switch this feature introduces *explicitly set* in the environment produces a `run_summary` line with the CPU-default identifier value, performs no module-disable and no model swap, emits a clear stderr warning that the switch was ignored because the active profile is not `ppstructurev3@gpu`, and exits with the same status it would have produced without the switch.
- **SC-005**: The default test suite passes on a host without Paddle GPU. All FR-001 / FR-005 / FR-008 / FR-015 verifications that require GPU are skipped via `@pytest.mark.gpu` rather than failed.
- **SC-006**: No committed corpus baseline file under `tests/stage1_vendor_identity/` is modified by this feature outside the established dataset/baseline flow. Verified by checking the diff of this feature's PR against `main` for those paths.
- **SC-007**: For every evaluated configuration, end-to-end pipeline runs on a small corpus subset (preprocess → evidence packet → extract → route → assemble → evaluate) complete with every emitted artifact validating against its existing schema in the active contract set.
- **SC-008**: If a lighter configuration is promoted to the new `ppstructurev3@gpu` default, BOTH (a) the per-corpus aggregate vendor-identity field score from `evaluation_run_summary.json` and (b) the per-document pass count on the small corpus subset (per `docs/stage1-vendor-identity/scoring.md`) are ≥ the legacy default's values on the same subset. If either metric is below the legacy value, no promotion is made: the legacy default remains in place and the lighter configurations stay selectable only via explicit configuration.
- **SC-009**: All feature 014 / 015 / 016 success criteria continue to hold for runs configured under this feature: PPStructureV3 constructed exactly once per process, GPU readiness probed at most once per process, single-device-per-process guard enforced, no silent CPU fallback after `ppstructurev3@gpu` is selected, warmup behavior under `--gpu-warmup` unchanged, `pipeline_version` continues to end in `.gpu0` / `.cpu0` per profile.
- **SC-010**: `schema_version` and the four canonical stage 1 artifact schemas are unchanged by this feature. Verified by `git diff main -- contracts/stage1_vendor_identity/` showing no schema or `contract_set.json` diff attributable to this feature.

## Assumptions

- This feature builds directly on features 014, 015, and 016. The `ppstructurev3@gpu` profile, the single-engine-construction guarantee, the `phase_timings` schema, the `kind: "run_summary"` stdout shape, the `--gpu-warmup` opt-in, and the `@pytest.mark.gpu` test-marker convention are treated as established infrastructure, not as work to redo.
- The workstation ROCm Paddle path used for verification is the host WSL `.venv-paddle-rocm` environment with `paddlepaddle-dcu` bound to `gpu:0`, as established in features 014 and 015. CI continues to run CPU and stub paths only.
- The "small stage 1 vendor identity corpus" used for benchmarking is a fixed subset of `tests/stage1_vendor_identity/inv_*` chosen at `/speckit.plan` time. The same subset is used for every configuration evaluated under FR-005 so quality and timing numbers are comparable.
- Module reduction targets PPStructureV3 sub-modules that vendor identity does not depend on (candidate set: table, formula, chart, document orientation, seal — to be confirmed by the FR-001 audit). The audit, not intuition, determines which modules are safe to disable.
- "Lighter" detection/recognition variants are PaddleOCR-supported detection and recognition model pairings that are smaller, faster, or lower-precision than the legacy variant — selected from PaddleOCR's officially supported model set, not custom-trained weights.
- The configuration-identifier surface for FR-008 / FR-010 lands on `run_summary` per features 015/016's additive-only pattern, NOT inside `preprocess_output.json` (which is schema-frozen by FR-019). Identifier shape is two additive top-level string fields on `run_summary` — `module_set_id` and `det_rec_variant_id` — both human-readable strings, both emitted on every run regardless of profile. The exact CPU-default and legacy GPU-default string values for each field (e.g., `cpu-default`, `legacy`) are agreed at `/speckit.plan` time.
- The activation mechanism for the module-disable switch and the model-variant selector follows the same CLI-flag-with-env-var-fallback pattern feature 016 established for `--gpu-warmup`. Exact flag names are resolved at `/speckit.plan`.
- Workstation GPU verification of FR-001 / FR-005 / FR-008 / FR-015 / FR-024 is best-effort at landing time. If GPU hardware is unavailable, those verifications are tracked as follow-ups under FR-024 rather than blocking merge of CPU-safe code; the deferral is captured in `tasks.md`.
- No new persisted benchmark artifact is needed at landing time. The benchmark numbers from FR-005 / FR-016 land in this feature's `research.md` (and/or quickstart) under FR-020. If `/speckit.plan` later finds `run_summary` + harness outputs insufficient, FR-020's escape hatch applies.
