# Research: Harness Baseline Readiness

## Decision: Use Full Corpus Folder Name As `document_id`

**Rationale**: The committed `tests/stage1_vendor_identity/*/expected.json` files already use full folder names such as `inv_001_easy`, and `docs/stage1-vendor-identity/labeling-guide.md` states that `document_id` equals the folder name. Preserving that rule fixes the merged harness-controller path without migrating truth labels or changing schemas.

**Alternatives considered**:
- Numeric prefix only (`inv_001`): rejected because it conflicts with committed labels and the current labeling guide.
- Dual ID fields: rejected because it would require schema changes and blur the existing artifact contract.
- Temporary evaluator normalization: rejected because it would hide the mismatch rather than making the pipeline output contract authoritative.

## Decision: Fix ID Derivation In Pipeline Path Resolution

**Rationale**: The evaluator must keep invoking the public pipeline CLI. The source of the mismatch is the pipeline controller deriving `inv_001` from `inv_001_easy`; fixing `derive_document_id()` makes cold document, warm corpus, and harness preparation share one deterministic rule.

**Alternatives considered**:
- Override `--document-id` from the evaluator: rejected because it would create harness-specific behavior that operators would not see.
- Rewrite `expected.json` labels: rejected because committed labels are already consistent with the labeling guide.

## Decision: Convert Stage Callable Resolution Failures Into Structured Pipeline Failures

**Rationale**: Missing dependencies such as `PIL` can occur while resolving live adapter factories before the stage callable is invoked. The runner should catch resolution-time `ModuleNotFoundError`/`ImportError` and return the same `RunResult` failure shape as compute-time stage exceptions, allowing the CLI and evaluator to report a concise preparation error without a Python traceback.

**Alternatives considered**:
- Add dependency installation to `py-bench`: rejected because this feature is about readiness diagnostics, not environment provisioning.
- Move optional imports to global module load: rejected because stub-safe tests must not import optional OCR/model dependencies.
- Catch errors only in the evaluator: rejected because operators running the pipeline CLI directly would still see tracebacks.

## Decision: Keep Smoke Validation Stub-Safe

**Rationale**: The readiness gate should prove the merged evaluator-controller path works on committed corpus data without requiring OCR/model dependencies, network, GPU, or benchmark runtime setup. Real-profile smoke remains limited to failure-shape validation for missing dependencies.

**Alternatives considered**:
- Use `full-workstation` for the primary smoke: rejected because it is environment-dependent and can take too long for PR checks.
- Add benchmark/rerun helpers now: rejected because the committed corpus must first evaluate reliably through the merged harness-controller path.
