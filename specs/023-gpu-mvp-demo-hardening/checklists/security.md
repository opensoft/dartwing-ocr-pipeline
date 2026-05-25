# Security Requirements Quality Checklist: GPU MVP Demo Hardening

**Purpose**: Release-gate audit of security-related requirements quality. The feature is a local CLI on a workstation; the threat surface is small but real (operator-supplied paths, model names rendered into stderr, partial artifact deletion).
**Created**: 2026-05-24
**Feature**: [spec.md](../spec.md)

## Threat Model & Trust Boundaries

- [ ] CHK001 Is the threat model documented — i.e., the demo command runs in a single-user trusted workstation context, with no untrusted network input? [Completeness, Gap]
- [ ] CHK002 Are the trust boundaries enumerated (operator input → CLI args; local filesystem → per-doc folder; localhost HTTP → host Ollama; local Python interpreter → Paddle ROCm)? [Completeness, Gap]
- [ ] CHK003 Are inputs that cross a trust boundary identified — specifically `--voter-config <path>`, `--document-folder <path>`, the active voter config's contents, and the `/api/ps` response — and are validation rules required for each? [Coverage, Gap]

## Path-Traversal & Filesystem Safety

- [ ] CHK004 Are requirements specified for validating `--document-folder <path>` to prevent the eager-delete from operating outside the intended per-doc folder (e.g., `--document-folder /` deleting `/preprocess_output.json` at the filesystem root)? [Coverage — Exception, Gap]
- [ ] CHK005 Are requirements specified for resolving symlinks in `--document-folder` (follow vs. reject) so the deletion scope cannot be redirected via a malicious symlink? [Coverage, Gap]
- [ ] CHK006 Are requirements specified for the deletion safety of the four canonical artifacts (e.g., only delete a path whose basename matches one of the four canonical filenames, never delete arbitrary file contents)? [Completeness, Spec §FR-017, §SC-010]
- [ ] CHK007 Is the requirement to preserve operator-owned files (`source.pdf`, `expected.json`, `notes.md`, `semantic_table_truth.json`) enforceable from a code audit (i.e., the spec names exactly which paths are touched, not "everything except…")? [Clarity, Spec §SC-010]
- [ ] CHK008 Are requirements specified for `--voter-config <path>` validation (e.g., the file must be a regular file readable by the operator, not a special file or device)? [Coverage, Gap]

## Output Sanitization

- [ ] CHK009 Are requirements specified for sanitizing model names, voter-config paths, and `/api/ps` response excerpts before they appear in stderr diagnostics, to prevent log injection (newlines, ANSI escapes) that could confuse downstream parsers? [Coverage, Gap]
- [ ] CHK010 Are requirements specified for sanitizing the same data before it appears in the stdout `DemoRunReport` JSON — e.g., escaping control characters that would break the single-line JSON contract? [Completeness, Spec §FR-019]
- [ ] CHK011 Is the requirement that stdout contains exactly one JSON line (no second line, no trailing data) auditable against potentially-malicious values in any string field? [Clarity, Spec §FR-019]

## Sensitive Data in the Report

- [ ] CHK012 Is it specified whether the interpreter path, voter-config path, model name, and `/api/ps` excerpt are considered sensitive (e.g., usernames in `~/...` paths) and whether they should be redacted? [Coverage, Gap]
- [ ] CHK013 Is the diagnostic context for any readiness failure required to redact or truncate large `/api/ps` excerpts so an unintended payload does not appear in operator logs/screenshots? [Completeness, Gap]
- [ ] CHK014 Are requirements specified for whether the demo report is safe to paste into a public issue tracker (i.e., contains no operator-identifying information), or whether the operator must redact it? [Coverage, Gap]

## PII in Source Documents

- [ ] CHK015 Is it specified that `source.pdf` may contain PII from real invoices and that the demo command must not log document content (OCR text, vendor names) to stderr beyond what is already in the four canonical artifacts? [Coverage, Gap]
- [ ] CHK016 Are requirements specified for whether `phase_timings` or `stalled_phase` diagnostics may include OCR'd content (they should not), to keep stderr free of PII? [Coverage, Gap]
- [ ] CHK017 Is the runbook required to instruct operators not to share `DemoRunReport` output containing real-invoice fixtures externally? [Coverage, Gap]

## Authentication & Authorization

- [ ] CHK018 Is the assumption that host Ollama on `localhost:11434` is unauthenticated explicitly stated as a workstation-only constraint, ruling out demo deployment on multi-user or networked hosts? [Completeness, Spec §Assumptions]
- [ ] CHK019 Are requirements specified for the case where `OLLAMA_BASE_URL` points to a non-localhost address — should readiness refuse (since the demo is workstation-only) or proceed silently? [Coverage — Edge Case, Gap]

## Supply-Chain & Runtime Integrity

- [ ] CHK020 Are requirements specified for verifying that the running Paddle wheel is the intended ROCm build (FR-002 Paddle ROCm preflight handles the device check, but is a wheel-identity check required)? [Coverage, Gap]
- [ ] CHK021 Is the requirement to fail at the Paddle preflight stage (Edge Cases) explicitly enforceable on a stale-or-uninstalled wheel rather than silently degrading? [Clarity, Spec §Edge Cases]

## CPU Fallback as a Security/Integrity Concern

- [ ] CHK022 Is silent CPU fallback explicitly classified as an integrity bug (the demo would otherwise produce results from an untested code path) rather than a performance bug? [Clarity, Spec §SC-004/FR-012]
- [ ] CHK023 Is post-run device interrogation (FR-012) required to be tamper-evident — e.g., the same readiness check infrastructure is reused for the post-run check, so a single bypass cannot defeat both? [Completeness, Spec §FR-012]

## Primary / Alternate / Exception / Recovery / Non-Functional Coverage

- [ ] CHK024 Are security requirements defined for the **primary** flow (all inputs valid; nothing to attack)? [Coverage — Primary, Gap]
- [ ] CHK025 Are security requirements defined for **alternate** flows (operator-supplied `--document-folder`, `--voter-config` paths)? [Coverage — Alternate, Gap]
- [ ] CHK026 Are security requirements defined for **exception** flows (malformed `/api/ps` JSON, model name with control characters, voter config with path-injection attempts)? [Coverage — Exception, Gap]
- [ ] CHK027 Are security **recovery** requirements defined (e.g., refuse to delete on path-validation failure; do not partially delete then abort)? [Coverage — Recovery, Gap]
- [ ] CHK028 Are security **non-functional** requirements specified (no PII in logs, no credentials in the report)? [Coverage — Non-Functional, Gap]

## Ambiguities & Conflicts

- [ ] CHK029 Is the security implication of FR-017's "eager delete at run start" reconciled with the security implication of `--document-folder <path>` allowing operator-chosen targets? Specifically: is there a guard against `--document-folder /` deleting filesystem-root files? [Conflict, Spec §FR-017/FR-027]
- [ ] CHK030 Is the spec explicit that this feature does NOT introduce any new credential or secret-storage surface (no API keys, no auth tokens), so the security review can be scoped accordingly? [Clarity, Gap]


---

**Plan coverage verification (2026-05-25):** see [plan-coverage.md](./plan-coverage.md) for the cross-reference of this checklist's items against `plan.md` / `research.md` / `data-model.md` / `contracts/` / `quickstart.md`.
