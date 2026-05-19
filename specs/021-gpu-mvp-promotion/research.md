# Research: GPU MVP Promotion (Feature 021)

**Date**: 2026-05-18 · **Branch**: `021-gpu-mvp-promotion` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

This document resolves all planning-time decisions surfaced by the spec, the 2026-05-18 Clarifications session, and the deep-rigor checklists. There are no remaining NEEDS CLARIFICATION items.

Format per decision: **Decision** / **Rationale** / **Alternatives considered** / **Affected requirements**.

---

## R-021.1: Scratch-copy directory layout under `/tmp`

**Decision**: Use the layout `/tmp/021-bench/<lane>/run<N>/inv_XXX_<difficulty>/{source.pdf,preprocess_output.json,...}` where `lane ∈ {warmup, legacy, candidate}` and `N ∈ {1, 2}` (the warmup directory only contains run 1). Each per-document subfolder is a byte-for-byte mirror of `tests/stage1_vendor_identity/inv_XXX_<difficulty>/source.pdf` plus the lane's run-N outputs (`preprocess_output.json`, optionally `edge_extraction_output.json` etc. for the quality-gate runs). The runbook explicitly names the layout so a reproducer can find legacy run-2 vs. candidate run-2 outputs.

**Rationale**: This layout (a) preserves the per-document folder contract that feature-007 evaluator and the FR-019 quality gate expect; (b) keeps lane and run identity explicit in the path itself, so `cat /tmp/021-bench/legacy/run2/inv_001_easy/preprocess_output.json` is unambiguous; (c) keeps warmup separated from the comparison pairs so the FR-012 "discard first run of each pair" discipline maps directly to `run1/` discard, `run2/` keep; (d) lets an operator run `diff -r /tmp/021-bench/legacy/run2 /tmp/021-bench/candidate/run2` to spot artifact-level divergence; (e) is trivially scriptable for cleanup (`rm -rf /tmp/021-bench/`).

**Identical-input invariant**: the scratch-copy mirror procedure copies each `source.pdf` from the SAME canonical corpus path (`tests/stage1_vendor_identity/<doc>/source.pdf`) into every (lane × run) scratch location. This guarantees identical source.pdf bytes across all 25 per-document scratch folders, so any cross-lane phase-timing difference is attributable to the lane configuration, not to input drift.

**Same-session invariant**: legacy and candidate lanes MUST run in the same shell session, against the same workstation state, against the same Ollama placement (same loaded model, same `size_vram` from `/api/ps`). Cross-session comparison invalidates the jitter band because the cache-warmth baseline is no longer continuous across the four-run sequence.

**Alternatives considered**:

- **Document-first layout** (`/tmp/021-bench/inv_XXX/<lane>/run<N>/...`). Rejected: less convenient for evaluator-harness ingestion (the harness expects a directory root that contains per-document folders, not a directory root whose children are document IDs that themselves split into lanes).
- **Flat with embedded keys** (`/tmp/021-bench/inv_001_easy.legacy.run2.preprocess_output.json`). Rejected: breaks the evaluator's per-document-folder contract.
- **Timestamped roots** (`/tmp/021-bench-2026-05-18T14-22-00/...`). Rejected: makes the runbook's example commands non-copyable and complicates cleanup; the operator can choose a different root if isolating runs matters, but the default is the stable `/tmp/021-bench/`.

**Affected requirements**: FR-018 (scratch-copy discipline), FR-023 (Appendix A), FR-024 (Appendix B), SC-011 (zero corpus mutation), checklist `benchmark.md` CHK034.

---

## R-021.2: Timing unit + numeric formatting for Appendix A

**Decision**: All `phase_timings.*` values in Appendix A are recorded as **seconds with three decimal places** (e.g., `0.842`). This matches feature 015's `run_summary.phase_timings.*` emission format (seconds, three decimals). Jitter band values and material-change deltas use the same unit and formatting.

**Rationale**: Feature 015 (`015-gpu-engine-reuse-timing`) introduced the `phase_timings.*` keys with seconds-as-float emission; reusing the same unit avoids cross-feature confusion and makes Appendix A directly comparable to any raw `run_summary` stdout line. Three decimals are precise enough for the jitter formula (jitter band is typically in the 0.05–0.20s range on this workstation) without false precision.

**FP comparison tolerance**: all jitter-formula comparisons (`max(...)`, `|Δ| > threshold`) MUST operate on the recorded 3-decimal values, not on the underlying full-precision floats. Two reviewers transcribing the same `run_summary` line and applying the formula by hand or via spreadsheet will see identical 3-decimal inputs and therefore agree on every `is_material` verdict. Tools that hold full-precision floats (e.g., `numpy`-based audit scripts) MUST round to 3 decimals before comparison to preserve this byte-for-byte agreement.

**Alternatives considered**:

- **Milliseconds (int)**. Rejected: would require unit conversion in Appendix A relative to the raw `run_summary` line, introducing a manual error source.
- **Microseconds**. Rejected: false precision for a four-run discipline with measured jitter in the tens-of-ms range.

**Affected requirements**: FR-014 (record every emitted `phase_timings.*` key), FR-015 (jitter formula), checklist `benchmark.md` CHK022.

---

## R-021.3: Threshold-zero jitter edge case (`run1 == run2` on both lanes)

**Decision**: When `legacy_run1 == legacy_run2` AND `candidate_run1 == candidate_run2` for a given (document, phase key), the FR-015 threshold evaluates to zero. In that case, **any non-zero `|candidate_run2 − legacy_run2|` is treated as material**. The reasoning is recorded inline in Appendix A as "threshold=0 (no measured jitter); any delta material" so a reviewer understands why a small absolute delta is flagged.

**Rationale**: A measured jitter of zero is itself a measurement statement — it asserts the two lanes are individually noise-free. In that case the only conservative interpretation of "material change" is "any change". This preserves the spec's "the jitter band IS the threshold" principle (Assumptions clarification) without injecting an arbitrary fallback band.

**Alternatives considered**:

- **Fallback to a fixed-percentage band** (e.g., 5%). Rejected: contradicts the Assumptions clarification ("no absolute or fixed-percentage band is layered on top").
- **Treat threshold=0 as non-material** (suppress findings). Rejected: would mask genuine cross-lane drift in a noise-free phase key (the worst case for false negatives).

**Affected requirements**: FR-015, FR-016, SC-006, checklist `benchmark.md` CHK021.

---

## R-021.4: Direction symmetry for FR-016 "material change"

**Decision**: FR-016's material-change rule is **direction-symmetric**: on a suppressed document, ANY phase key other than `per_page_inference` and `total` crossing the jitter band — in either direction (increase or decrease) — is recorded as a finding. Additionally, an *increase* in `per_page_inference` or `total` on a suppressed document is also a finding (suppression is supposed to reduce inference time; an increase is the inverse signal).

**Rationale**: The spec already says "Movement in any other `phase_timings.*` key beyond the jitter band MUST be flagged as a finding, not absorbed silently" (FR-016) — the word *movement* is direction-agnostic. This decision makes the implicit direction-agnostic reading explicit. The extension to `per_page_inference`/`total` increases catches a regression pattern that would otherwise hide under the permission to "decrease materially".

**Alternatives considered**:

- **Decrease-only findings** (the spirit of "improvement direction"). Rejected: would silently accept cross-lane drift in either direction, masking regressions disguised as decreases-elsewhere.
- **Per_page_inference/total increases ignored**. Rejected: an increase on a suppressed document is a meaningful regression; the spec's "decrease materially" language describes the *permitted* outcome, not a permission for the inverse.

**Affected requirements**: FR-016, SC-006, checklist `benchmark.md` CHK024.

---

## R-021.5: Canonical demo-runbook file path

**Decision**: The demo runbook lands at `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`. This path slot is currently unoccupied (the `docs/stage1-vendor-identity/` tree already hosts `ollama-runtime.md`, `gpu-warmup-and-cache.md`, etc., and the kebab-case `runbook-gpu-mvp-demo.md` naming matches the existing convention).

**Rationale**: (a) Co-locates with existing stage-1 operator documentation so a discoverer browsing `docs/stage1-vendor-identity/` finds it without external pointers. (b) Kebab-case filename matches `prd-gpu-mvp-promotion.md`, `prd-model-pipeline.md`, etc. (c) The `-mvp-demo` suffix distinguishes it from other potential runbooks (e.g., a future `runbook-cpu-ci.md`). (d) Stable path lets future features cross-link the runbook (e.g., a future ops feature for over-time surveillance).

**Alternatives considered**:

- **`docs/stage1-vendor-identity/demo-runbook.md`**. Rejected: less specific (which demo? CPU? GPU?).
- **`docs/runbook.md` (repo root)**. Rejected: not co-located with stage-1 docs; breaks discoverability.
- **`specs/021-gpu-mvp-promotion/runbook.md`**. Rejected: spec-tree paths are typically frozen after feature landing; a runbook is a live operational doc that future features may edit, so it belongs in `docs/`.

**Affected requirements**: FR-025 (demo runbook), checklist `runbook.md` CHK026.

---

## R-021.6: Handling when Ollama is up but the extraction model is not yet loaded

**Decision**: The Ollama readiness helper treats "the model entry whose `name` matches the active voter config is absent from `/api/ps`" as a **FAIL with the explicit cause** "extraction model `<model_name>` not loaded in Ollama". The helper does NOT attempt to load the model itself (no `POST /api/generate` warmup). The runbook tells the operator to either issue a single warmup query (e.g., `ollama run <model_name> ""`) or wait for the demo's first extraction call to load the model, then re-run the readiness check.

**Rationale**: (a) Per FR-032, the readiness helper must not introduce new product behavior; auto-loading the extraction model would be exactly that. (b) An absent model is a FAIL not a BLOCKED — it's a directly remediable readiness gap, and the named cause ("model not loaded") gives the operator the exact next step. (c) Keeping load behavior out of the helper preserves the "no silent state change" property — the helper only reads `/api/ps`, never mutates Ollama state.

**Alternatives considered**:

- **Auto-load via POST `/api/generate` with a tiny prompt**. Rejected: side-effect-bearing; FR-032 violation; would also introduce a wait+retry loop with no defined timeout.
- **Treat absent model as BLOCKED**. Rejected: BLOCKED is reserved for hardware/runtime causes that cannot be operator-remediated in the moment; a not-yet-loaded model is exactly that — not yet loaded.
- **Silent retry with a fixed delay**. Rejected: introduces hidden non-determinism; violates the fail-fast posture.

**Affected requirements**: FR-002 (Ollama check), FR-004 (fail-fast surface), checklist `gpu-readiness.md` CHK011, CHK041.

---

## R-021.7: Active voter-config path resolution

**Decision**: The Ollama readiness helper takes a required `--voter-config PATH` flag pointing at the voter-config YAML file used by the same demo command. The runbook pins a single canonical path for the MVP demo: `configs/voter/ollama-gpu.yaml` (a NEW config file under a new `configs/voter/` directory). This config is a thin YAML wrapper that names the GPU-targeted extraction model — its `model_name` MUST equal the model the `--extract-profile ollama@gpu` profile actually binds (resolved by `src/dartwing_ocr/pipeline/stages.py::_ollama_extract_factory` → `src/dartwing_ocr/extract/voters/configs/gemma-edge.yaml::ollama.model_tag`). At landing the canonical value is `model_name: "gemma4:e4b"`. A CPU-safe contract test (`tests/contract_tests/test_voter_config_model_alignment.py`) asserts the equality so the readiness check and the extractor never validate different models.

**Rationale**: (a) Existing voter-config YAMLs live in `tests/fixtures/extract/*/voter_config.yaml` — fixture-only paths unsuitable for a demo command. (b) A canonical `configs/voter/ollama-gpu.yaml` gives the demo runbook a stable command target and lets the readiness helper resolve the model name without operator guesswork. (c) A new `configs/voter/` directory is a *configuration* surface, not pipeline code — it does not trip FR-032 (no new product behavior in `dartwing_ocr`). (d) The shell helper reads the YAML's `model_name` key (per feature 005 voter-config schema, `model_name: string (non-empty)`). (e) The same path is named in the demo runbook's `dartwing-extract` invocation, so the readiness check and the demo command share one source of truth.

**Alternatives considered**:

- **Hardcode the model name in the helper**. Rejected: couples the helper to one model identity; operator cannot demo a different model without editing the helper.
- **Read from an env var (`DARTWING_VOTER_CONFIG`)**. Rejected: invisible state; operators forget env vars between sessions; the runbook would have to set+unset.
- **Reuse a fixture path under `tests/`**. Rejected: violates intent — fixtures are for tests, not for demo commands.

**Affected requirements**: FR-002 (Ollama check + voter-config resolution), FR-025 (runbook canonical commands), checklist `gpu-readiness.md` CHK009, `runbook.md` CHK041.

---

## R-021.8: pytest mark + GPU gating mechanism

**Decision**: Preserve the existing `pytestmark = pytest.mark.gpu` collection marker on each of the five files being converted (the four `pipeline_tests/test_evidence_gate_*` files plus `tests/unit/preprocessing/test_warmup_skip_fallback_exception.py`). Remove the per-test `@pytest.mark.skip(reason="R-020.15")` decorator and replace its decorated body with the real GPU assertions. CPU CI continues to run with `pytest -m 'not gpu'` (or equivalent CI configuration); GPU CI / operator-run GPU validation uses `pytest -m gpu` against `.venv-paddle-rocm`. Register `gpu` as a known marker in `pyproject.toml` (or `pytest.ini`) if not already registered, to silence `PytestUnknownMarkWarning`.

**Rationale**: (a) The `pytest.mark.gpu` mark already exists on every placeholder file (verified by inspection), so the collection surface is unchanged. (b) Removing `@pytest.mark.skip(...)` is a *test-content* change, not a *test-selection* change — CPU CI behavior is untouched. (c) Using a single mark (`gpu`) keeps the CI matrix simple. (d) Registering the marker formally removes the warning that landed when feature 020 introduced the placeholder files. (e) The CPU-safe twins (`*_cpu.py`) continue to cover the invariants on CPU lanes.

**Alternatives considered**:

- **Add a second `gpu_only_workstation` mark**. Rejected: redundant; one `gpu` mark is sufficient.
- **Replace `pytest.mark.skip` with `pytest.mark.skipif(not gpu_available, ...)`**. Rejected: redundant with the file-level `pytest.mark.gpu` collection mark; double-gating creates confusion.
- **Delete the placeholder files and create new GPU test files**. Rejected: loses the explicit conversion narrative; spec language (US2 Independent Test) names these exact files.

**Affected requirements**: FR-006, FR-007, FR-008, FR-009, FR-010, SC-004, SC-010, checklist `requirements.md` CHK032.

---

## R-021.9: Ollama readiness shell helper invocation contract

**Decision**: The helper is `scripts/check-ollama-gpu-readiness.sh` with this invocation contract:

```bash
scripts/check-ollama-gpu-readiness.sh --voter-config configs/voter/ollama-gpu.yaml [--base-url http://localhost:11434]
```

Required flag: `--voter-config PATH` (path to a YAML file containing a top-level `model_name` string). Optional flag: `--base-url URL` (default `http://localhost:11434`).

**Exit codes**:

- `0` — PASS (extraction-model entry in `/api/ps` has `size_vram > 0 AND size_vram == size`)
- `1` — FAIL: model loaded but not fully on GPU (`size_vram == 0` or `0 < size_vram < size`)
- `2` — FAIL: model not loaded (model name absent from `/api/ps` response)
- `3` — FAIL: Ollama not reachable (curl non-zero, network error, non-200 HTTP response)
- `4` — FAIL: voter-config file missing or malformed (no `model_name` key, not valid YAML)

**Stdout** (on PASS): single JSON line summarizing the matched model entry: `{"status":"pass","model_name":"<name>","size":N,"size_vram":N,"base_url":"<url>"}`.

**Stderr** (on FAIL, any non-zero exit): a single line naming the unmet prerequisite, e.g., `FAIL: extraction model "gemma4:e4b" not loaded in Ollama at http://localhost:11434/api/ps`. The exit code distinguishes failure classes for scripting; the stderr message is human-friendly.

**Rationale**: (a) Distinct exit codes give the runbook (and any wrapper script) machine-checkable failure classes without parsing text. (b) JSON-on-PASS on stdout lets the runbook capture and record the model + sizes into Appendix A's environment notes. (c) Stderr-only failure messages keep stdout clean (suitable for `>` redirection or `| jq`). (d) Required `--voter-config` avoids implicit defaults. (e) Optional `--base-url` enables non-`localhost` Ollama in a future ops feature without changing the helper's contract today.

**Alternatives considered**:

- **Single exit code `0`/`1`**. Rejected: loses the FAIL-class signal that the runbook needs for actionable remediation.
- **Stdout on both PASS and FAIL**. Rejected: complicates `| jq` consumption.
- **Default `--voter-config` to a hardcoded path**. Rejected: implicit; operator might run the helper from a different terminal than the demo.

**Affected requirements**: FR-002 (check mechanism), FR-004 (fail-fast surface), SC-002 (non-zero exit + named prerequisite), checklist `gpu-readiness.md` CHK006, CHK010, checklist `failure-handling.md` CHK006.

---

## R-021.10: Stderr/stdout split for fail-fast error messages

**Decision**: All fail-fast error messages — from `python -m dartwing_ocr.preprocessing.preflight`, from the Ollama readiness helper, and from any wrapper invocation — go to **stderr only**. Stdout remains reserved for the canonical `kind: "run_summary"` line (feature 015 lineage) plus the helper's PASS JSON line. The runbook tells the operator to capture stderr with `2>readiness.log` for incident review.

**Rationale**: (a) Preserves machine-parseability of stdout (`run_summary` JSON line stays the only thing on stdout for pipeline runs). (b) Aligns with Unix convention. (c) Lets CI fail-loudly without polluting structured stdout output streams. (d) The runbook can show a single `2>readiness.log` capture as the canonical incident-review collection.

**Alternatives considered**:

- **Mix stderr and stdout**. Rejected: breaks `run_summary` stdout parsing.
- **JSON-only structured errors on a dedicated FD**. Rejected: over-engineered; FR-032 forbids new product behavior.

**Affected requirements**: FR-004, SC-002, checklist `failure-handling.md` CHK006, CHK048.

---

## R-021.11: Promotion-decision recording artifact (team-decision medium)

**Decision**: The "explicit team decision" required by FR-029 is recorded in **two synchronized locations** as required by FR-026:

1. **Authoritative**: a dedicated subsection in `specs/020-vendor-evidence-gate/quickstart.md` Appendix B titled `### Promotion Decision (2026-XX-XX)` containing: (a) the binary decision (`stay opt-in` or `promote to default`); (b) the cited FR-019 verdict (PASS / FAIL / BLOCKED) including the appendix paragraph reference; (c) the rationale (2–4 sentences); (d) if promote-to-default: the explicit-off legacy-path flag/env-var, the test path, the inverted default location.
2. **Mirror**: a short `## Promotion Decision` section in `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` that links back to the Appendix B subsection and restates the binary verdict + flag surface.

The Appendix B subsection is the source of truth; the runbook section is a derivative summary. The two MUST agree on the binary decision; agreement is verified by a CPU-safe contract test that loads both files and asserts the same `Decision:` line appears in each.

**Rationale**: (a) Two recording media (FR-026) are synchronized via a contract test, not by a separate workflow; this matches the spec's discipline. (b) The Appendix B subsection's header (`### Promotion Decision (YYYY-MM-DD)`) makes the date and ownership unambiguous. (c) Mirror in the runbook ensures a demo audience can see the operational posture without leaving the runbook. (d) Contract test catches drift early.

**Alternatives considered**:

- **Commit-message-only record**. Rejected: not persistent in the documented surface; reviewers reading Appendix B months later would not see the decision.
- **Separate `PROMOTION-DECISION.md`**. Rejected: fragments the record across more files; Appendix B already exists.
- **Free-form prose anywhere in Appendix B**. Rejected: not machine-checkable; risks drift between Appendix B and runbook.

**Affected requirements**: FR-026, FR-027, FR-029, SC-009, checklist `promotion.md` CHK016, CHK033.

---

## R-021.12: Partial-progress benchmark recording

**Decision**: If the four-run benchmark sequence terminates after K of the planned five documents complete a run (e.g., a mid-run runtime error), the partial output is recorded in Appendix A under a **clearly-labeled "Partial Benchmark Run (K/5 documents)" sub-block** with the named cause of termination. The promotion-decision verdict (PASS/FAIL/BLOCKED via FR-019) MUST then be derived from a **full re-run** — partial data is informative only, never decisional. The partial sub-block is preserved as evidence for the named blocker; the full re-run produces the canonical Appendix A entries used by the verdict.

**Rationale**: (a) Discarding partial data destroys forensic value (the blocker cause is most easily diagnosed from the partial output). (b) Letting partial data influence the verdict violates FR-013's same-subset rule and FR-020's both-metrics-non-regression rule (per-document pass count is undefined for a missing document). (c) The labeled sub-block makes it impossible for a future reader to mistake partial evidence for a verdict source.

**Alternatives considered**:

- **Erase partial output, require full re-run from scratch**. Rejected: destroys forensic evidence about the blocker.
- **Promote partial PASS to full PASS if K ≥ 4**. Rejected: violates FR-013/FR-020; opens a sample-size gaming surface.

**Affected requirements**: FR-011 through FR-018, FR-019, FR-020, FR-022, checklist `failure-handling.md` CHK046.

---

## R-021.13: FR-019 two-metric quality-gate formula (feature-007 evaluator surface)

**Decision (verification-round revision, 2026-05-19)**: FR-019's two metrics are read directly from `evaluation_run_summary.json`'s `overall_metrics` block, which the feature-007 evaluator persists unchanged:

- **Metric A** — `overall_metrics.vendor_identity_pass_rate` (mean of the per-document boolean `vendor_identity_passed` flag across the corpus; range `[0.0, 1.0]`).
- **Metric B** — `overall_metrics.field_accuracy` (mean of the per-document field-level match rate across the corpus; range `[0.0, 1.0]`).

PASS verdict requires `candidate >= legacy` on BOTH metrics (FR-020 strict conjunction). The feature-007 outputs are produced by running the existing evaluator harness with the per-lane benchmark roots: `evaluator <CORPUS_ROOT>=/tmp/021-bench/legacy/run2/` and `evaluator <CORPUS_ROOT>=/tmp/021-bench/candidate/run2/`. The harness emits `evaluation_document.json` per per-document folder and `evaluation_run_summary.json` at the corpus root. Appendix B records the two `overall_metrics` aggregates per lane plus the per-document `overall_passed` / `field_accuracy` table from each `evaluation_run_summary.json`'s `documents[]` array.

**Rationale**: (a) Both metrics are aggregates that the feature-007 evaluator already persists in `overall_metrics`, so no new metric is introduced (FR-032 — no new product behavior in `dartwing_ocr`). (b) The two metrics are **mathematically independent** on a fixed-N corpus: a document can clear the boolean vendor-identity threshold (Metric A) while showing variable field-level accuracy across the other fields (Metric B). A regression in Metric B catches subtle quality dips that Metric A would not. (c) Reusing the existing aggregates preserves the "feature-007 as-is" boundary (Assumptions clarification).

**Why the original draft was wrong**: The original decision named "sum of per-document `vendor_identity_score`" for Metric A and "count of per-document `vendor_identity_pass` flags" for Metric B. Inspection of `src/dartwing_ocr/evaluator/corpus.py::to_persistable_dict` showed (a) no per-document `vendor_identity_score` numeric field exists in the feature-007 schema; the schema has a per-document `document_pass_fail.vendor_identity_passed` boolean only, and that boolean lives in `evaluation_document.json` (per-doc), not in the run summary; (b) `evaluation_run_summary.json`'s `documents[]` array persists only `{document_id, overall_passed, field_accuracy}` per document — no `document_pass_fail` sub-object; (c) on a fixed-N corpus, `vendor_identity_pass_rate` and "per-document pass count" are monotonically equivalent (`rate = count / N`), so using both as the FR-020 conjunction collapses to a single check. Switching Metric B to `overall_metrics.field_accuracy` restores genuine independence while preserving FR-032 (no schema change, no new aggregator).

**Alternatives considered**:

- **Reading per-document `evaluation_document.json` files for `vendor_identity_passed` booleans**. Rejected: forces the test to walk the corpus folder per lane and parse N files instead of one aggregate; adds I/O without changing the verdict logic, since the same boolean is already aggregated into `vendor_identity_pass_rate`.
- **Adding a new aggregate (e.g., sum of vendor-identity scores)**. Rejected: would require adding a new field to feature-007's `overall_metrics`, violating FR-032's "no new product behavior" rule.
- **Keeping Metric B as "per-document pass count"** by computing it from `documents[i].overall_passed`. Rejected: still collapses with Metric A on fixed N (count = pass_rate × N).

**Affected requirements**: FR-019 (two-metric quality gate), FR-020 (PASS conjunction), Assumptions §"feature-007 evaluator used as-is", checklist `quality-gate.md` CHK005, CHK025.

---

## R-021.14: Warm-corpus output semantics — `--output-dir` is NOT honored in `--documents-file` mode

**Decision**: In warm-corpus mode (`python -m dartwing_ocr.pipeline run --documents-file <list>`), per-document output artifacts are written **back into each folder listed in the documents-file** (verified against `src/dartwing_ocr/pipeline/runner.py::run_plan(plan, folder=folder_resolved)` and `src/dartwing_ocr/pipeline/corpus_run.py` iteration loop, which passes `folder=folder_resolved` per document). The `--output-dir` flag is only honored in single-document `--input <pdf>` cold mode (via `path_resolution.resolve_destination`). Therefore, to satisfy FR-018 / SC-011 (no committed-corpus mutation), this feature's benchmark and demo commands MUST list **scratch-copied** per-document folders under `/tmp/021-bench/...` in their documents-file, NOT the committed paths under `tests/stage1_vendor_identity/`. The scratch-copy mirror (`mkdir -p` + `cp source.pdf`) is the discipline; `--output-dir` is not the mechanism.

**Rationale**: (a) Warm-corpus mode is the only practical invocation pattern for the FR-011 five-document subset — single-document cold mode would require five separate invocations per lane per run, losing the canonical aggregated `run_summary` stdout line. (b) The pipeline's read+write semantics (input source.pdf + output artifacts co-located in one folder) inherits from the stage-1 per-document folder contract; warm-corpus mode preserves that contract per iteration. (c) Mirroring `source.pdf` to scratch and listing the scratch folders is operationally trivial (a few shell lines) and keeps every byte of write activity outside `tests/stage1_vendor_identity/`.

**Alternatives considered**:

- **Add `--output-dir` honoring to warm-corpus mode in feature 011/020**. Rejected: feature-021 is validation/promotion-only (FR-032); modifying the pipeline CLI is out of scope. A future feature could revisit this if scratch-tree friction becomes an operator pain point.
- **Invoke single-document cold mode five times per lane per run with `--output-dir`**. Rejected: explodes the four-run discipline into 4 × 5 = 20 invocations per benchmark, fractures the per-document `run_summary` aggregation, and complicates the operator workflow. Scratch-mirror per-doc folders is simpler.
- **Run the pipeline against committed corpus and `git stash` / `git restore` the writes after**. Rejected: violates SC-011 mid-run (the corpus IS mutated during execution, even if reverted after); also risks accidental commits.

**Affected requirements / artifacts**: FR-018 (scratch discipline), SC-011 (zero committed-corpus mutation), [quickstart.md §Path 3](./quickstart.md), [contracts/runbook.md §Step 2a](./contracts/runbook.md), [tasks.md T014 / T023](./tasks.md). Discovery: surfaced by `/speckit.analyze` rerun finding C6 (2026-05-18). Closure: this R-021.14 entry plus the corresponding quickstart / contracts / tasks edits.

---

## R-021.15: Re-run scope after procedural-finding corpus mutation

**Decision**: After a procedural-finding corpus mutation (Edge Case: "benchmark run accidentally targets committed corpus folders"), the operator MUST restart the **full four-run sequence from warmup** — not just the contaminated lane's pair. The contamination invalidates the cache-warmth baseline for BOTH pairs because the mutated state (any committed-corpus write) may have triggered MIOpen / COMGR cache regeneration, leaving the workstation in an unknown cache state relative to the original warmup.

**Rationale**: (a) Partial re-runs (just the contaminated lane) cannot guarantee the four-run jitter-band invariant (paired-run spread reflects the workstation's noise floor, not the contamination's noise floor). (b) The four-run discipline's whole point is comparison against a continuous cache-warmth baseline; breaking that baseline mid-sequence is operationally equivalent to a workstation reboot (Edge Case "Four-run sequence interrupted by workstation reboot or process restart") and is handled the same way. (c) The cost (one extra warmup + two extra runs) is small compared to the cost of a tainted Appendix A entry.

**Alternatives considered**:

- **Re-run only the contaminated lane's pair**. Rejected: the cache state may have drifted between pairs; comparing the new pair against the prior pair's run-2 risks a false-negative finding.
- **Mark the prior Appendix A entry as "tainted" and amend in place**. Rejected: violates the re-derivability discipline (SC-005) and creates a confused audit trail.

**Affected requirements**: FR-012 (four-run discipline), FR-018 (scratch discipline), SC-011 (zero corpus mutation), Edge Cases §"benchmark run accidentally targets committed corpus folders", failure-handling.md CHK031.

---

## R-021.16: Quality-gate BLOCKED on missing `expected.json`

**Decision**: If any document in the FR-011 benchmark subset lacks an `expected.json` at the time the FR-019 quality gate runs, the gate's verdict is **BLOCKED** with named cause `"missing expected.json for <document_id>"` (one named cause per missing document, joined if multiple). Skip-fallback remains opt-in per FR-027 (BLOCKED → stay opt-in). The `legacy_pass_rate` / `candidate_pass_rate` / `legacy_field_accuracy` / `candidate_field_accuracy` fields in the Quality-Gate Verdict entity are all `null` per data-model.md §4 BLOCKED-state validation (verification-round revision per R-021.13).

**Rationale**: (a) Both metrics are undefined when any truth file is missing; the feature-007 evaluator returns a missing-expected error rather than guessing. (b) Treating missing-expected as BLOCKED (not FAIL) is correct because it's a corpus-state issue, not a candidate-regression issue. (c) The named cause includes the offending document_id so the operator knows which `expected.json` to add or restore before re-running.

**Alternatives considered**:

- **Treat as FAIL with zero score for the missing doc**. Rejected: conflates corpus-state issue with candidate regression; misleads the promotion-decision reviewer.
- **Score only the documents with expected.json present**. Rejected: violates FR-013's same-subset rule (legacy and candidate must use the same 5 documents in the verdict).

**Affected requirements**: FR-019 (two-metric quality gate), FR-022 (BLOCKED verdict with named cause), data-model.md §4 (Quality-Gate Verdict shape), quality-gate.md CHK041.

---

## Phase-0 Outcome

All **16** planning decisions resolved (13 original + R-021.14 added during /speckit.analyze remediation + R-021.15 and R-021.16 added during /speckit.checklist walk resolution). No NEEDS CLARIFICATION items remain. Constitution Check re-evaluated post-Phase-0: still PASS (no decision above introduces a new package, schema, or pipeline-code surface; the new `configs/voter/ollama-gpu.yaml` is a configuration file, not pipeline code, and the new `scripts/check-ollama-gpu-readiness.sh` is explicitly outside `dartwing_ocr` per the FR-002 carve-out and Constitution §I; R-021.14–R-021.16 document existing semantics and procedural rules, not new pipeline behavior).

**Next**: Phase 1 — generate `data-model.md`, `contracts/`, `quickstart.md`, then re-evaluate the Constitution Check.
