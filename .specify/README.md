# OpenSpec and Speckit Workflow

This repository uses OpenSpec for change governance and Speckit with Git
worktrees for implementation work.

## OpenSpec Role

Use OpenSpec before implementation when a change affects project boundaries:

- stage 1 artifact schemas or folder contracts
- runtime/container/model orchestration
- consensus, routing, review, or escalation policy
- Jetson/edge deployment constraints
- the development workflow itself

OpenSpec captures intent, scope, and design decisions. Speckit remains the
implementation system. Do not duplicate task lists between OpenSpec and Speckit:
an OpenSpec change should hand off to exactly one Speckit feature under
`specs/NNN-*` for implementation.

Run OpenSpec from the bench/workbench container (`py-bench`), where `openspec`
is on `PATH`. Do not add OpenSpec to the lightweight Dartwing project
container; that container remains focused on the pipeline runtime and local
validation path.

Skip OpenSpec for small implementation-only fixes where an existing Speckit
artifact already defines the behavior.

## Default Model

- Keep the root checkout at `/home/brett/projects/dartwing/dartwing-ocr-pipeline`
- Keep that root checkout on `main`
- Run `/speckit.specify ...` from the root checkout
- Speckit creates a new feature branch in a linked worktree under `../ocr-pipeline-worktrees/`
- Continue that feature from the returned `WORKTREE_PATH`, not from the root checkout

The current git extension config is:

- `checkout_mode: worktree`
- `base_branch: main`
- `worktree_root: ../ocr-pipeline-worktrees`

Config lives in `.specify/extensions/git/git-config.yml`.

## One Feature

Start from the root checkout:

```bash
cd /home/brett/projects/dartwing/dartwing-ocr-pipeline
git switch main
```

Run Speckit specify from that root checkout:

```text
/speckit.specify <feature description>
```

Speckit will return a new branch name and a `WORKTREE_PATH`, for example:

```text
BRANCH_NAME=002-one-doc-cli
WORKTREE_PATH=/home/brett/projects/dartwing/ocr-pipeline-worktrees/002-one-doc-cli
```

Important: the new worktree is created on disk, but your current shell does **not** automatically `cd` into it.

Move into that worktree and continue the feature there:

```bash
cd /home/brett/projects/dartwing/ocr-pipeline-worktrees/002-one-doc-cli
```

Then run the rest of the flow from that worktree. The core path is:

```text
/speckit.clarify
/speckit.plan
/speckit.tasks
/speckit.implement
```

### All Speckit commands (required + optional)

**Project-wide (run from root checkout, usually once):**

- `/speckit.constitution` — create or update the project constitution and keep dependent templates in sync. Lives at `.specify/memory/constitution.md`.

**Per-feature core flow (run from the feature worktree):**

- `/speckit.specify <description>` — create the feature spec and (via the git extension) the linked worktree. **Required, run from root checkout on `main`.**
- `/speckit.clarify` — ask clarifying questions and update `spec.md`. *Optional but recommended before `plan`.*
- `/speckit.plan` — generate `plan.md` and design artifacts (data model, research, quickstart, contracts). **Required before tasks.**
- `/speckit.tasks` — generate dependency-ordered `tasks.md` from the plan. **Required before implement.**
- `/speckit.analyze` — non-destructive cross-artifact consistency check across `spec.md`, `plan.md`, `tasks.md`. *Optional, run after `tasks`.*
- `/speckit.implement` — execute `tasks.md` end-to-end with verification. **Terminal step of the core flow.**

**Per-feature optional add-ons (run from the feature worktree, any time after `specify`):**

- `/speckit.checklist <topic>` — generate a custom checklist for the feature (security, a11y, rollout, etc.). Writes under `specs/<feature>/checklists/`. Can be re-run with different topics.
- `/speckit.taskstoissues` — convert `tasks.md` into dependency-ordered GitHub issues. *Optional, run after `tasks` if you want issue tracking.*

**Git extension helpers (mostly invoked automatically, but available directly):**

- `/speckit.git.feature` — the worktree/branch creator that `/speckit.specify` calls under the hood. Rarely invoked manually.
- `/speckit.git.initialize` — one-time git extension bootstrap for a repo.
- `/speckit.git.validate` — verify the current branch follows feature-branch naming.
- `/speckit.git.commit` — auto-commit the changes a Speckit command just produced.
- `/speckit.git.remote` — detect the GitHub remote URL (used by `taskstoissues`).

**Typical full flow for a new feature:**

```text
/speckit.specify <description>   # from root checkout
cd <WORKTREE_PATH>                # or run /ct, then ct
/speckit.clarify                  # optional
/speckit.plan
/speckit.checklist <topic>        # optional, repeatable
/speckit.tasks
/speckit.analyze                  # optional
/speckit.taskstoissues            # optional
/speckit.implement
```

**After implementation:** open a PR, then run an agent-team review against that
PR. Treat high-severity architecture or logic findings as blockers: fix them on
the branch, commit the changes, and run review again before merge.

## `/ct`, `/ctp`, `ct`, `cta`, `ctc`, `ctg`, And `cts`

After `/speckit.specify`, there are two shortcuts:

- `/ct`
  - asks the agent for the latest Speckit worktree jump target
  - returns the resolved worktree path and the exact `cd` command
  - does not change your current shell directory automatically
- `/ctp`
  - asks the agent to show the latest Speckit worktree path and metadata
  - returns `WORKTREE_PATH`, `BRANCH_NAME`, `BASE_BRANCH`, and source details
- `ct`
  - shell helper that changes into the latest Speckit worktree without typing the full path
  - requires sourcing `.specify/shell/ct.zsh` first
- `cta`
  - shows the worktree list, lets you choose one, then starts Claude in that worktree
- `ctc`
  - shows the worktree list, lets you choose one, then starts Codex in that worktree
- `ctg`
  - shows the worktree list, lets you choose one, then starts Gemini in that worktree
- `cts`
  - shows the worktree list first
  - then shows an AI CLI chooser:
    - `1` Anthropic
    - `2` Codex
    - `3` Gemini
  - pressing Enter picks the newest worktree and Anthropic by default

The shell helpers (`ct`, `ctp`, `cta`, `ctc`, `ctg`, `cts`, `ctlist`) are loaded automatically in every new shell via `/usr/local/share/ct/ct-functions.zsh`, which is sourced from `~/.zshrc`. No per-shell setup is required.

Each command detects the current repo at call time via `git rev-parse`. If you run one outside a git repo or inside a repo without a `.specify/` directory, it errors with a clear message.

**Fallback for environments without the container-level helper** (e.g. a plain WSL shell outside the devcontainer): source the in-repo file directly.

```bash
source "$(git rev-parse --show-toplevel)/.specify/shell/worktrees.sh"
```

Then your flow can be:

```text
/speckit.specify <feature description>
/ct
```

If you want the detailed view instead:

```text
/ctp
```

To actually jump into the latest worktree from a shell:

```bash
ct
```

To pick a worktree and start Claude directly:

```bash
cta
```

To pick a worktree and start Codex directly:

```bash
ctc
```

To pick a worktree first and then choose which AI CLI to start:

```bash
cts
```

## Multiple Features In Parallel

Use one CLI session per active feature worktree.

Example:

1. Session 1 stays in the root checkout on `main` and is used only to launch new work.
2. Session 2 works in `.../ocr-pipeline-worktrees/002-one-doc-cli`.
3. Session 3 works in `.../ocr-pipeline-worktrees/003-pdf-preprocess`.

To start another feature:

```bash
cd /home/brett/projects/dartwing/dartwing-ocr-pipeline
git switch main
```

Then run `/speckit.specify ...` again and move into the new returned `WORKTREE_PATH`.

## Important Rules

- Do not do feature implementation work in the root checkout.
- Do not switch the root checkout onto an active feature branch.
- Do not continue a feature in the root checkout after Speckit creates its worktree.
- If a feature already has a worktree, continue using that worktree.
- The same Git branch cannot be checked out in two worktrees at once.

## Cleanup

List active worktrees:

```bash
git worktree list
```

Remove a finished worktree:

```bash
git worktree remove /home/brett/projects/dartwing/ocr-pipeline-worktrees/002-one-doc-cli
```

Delete the local feature branch after merge or after you no longer need it:

```bash
git branch -d 002-one-doc-cli
```

## Troubleshooting

If Speckit returns a `WORKTREE_PATH`, always treat that path as the repo root for the rest of that feature.

If a worktree path already exists or a branch is already checked out elsewhere, either:

- continue using the existing worktree, or
- remove the stale worktree before retrying

Extension details are documented in:

- `.specify/extensions/git/README.md`
- `.specify/extensions/git/commands/speckit.git.feature.md`
