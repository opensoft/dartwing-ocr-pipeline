# Project-agnostic Speckit worktree helpers.
#
# Defines: ct, ctp, ctlist, cta, ctc, ctg, cts.
#
# Each function resolves the current Git repo at call time via
# `git rev-parse --show-toplevel`, then dispatches to per-repo helper scripts
# under `.specify/`. Errors nicely if you're not inside a Git repo or the
# repo has no `.specify/` tree.
#
# Sourced automatically by ~/.zshrc when the container-wide installer places
# this file at /usr/local/share/ct/ct-functions.zsh.

_ct_repo_root() {
  local root
  root=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "ct: not inside a Git repository" >&2
    return 1
  }
  if [ ! -d "$root/.specify" ]; then
    echo "ct: .specify/ not found in repo root: $root" >&2
    return 1
  fi
  printf '%s\n' "$root"
}

_ct_last_worktree_script() {
  local root script
  root=$(_ct_repo_root) || return 1
  script="$root/.specify/extensions/git/scripts/bash/get-last-worktree.sh"
  if [ ! -f "$script" ]; then
    echo "ct: helper script not found: $script" >&2
    return 1
  fi
  printf '%s\n' "$script"
}

_ct_select_worktree_script() {
  local root script
  root=$(_ct_repo_root) || return 1
  script="$root/.specify/shell/select-worktree.sh"
  if [ ! -f "$script" ]; then
    echo "ct: helper script not found: $script" >&2
    return 1
  fi
  printf '%s\n' "$script"
}

_ct_select_worktree() {
  local script target
  script=$(_ct_select_worktree_script) || return 1
  target=$(bash "$script" --path) || return 1
  if [ -z "$target" ]; then
    echo "ct: no Speckit worktree selected" >&2
    return 1
  fi
  printf '%s\n' "$target"
}

_ct_prompt_cli() {
  local selection cli_name cli_command

  while true; do
    printf '1. Anthropic' >&2
    if command -v claude >/dev/null 2>&1; then
      printf ' [available]\n' >&2
    else
      printf ' [not installed]\n' >&2
    fi

    printf '2. Codex' >&2
    if command -v codex >/dev/null 2>&1; then
      printf ' [available]\n' >&2
    else
      printf ' [not installed]\n' >&2
    fi

    printf '3. Gemini' >&2
    if command -v gemini >/dev/null 2>&1; then
      printf ' [available]\n' >&2
    else
      printf ' [not installed]\n' >&2
    fi

    printf 'Select AI CLI [1] (q to cancel): ' >&2
    if ! IFS= read -r selection; then
      echo >&2
      return 1
    fi

    selection="${selection#"${selection%%[![:space:]]*}"}"
    selection="${selection%"${selection##*[![:space:]]}"}"
    [ -z "$selection" ] && selection=1

    case "$selection" in
      q|Q)
        return 1
        ;;
      1)
        cli_name="Anthropic"
        cli_command="claude"
        ;;
      2)
        cli_name="Codex"
        cli_command="codex"
        ;;
      3)
        cli_name="Gemini"
        cli_command="gemini"
        ;;
      *)
        echo "Invalid selection. Enter 1-3 or q." >&2
        continue
        ;;
    esac

    if ! command -v "$cli_command" >/dev/null 2>&1; then
      echo "$cli_name CLI is not installed on PATH." >&2
      continue
    fi

    printf '%s\n' "$cli_command"
    return 0
  done
}

_ct_start_cli() {
  local cli_command="$1"
  local target="$2"
  shift 2 || true

  cd "$target" || return 1
  "$cli_command" "$@"
}

ct() {
  local script target
  script=$(_ct_last_worktree_script) || return 1
  target=$(bash "$script") || return 1
  if [ -z "$target" ]; then
    echo "ct: no Speckit worktree path returned" >&2
    return 1
  fi
  cd "$target" || return 1
}

ctp() {
  local script
  script=$(_ct_last_worktree_script) || return 1
  bash "$script" --json
}

ctlist() {
  local script
  script=$(_ct_select_worktree_script) || return 1
  bash "$script" --list
}

cta() {
  local target
  if ! command -v claude >/dev/null 2>&1; then
    echo "cta: Claude CLI not found on PATH" >&2
    return 1
  fi
  target=$(_ct_select_worktree) || return 1
  _ct_start_cli claude "$target" "$@"
}

ctc() {
  local target
  if ! command -v codex >/dev/null 2>&1; then
    echo "ctc: Codex CLI not found on PATH" >&2
    return 1
  fi
  target=$(_ct_select_worktree) || return 1
  _ct_start_cli codex "$target" "$@"
}

ctg() {
  local target
  if ! command -v gemini >/dev/null 2>&1; then
    echo "ctg: Gemini CLI not found on PATH" >&2
    return 1
  fi
  target=$(_ct_select_worktree) || return 1
  _ct_start_cli gemini "$target" "$@"
}

cts() {
  local target cli_command
  target=$(_ct_select_worktree) || return 1
  cli_command=$(_ct_prompt_cli) || return 1
  _ct_start_cli "$cli_command" "$target" "$@"
}
