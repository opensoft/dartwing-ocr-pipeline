## Context

The active repository is `opensoft/ledgerlinc-model-ocr-pipeline`, and the local checkout lives under `/home/brett/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline`. The project now needs the active identity `dartwing-ocr-pipeline` while preserving the existing stage 1 OCR behavior, artifact contracts, and local validation flows.

The rename touches multiple layers: GitHub repository identity, SonarQube project key, Python import package, console scripts, Speckit worktree paths, devcontainer metadata, Docker Compose names, and operator documentation. Some historical artifacts also contain LedgerLinc references; those should not be mechanically rewritten when doing so would change archived design history or frozen contract identifiers.

## Goals / Non-Goals

**Goals:**

- Make Dartwing the active repository, package, CLI, workflow, container, and quality-tooling identity.
- Keep the OCR pipeline behavior and JSON artifact shapes unchanged.
- Make the local developer workflow work from a `dartwing-ocr-pipeline` checkout and `dartwing-ocr-pipeline-worktrees` worktree parent.
- Keep SonarQube analysis pointed at the new `opensoft_dartwing-ocr-pipeline` key.
- Leave historical logs and frozen schema IDs alone unless they are active operator guidance.

**Non-Goals:**

- No model, OCR, routing, extraction, or evaluation behavior changes.
- No JSON schema shape changes.
- No migration of historical Git commit text, old logs, or archived feature records.
- No compatibility bridge for old package/CLI/env names in this change.

## Decisions

1. **Rename the primary Python package to `dartwing_ocr`.**
   - Rationale: active imports and module invocations should match the new project identity.
   - Alternative considered: leave `ledgerlinc_ocr` as an internal package. Rejected because it leaves the most visible developer API on the old identity.

2. **Rename the distribution to `dartwing-ocr` and the repository to `dartwing-ocr-pipeline`.**
   - Rationale: the package is the importable OCR toolkit; the repository names the full pipeline project.
   - Alternative considered: use `dartwing-ocr-pipeline` as the package distribution. Rejected because the existing distribution was `ledgerlinc-ocr`, not `ledgerlinc-model-ocr-pipeline`.

3. **Use `DARTWING_*` for active environment variables.**
   - Rationale: env vars are operator-facing configuration and should not retain the old project name.
   - Alternative considered: support both `LEDGERLINC_*` and `DARTWING_*`. Rejected for this change to keep semantics crisp; compatibility aliases can be added separately if real consumers need them.

4. **Preserve frozen schema `$id` domains.**
   - Rationale: contract versions `v1.0.0` through `v1.2.0` are historical machine contracts. Renaming their `$id` values would be a contract amendment, not a repository rename.
   - Alternative considered: rewrite `ledgerlinc.local` to `dartwing.local` everywhere. Rejected because it would blur frozen-contract history with active project identity.

5. **Rename external services after local code/config is consistent.**
   - Rationale: GitHub redirects help with old remotes, but SonarQube scans and developer tooling need the local configuration to point at the new identity.

## Risks / Trade-offs

- Existing local scripts or shells using `ledgerlinc_ocr`, `ledgerlinc-*`, or `LEDGERLINC_*` will break → document the new names and add compatibility only if needed in a follow-up.
- Open Speckit worktrees under old absolute paths may be stale or prunable → prune stale worktree metadata and create new worktrees under `dartwing-ocr-pipeline-worktrees`.
- SonarQube binding can lag the GitHub rename → verify project lookup and run one manual scan after renaming.
- Contract schema IDs will still contain `ledgerlinc.local` → document this as historical/frozen contract identity, not active brand identity.

## Migration Plan

1. Apply repository file changes on a feature branch.
2. Run static import checks and the test suite.
3. Rename GitHub repository to `opensoft/dartwing-ocr-pipeline`.
4. Update local `origin` to `git@github.com:opensoft/dartwing-ocr-pipeline.git`.
5. Rename or update the SonarQube project key/name/binding to `opensoft_dartwing-ocr-pipeline`.
6. Move local checkout and worktree folders to Dartwing paths.
7. Re-run tests and Sonar analysis from the new path.
