# Feature Specification: Stage 1 One-Document CLI Contract

**Feature Branch**: `002-cli-contract`
**Created**: 2026-04-13
**Status**: Draft
**Input**: User description: "CLI Contract — Create the stage 1 one-document CLI contract for the LedgerLinc OCR pipeline. Define the command-line entry point that processes a single invoice PDF from source file to stage 1 artifact outputs, accepts one `source.pdf`, validates the required inputs, resolves document and output paths deterministically, and defines exactly where the pipeline writes the four stage 1 artifacts: `preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, and `final_structured_payload.json`. Freeze the CLI contract and one-document execution shape so later work on preprocessing, evidence packet assembly, extraction, routing, and evaluation can plug into it without changing the command surface. Stage-1-only, PDF-only, CLI-first, not a service. Callable by the external harness without code changes."

## Context

Contract set `v1.0.0` (feature 001) locked the seven JSON shapes and the per-document folder layout. That unblocked hand-labeling and downstream schema work, but it does not yet give callers — whether a developer on this workstation or the external test harness — a stable way to actually produce the four pipeline artifacts for one document. Every stage 1 pipeline component downstream of this one (PDF preprocessing, evidence packet assembly, single-voter extraction, deterministic routing, final payload assembly) needs the same question answered: *what is the stable command surface that will produce the four artifacts for one PDF, and where exactly will those artifacts appear on disk?* Until that surface is frozen, each downstream component will hand-roll its own inputs and outputs, the harness will couple to implementation details, and parallel work will converge onto the wrong seam.

This feature freezes the CLI contract for one-document stage 1 runs. It does not implement preprocessing, extraction, routing, or payload assembly — it defines the external surface those components will plug into. The deliverable is a stable command, stable argument names and meanings, stable output-path resolution, stable exit codes, and stable run metadata and traceability, all aligned to the frozen `v1.0.0` contract set and to the runtime boundaries in `.specify/memory/constitution.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pipeline Developer Runs One PDF End to End (Priority: P1)

A pipeline developer has a PDF on their workstation and wants to produce all four stage 1 artifacts for it. They are not building the harness, not tuning prompts, not building evaluation — just running the pipeline once and inspecting the outputs on disk. They need a single command that takes one PDF, resolves an output directory deterministically, writes exactly four artifacts with the reserved filenames, and exits with a code that reflects success or the specific kind of failure.

**Why this priority**: Every other stage 1 pipeline component assumes one-document execution works. Preprocessing, extraction, routing, and payload components will each be coded against this CLI surface. Without it, every component owner invents their own harness wiring, and downstream work cannot parallelize.

**Independent Test**: Hand a developer a PDF and this spec. They can point the CLI at the file, observe artifacts in a known folder, and confirm they match the reserved filenames and the frozen schemas without reading any pipeline source code.

**Acceptance Scenarios**:

1. **Given** a valid PDF and an existing destination folder, **When** the developer invokes the CLI with those inputs, **Then** exactly four artifacts with the reserved filenames appear in the destination folder and the CLI exits with code `0`.
2. **Given** the input path does not exist, **When** the CLI is invoked, **Then** it exits with a non-zero "input not found" code and no artifact files are created anywhere on disk.
3. **Given** the input file exists but is not a PDF, **When** the CLI is invoked, **Then** it exits with a non-zero "invalid PDF" code distinct from "input not found" and no artifact files are created.
4. **Given** the destination folder already contains one or more reserved artifact filenames, **When** the CLI is invoked without `--overwrite`, **Then** it exits with a non-zero "output in use" code and does not touch any existing file on disk.
5. **Given** the CLI exits with `0`, **When** each of the four produced artifacts is validated against the frozen `v1.0.0` contract set, **Then** every artifact validates with zero violations.

---

### User Story 2 - External Test Harness Runs One Document of the Corpus (Priority: P1)

The external test harness iterates over the 20-document stage 1 corpus and, for each document, needs to invoke the pipeline on a per-document folder (`inv_<NNN>_<difficulty>/` containing `source.pdf`) and then find the four generated artifacts in that same folder alongside the human-authored `expected.json` and `notes.md`. The harness is not allowed to know anything about the pipeline's internal module layout; it must be a pure CLI consumer.

**Why this priority**: The model-pipeline PRD requires that the pipeline be "callable from the external test harness without requiring code changes", and the folder contract in `v1.0.0` requires per-document folders to hold inputs, human truth, and generated artifacts together. Evaluation work cannot proceed in parallel with pipeline work unless the harness can assume a stable command surface and a deterministic output location.

**Independent Test**: Without running any pipeline code, a harness developer can copy the command surface from this spec, write a harness loop that invokes it per-document, and know exactly which files will appear inside each folder after each invocation.

**Acceptance Scenarios**:

1. **Given** a corpus folder `inv_001_easy/` containing `source.pdf`, **When** the harness invokes the CLI with that folder as the document folder, **Then** all four generated artifacts appear inside `inv_001_easy/` with the reserved filenames — no subfolders, no prefixes, no timestamped suffixes.
2. **Given** the harness needs to know whether a document was routed to manual review, **When** it reads `routing_decision.json` and `final_structured_payload.json` from the folder, **Then** both report the same `review_status.manual_review_required` and the same `review_status.review_reason`.
3. **Given** a corpus document has `difficulty = missing_name`, **When** the pipeline runs successfully, **Then** the produced artifacts satisfy the company-name provenance triad (`company_name.present = false`, `company_name.inferred = true`, `review_status.manual_review_required = true`, `review_status.review_reason = "company_name_inferred"`) and all four artifacts validate against `v1.0.0`.
4. **Given** the harness needs to re-run the pipeline on a document that was previously processed, **When** it invokes the CLI with `--overwrite`, **Then** the four reserved artifact files are regenerated in place and any prior content at those filenames is replaced.
5. **Given** the CLI is invoked on a folder that does not contain `source.pdf`, **When** the command runs, **Then** it exits with a non-zero "input not found" code and writes no artifacts.
6. **Given** the harness invokes the CLI once per document for the 20-document corpus, **When** every invocation completes, **Then** every per-document folder contains exactly the four reserved artifact filenames plus its existing human-authored files, and no stray temporary files or lockfiles remain.

---

### User Story 3 - Operator Diagnoses a Failed Run (Priority: P2)

An operator is triaging a failed pipeline run. They need the CLI to fail fast with a specific, well-documented exit code and to leave enough on disk and on stderr that they can tell which stage failed (argument parsing, input validation, preprocessing, extraction, routing, payload assembly, or post-hoc schema validation) without attaching a debugger or reading pipeline source code.

**Why this priority**: Diagnosability is an always-on concern, but stage 1 is small enough that a single non-zero exit code would technically produce functional harness behavior. Granular, stable exit codes and a structured stderr record pay off once the corpus is being run end to end; until then they are a quality-of-life win rather than a strict blocker, which is why this is P2 rather than P1.

**Independent Test**: An operator can read the exit-code vocabulary from this spec and, given a failure in a pre-staged broken document (missing PDF / corrupt PDF / unreachable OCR backend / schema-invalid output / read-only destination), predict the exact exit code category before running the CLI and then confirm it matches what the CLI actually produces.

**Acceptance Scenarios**:

1. **Given** the CLI is invoked with a missing PDF, **When** it exits, **Then** the exit code is the "input not found" category and is distinct from every other failure category.
2. **Given** the PDF exists but cannot be parsed as a PDF, **When** the CLI exits, **Then** the exit code is the "invalid PDF" category and is distinct from "input not found".
3. **Given** the pipeline successfully produced an artifact that fails the frozen `v1.0.0` schema, **When** the CLI exits, **Then** the exit code is the "schema validation failure" category (distinct from "processing failure") and the structured stderr record names the offending artifact and the failing field path.
4. **Given** the CLI fails after writing one or more artifacts to disk, **When** it exits, **Then** it emits a structured failure record to stderr as a single JSON line listing (at minimum) the exit-code name, the stage that failed, a human-readable message, and an `artifacts_written` list of absolute paths already present on disk — and it leaves those partial artifacts in place for debugging.
5. **Given** a successful run, **When** the CLI exits with `0`, **Then** it emits a single JSON summary line to stdout reporting `document_id`, `decision`, `manual_review_required`, `review_reason`, and an `artifacts` object with the absolute paths of the four produced artifacts.

---

### User Story 4 - Future Component Plugs In Without Changing the Surface (Priority: P3)

Later stage 1 work will add a second and third voter (ensemble mode), richer Trijunction evidence (Falcon OCR, Falcon Perception), and — eventually — a service wrapper around the same logic. Each of those should slot in behind the same command surface without breaking existing harness invocations or requiring labelers, operators, or downstream tooling to relearn how to run the pipeline.

**Why this priority**: This is a design-for-extensibility concern, not a deliverable. It is P3 because it does not block the first one-document run; it asserts the surface stays stable through stage 1 evolution so that the work this feature unblocks does not have to be re-unblocked.

**Independent Test**: Re-read the CLI contract after stage 1 ensemble work lands. The required-argument list, the reserved artifact filenames, the destination-folder rules, the exit-code vocabulary, and the stdout summary shape should be unchanged; any new arguments should be optional with sensible defaults.

**Acceptance Scenarios**:

1. **Given** an ensemble mode is added later, **When** a caller runs the CLI without any ensemble-specific arguments, **Then** the command behaves identically to the single-voter baseline contract defined here and still writes exactly the four reserved artifacts.
2. **Given** later work reserves additional artifact filenames inside the per-document folder (`votes/`, `consensus_output.json`), **When** this stage 1 CLI runs, **Then** it does not write those names, does not fail if they already exist, and still leaves the four reserved artifacts in the folder.
3. **Given** a later service wrapper is added around the pipeline, **When** it invokes the pipeline internals directly, **Then** it can do so without reimplementing the argument-to-path resolution logic, because the CLI's path-resolution rules are expressible as a small, deterministic function over the inputs.

---

### Edge Cases

- The input PDF is zero bytes or truncated. → Invalid PDF; exit with the "invalid PDF" code; no artifacts written.
- The input PDF is a valid file but contains only blank pages. → The pipeline runs to completion; the CLI exits `0`; review-status and spam-gate checks in `routing_decision.json` reflect the blank content.
- The input path is a directory but does not contain `source.pdf`. → Exit with "input not found" (distinct from "invalid PDF").
- The input path is a symlink. → Resolved to its target; if the target is not a PDF, fall through to "invalid PDF".
- The destination folder is on a read-only filesystem. → Exit with "output path not usable"; no partial files.
- The destination folder is the same as the input folder and the input PDF is `source.pdf`. → Supported (this is the corpus case); four artifacts land alongside `source.pdf`.
- The destination folder already contains `expected.json`, `notes.md`, or any other file that is not one of the four reserved pipeline artifact filenames. → Never touched by the CLI. `--overwrite` applies only to the four reserved pipeline-generated filenames.
- The destination folder already contains `evaluation_document.json`. → Never touched; `evaluation_document.json` is an evaluator artifact, not a pipeline artifact. Its presence neither enables nor blocks this CLI.
- A subsequent run uses a `--contract-set-version` that differs from the version stamped in previously written artifacts in the same folder. → The CLI does not compare against old artifacts; it stamps the version it was invoked with and overwrites (with `--overwrite`) or refuses (without it).
- `document_id` cannot be unambiguously derived from the destination folder name (folder does not match the corpus `inv_<NNN>_<difficulty>` pattern). → Exit with a "document id required" usage error distinct from "input not found"; caller must pass `--document-id`.
- The CLI is invoked with both `--input` and `--document-folder` and they disagree. → Usage error; exit with "conflicting arguments".
- The pipeline is interrupted (SIGINT) partway through. → CLI writes a structured failure record to stderr naming the stage at which interruption occurred; whatever was already on disk stays on disk so the operator can inspect it.
- The CLI is invoked on a PDF where processing exceeds available memory or an underlying dependency errors out. → Exits with "processing failure" (distinct from input or schema failure); stderr record names the stage.
- Host Ollama is unreachable at the configured base URL. → Exits with "processing failure" at the `extraction` stage; stderr record names the stage and includes a human-readable message pointing at the Ollama endpoint, without embedding implementation internals.

## Requirements *(mandatory)*

### Functional Requirements

**Command surface**

- **FR-001**: The system MUST provide a single CLI entry point that processes exactly one input PDF per invocation. Multi-document batch orchestration MUST NOT be implemented at this surface; a harness composes one-document invocations.
- **FR-002**: The CLI MUST accept the input PDF in one of two mutually exclusive forms: (a) a path to a PDF file, via a named option (e.g. `--input`), or (b) a path to a per-document folder that already contains `source.pdf`, via a named option (e.g. `--document-folder`). At least one form MUST be provided. Providing both MUST be rejected as a usage error.
- **FR-003**: The CLI MUST accept an optional `--output-dir` that names the destination per-document folder. When omitted and `--document-folder` was provided, the document folder IS the destination. When omitted and `--input` was provided, the PDF's parent directory IS the destination.
- **FR-004**: The CLI MUST accept an optional `--document-id`. When omitted, the document identifier MUST be derived deterministically from the destination folder name using the documented corpus convention; if derivation is ambiguous, the CLI MUST exit with a usage error directing the caller to pass `--document-id` explicitly.
- **FR-005**: The CLI MUST accept an optional `--overwrite` flag. With the flag, the four reserved pipeline artifact files in the destination folder MAY be replaced. Without the flag, if any reserved artifact filename already exists in the destination folder, the CLI MUST exit with an "output in use" failure before performing any processing and MUST NOT modify any file on disk.
- **FR-006**: The CLI MUST accept optional `--pipeline-version`, `--policy-version`, and `--contract-set-version` arguments. Sensible defaults come from the pipeline build and installed contract set. Overrides MUST be written into the corresponding stamped fields of the produced artifacts. `--contract-set-version` MUST be rejected as a usage error when it names a version the installed contract set cannot validate against.
- **FR-007**: The CLI MUST accept an optional `--log-level` controlling stderr verbosity, with valid values at minimum `error`, `warning`, `info`, `debug`.
- **FR-008**: The stage 1 CLI MUST NOT expose flags that enable cloud execution, batch/multi-document mode, HTTP service mode, or image-only inputs. Such flags are out of scope for stage 1 and are not present in the frozen argument set.
- **FR-009**: The full list of required and optional arguments in the frozen stage 1 CLI MUST be exhaustively documented alongside the CLI. Any addition or removal of an argument MUST go through the contract-set amendment path.

**Deterministic path resolution and artifact layout**

- **FR-010**: On successful exit, the CLI MUST have written exactly four artifact files: `preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, and `final_structured_payload.json`. No other files MUST persist in the destination folder as a result of the CLI's execution. Temporary files used during processing MUST NOT remain after the CLI exits.
- **FR-011**: The four artifact filenames MUST be exactly the reserved names defined in the `v1.0.0` folder contract. Filename prefixes, suffixes, timestamps, run identifiers, or subdirectories MUST NOT appear in the persisted artifact filenames.
- **FR-012**: All four artifacts MUST be written into the destination per-document folder resolved from the arguments — not into a subfolder, not into a sibling directory, and not to stdout.
- **FR-013**: The CLI MUST NOT write or modify `expected.json`, `notes.md`, or any file in the destination folder that is not one of the four reserved pipeline artifact filenames. The reserved evaluation-layer filename `evaluation_document.json` is also off-limits to this CLI; it is produced by the evaluator, not by the pipeline.
- **FR-014**: The CLI MUST reserve the ensemble-mode names `votes/` (folder) and `consensus_output.json` (file) as off-limits. It MUST NOT write them and MUST NOT fail if either already exists.
- **FR-015**: The CLI MUST NOT perform any in-place modification of `source.pdf`. The input PDF is read-only from the pipeline's point of view.

**Input validation**

- **FR-016**: The CLI MUST verify that the resolved input PDF path exists before starting any processing stage. If it does not, the CLI MUST exit with an "input not found" code and MUST NOT create the destination folder or any artifact.
- **FR-017**: The CLI MUST verify that the resolved input is a PDF using content inspection (file magic), not only the file extension. If it is not, the CLI MUST exit with an "invalid PDF" code distinct from "input not found".
- **FR-018**: The CLI MUST verify that the destination folder already exists and is writable before starting any processing stage. If it does not exist, the CLI MUST NOT create it implicitly and MUST exit with an "output path not usable" code directing the caller to create the folder. (Rationale: the harness and the corpus layout already create per-document folders; silent creation would hide harness bugs.)
- **FR-019**: The CLI MUST reject any argument combination that conflicts with FR-002 through FR-008 (e.g., both `--input` and `--document-folder`, unknown arguments, invalid `--log-level` values) as a usage error before performing any processing.

**Exit codes**

- **FR-020**: The CLI MUST exit with code `0` if and only if the pipeline produced all four artifacts and every produced artifact validates against the `v1.0.0` contract set.
- **FR-021**: The CLI MUST use a small, stable, documented set of non-zero exit code categories, at minimum:
  - usage error (bad, missing, or conflicting arguments)
  - input not found (PDF missing, document folder missing `source.pdf`, destination folder missing)
  - invalid PDF (content is not a PDF)
  - output in use (reserved artifact filenames already present without `--overwrite`)
  - output path not usable (destination not writable or not a directory)
  - processing failure (a pipeline stage — preprocess, extraction, routing, or final payload — raised a failure)
  - schema validation failure (a produced artifact does not validate against `v1.0.0`)
  The specific numeric values MUST be documented alongside the CLI and MUST remain stable across stage 1.
- **FR-022**: The CLI MUST NOT collapse distinct categories from FR-021 into a single exit code. An operator reading the exit code alone MUST be able to distinguish input-layer from processing-layer from schema-layer from usage failures.
- **FR-023**: On any non-zero exit, the CLI MUST write a single JSON-object line to stderr containing at minimum `exit_code` (int), `exit_code_name` (string matching FR-021), `stage` (one of `arguments | input_validation | preprocess | extraction | routing | final_payload | schema_validation`), `message` (human-readable), and `artifacts_written` (list of absolute paths to files already on disk when the failure occurred, possibly empty).
- **FR-024**: On any failure after at least one artifact has been written, the CLI MUST leave those partial artifacts on disk. The structured stderr record (FR-023) MUST list them so a harness can reason about or clean up after a partial run.

**Run metadata and traceability**

- **FR-025**: On successful exit, the CLI MUST emit a single JSON-object line to stdout containing at minimum `document_id`, `decision` (mirroring `routing_decision.decision`), `manual_review_required` (boolean), `review_reason` (string or null), and `artifacts` (object mapping each of the four reserved filenames to its absolute path on disk).
- **FR-026**: Every artifact produced by the CLI MUST carry every metadata field already required by the frozen `v1.0.0` contract set (at minimum `document_id`, `processed_at`, `contract_set_version`, and — for artifacts that carry them — `pipeline_version` and `policy_version`). The CLI MUST NOT introduce new top-level metadata fields into artifacts at this contract; new fields require a contract-set amendment.
- **FR-027**: The `final_structured_payload.trace` block MUST reference the three other artifacts by bare filename, not by absolute path, so that the per-document folder remains relocatable without invalidating traceability.
- **FR-028**: The CLI MUST stamp the same `document_id` into all four artifacts produced by a single invocation. A single invocation MUST NOT produce artifacts with mismatched identifiers.
- **FR-029**: The CLI MUST NOT write a host-specific absolute path into any persisted artifact. Absolute paths MAY appear in the stdout summary (FR-025) and the stderr failure record (FR-023), but not in on-disk artifacts.

**Compatibility with frozen contracts and runtime boundaries**

- **FR-030**: Every artifact produced by the CLI MUST validate against the frozen `v1.0.0` contract set with zero post-hoc editing. Any change to artifact shape requires an amendment through the contract-set governance path, not a CLI change.
- **FR-031**: The CLI MUST live in the pipeline layer only. It MUST NOT implement or embed the test harness, the evaluator, labeling tooling, or cross-document reporting.
- **FR-032**: The CLI MUST target host Ollama over HTTP for model inference in stage 1, per the constitution's runtime boundary. Selection of the Ollama base URL MUST be readable from an environment variable (`OLLAMA_BASE_URL`) with a documented default; a CLI flag MAY be provided as an override but MUST NOT be the only way to configure the endpoint, so that harness and operator workflows can remain environment-driven.
- **FR-033**: The stage 1 CLI MUST NOT require network access beyond the configured Ollama endpoint. It MUST NOT reach out to any cloud model provider, external storage service, or telemetry endpoint.
- **FR-034**: The CLI MUST be callable by the external test harness without code changes to the pipeline. All configuration required by a harness invocation MUST be expressible through CLI arguments and environment variables documented in this contract.
- **FR-035**: The CLI MUST be forward-compatible with ensemble expansion: adding additional voters later MUST NOT change the required-argument list, the reserved artifact filenames, the destination-folder rules, the exit-code vocabulary, or the stdout summary shape.

**Stage 1 scope boundary**

- **FR-036**: The CLI contract MUST NOT accept image inputs (PNG, JPG, TIFF) in stage 1. PDF is the only supported input type.
- **FR-037**: The CLI contract MUST NOT expose line-item extraction flags, line-item-related output arguments, or line-item-bearing artifact names. Line items are out of scope for stage 1.
- **FR-038**: The CLI contract MUST NOT expose latency or timeout knobs as release gates. A simple overall processing timeout MAY be implemented for robustness but MUST NOT be positioned as a quality or SLA control at stage 1, and MUST NOT be required to tune for the 20-document corpus to run successfully.

### Key Entities

- **CLI Invocation**: A single-shot command whose inputs are one PDF, a destination per-document folder, and a small optional metadata/argument set. Its outputs are four JSON artifacts on disk, a single exit code, a stdout JSON summary line on success, and a stderr JSON failure record on any non-zero exit. Consumed by pipeline developers, operators, and the external test harness.

- **Destination Per-Document Folder**: The existing directory into which the four reserved artifact filenames are written. May be a corpus document folder (`inv_<NNN>_<difficulty>/`) or an ad-hoc folder. The pipeline treats both the same and neither is created implicitly by the CLI.

- **Reserved Artifact Filenames**: The closed set `preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`. The only filenames this CLI is authorized to write into the destination folder. `evaluation_document.json`, `votes/`, and `consensus_output.json` are reserved for other roles and are off-limits to the pipeline CLI.

- **Stdout Run Summary**: A single-line JSON object emitted on `exit 0`, carrying just enough identity and routing outcome for a harness to branch without re-reading the four artifacts from disk.

- **Structured Failure Record**: A single-line JSON object emitted on stderr on any non-zero exit, carrying the exit-code category, the failing pipeline stage, a human-readable message, and the set of artifacts that had already been written before the failure. Consumed by operators and by harness retry/cleanup logic.

- **Exit Code Vocabulary**: The closed, versioned set of exit-code categories the stage 1 CLI commits to use. Stable through stage 1; extended only through the contract-set governance path.

- **Argument Surface**: The closed, documented set of required and optional CLI arguments for the stage 1 one-document run. Addition, removal, or renaming of arguments requires a contract-set amendment.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A pipeline developer can run one PDF through the stage 1 CLI and locate all four artifacts on disk in the correct folder without reading any pipeline source code, using only this spec and the CLI's `--help` output, within 10 minutes of first exposure.
- **SC-002**: The external test harness can be written against this CLI contract — command surface, argument names, exit-code vocabulary, stdout summary, stderr failure record — without reading any pipeline implementation file.
- **SC-003**: 100% of the CLI failure modes enumerated in FR-021 map to a distinct, documented exit-code category; zero categories collapse into a single generic "error" code.
- **SC-004**: 100% of artifacts produced by a successful run validate against the frozen `v1.0.0` contract set with zero post-hoc editing, and zero successful runs produce artifacts whose stamped `contract_set_version` mismatches the version used to validate them.
- **SC-005**: Any change to the CLI argument set, the reserved artifact filenames, the destination-folder rules, or the exit-code vocabulary requires a documented amendment — demonstrated by a new entry in the amendment path and a contract-set version bump when the CLI contract itself changes.
- **SC-006**: Switching from the stage 1 single-voter baseline to a later ensemble mode requires zero changes to the required-argument list, the reserved artifact filenames, the stdout summary shape, or the exit-code vocabulary. Demonstrable by a forward-compatible example invocation from the ensemble stage that reuses today's command line verbatim.
- **SC-007**: The CLI is callable by the external test harness unchanged across stage 1: the harness's invocation shape does not have to change between the first one-document run and the full 20-document corpus run.
- **SC-008**: After this feature ships, the downstream stage 1 pipeline components (preprocessing, evidence packet assembly, single-voter extraction, routing, final payload assembly) can be implemented in parallel, each able to stub upstream stages against the resolved destination folder, with no component owner needing to coordinate input or output path decisions through side channels.
- **SC-009**: An operator reading an exit code and a single stderr JSON line can identify which pipeline stage failed without attaching a debugger, for every failure category in FR-021.

## Assumptions

- The CLI entry point lives in the pipeline package alongside the validator that already exists at `src/ledgerlinc_ocr/validator/`. The exact module path and executable name are implementation choices deferred to `/speckit.plan`; this spec treats the command as "the stage 1 pipeline CLI" in the abstract.
- The default behavior when the destination folder contains reserved artifact filenames is to refuse and require `--overwrite`. This is chosen over "silently overwrite" because reproducibility is a constitutional concern and the harness can always pass the flag explicitly when re-running a document.
- On processing failure, the CLI leaves any artifacts it had already written in place on disk for debugging. Rolling back or deleting partial outputs would hide diagnosable state; the structured stderr record lists exactly which artifacts were written, so a harness that wants rollback semantics can implement them without CLI help.
- `document_id` derivation from the destination folder name follows the corpus convention `inv_<NNN>_<difficulty>` → `inv_<NNN>` (for example, `inv_001_easy` → `inv_001`). When the folder name does not match that pattern, the CLI refuses to guess and requires `--document-id`. This keeps the stamped `document_id` stable against folder-rename patterns labelers are expected to use.
- The stage 1 CLI has no dependency on cloud model providers, external storage, or telemetry services. Host Ollama over HTTP is the only required network endpoint; its URL is read from `OLLAMA_BASE_URL` with a documented default, consistent with the constitution's runtime boundary.
- A single-voter baseline is acceptable for stage 1. `edge_extraction_output.vote_metadata.consensus_mode = "single_voter_baseline"` and `routing_decision.consensus_summary.mode = "single_voter_baseline"` are stamped by the pipeline regardless of how many voters actually ran; the stage 1 CLI does not expose a voter-selection argument.
- Image-only inputs, batch orchestration, HTTP service mode, cloud escalation, line-item extraction, and latency-SLA gating are explicitly out of scope for the stage 1 CLI. None of them appear in the frozen argument set; adding them in a later stage is governed by the contract-set amendment path.
- `evaluation_document.json` is authored by the evaluator (test harness), not by this CLI. The pipeline CLI's responsibility ends at `final_structured_payload.json`. `evaluation_run_summary.json` is authored by the harness at the corpus root and is never written by this CLI.
- The stage 1 CLI runs inside the existing pipeline devcontainer and against host Ollama. Production-style native Linux ROCm container validation remains orthogonal and does not change this CLI contract.
