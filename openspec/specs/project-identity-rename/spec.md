# project-identity-rename Specification

## Purpose

Records the coordinated rename of the OCR pipeline's project identity from LedgerLinc to Dartwing across the repository slug, the primary Python package (`ledgerlinc_ocr` → `dartwing_ocr`), console scripts (`ledgerlinc-*` → `dartwing-*`), the SonarQube project key, and runtime/container/tooling identifiers. Historical contract schema `$id`s in frozen contract versions are preserved as-is; only active operator and runtime guidance is rewritten.
## Requirements
### Requirement: Active Repository Identity
The repository SHALL use `dartwing-ocr-pipeline` as the active repository slug in maintained configuration, workflow documentation, and external-service examples.

#### Scenario: GitHub remote documentation uses Dartwing slug
- **WHEN** a maintainer follows repository settings or remote-update instructions
- **THEN** the referenced GitHub repository is `opensoft/dartwing-ocr-pipeline`

### Requirement: Active Python Package Identity
The Python source package SHALL use `dartwing_ocr` as the active import and module execution namespace.

#### Scenario: Module execution uses Dartwing package
- **WHEN** a developer invokes a pipeline module from the command line
- **THEN** the command uses `python -m dartwing_ocr.<module>` rather than `python -m ledgerlinc_ocr.<module>`

### Requirement: Active Console Script Identity
The installable console scripts SHALL use the `dartwing-` prefix for active command names.

#### Scenario: Installed preprocessing command uses Dartwing prefix
- **WHEN** the package is installed from `pyproject.toml`
- **THEN** the preprocessing entry point is exposed as `dartwing-preprocess`

### Requirement: Active Operator Environment Identity
Operator-facing environment variables owned by this project SHALL use the `DARTWING_` prefix.

#### Scenario: GPU warmup opt-in uses Dartwing prefix
- **WHEN** an operator enables GPU warmup through the environment
- **THEN** the active variable is `DARTWING_GPU_WARMUP`

### Requirement: Active Workflow Paths
Maintained local workflow instructions SHALL use `/home/brett/projects/dartwing/dartwing-ocr-pipeline` for the root checkout and `dartwing-ocr-pipeline-worktrees` for Speckit worktrees.

#### Scenario: Speckit creates a new worktree
- **WHEN** the Speckit git extension creates a feature worktree
- **THEN** the configured worktree root is `../dartwing-ocr-pipeline-worktrees`

### Requirement: Active Quality Tooling Identity
SonarQube configuration SHALL use `opensoft_dartwing-ocr-pipeline` as the project key and `dartwing-ocr-pipeline` as the project display name when referenced.

#### Scenario: Manual Sonar analysis runs
- **WHEN** `scripts/sonarcloud-manual.sh` invokes `sonar-scanner`
- **THEN** the scanner reads a `sonar.projectKey` of `opensoft_dartwing-ocr-pipeline`

### Requirement: Frozen Contract IDs Remain Historical
Frozen JSON Schema `$id` values in existing contract versions SHALL remain unchanged unless a separate contract amendment explicitly changes them.

#### Scenario: v1.2.0 schema IDs are validated
- **WHEN** contract tests inspect existing v1.2.0 `$id` values
- **THEN** the historical `$id` values remain valid for that contract version

