## Why

The OCR pipeline is moving from the LedgerLinc project identity to Dartwing, and the repository name is changing to `dartwing-ocr-pipeline`. The current codebase embeds the old identity in package names, CLI commands, workflow paths, SonarQube configuration, container names, and documentation, so a coordinated rename is needed to avoid split-brain tooling.

## What Changes

- Rename repository-facing identifiers from `ledgerlinc-model-ocr-pipeline` to `dartwing-ocr-pipeline`.
- **BREAKING**: Rename the primary Python import package from `ledgerlinc_ocr` to `dartwing_ocr`.
- **BREAKING**: Rename primary console scripts from `ledgerlinc-*` to `dartwing-*`.
- Rename the Python distribution from `ledgerlinc-ocr` to `dartwing-ocr`.
- Rename runtime/container/tooling identifiers and local workflow paths from LedgerLinc to Dartwing.
- Rename SonarQube project configuration from `opensoft_ledgerlinc-model-ocr-pipeline` to `opensoft_dartwing-ocr-pipeline`.
- Preserve historical contract schema IDs in frozen contract versions unless a future contract amendment explicitly changes them.
- Leave explicitly historical logs and archived feature text untouched when they are not active operator or runtime guidance.

## Capabilities

### New Capabilities
- `project-identity-rename`: Defines the active Dartwing repository, package, CLI, workflow, and quality-tooling identity.

### Modified Capabilities

## Impact

- Affected code: `src/`, tests, scripts, `pyproject.toml`, package-data paths, coverage settings.
- Affected developer workflows: README, AGENTS/CLAUDE context, Speckit worktree helpers, devcontainer metadata, Docker Compose container names, SonarCloud manual analysis docs.
- Affected external systems: GitHub repository name/remote and SonarQube project key/name/binding.
- Compatibility risk: downstream callers using `ledgerlinc_ocr`, `ledgerlinc-*`, or `LEDGERLINC_*` must migrate or rely on any temporary aliases added in a future compatibility-specific change.
