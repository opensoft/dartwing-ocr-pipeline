# PRD: Stage Runtime Profiles For The Top-Level Pipeline

## Purpose

This PRD defines the product requirements for turning the top-level stage 1 pipeline CLI into the real vertical-slice entrypoint while preserving explicit per-stage test seams.

It covers how `python -m dartwing_ocr.pipeline run` selects stage implementations, how callers run only part of the four-artifact flow, and how full-workstation, cloud-workstation, and Jetson edge lane selection fits into stage 1 benchmarking and diagnostics.

It also records the preprocessing-profile direction that follows from the
PPStructureV3 migration: stage 1 needs both a full document-structure stack and
a lightweight edge OCR stack, selected through the same profile mechanism rather
than split into a separate repository.

## Problem Statement

Today the repository has a split reality:

- the top-level pipeline CLI is still the frozen contract/stub runner
- the preprocessing CLI is real
- the extraction CLI is real
- routing and final payload logic exist, but the harness cannot use the top-level pipeline command as the real end-to-end path

That split is acceptable for slice-by-slice development, but it blocks the next phase of testing:

- the harness cannot call one stable pipeline entrypoint for real runs
- developers cannot mix stub and live stages through the top-level runner
- benchmarking still depends on separate helper wiring instead of a slice-aware pipeline command
- preprocessing now has two distinct runtime needs:
  - a full PPStructureV3 document-structure path for layout, tables, and corpus baselines
  - a lightweight Jetson Nano Super edge OCR path for fast first-pass scanning when full table/layout evidence is not required
- corpus regeneration and production workers should not pay full model import and construction cost once per document; warm batch/worker execution must be possible for any live preprocessing profile

## Goal

Keep the top-level pipeline entrypoint stable while making its behavior configurable enough for both real runs and mixed stub/live runs.

The desired end state is:

- the same top-level `pipeline run` command can execute the real stage 1 pipeline by default
- each of the four stages can still be forced to `stub`
- supported live stages can choose CPU or GPU runtime lanes where meaningful
- the cloud-class solution can be validated on workstation GPU cards before
  remote cloud deployment exists
- the edge-fast stack uses the Jetson GPU lane for OCR and model inference, with no silent CPU fallback for heavy work
- callers can run any contiguous slice of the four-stage pipeline without recomputing upstream stages
- corpus and harness-driven live preprocessing runs can reuse a warmed
  preprocessing profile instance instead of rebuilding PPStructureV3 once per
  document

## Scope

Included:

- a contract amendment to the stage 1 pipeline CLI
- one profile selector for each of the four stages
- explicit start/stop bounds for partial runs
- CPU/GPU lane selection for live stages that support multiple runtime lanes
- local cloud-class workstation validation for the future cloud solution
- multiple live preprocessing implementations where the artifact contract can be preserved
- Jetson Nano Super edge stack selection for lightweight OCR and Gemma 4 E2B extraction
- a warm corpus/batch execution path that can process many documents after initializing the selected live stage once
- default non-stub profiles for full top-level runs
- preservation of the current artifact contracts and filenames
- preservation of the current programmatic test seam for injected stage callables

Explicitly out of scope:

- schema changes to any of the four stage 1 artifacts
- moving benchmark reporting out of the harness and into the pipeline
- provider-managed or production multi-voter orchestration outside the local
  `cloud-workstation` validation stack
- remote cloud execution or provider-managed fallback
- workstation GPU/ROCm preprocessing for the PPStructureV3 full-structure profile
  in the 011 controller slice; feature 014 reopens this as an explicit
  opt-in `ppstructurev3@gpu` validation path without changing the CPU default
- a second repository for the edge OCR scanner
- allowing two canonical `preprocess_output.json` files in the same document folder at the same time

## Implementation Priority

The first implementation increment should optimize the testing loop without
changing the artifact contracts. That means 011 should start with the smallest
root/master controller surface that enables a warm `ppstructurev3@cpu` corpus
path, then expand into the full runtime-profile matrix.

Recommended implementation order:

1. Add the thin controller foundation: profile parsing, profile validation,
   stage-slice parsing, overwrite scoping, and prerequisite-artifact validation.
   Keep explicit `stub` profiles and injected stage callables working so
   contract tests remain fast and deterministic.
2. Add warm preprocessing execution for corpus and harness use: initialize the
   selected live preprocessing profile once per process, process many
   per-document folders through that warmed instance, preserve normal
   per-folder artifacts, and expose run metadata that separates one-time
   initialization time from per-document work.
3. Wire the default top-level one-document run to named non-stub profiles:
   `ppstructurev3@cpu`, `ollama@gpu`, `rules@cpu`, and `assembler@cpu`.
4. Add secondary lane and stack support after the faster feedback loop exists:
   `ollama@cpu`, `ollama@jetson`, `ensemble@workstation`,
   `cloud-workstation`, and `edge-fast`.

This sequencing treats warm preprocessing as an enabling optimization inside
the controller feature, not as a separate side script. The harness still owns
corpus selection, repeated benchmark runs, scoring, and reports; the controller
owns stage selection, execution slicing, profile lifecycle, and per-run timing
metadata needed by the harness.

## Recommended Interface Shape

Use named stage profiles rather than a generic `real` keyword.

Recommended flags:

- `--preprocess-profile`
- `--extract-profile`
- `--routing-profile`
- `--final-payload-profile`
- `--start-at`
- `--stop-after`
- `--stack-preset`
- `--ollama-cpu-url`
- `--ollama-jetson-url`

Recommended profile grammar:

- `stub`
- `<implementation>@<lane>`

Examples:

- `ppstructurev3@cpu`
- `edge-ocr@jetson`
- `ollama@gpu`
- `ollama@cpu`
- `ollama@jetson`
- `ensemble@workstation`
- `rules@cpu`
- `assembler@cpu`

This naming avoids the ambiguity of `real`, which means different things in each stage.

## Stage 1 Profile Set

Recommended supported profiles for this profile contract:

- preprocess:
  - `stub`
  - `ppstructurev3@cpu`
  - `edge-ocr@jetson`
- extract:
  - `stub`
  - `ollama@gpu`
  - `ollama@cpu`
  - `ollama@jetson`
  - `ensemble@workstation`
- routing:
  - `stub`
  - `rules@cpu`
- final payload:
  - `stub`
  - `assembler@cpu`

Recommended preprocessing profile roadmap:

- `ppstructurev3@cpu` — the full document-structure stack. Produces OCR lines,
  layout blocks, table projections, document text, quality, and ingestion-source
  status. This is the canonical full-evidence preprocessing profile for corpus
  baselines and downstream extraction grounding.
- `edge-ocr@jetson` — a lightweight edge scanner for the Jetson Nano Super
  target. Produces fast OCR-first evidence for triage and first-pass
  vendor-identity scanning. It must run OCR on the Jetson GPU lane, not as a
  CPU-only fallback. It must either preserve the `preprocess_output.json`
  contract with explicit empty/typed layout and table slots, or land with a
  contract amendment that defines exactly which fields are profile-dependent. It
  must not fabricate layout blocks or table structure.

The first implementation of this PRD may ship only `ppstructurev3@cpu` for
preprocessing. Adding `edge-ocr@jetson` is a follow-up feature under the same
profile grammar, not a separate product or repository.

Recommended default full-run profile set:

- preprocess = `ppstructurev3@cpu`
- extract = `ollama@gpu`
- routing = `rules@cpu`
- final payload = `assembler@cpu`

The default full-run profile remains `ppstructurev3@cpu` until the edge OCR
profile has its own contract coverage and evaluator evidence. Operators may
explicitly choose `edge-ocr@jetson` for fast scanning once that profile exists.

## Named Stack Presets

The profile flags remain the source of truth, but operators need named presets
for common combinations. A `--stack-preset` convenience flag may expand to the
stage profiles below; explicit per-stage profile flags should remain the final
resolved source of truth.

- `full-workstation`
  - preprocess: `ppstructurev3@cpu`
  - extract: `ollama@gpu` using the Gemma 4 E4B voter config
  - routing: `rules@cpu`
  - final payload: `assembler@cpu`
- `cloud-workstation`
  - target: workstation with local GPU cards
  - preprocess: `ppstructurev3@cpu` initially, with Trijunction-local
    contributors added when available
  - extract: `ensemble@workstation` using a cloud-class voter set on local
    workstation model endpoints
  - routing: `rules@cpu`
  - final payload: `assembler@cpu`
- `edge-fast`
  - target: Jetson Nano Super class hardware
  - preprocess: `edge-ocr@jetson`
  - extract: `ollama@jetson` using the Gemma 4 E2B voter config
  - routing: `rules@cpu`
  - final payload: `assembler@cpu`

`cloud-workstation` is the place to test the future cloud solution before
remote cloud deployment exists. It should use the same artifact filenames and
schema contracts, but run the larger voter set locally on workstation GPUs. It
must not call external cloud-provider APIs or require provider credentials.

`edge-fast` keeps Gemma 4 E2B in the stack because it is the smaller edge
extractor. Gemma 4 E4B remains the default full-workstation extractor until
evaluation data proves a different default should replace it.

The `edge-fast` preprocessing sequence is:

1. run the lightweight Paddle OCR scanner on the Jetson GPU lane
2. apply deterministic OCR-quality gates
3. if the gates fail, use a larger Paddle fallback only when that fallback also
   runs on the Jetson GPU lane and records the fallback in profile metadata
4. if no Jetson GPU fallback is available, emit a review/escalation signal
   rather than running the heavy OCR stack on CPU

Gemma 4 E2B is the edge extractor/judge over the evidence packet. It reads the
OCR evidence, proposes normalized vendor-identity fields, cites evidence ids,
and returns confidence signals. It does not perform OCR, own layout recovery,
decide final routing, or override deterministic provenance rules such as
`company_name.present`, `company_name.inferred`, and
`manual_review_required`.

## Preprocessing Output Modes

Only one profile output is canonical in a normal per-document folder:

- `preprocess_output.json` is the output of the selected preprocessing profile
  for that invocation.
- The selected profile must be visible in `pipeline_version` so downstream
  consumers and evaluators can distinguish full-structure and edge-OCR outputs.
- A normal pipeline run must not keep both full and edge outputs side by side
  under the same filename.

For side-by-side comparison, profile outputs should be written under an explicit
run namespace rather than overwriting each other:

```text
runs/full-structure/preprocess_output.json
runs/edge-ocr/preprocess_output.json
```

The harness may compare those run namespaces, but the stage contract still has
one canonical preprocessing artifact per selected run.

## Warm Execution Requirement

Live preprocessing profiles may have expensive model imports and construction.
The pipeline must therefore support a warm execution shape for corpus and worker
use cases:

- initialize the selected live preprocessing profile once per process
- process many document folders through that warmed profile
- support both fail-fast baseline regeneration and continue-through-failures
  corpus diagnostics, with failed documents reported by stage and profile
- expose enough per-run and per-document timing detail to separate one-time
  profile initialization, rasterization, page inference, artifact writing, and
  total document time

The single-document CLI remains useful for local debugging and isolated failure
tests, but it is not the expected production serving shape for full-stack OCR.

## Runtime Boundaries

This feature does not change the repository's runtime boundaries.

- pipeline code still owns preprocessing orchestration, extraction orchestration, routing, and final payload
- the harness still owns corpus iteration, benchmark loops, evaluation, and reporting
- host Ollama remains the GPU-capable extraction path
- the optional CPU Ollama lane remains a benchmark/comparison path
- preprocessing profile selection remains inside the pipeline layer; the edge
  OCR scanner does not become a separate repository or independent schema owner

The change is orchestration-level: the top-level pipeline runner becomes configurable enough to call the existing real stages and still preserve stubs where needed.

## Success Criteria

1. The harness can call the top-level pipeline command for real stage 1 runs without changing artifact filenames or folder layout.
2. A developer can run any contiguous stage slice through the top-level runner using existing prerequisite artifacts.
3. A developer can force any stage to `stub` without losing the ability to run other stages live.
4. Extraction can be switched between CPU and GPU lanes through stage-profile selection, with no schema or path changes.
5. Invalid stage-profile combinations fail before any artifact write.
6. A follow-up preprocessing-profile feature can add `edge-ocr@jetson` without changing repositories, artifact filenames, or downstream stage boundaries.
7. The first 011 implementation slice can run at least a small corpus through a
   warm `ppstructurev3@cpu` preprocessing process that initializes the selected
   preprocessing stack once and then processes multiple document folders.
8. Warm preprocessing metadata separates one-time profile initialization from
   per-document rasterization, page inference, artifact writing, and total
   document time so the harness can produce faster and more meaningful corpus
   reports.
9. A `cloud-workstation` stack can run the future cloud-style voter set on local workstation GPUs without introducing remote cloud execution, provider credentials, or artifact schema changes.

## Risks And Mitigations

- **Risk: CLI contract drift becomes confusing.**
  Mitigation: treat this as an explicit amendment to `002-cli-contract`, not an undocumented extension.

- **Risk: benchmark concerns leak into the pipeline layer.**
  Mitigation: keep benchmark loops, scoring, and report generation in the
  harness; the pipeline exposes only execution controls and per-run timing
  metadata needed by those reports.

- **Risk: unsupported live/stub mixes create unclear behavior.**
  Mitigation: define slice prerequisites and overwrite rules explicitly in the feature spec before implementation.

- **Risk: cloud-workstation gets mistaken for deployed cloud fallback.**
  Mitigation: name the stack `cloud-workstation`, require local workstation
  model endpoints, reject provider credentials in this feature, and reserve
  remote cloud fallback for a separate change.

- **Risk: lane selection is over-generalized.**
  Mitigation: only expose multi-lane choices where stage 1 actually supports them; reject unsupported combinations fast.

- **Risk: edge OCR output is mistaken for full layout evidence.**
  Mitigation: encode the selected preprocessing profile in `pipeline_version`,
  keep empty layout/table slots typed and explicit, and require evaluator
  comparison before making `edge-ocr@jetson` a default.

- **Risk: edge-fast silently runs heavy OCR or model inference on CPU.**
  Mitigation: make `edge-ocr@cpu` unsupported, require Jetson GPU lane checks
  for `edge-ocr@jetson` and `ollama@jetson`, and fail fast or route to review
  when the Jetson GPU lane is unavailable.

- **Risk: full-stack preprocessing appears too slow because corpus jobs launch
  one process per document.**
  Mitigation: require a warm batch/worker path for live preprocessing profiles
  and keep per-document CLI timing separate from production-style warm timing.
