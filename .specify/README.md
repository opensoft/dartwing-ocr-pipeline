# Speckit Workflow

This repository uses Speckit with Git worktrees for feature work.

## Default Model

- Keep the root checkout at `/home/brett/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline`
- Keep that root checkout on `main`
- Run `/speckit.specify ...` from the root checkout
- Speckit creates a new feature branch in a linked worktree under `../ledgerlinc-model-ocr-pipeline-worktrees/`
- Continue that feature from the returned `WORKTREE_PATH`, not from the root checkout

The current git extension config is:

- `checkout_mode: worktree`
- `base_branch: main`
- `worktree_root: ../ledgerlinc-model-ocr-pipeline-worktrees`

Config lives in `.specify/extensions/git/git-config.yml`.

## One Feature

Start from the root checkout:

```bash
cd /home/brett/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline
git switch main
```

Run Speckit specify from that root checkout:

```text
/speckit.specify <feature description>
```

Speckit will return a new branch name and a `WORKTREE_PATH`, for example:

```text
BRANCH_NAME=002-one-doc-cli
WORKTREE_PATH=/home/brett/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline-worktrees/002-one-doc-cli
```

Important: the new worktree is created on disk, but your current shell does **not** automatically `cd` into it.

Move into that worktree and continue the feature there:

```bash
cd /home/brett/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline-worktrees/002-one-doc-cli
```

Then run the rest of the flow from that worktree:

```text
/speckit.clarify
/speckit.plan
/speckit.tasks
/speckit.implement
```

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

Enable the shell helper in your current zsh session:

```bash
source /home/brett/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline/.specify/shell/ct.zsh
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
2. Session 2 works in `.../ledgerlinc-model-ocr-pipeline-worktrees/002-one-doc-cli`.
3. Session 3 works in `.../ledgerlinc-model-ocr-pipeline-worktrees/003-pdf-preprocess`.

To start another feature:

```bash
cd /home/brett/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline
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
git worktree remove /home/brett/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline-worktrees/002-one-doc-cli
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
