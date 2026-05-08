## ADDED Requirements

### Requirement: Jetson work follows the feature 019 fast-lane decision
The system MUST NOT promote live Jetson edge implementation before feature 019 records a decision to promote, conditionally promote, revise, or discard the OCR-only fast lane. Live Jetson preprocessing MUST reuse or explicitly adapt the OCR evidence strategy and quality gates selected by feature 019.

#### Scenario: Feature 019 has no recorded decision
- **WHEN** a developer attempts to start live `edge-ocr@jetson` implementation
- **THEN** the change is blocked until the feature 019 decision is documented

#### Scenario: Feature 019 accepts a revised fast lane
- **WHEN** feature 019 accepts a revised OCR-only strategy with quality gates
- **THEN** the Jetson preprocessing feature uses that revised strategy as its starting contract

### Requirement: Jetson preflight classifies edge readiness before artifact writes
The system MUST provide a Jetson edge preflight that classifies whether the target can run the `edge-fast` stack before live Jetson stages write canonical artifacts. The preflight MUST distinguish at least missing Jetson runtime, missing OCR dependency, OCR GPU unavailable, Jetson-local Ollama unreachable, selected edge model unavailable, and ready states.

#### Scenario: Jetson-local Ollama endpoint is unavailable
- **WHEN** `edge-fast` is selected and the configured `ollama@jetson` endpoint cannot be reached
- **THEN** the run fails before writing `edge_extraction_output.json` and names the Jetson endpoint failure

#### Scenario: OCR dependency exists but GPU execution is unavailable
- **WHEN** `edge-ocr@jetson` is selected and OCR can only run on CPU
- **THEN** the run fails before writing `preprocess_output.json` and names the no-CPU-fallback rule

#### Scenario: Jetson preflight passes
- **WHEN** OCR GPU execution, Jetson-local Ollama, and the selected edge model are all available
- **THEN** the run may proceed to live `edge-ocr@jetson` preprocessing and `ollama@jetson` extraction

### Requirement: Edge OCR preprocessing preserves the stage 1 artifact contract
The `edge-ocr@jetson` preprocessing profile MUST emit the canonical `preprocess_output.json` filename and MUST validate against the active stage 1 preprocessing schema. The selected profile and Jetson lane MUST be visible in metadata or a parseable profile/version string.

#### Scenario: Lightweight OCR observes lines and coordinates only
- **WHEN** `edge-ocr@jetson` processes a PDF and does not observe layout blocks or tables
- **THEN** `preprocess_output.json` remains schema-valid with truthful empty or typed structure fields rather than fabricated layout/table evidence

#### Scenario: Edge OCR writes an artifact
- **WHEN** `edge-ocr@jetson` completes successfully
- **THEN** the document folder contains exactly one canonical `preprocess_output.json` for the selected run

### Requirement: Edge-fast never silently falls back to CPU-only heavy work
The `edge-fast` stack MUST run OCR and model inference on the Jetson GPU lane. CPU-only OCR, CPU-only model inference, and heavy full-structure CPU fallback MUST NOT be used as silent substitutes for unavailable Jetson GPU execution.

#### Scenario: Lightweight OCR quality gates fail
- **WHEN** `edge-ocr@jetson` quality gates fail and a larger fallback is available on the Jetson GPU lane
- **THEN** the fallback may run and MUST record the fallback in profile metadata

#### Scenario: Lightweight OCR quality gates fail without Jetson GPU fallback
- **WHEN** `edge-ocr@jetson` quality gates fail and no Jetson GPU fallback is available
- **THEN** the document is routed to review or full-workstation processing rather than running heavy OCR on CPU

### Requirement: Jetson extraction uses the Jetson-local edge model lane
The `ollama@jetson` extraction profile MUST use the Jetson lane endpoint resolution order `--ollama-jetson-url` flag, then `OLLAMA_JETSON_BASE_URL`, then the documented Jetson default. It MUST use the configured Gemma 4 E2B edge voter profile and MUST preserve the existing `edge_extraction_output.json` schema.

#### Scenario: Explicit Jetson URL is supplied
- **WHEN** the caller passes `--ollama-jetson-url`
- **THEN** `ollama@jetson` uses that endpoint instead of the environment variable or default

#### Scenario: Edge model is missing
- **WHEN** the Jetson-local endpoint is reachable but the configured Gemma 4 E2B edge model is unavailable
- **THEN** extraction fails before writing `edge_extraction_output.json` and names the missing model

#### Scenario: Jetson extraction succeeds
- **WHEN** `ollama@jetson` returns a valid extraction response
- **THEN** the system writes schema-valid `edge_extraction_output.json` with evidence references and vote metadata compatible with the single-voter baseline

### Requirement: Edge-fast stack runs through the existing pipeline and harness surfaces
The `edge-fast` stack MUST be runnable through the existing `--stack-preset edge-fast` pipeline surface and through evaluator `--run-pipeline` pass-through. It MUST emit the same four canonical stage 1 artifacts as other selected stacks.

#### Scenario: Single document edge-fast run succeeds
- **WHEN** a caller runs the pipeline with `--stack-preset edge-fast` on one document and Jetson preflight passes
- **THEN** the document folder contains schema-valid `preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, and `final_structured_payload.json`

#### Scenario: Evaluator prepares an edge-fast corpus run
- **WHEN** the evaluator is invoked with `--run-pipeline --stack-preset edge-fast`
- **THEN** it passes the preset and Jetson endpoint options to the pipeline rather than importing pipeline runtime modules

### Requirement: Edge-fast results are distinguishable from workstation baselines
The system MUST expose enough stack/profile/model/lane metadata for evaluator reports to distinguish `edge-fast` results from `full-workstation` and `cloud-workstation` results. Side-by-side comparison MUST use explicit run namespaces or copied document folders, not two competing canonical artifacts in the same normal document folder.

#### Scenario: Edge and workstation runs are compared
- **WHEN** the harness compares `edge-fast` and `full-workstation` results for the same source document
- **THEN** each selected run has its own artifact namespace or document-folder copy and evaluator output identifies which stack produced each result

#### Scenario: Normal edge-fast run completes
- **WHEN** `edge-fast` runs in a normal per-document folder
- **THEN** the folder contains one canonical set of stage artifacts and metadata identifies the selected stack/profile/lane

### Requirement: Jetson hardware tests remain opt-in
Default automated tests MUST NOT require Jetson hardware, Jetson GPU access, Jetson-local Ollama, or edge model weights. Jetson-dependent tests MUST be opt-in or skipped with an actionable readiness reason when prerequisites are absent.

#### Scenario: CI runs without Jetson hardware
- **WHEN** the default test suite runs in a non-Jetson environment
- **THEN** Jetson-dependent tests are skipped or excluded without failing the suite

#### Scenario: Jetson tests are explicitly enabled
- **WHEN** a developer opts into Jetson tests on configured hardware
- **THEN** the tests execute live preflight, preprocessing, extraction, and at least one end-to-end `edge-fast` smoke run
