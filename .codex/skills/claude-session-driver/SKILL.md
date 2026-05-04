---
name: claude-session-driver
description: Drive an existing Claude Code CLI session running in tmux or another persistent terminal. Use when the user wants Codex to operate Claude step-by-step, send commands, answer Claude's follow-up questions, and steer Speckit or similar workflows through that session.
---

# Claude Session Driver

Use this skill when Codex is acting as the operator for a live Claude session rather than doing the work locally.

The job is not just "send text to tmux." The job is to:

- identify the session state correctly
- send the right kind of input for that state
- avoid corrupting an in-flight slash command
- keep the user informed about what Claude is doing
- answer Claude's questions with scoped operator prompts

Keep this workflow disciplined. Small input mistakes can derail the other session.

## Core Rules

1. **Target the exact session and pane**
   - Confirm the container, tmux session, window, and pane before sending anything.
   - Capture recent pane output first so you know what Claude is currently doing.

2. **Detect the current input mode before typing**
   - Treat the pane as being in one of these modes:
     - shell prompt
     - normal Claude prompt
     - slash-command menu/list
     - slash-command follow-up question
     - interactive selector/menu
     - long-running work / thinking
   - Do not send a new command until you know which mode you are in.

3. **When a slash command is active, reply with plain text unless Claude explicitly wants another slash command**
   - If Claude asks a question inside an active slash-command flow, answer with regular text only.
   - Do not prefix that reply with `/`.
   - Do not send meta-commentary like "please continue."
   - Answer the question directly and scope the work precisely.

4. **Use the exact command name Claude exposes**
   - Never assume aliases.
   - If needed, inspect the live slash-command list from the pane first.
   - Prefer the exact registered form shown in that session, for example:
     - `/speckit-analyze`
     - not `/speckit.analyze`

5. **Do not stack commands**
   - After sending input, wait for visible acknowledgment or progress output.
   - Poll the pane instead of sending extra messages while Claude is still working.
   - If Claude is clearly still thinking, wait.

6. **Preserve the current command contract**
   - If Claude is in a read-only analysis command, do not tell it to edit files.
   - If Claude is in a clarification command, answer the clarification rather than broadening scope.
   - If Claude is in implementation, direct it toward the next execution step, not back into planning unless the work truly requires it.

## Session-State Heuristics

Use the captured pane output to classify the state.

### 1. Shell prompt

You see a normal shell prompt and no Claude UI.

What to do:
- Start or attach to the intended Claude session.
- Do not assume the cwd is correct; verify it.

### 2. Normal Claude prompt

You see the Claude prompt ready for a new user message.

What to do:
- You may send either:
  - a slash command
  - a normal-language prompt
- Keep the input minimal and specific.

### 3. Slash-command list/menu

You see available slash commands listed.

What to do:
- Read the exact command name from the list.
- Send that exact command name.
- Do not improvise punctuation or aliases.

### 4. Slash-command follow-up question

Claude has already entered a slash-command workflow and asks something like:
- "Do you want to proceed anyway?"
- "Would you like me to suggest concrete remediation edits?"
- "Which option do you want?"

What to do:
- Reply in plain text only.
- Answer the actual decision point.
- Add scope constraints if needed.

Good example:

```text
Yes. Draft concrete remediation for all findings, ordered by severity. Stay read-only. For each one, name the exact file/section to change, the recommended edit, and whether it requires rerunning clarify/plan/tasks or can be fixed directly.
```

Bad examples:

```text
/continue
/speckit-analyze
Proceed with option 2.
```

The last example is bad because it often gets parsed as a new command instead of an answer.

### 5. Interactive selector/menu

You see numbered options, worktree selectors, or in-terminal menus.

What to do:
- Reply with the smallest valid selection.
- Avoid extra prose.

### 6. Long-running work / thinking

Claude shows progress like:
- thinking
- reading files
- almost done
- tool execution in progress

What to do:
- Wait.
- Poll the pane.
- Do not send steering text unless it is clearly stalled or asking for input.

## Speckit-Specific Driving Pattern

For Speckit workflows driven through Claude:

1. **Discover the actual command names in that Claude session**
   - Hyphenated names may be registered even if the human workflow uses dotted names.
   - Example:
     - use `/speckit-analyze`
     - not `/speckit.analyze`

2. **Respect phase boundaries**
   - `specify` / `clarify` / `plan` / `checklist` / `tasks` / `analyze` are specification-phase tools.
   - `implement` is execution-phase.
   - Do not accidentally collapse them.

3. **Optional hooks**
   - If Claude surfaces an optional pre-hook like auto-commit:
     - default to skipping it unless the user asked for that hook or it is clearly useful
   - If you skip, say so plainly:

```text
Skip the optional git pre-hook and continue with the analysis.
```

4. **Analysis-stage replies**
   - If `analyze` asks whether to suggest remediation:
     - ask for concrete remediation
     - keep it read-only
     - request exact file/section targeting
     - request guidance on whether another Speckit loop is needed

Recommended pattern:

```text
Yes. Draft concrete remediation for all findings, ordered by severity. Stay read-only. For each one, name the exact file/section to change, the recommended edit, and whether it requires rerunning clarify/plan/tasks or can be fixed directly.
```

5. **Implementation-stage replies**
   - If `implement` asks whether to proceed despite incomplete checklists:
     - do not blindly approve
     - first prefer a read-only checklist triage pass unless the user has explicitly chosen a scope already
   - Otherwise stop and report to the user.

Recommended checklist-triage reply:

```text
Before implementation, walk the incomplete checklist items and triage them into:
1. actionable now before coding
2. blocked on implementation
3. blocked on corpus sweep or final validation

Do not mark items complete unless they are actually satisfied. Stay read-only for this triage, then recommend whether we should still proceed with option 1.
```

Only after that triage should you decide whether to proceed with implementation scope. The default bias is:
- triage first
- then choose the narrowest sensible implementation scope
- avoid kicking off long corpus sweeps or expensive validation runs silently

## Response Construction Rules

When answering Claude inside its session:

- Prefer one short paragraph or a few flat bullets.
- Tell Claude exactly what to do next.
- Avoid motivational or conversational filler.
- Avoid ambiguous phrases like:
  - "continue"
  - "go ahead"
  - "do the thing"
- Replace them with explicit operational instructions.

## Recovery Rules

If a command misfires:

1. Capture the pane immediately.
2. Identify whether the failure was:
   - wrong command name
   - wrong mode
   - input parsed as a new slash command
   - stalled interactive state
3. Correct only the minimum necessary thing.
4. Do not pile on explanations inside the Claude pane.

Good recovery:

- discover the command list
- resend the exact command

Bad recovery:

- sending multiple guesses
- sending free text while Claude is still parsing slash commands

## Watch Mode

Default behavior can use simple polling, but when you are driving a long Claude session you should prefer an activity-driven watch path over blind pane snapshots.

### Preferred watch hierarchy

1. **Best**: `tmux pipe-pane` + prompt-return detection
2. **Good**: `tmux monitor-activity`
3. **Fallback**: adaptive polling with backoff

### `tmux pipe-pane` protocol

When you control the Claude launch flow, prefer starting the session through a driver-aware wrapper that enables pane output capture from the start.

If the pane already exists, you can still attach a pipe:

```sh
tmux pipe-pane -o -t <target-pane> "cat >> /tmp/claude-driver-<session>.log"
```

Use that log as the primary event stream.

Watch for:
- new output appended
- Claude status transitions like `Reading...`, `Crunching...`, `Forging...`, `Transfiguring...`
- a visible prompt return (`❯`) after output

### Prompt-return detection

The best practical completion heuristic without modifying Claude is:

- output activity stops
- then the Claude prompt returns

Treat this as:
- likely ready for a new command, or
- likely asking for a decision if the last lines contain a question

Always confirm by inspecting the latest tail before sending input.

### `tmux monitor-activity`

If `pipe-pane` is not available or not yet set up, use `tmux monitor-activity` to detect that the pane changed, then inspect the tail.

This gives a signal that something happened, but not what happened. It does not replace reading the pane.

### Polling fallback

If neither watch mode is available, poll with backoff:

- `3-5s` after sending input
- `10-15s` when active reading/thinking is visible
- `30-60s` for long analyze/implement phases
- immediate poll when the human asks for status

Never poll at a fixed fast interval for long-running phases unless you have no other option.

### Driver-launch preference

If you are responsible for launching the Claude session, prefer a wrapper around the normal `cta`/Claude start flow that:

- records the target pane id
- enables `pipe-pane` logging automatically
- optionally writes a small metadata file with:
  - container
  - tmux session/window/pane
  - cwd
  - log path

That wrapper gives you an event stream and reduces manual pane scraping.

## User-Facing Loop

Outside the Claude pane, keep the human informed:

- say what session you are targeting
- say what you are sending and why
- report what Claude replied
- surface blockers quickly

The human should never have to infer where the remote session stands.

## Default Mental Model

Think of this as a small state machine:

1. capture
2. classify state
3. send the smallest correct input
4. wait
5. capture again
6. summarize
7. repeat

If you skip step 2, you will eventually corrupt the session.
