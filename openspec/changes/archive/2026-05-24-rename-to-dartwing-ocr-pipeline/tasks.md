## 1. Project Identity

- [x] 1.1 Rename the Python package tree from `src/ledgerlinc_ocr` to `src/dartwing_ocr` and update all active imports, module invocations, package-data references, and tests.
- [x] 1.2 Update `pyproject.toml`, coverage configuration, scripts, and console entry points to the `dartwing_ocr` package and `dartwing-*` command names.
- [x] 1.3 Update operator-owned environment-variable names from `LEDGERLINC_*` to `DARTWING_*` in code, tests, and active documentation.

## 2. Repository And Workflow Tooling

- [x] 2.1 Update maintained repository slug references to `dartwing-ocr-pipeline` in README, agent guidance, GitHub settings documentation, and workflow docs.
- [x] 2.2 Update Speckit worktree configuration and helper scripts to use `dartwing-ocr-pipeline-worktrees` and Dartwing helper names.
- [x] 2.3 Update devcontainer and Docker Compose metadata/container names to Dartwing.

## 3. Quality Tooling

- [x] 3.1 Update SonarQube project key and manual analysis defaults to `opensoft_dartwing-ocr-pipeline` and Dartwing config paths.
- [x] 3.2 Verify frozen contract schema IDs remain unchanged and update tests only if they reference active project identity rather than frozen contract identity.

## 4. External Rename And Validation

- [x] 4.1 Run static scans and automated tests for the local rename.
- [x] 4.2 Rename GitHub repository and update local `origin` to `git@github.com:opensoft/dartwing-ocr-pipeline.git`.
- [x] 4.3 Rename or rebind the SonarQube project to `opensoft_dartwing-ocr-pipeline`.
- [x] 4.4 Move the local checkout/worktree folders to Dartwing paths and prune stale worktree metadata.

Validation note: rename-focused validation passes from `/home/brett/projects/dartwing/dartwing-ocr-pipeline`; the broader suite still has unrelated environment/runtime and feature-drift failures outside this rename.
