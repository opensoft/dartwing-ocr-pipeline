# Feature 021 — Checklist Open Items for Resolution

**Created**: 2026-05-18
**Source**: `/speckit.checklist` walk of the 657-item deep release-gate set
**State after walk**: 612 / 673 ticked green; 61 items remain `[ ]` as documented Gaps

This file enumerates each of the 61 open checklist items, grouped by theme, with a **Your answer** field for you to populate inline. Once you finish, ping me and I'll read the file, apply your decisions (close / defer / amend-and-close), update the source checklists, and proceed to `/speckit.implement`.

## How to use this file

For each item:

1. Read the question and my recommendation.
2. Fill in **Your decision**, one of:
   - **close** — the item is satisfied; tick it green now (optionally with a one-line rationale).
   - **close-with-edit** — the item needs a small spec/plan/research/contract amendment first; describe the edit, then tick.
   - **defer** — out of scope for this feature; record as a known limitation. Tick on the strength of the deferral.
   - **leave-open** — genuine gap that should remain `[ ]` until a future amendment. Note: this is the default for `[Gap]`-flagged items that aren't worth closing now.
3. Optionally fill in **Your note** with any extra context, planning-time decision, or future-feature handoff direction.

You can answer in any order. Items left blank will be treated as **defer** by default.

---

## Theme A — Recovery / Re-run / Rollback Procedures (~14 items)

These document *what to do when something breaks*. The current spec defines the operational *posture* (Fallback discipline) but not specific *procedures*. Most are natural candidates for a future ops feature.

### A1 — `failure-handling.md::CHK021` — Blocker self-resolves between recording and re-run

**Question**: Is the case "the blocker resolves itself between recording and re-run" addressed — should the recorded blocked verdict be re-evaluated, or is it frozen in time?
**My recommendation**: defer (future ops feature). Current spec implies blocked verdicts are dated snapshots that don't auto-re-evaluate; re-attempt requires a fresh run.

**Your decision**: defer
**Your note**: Accept recommendation.

### A2 — `failure-handling.md::CHK031` — Re-run scope after corpus mutation

**Question**: Is the re-run obligation defined — must the operator restart the four-run sequence from warmup, or only re-run the contaminated lane?
**My recommendation**: close-with-edit. Add to research.md §R-021.12 or a new R-021.15: "After a procedural-finding corpus mutation, the operator MUST restart the four-run sequence from warmup (not just the contaminated lane), because the contamination invalidates the cache-warmth baseline for both pairs."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### A3 — `failure-handling.md::CHK036` — Re-attempt promotion after Fallback

**Question**: Is the case "Fallback engaged but the team later wants to re-attempt promotion" addressed — does the spec require a fresh four-run + quality-gate, or can previously-blocked evidence be amended?
**My recommendation**: defer. The Fallback discipline is the posture; re-attempt is a future operational decision out of this feature's scope.

**Your decision**: defer
**Your note**: Accept recommendation.

### A4 — `failure-handling.md::CHK038` — Aborted attempt: what to keep vs. discard

**Question**: Is the case "the entire promotion attempt is aborted" addressed — does the spec specify what to keep (blocked evidence) and what to discard (incomplete Appendix A/B drafts)?
**My recommendation**: defer. R-021.12 handles partial-progress; full abort is operator judgment.

**Your decision**: defer
**Your note**: Accept recommendation.

### A5 — `failure-handling.md::CHK039` — Rollback path for over-eager promotion

**Question**: Is the rollback path for an over-eager promote-to-default change explicit (revert the default flip, update Appendix B and runbook to record the reversion)?
**My recommendation**: close-with-edit. Add to data-model §5 Promotion Decision Record: "A future demotion (promote-to-default → stay-opt-in) creates a NEW dated record with `decision: stay opt-in`; the prior promote-to-default record is retained as history. The inverted-default code change is reverted in the same body of work."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### A6 — `failure-handling.md::CHK049` — Demo fail-fast mid-audience-session

**Question**: Are requirements defined for the case "fail-fast triggers but the operator has already started a demo audience session" — does the spec want a graceful interrupt or only a hard exit?
**My recommendation**: defer. The fail-fast posture (FR-004) is "hard exit with named cause"; graceful audience-handling is a presentation skill, not a spec requirement.

**Your decision**: defer
**Your note**: Accept recommendation.

### A7 — `performance.md::CHK024` — Four-run failure mode (second run also cold)

**Question**: Are the failure modes of the four-run discipline addressed (e.g., what if the second run is also cold-cache because the workstation rebooted between runs)?
**My recommendation**: close-with-edit. Add an Edge Case: "If the four-run sequence is interrupted by workstation reboot or process restart, the run-1/run-2 cache-warmth invariant is broken; the operator MUST restart the affected lane's pair from a fresh warmup."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### A8 — `performance.md::CHK042` — Appendix-A invalidation conditions

**Question**: Are performance-claim *invalidation* conditions documented — i.e., what changes between two runs would force re-recording Appendix A (e.g., a Paddle wheel upgrade)?
**My recommendation**: close-with-edit. Add to contracts/appendix-recording.md §1 Environment fingerprint: "If any fingerprint field changes between the recorded run and a comparison run, the prior Appendix A entry is no longer comparison-valid; a fresh four-run sequence is required."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### A9 — `performance.md::CHK043` — Doc relabel/remove → retroactive appendix invalidation

**Question**: Is the case "one of the five benchmark documents is later relabeled or removed from the corpus" addressed — does the appendix become invalid retroactively?
**My recommendation**: defer. Cross-feature corpus mutation is out of scope; FR-033 forbids regeneration anyway.

**Your decision**: defer
**Your note**: Accept recommendation.

### A10 — `performance.md::CHK044` — Implausibly wide jitter band → re-run trigger

**Question**: Is the case "the four-run sequence's per-document jitter band is implausibly wide (e.g., > 1 second on `per_page_inference`)" addressed — does the spec want a re-run trigger?
**My recommendation**: defer. Operator judgment; not a spec-level rule. A wide jitter band → conservative "no material change found" verdict, which is itself a finding.

**Your decision**: defer
**Your note**: Accept recommendation.

### A11 — `performance.md::CHK045` — Intra-lane cache warming

**Question**: Is the case "candidate run-2 lower than candidate run-1 by more than the jitter band ON ITSELF" (intra-lane cache warming effect) addressed — does it invalidate the pair?
**My recommendation**: defer. The four-run discipline already discards run-1; if intra-lane spread is huge, the threshold is correspondingly conservative.

**Your decision**: defer
**Your note**: Accept recommendation.

### A12 — `promotion.md::CHK036` — Promote-to-default + later regression

**Question**: Is the case "promote-to-default was chosen, but a later regression appears" addressed — does the spec require a re-evaluation path that can revert to stay-opt-in?
**My recommendation**: close-with-edit. Same as A5: add the demotion-path requirement to data-model §5 + contracts/appendix-recording.md.

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### A13 — `promotion.md::CHK037` — Revisit cadence

**Question**: Are requirements defined for revisiting the promotion decision (e.g., "after N weeks of operation, the team SHOULD re-evaluate")?
**My recommendation**: defer. Operational cadence is a future ops-feature concern.

**Your decision**: defer
**Your note**: Accept recommendation.

### A14 — `requirements.md::CHK036` — Recovery flow for quality-gate FAIL

**Question**: Are recovery-flow requirements defined for the case where a quality-gate FAIL is observed (re-run? abandon? requalify the corpus?) — the PRD §Fallback specifies posture but not recovery actions?
**My recommendation**: defer. Same theme as A1, A3.

**Your decision**: defer
**Your note**: Accept recommendation.

---

## Theme B — Multi-user workstation / Threat model (~11 items)

The spec's implicit threat model is "single-operator workstation; operator who can read `/tmp` is trusted." All items are out of scope until multi-user workstation becomes a real concern.

### B1 — `security.md::CHK013` — `/tmp` world-readable awareness

**Question**: Is the scratch-root directory (`/tmp/021-bench/`) location explicit, with awareness that `/tmp` may be world-readable on multi-user systems?
**My recommendation**: defer. Single-operator workstation context; out of threat model.

**Your decision**: defer
**Your note**: Accept recommendation.

### B2 — `security.md::CHK014` — Scratch PII permissions weaker than corpus

**Question**: Are requirements present that prevent the four-run benchmark from copying PII-bearing PDFs into a scratch location with weaker permissions than the committed corpus?
**My recommendation**: defer. Same threat model.

**Your decision**: defer
**Your note**: Accept recommendation.

### B3 — `security.md::CHK015` — Cleanup discipline (`rm -rf /tmp/021-bench/`)

**Question**: Is the cleanup discipline explicit — does the spec or runbook say `rm -rf /tmp/021-bench/` after the demo/benchmark, or is post-run scratch retention indefinite?
**My recommendation**: close-with-edit (small). Add a one-line note to the runbook contract: "After the demo, the operator MAY `rm -rf /tmp/021-bench/` to clean up; scratch retention is operator choice."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### B4 — `security.md::CHK016` — Shared-workstation scratch permissions

**Question**: Are requirements present for shared-workstation scenarios — i.e., is the scratch directory permission-restricted to the running operator?
**My recommendation**: defer. Multi-user out of threat model.

**Your decision**: defer
**Your note**: Accept recommendation.

### B5 — `security.md::CHK029` — Explicit threat-model section

**Question**: Is the threat model for this feature implicit-but-explicit (workstation-local; no adversarial network reach; trust model = "operator who can read `/tmp` is trusted")?
**My recommendation**: close-with-edit. Add a one-paragraph "Threat Model" note to the spec Assumptions: "This feature assumes a single-operator workstation; multi-user workstation, network adversary, and host-Ollama compromise are out of scope."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### B6 — `security.md::CHK030` — Another user reads `/tmp/021-bench/` mid-run

**Question**: Are requirements present for the case "another user on the same workstation reads `/tmp/021-bench/` mid-run" — does the threat model permit this, or require restricted permissions?
**My recommendation**: defer. Multi-user out of threat model.

**Your decision**: defer
**Your note**: Accept recommendation.

### B7 — `security.md::CHK041` — Demo audience permission to see `run_summary`

**Question**: Is the demo audience's permission to see `run_summary` output addressed — are there cases where the audience should not see per-document fallback counts (e.g., external stakeholders)?
**My recommendation**: defer. Audience-permission is an operational/presentation concern, not a spec requirement.

**Your decision**: defer
**Your note**: Accept recommendation.

### B8 — `security.md::CHK042` — Cryptographic verification of Appendix A/B

**Question**: Are requirements present for cryptographic verification of the recorded Appendix A/B (e.g., signed commit, hash chain)?
**My recommendation**: defer. Out of scope; git history is the existing audit trail.

**Your decision**: defer
**Your note**: Accept recommendation.

### B9 — `security.md::CHK043` — MITM on localhost Ollama

**Question**: Is the readiness helper's response to a man-in-the-middle attack on localhost Ollama addressed?
**My recommendation**: defer. Localhost MITM is out of threat model.

**Your decision**: defer
**Your note**: Accept recommendation.

### B10 — `runbook.md::CHK039` — Multi-user Ollama-model contention

**Question**: Is the case "demo runbook executed against a workstation where another team member is running Ollama with a different model" addressed (multi-user contention)?
**My recommendation**: defer. Single-operator workstation context.

**Your decision**: defer
**Your note**: Accept recommendation.

### B11 — `gpu-readiness.md::CHK043` — Mid-demo Ollama unload

**Question**: Are requirements defined for the demo case where readiness passes initially but Ollama unloads the model mid-demo (re-check obligation)?
**My recommendation**: defer. Ollama doesn't unload mid-session under normal operation; this is an edge of edge cases.

**Your decision**: defer
**Your note**: Accept recommendation.

---

## Theme C — Future-feature handoff / Contract amendment / Audit infrastructure (~12 items)

Process-level questions about handoff to future features, contract versioning, automated audit. Most are genuine future improvements safe to defer.

### C1 — `contract.md::CHK056` — Separate contract for `configs/voter/ollama-gpu.yaml` shape

**Question**: Is a separate contract for the `configs/voter/ollama-gpu.yaml` file's content shape needed, or is its single key (`model_name`) trivially covered by feature 005's voter-config spec?
**My recommendation**: close. Covered by feature 005 voter-config schema; no separate contract needed.

**Your decision**: close
**Your note**: Accept recommendation.

### C2 — `contract.md::CHK057` — Separate contract for promotion-sync test

**Question**: Is a contract for the CPU-safe promotion-decision-sync test (`tests/contract_tests/test_promotion_decision_sync.py`) needed, or is the synchronization rule already adequately specified in `appendix-recording.md`?
**My recommendation**: close. Synchronization rule is specified in `contracts/appendix-recording.md`; test contract is a task-level detail.

**Your decision**: close
**Your note**: Accept recommendation.

### C3 — `contract.md::CHK058` — Contract versioning / amendment expectations

**Question**: Are versioning / amendment expectations for these contracts specified — i.e., if a contract changes after landing, how is the change recorded?
**My recommendation**: defer. Future ops/governance concern.

**Your decision**: defer
**Your note**: Accept recommendation.

### C4 — `contract.md::CHK059` — Contract for BLOCKED-marking across hardware causes

**Question**: Is a contract needed for the four converted GPU tests' BLOCKED-marking behavior across hardware-cause categories (kernel mismatch, paddle wheel mismatch, MIOpen state)?
**My recommendation**: defer. R-021.6 + helper exit-code taxonomy cover this; a separate contract is overkill.

**Your decision**: defer
**Your note**: Accept recommendation.

### C5 — `traceability.md::CHK045` — Cross-reference matrix document

**Question**: Is a cross-reference table (FR → US scenario → checklist item → R-021 decision) needed as a separate matrix document, or is the existing in-file cross-referencing sufficient?
**My recommendation**: defer. Existing cross-refs are sufficient for this feature; matrix would help across all features and is a future ops concern.

**Your decision**: defer
**Your note**: Accept recommendation.

### C6 — `traceability.md::CHK046` — Automated traceability verification

**Question**: Are requirements present for verifying traceability automatically (e.g., a CPU-safe test that parses spec.md FRs and asserts each is referenced by ≥ 1 checklist or contract)?
**My recommendation**: defer. Future feature; nice-to-have.

**Your decision**: defer
**Your note**: Accept recommendation.

### C7 — `traceability.md::CHK047` — feature 020 R-020.15 → US2 forward-chain

**Question**: Is the traceability handling for items deferred from feature 020 (R-020.15 → this feature's US2) explicit — does a future audit start at R-020.15 and follow the chain forward?
**My recommendation**: close. spec §US2 + research §R-021.8 reference R-020.15 explicitly; an auditor following the chain lands here.

**Your decision**: close
**Your note**: Accept recommendation.

### C8 — `traceability.md::CHK048` — Bidirectional links

**Question**: Are bidirectional links explicit — does the spec link forward to plan/research/contracts, and do plan/research/contracts link back to the spec?
**My recommendation**: defer. Most links are forward (spec → plan → research → contracts); back-links exist for FR refs but aren't exhaustive. Acceptable.

**Your decision**: defer
**Your note**: Accept recommendation.

### C9 — `clarifications.md::CHK030` — §Clarifications append-only convention

**Question**: Is the §Clarifications block stable — i.e., is there a written rule that further session decisions append (not overwrite) so historical resolution is auditable?
**My recommendation**: defer. Convention is implicit; future amendment can add an explicit rule.

**Your decision**: defer
**Your note**: Accept recommendation.

### C10 — `scope.md::CHK037` — Out-of-scope-encounter procedure

**Question**: Does the spec define what happens when implementation work surfaces an apparent need that crosses an Out-of-Scope line (defer to a future feature, not absorb)?
**My recommendation**: close-with-edit. Add a one-line note to spec Out of Scope: "If implementation work surfaces a genuine need that crosses these lines, the work is deferred to a future feature via /speckit.specify; this feature MUST NOT absorb the new behavior."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### C11 — `requirements.md::CHK008` — Archival of obsolete runbook content

**Question**: Are requirements defined for archival of replaced/obsolete runbook content when the GPU runbook supersedes a prior CPU-permissive runbook?
**My recommendation**: close. No prior CPU-permissive demo runbook exists at the canonical path; this feature creates the file fresh.

**Your decision**: close
**Your note**: Accept recommendation.

### C12 — `runbook.md::CHK040` — Abort-and-cleanup mid-demo

**Question**: Are requirements defined for an "abort and clean up" path — what does the operator do mid-demo to leave the workstation in a clean state?
**My recommendation**: close-with-edit (small). Add to runbook contract §"When Things Go Wrong": "Abort path: Ctrl+C interrupts the pipeline; `rm -rf /tmp/021-bench/` cleans up scratch; readiness state is unchanged."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

---

## Theme D — Edge cases / Robustness (~10 items)

Specific edge cases the spec doesn't enumerate but the design's deterministic semantics handle implicitly.

### D1 — `benchmark.md::CHK011` — Same source.pdf BYTES across lanes

**Question**: Is the symmetry requirement extended to identical input files (same `source.pdf` bytes) across lanes, or only to the document set list?
**My recommendation**: close-with-edit. Add to FR-013 or research.md §R-021.1: "The scratch-copy mirror procedure ensures identical source.pdf bytes across lanes — each scratch per-doc folder is copied from the same canonical corpus path."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### D2 — `benchmark.md::CHK047` — Unexpected suppressed-doc count

**Question**: Are requirements defined for the case where the candidate-lane suppressed-document count differs from the expected (e.g., a document the operator expected to be `sufficient` is `borderline` on this run)?
**My recommendation**: defer. The evidence gate is deterministic per feature 020; if a doc's classification changes, that's a feature-020 question.

**Your decision**: defer
**Your note**: Accept recommendation.

### D3 — `gpu-readiness.md::CHK033` — Composite verdict canonical recording medium

**Question**: Is the verdict's recording medium implied or explicit — i.e., is there a single canonical place where the composite PASS/FAIL is observable per run?
**My recommendation**: close-with-edit. Add to spec Key Entities §"GPU Readiness Verdict" entry: "Recording medium: the verdict is observable from (a) Paddle preflight stderr + (b) Ollama helper stdout JSON; Appendix A §1 environment fingerprint composes them. No single artifact carries the composite verdict."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### D4 — `gpu-readiness.md::CHK042` — Readiness gate idempotence

**Question**: Are requirements defined for the case where the same readiness gate is invoked twice in rapid succession (idempotence expectations)?
**My recommendation**: close. The helper is read-only and stateless per R-021.9; idempotence is implicit. (Mark ✓ without edit.)

**Your decision**: close
**Your note**: Accept recommendation.

### D5 — `determinism.md::CHK039` — FP rounding for jitter comparison

**Question**: Is the floating-point comparison surface for the jitter formula resilient to FP rounding (e.g., if `legacy_run2 = 0.842` but actual stored value is `0.8420000000000001`)?
**My recommendation**: close-with-edit. Add to research.md §R-021.2: "FP comparison tolerance: all jitter-formula comparisons round inputs to 3 decimals (per the recording precision) before applying the strict-greater-than rule. Two reviewers using the recorded 3-decimal values will agree on every `is_material` verdict."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### D6 — `quality-gate.md::CHK040` — Evaluator surface drift

**Question**: Is the case "evaluator surface changed between feature 020 landing and this feature's quality-gate run" addressed (evaluator version pin, reproducibility)?
**My recommendation**: defer. Cross-feature change is a feature-007 amendment concern; this feature uses what's on `main` at landing time.

**Your decision**: defer
**Your note**: Accept recommendation.

### D7 — `quality-gate.md::CHK041` — Missing `expected.json`

**Question**: Are requirements defined for what happens when the per-document pass count is undefined (e.g., a document's `expected.json` is missing)?
**My recommendation**: close-with-edit. Add to research.md or quality-gate contract: "If any benchmarked document lacks an `expected.json`, the FR-019 quality gate verdict is BLOCKED with named cause 'missing expected.json for <doc_id>'; skip-fallback remains opt-in (FR-027)."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### D8 — `promotion.md::CHK009` — No recorded verdict → implicit default

**Question**: Is the case "FR-019 has not been run / no recorded verdict" addressed — is the implicit default "stay opt-in", or is the spec ambiguous?
**My recommendation**: close-with-edit. Add a one-line note to FR-029: "If no FR-019 verdict has been recorded at the time a promotion decision is sought, the operational posture remains 'stay opt-in' by default (FR-027 applies to the absent verdict as if it were FAIL or BLOCKED)."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### D9 — `promotion.md::CHK038` — Different team views

**Question**: Is the case "different team members hold different views" addressed — is the team-decision required to be unanimous, majority, or single-owner?
**My recommendation**: defer. Team governance is out of spec scope.

**Your decision**: defer
**Your note**: Accept recommendation.

### D10 — `promotion.md::CHK039` — Flaky legacy-path test

**Question**: Is the case "promote-to-default chosen, but the explicit-off legacy path test is flaky" handled — does flakiness violate SC-009 "passes"?
**My recommendation**: close-with-edit. Add to T030 or SC-009: "The FR-028 legacy-path test MUST pass deterministically on every CPU CI run; a flaky test violates SC-009's 'passes' requirement and blocks promote-to-default landing."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

---

## Theme E — Documentation depth / Polish (~14 items)

Soft documentation polish; non-blocking.

### E1 — `requirements.md::CHK038` — Read-only audit path for runbook

**Question**: Are requirements present for the case where the demo runbook is consumed by a reviewer who never runs it (read-only audit path)?
**My recommendation**: defer. The runbook content is plain English readable by an auditor; explicit audit-mode requirements are nice-to-have.

**Your decision**: defer
**Your note**: Accept recommendation.

### E2 — `runbook.md::CHK023` — Operator skill floor

**Question**: Is the runbook required to assume a specific operator skill floor (e.g., comfortable with `git`, `python`, `curl`), or is the runbook self-contained even for that?
**My recommendation**: close-with-edit. Add a "Prerequisites — Operator skills" line to the runbook contract: "Assumes operator familiarity with `git`, Python venvs, and basic shell (`bash`/`zsh`). Anything beyond is explained inline."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### E3 — `runbook.md::CHK033` — Demo audience

**Question**: Is the audience for the demo defined (internal reviewer, external stakeholder, both)?
**My recommendation**: close-with-edit. Add a "Demo audience" line to the runbook contract: "Audience: internal pipeline engineers + reviewers; external stakeholders (compliance, legal) by invitation."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### E4 — `runbook.md::CHK035` — Demo duration bound

**Question**: Is the demo length / duration bounded — i.e., is the operator told the expected wall-time so a slow demo is recognizable as a finding?
**My recommendation**: close-with-edit. Add expected wall-time to the runbook contract Step 2: "Expected wall-time: ~30s readiness + ~60-120s per demo command on this workstation. A run > 5× expected is a finding."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### E5 — `performance.md::CHK004` — Performance-claim audience

**Question**: Is the audience of the performance claim explicit (the promotion-decision reviewer, not external stakeholders)?
**My recommendation**: close-with-edit. Add to performance.md or spec Notes: "Performance claim audience: the promotion-decision reviewer; the recorded numbers in Appendix A are NOT marketing latency claims."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### E6 — `performance.md::CHK030` — Workstation-stability assumptions

**Question**: Are workstation-stability assumptions explicit (e.g., no other process consuming GPU memory during the four-run sequence)?
**My recommendation**: close-with-edit. Add to spec Assumptions: "During the four-run sequence, the workstation has exclusive GPU access (no other process consuming `rocm-smi`-reported GPU memory beyond the running pipeline)."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### E7 — `performance.md::CHK033` — Same-environment rule

**Question**: Is the same-environment rule explicit (legacy and candidate lanes run in the same shell session, same workstation state, same Ollama placement)?
**My recommendation**: close-with-edit. Add to research.md §R-021.1 layout note: "Legacy and candidate lanes MUST run in the same shell session against the same workstation Ollama placement; cross-session comparison invalidates the jitter band."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### E8 — `security.md::CHK017` — feature 006 PII screening inheritance

**Question**: Is the labeling-guide PII screening (feature 006 lineage) preserved — does the spec implicitly trust that committed corpus already passed PII screening, and that the scratch copy doesn't reintroduce unscreened content?
**My recommendation**: close-with-edit. Add to spec Assumptions: "Committed corpus under `tests/stage1_vendor_identity/` has passed feature 006 PII screening; scratch copies preserve the same content, so no new PII exposure surface is introduced."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### E9 — `security.md::CHK025` — Runbook synthetic-example requirement

**Question**: Is the runbook required to NOT include sample output containing real vendor names, addresses, or other PII — only synthetic examples or document-ID references?
**My recommendation**: close-with-edit. Add to runbook contract §"Documentation discipline": "Runbook examples MUST use document IDs (e.g., `inv_001_easy`) and synthetic vendor strings, NEVER real vendor names or addresses extracted from any document."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### E10 — `dependencies.md::CHK033` — Verified/violated recording mechanism

**Question**: Is there a stated mechanism for a reviewer to record an Assumption as "verified" vs. "violated" against a candidate workstation (a sign-off line, a runbook checklist row)?
**My recommendation**: defer. Operational checklist surface for a future ops feature.

**Your decision**: defer
**Your note**: Accept recommendation.

### E11 — `dependencies.md::CHK034` — `paddleocr>=3.5,<4` pin in Assumptions

**Question**: Is the dependency on `paddleocr>=3.5,<4` (used by PPStructureV3 and the OCR-only lane both) named explicitly in Assumptions, or only inherited from features 014–019 Active Technologies?
**My recommendation**: close-with-edit (small). Add to spec Assumptions §1: "Inherited dependency pins: `paddleocr>=3.5,<4`, `paddlepaddle-dcu` (workstation optional), `pypdfium2>=4.30,<5`, `Pillow>=10.4,<11`, `numpy>=1.26,<3`, `httpx>=0.27,<1` per features 014–019 Active Technologies."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### E12 — `dependencies.md::CHK035` — `httpx>=0.27,<1` pin in Assumptions

**Question**: Is the dependency on `httpx>=0.27,<1` (used by feature 005 extractor; reachable by tests calling Ollama) named, or is it implicit from feature 005?
**My recommendation**: close-with-edit. Same edit as E11 covers this.

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### E13 — `contract.md::CHK046` — Step 2 demo command flag-list stale-text

**Question**: Is the Step 2 demo command's required flag set pinned (`--preprocess-strategy ppstructurev3@gpu` + `--voter-config configs/voter/ollama-gpu.yaml`), so a reviewer can assert no CPU profile slipped in?
**My recommendation**: close-with-edit. The checklist question's example flags are stale (pre-C1-C4 fix). Update the question text to reference the corrected flags: `--preprocess-profile ppstructurev3@gpu` + `--preprocess-strategy ocr-only-v1` + `--extract-profile ollama@gpu`.

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### E14 — `failure-handling.md::CHK020` — Closed list of named-cause categories

**Question**: Are the categories of acceptable named causes enumerated (hardware drift, ROCm/MIOpen state, Paddle wheel mismatch, Ollama unavailability, interpreter mismatch)?
**My recommendation**: close-with-edit. Add a closed list to FR-010 or research.md: "Acceptable named-cause categories: (a) ROCm/MIOpen runtime state (kernel mismatch, missing SDMA, etc.), (b) Paddle wheel mismatch, (c) Ollama unavailability or model not loaded, (d) interpreter mismatch (wrong venv), (e) workstation hardware drift. Any other cause must be added to this list via spec amendment."

**Your decision**: close-with-edit
**Your note**: Accept recommendation.

### E15 — `failure-handling.md::CHK027` — Regression-cause analysis required

**Question**: Is the requirement for a regression-cause analysis explicit, or only the regression description (delta and direction)?
**My recommendation**: defer. Analysis is a team activity; spec requires only the recording of magnitude/direction.

**Your decision**: defer
**Your note**: Accept recommendation.

---

## After you finish

Once you've populated **Your decision** for each item (or a subset — items left blank are treated as **defer**), ping me. I'll:

1. Read this file.
2. Apply each **close** → tick the source-checklist CHK as `[X]`.
3. Apply each **close-with-edit** → make the proposed amendment to spec/plan/research/contracts as described, then tick the CHK.
4. Apply each **defer** → tick the CHK with a one-line "deferred to future feature" annotation.
5. Leave **leave-open** items as `[ ]` (their default state).
6. Re-tally; if anything material changed in the spec, propose re-running `/speckit.analyze` for a clean verdict.
7. Commit the updates and resume `/speckit.implement` per your original intent.

If you want me to act on a single theme at a time (e.g., "process Theme E first since those are easy"), just say so.
