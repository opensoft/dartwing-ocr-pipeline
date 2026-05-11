# Engine-Coordination Checklist: OCR-Only Fast Lane For Vendor Identity

**Purpose**: Validate that requirements covering the dual-singleton engine pattern (PPStructureV3 + PaddleOCR coexisting in one process), the `--gpu-warmup` binding rule (warm only the strategy-implied engine), the engine lifecycle under OCR-only selection, and the cold-start cost accounting on fallback are complete, clear, and consistent. This is a release-gate checklist focused on the slice-specific engine-coordination dimension Clarifications Q3 introduced.
**Created**: 2026-05-11
**Feature**: [spec.md](../spec.md)

## Dual-Singleton Engine Pattern (R-019.10 / I-019.2)

- [x] CHK001 - Is the dual-singleton pattern explicit (PPStructureV3 `_ENGINE` in `ocr.py` AND PaddleOCR `_OCR_ENGINE` in `ocr_only.py` coexist independently in one process)? [Completeness, R-019.10, I-019.2]
- [x] CHK002 - Is the "each engine constructed at most once per process *when invoked*" rule applied to BOTH engines individually (not just PPStructureV3)? [Clarity, R-019.10, I-019.2, Spec §FR-022]
- [x] CHK003 - Is the FR-022 explicit exception "PPStructureV3 MAY remain unconstructed under `preprocess_strategy_id = ocr-only-v1`" reasserted alongside the symmetric exception "PaddleOCR `_OCR_ENGINE` MAY remain unconstructed under `preprocess_strategy_id = ppstructurev3`"? [Completeness, Spec §FR-022, R-019.10]
- [x] CHK004 - Is the rule "an OCR-only run with ≥1 fallback constructs both engines (each exactly once)" explicit? [Clarity, R-019.10]
- [x] CHK005 - Is the single-device-per-process guard (feature 015 FR-006) applied per-engine (each engine records its `_*_DEVICE` on first construction; `RuntimeError` on subsequent different-device request)? [Coverage, Spec §FR-022, I-019.2]
- [x] CHK006 - Is the rule "both engines bind to the same `gpu:0` device when GPU is selected" explicit so the single-device-per-process guard is not accidentally split across engines? [Consistency, Spec §FR-022, I-019.2]

## Warmup Binding Rule (Clarifications Q3 / R-019.16 / I-019.16)

- [x] CHK007 - Is the warmup binding rule "the `--gpu-warmup` pass binds **only** the engine implied by the selected `preprocess_strategy_id`" explicit and stated in spec.md (FR-022 / Edge Cases / Clarifications Q3) AND in `research.md` R-019.16 AND in `contracts/module-invariants.md` I-019.16? [Consistency, Spec §FR-022, R-019.16, I-019.16]
- [x] CHK008 - Is the mapping `preprocess_strategy_id → engine warmed at `--gpu-warmup`` explicit for all 4 closed-vocabulary values (`ppstructurev3` ⇒ PPStructureV3; `ocr-only-v1` ⇒ PaddleOCR; `cpu-default` / `stub-default` ⇒ profile-defined per warn-and-proceed)? [Completeness, R-019.16, I-019.16]
- [x] CHK009 - Is the prohibition "warming both engines on `ocr-only-v1`" explicit (the unconstructed engine MUST remain `None`)? [Clarity, I-019.16]
- [x] CHK010 - Is the prohibition "warming PPStructureV3 on `ocr-only-v1`" explicit (would violate FR-002 by invoking layout pre-emptively)? [Clarity, FR-002, I-019.16]
- [x] CHK011 - Is the prohibition "skipping warmup entirely on `ocr-only-v1`" explicit (would regress feature 016's warmup benefits on the OCR-only path itself)? [Coverage, I-019.16]
- [x] CHK012 - Is the rejected alternative "eager-then-lazy hybrid (warm OCR-only eagerly, warm PPStructureV3 just-in-time on first fallback)" documented in research.md so a reviewer can find the rationale for the rejection? [Traceability, R-019.16]

## `phase_timings.warmup` Semantics Under Q3

- [x] CHK013 - Is the rule "`phase_timings.warmup` measures the single warmed engine's warmup cost only" explicit (not the sum across both engines; not zero-padded for the unconstructed engine)? [Clarity, R-019.16, I-019.16]
- [x] CHK014 - Is the rule "`phase_timings.warmup` is unchanged in shape from feature 016 (single scalar key)" explicit so this feature does not split it into per-engine sub-keys? [Completeness, Spec §Edge Cases, FR-022]
- [x] CHK015 - Is the consistency rule "`phase_timings.warmup` value reflects PaddleOCR warmup time on `ocr-only-v1`; PPStructureV3 warmup time on `ppstructurev3`" stated so operators can interpret the value? [Clarity, R-019.16]
- [x] CHK016 - Is the rule "warmup credit is not transferred across engines" stated alongside the cold-start-cost accounting rule (R-019.15) so reviewers see both halves of the story together? [Consistency, Spec §FR-022, Edge Cases, R-019.15, R-019.16]

## Cold-Start Cost Accounting on Fallback (R-019.15 / R-019.16)

- [x] CHK017 - Is the rule "PPStructureV3 cold-start (construction + first-predict) cost on a fallback document is included in that document's `phase_timings.per_page_inference` and `phase_timings.rasterization`" explicit (per R-019.15's combined-cost rule)? [Completeness, Spec §FR-022, Edge Cases, R-019.15]
- [x] CHK018 - Is the rule "the PPStructureV3 cold-start cost is NOT folded back into `phase_timings.warmup` retroactively" explicit so a fallback-document run doesn't have its warmup line silently mutated? [Clarity, I-019.11, R-019.16]
- [x] CHK019 - Is the rule "the cold-start cost on the FIRST fallback document is higher than on subsequent fallback documents (only the first triggers construction)" explicit, or is the deferral to plan explicit? [Gap, R-019.10]
- [x] CHK020 - Is the consequence "a benchmark that times the first vs. subsequent fallback documents will see uneven per-document timings on OCR-only runs with fallback" documented so the benchmark interpretation is not surprised? [Gap, FR-015, R-019.15]

## Engine Lifecycle Discipline

- [x] CHK021 - Is the rule "an `ocr-only-v1` warmup run that completes successfully leaves `_ENGINE = None` and `_OCR_ENGINE != None` post-warmup" explicit so post-warmup engine state is auditable? [Coverage, I-019.16, R-019.10]
- [x] CHK022 - Is the rule "a `ppstructurev3` warmup run that completes successfully leaves `_ENGINE != None` and `_OCR_ENGINE = None` post-warmup" explicit (symmetric statement)? [Coverage, I-019.16, R-019.10]
- [x] CHK023 - Is the rule "an `ocr-only-v1` run with ≥1 fallback transitions `_ENGINE` from `None` to constructed mid-run (specifically, just before the first fallback document's predict)" explicit, or is the construction point left to plan? [Gap, R-019.10]
- [x] CHK024 - Is the rule "both engines persist for the lifetime of the process once constructed (no teardown between documents)" explicit so corpus runs reuse both engines correctly? [Coverage, R-019.10, FR-022]
- [x] CHK025 - Is the rule "the existing CPU-import-safe discipline applies to `ocr_only.py` at module-load time (no Paddle import until first predict)" explicit and consistent with feature 014/015/016/017/018 precedent? [Consistency, I-019.10, FR-014]

## CLI-Surface Coverage

- [x] CHK026 - Is the orthogonality of `--gpu-warmup` with `--preprocess-strategy` documented in `contracts/cli-contract.md` §6 with the resolved Q3 behavior (not a `[DEFERRED]` marker)? [Completeness, contracts/cli-contract.md §6, Clarifications Q3]
- [x] CHK027 - Is the behavior matrix coverage explicit for the 4 combinations of `--gpu-warmup` × `--preprocess-strategy` (set/unset × `ppstructurev3`/`ocr-only-v1`)? [Coverage, contracts/cli-contract.md §6]
- [x] CHK028 - Is the rule "on CPU/stub profiles, `--gpu-warmup` and `--preprocess-strategy` BOTH follow the warn-and-proceed pattern independently" explicit so both flags can warn separately if both are set? [Coverage, Spec §FR-013, FR-014]

## Warmup-Failure Coverage Under Q3

- [x] CHK029 - Is the `WarmupError` contract carried forward unchanged for the OCR-only engine (same exception class, same `cause_class` taxonomy, exit code 15 from feature 016)? [Consistency, Spec §FR-022, R-019.16]
- [x] CHK030 - Is the rule "an OCR-only warmup failure (PaddleOCR cannot bind GPU) does NOT fall through to PPStructureV3 warmup" explicit so the user gets a clear failure rather than a silent engine swap? [Coverage, Spec §FR-022, R-019.16]
- [x] CHK031 - Is the rule "the FR-016 quality gate is unreachable on a run that failed warmup" implicit-from-fail-fast (exit before any document processed) or explicit? [Coverage, Spec §FR-022, FR-016]

## Cross-Reference Consistency

- [x] CHK032 - Are the Q3 resolution references consistent across spec.md (Clarifications + Edge Cases + FR-022), research.md (R-019.16), `contracts/cli-contract.md` §6, and `contracts/module-invariants.md` I-019.16 — all naming the same rule with the same outcomes? [Consistency, Clarifications Q3]
- [x] CHK033 - Is the relationship to feature 016 FR-001..FR-020 explicit (mechanics unchanged) AND the new binding rule explicit (additive) so a reviewer can distinguish "what feature 016 still owns" from "what feature 019 adds"? [Traceability, Spec §FR-022, Clarifications Q3]
- [x] CHK034 - Is the relationship between the dual-singleton pattern (R-019.10 / I-019.2) and the warmup-binding rule (R-019.16 / I-019.16) explicit (the binding rule is meaningful only because dual-singleton makes "which engine to bind" a real choice)? [Consistency, R-019.10, R-019.16]

## Notes

- Items test the spec's text describing engine coordination — not that the code under test coordinates engines correctly.
- This checklist exists because Clarifications Session 2026-05-11 Q3 elevated the warmup binding rule from a `[DEFERRED to /speckit.tasks]` marker to a normative invariant (I-019.16); the engine-coordination dimension is now substantial enough to warrant its own release-gate checklist alongside the seven generated earlier.
- CHK017–CHK020 (cold-start cost accounting on fallback) are the highest-risk subset; benchmark interpretation depends on operators understanding that fallback documents do NOT get equivalent warmup treatment to non-fallback documents.
