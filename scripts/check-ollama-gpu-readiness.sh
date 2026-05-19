#!/usr/bin/env bash
# scripts/check-ollama-gpu-readiness.sh — feature 021 FR-002 readiness helper.
#
# Contract: specs/021-gpu-mvp-promotion/contracts/ollama-readiness-helper.md
# Constitution: §I (outside dartwing_ocr package; no new product behavior in
# pipeline code), §III (deterministic placement check; see disk + stdout
# carve-outs below).
#
# Asserts that the extraction model named by an active voter config (feature
# 005 voter-config schema) is fully GPU-placed in host Ollama. Read-only
# against Ollama — no model loading, no retries.
#
# Disk carve-out: the helper creates ONE ephemeral tmpfile via mktemp(1) to
# hold the /api/ps response body for jq parsing; the file is unlinked on
# EXIT/INT/TERM via a trap handler. No persistent state is written. The
# contract's "no writes to disk" clause is read as "no persistent writes" —
# the trap-cleaned ephemeral tmpfile is documented as an allowed side
# effect (see contracts/ollama-readiness-helper.md §Disallowed surfaces).
#
# Stdout carve-out: the PASS-JSON line includes a `timestamp_utc` field
# captured at invocation time (date -u +%Y-%m-%dT%H:%M:%SZ). The placement
# check itself is deterministic — given identical voter-config + identical
# /api/ps response, the exit code and the structural stdout JSON keys are
# identical; only `timestamp_utc` varies as provenance metadata. Callers
# MUST NOT key cache lookups or equality assertions on `timestamp_utc`.
#
# Exit codes (one-to-one with status literals):
#   0 — PASS (size_vram > 0 AND size_vram == size)
#   1 — FAIL: partial GPU (size_vram == 0 OR size_vram != size)
#   2 — FAIL: extraction model not loaded in Ollama
#   3 — FAIL: Ollama unreachable (curl non-zero, non-200, unparseable JSON)
#   4 — FAIL: voter-config missing or malformed
#
# Output streams:
#   stdout (PASS only): one JSON line — {status, model_name, size, size_vram,
#                       base_url, voter_config_path, timestamp_utc}.
#   stderr (FAIL only): one human-readable line beginning with "FAIL:".

set -u
# SonarCloud security/reliability hardening (PR #43): -o pipefail ensures
# a non-zero exit from any pipe stage (e.g., yq segfault piped to head)
# propagates as the pipe's exit code instead of being masked by the
# rightmost stage's success. The script's explicit `if ! ...` blocks
# retain control of the determinism contract; pipefail just removes the
# silent-failure surface.
set -o pipefail

# ----------------------------------------------------------------------------
# Argument parsing
# ----------------------------------------------------------------------------
voter_config=""
base_url="http://localhost:11434"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --voter-config)
            if [ "$#" -lt 2 ]; then
                echo "FAIL: voter-config <unset> missing or malformed (--voter-config requires a value)" >&2
                exit 4
            fi
            voter_config="$2"
            shift 2
            ;;
        --voter-config=*)
            voter_config="${1#--voter-config=}"
            # PR #43 Copilot review: reject `--voter-config=` with an
            # empty value; otherwise downstream `if [ ! -f "" ]` would
            # exit 4 with a confusing "file not found" message. Classify
            # as a config error up-front.
            if [ -z "$voter_config" ]; then
                echo "FAIL: voter-config <unset> missing or malformed (--voter-config= requires a value)" >&2
                exit 4
            fi
            shift
            ;;
        --base-url)
            if [ "$#" -lt 2 ]; then
                echo "FAIL: voter-config ${voter_config:-<unset>} missing or malformed (--base-url requires a value)" >&2
                exit 4
            fi
            base_url="$2"
            shift 2
            ;;
        --base-url=*)
            base_url="${1#--base-url=}"
            # PR #43 Copilot review: `--base-url=` with an empty value
            # would yield `api_url="/api/ps"` and exit 3 (unreachable),
            # sending operators down the wrong remediation path. An
            # empty base URL is a typo, not a network issue — classify
            # as config error (exit 4) here.
            if [ -z "$base_url" ]; then
                echo "FAIL: voter-config ${voter_config:-<unset>} missing or malformed (--base-url= requires a value)" >&2
                exit 4
            fi
            shift
            ;;
        *)
            echo "FAIL: voter-config ${voter_config:-<unset>} missing or malformed (usage error)" >&2
            exit 4
            ;;
    esac
done

if [ -z "$voter_config" ]; then
    echo "FAIL: voter-config <unset> missing or malformed (--voter-config <PATH> is required)" >&2
    exit 4
fi

# Multi-agent-review LOW-4 fix: strip a trailing slash from --base-url so the
# helper emits `http://localhost:11434/api/ps`, not `...//api/ps`. Ollama
# tolerates both but the doubled-slash leaks into the PASS-JSON `base_url`
# echo and the stderr FAIL templates.
base_url="${base_url%/}"

# ----------------------------------------------------------------------------
# Voter-config read: extract `model_name` via yq.
# ----------------------------------------------------------------------------
if [ ! -f "$voter_config" ]; then
    echo "FAIL: voter-config $voter_config missing or malformed (file not found)" >&2
    exit 4
fi

if ! command -v yq >/dev/null 2>&1; then
    echo "FAIL: voter-config $voter_config missing or malformed (yq not found on PATH)" >&2
    exit 4
fi

# PR #43 Codex review (P2): validate `model_name` is a STRING scalar
# before using it. A non-scalar value (list, object, multi-line block
# scalar, null) would otherwise have its first-rendered-line treated as
# a real model name and the helper would exit 2 ("not loaded") instead
# of the contract's exit 4 ("config"). yq's `tag` filter returns the
# YAML type tag of the queried value: `!!str` for strings, `!!seq` for
# lists, `!!map` for objects, `!!null` for null/missing.
#
# Both yq variants (mikefarah/yq v4 Go binary; kislyuk/yq Python wrapper)
# accept the `tag` filter; the latter may return slightly different tag
# names — we accept the canonical `!!str` only.
model_name_tag="$(yq -r '.model_name | tag // "!!null"' "$voter_config" 2>/dev/null || echo "!!error")"
if [ "$model_name_tag" != "!!str" ]; then
    echo "FAIL: voter-config $voter_config missing or malformed (model_name must be a string scalar; got YAML tag $model_name_tag)" >&2
    exit 4
fi

model_name="$(yq -r '.model_name' "$voter_config" 2>/dev/null || echo "")"
# Strip any surrounding whitespace just in case.
model_name="${model_name#"${model_name%%[![:space:]]*}"}"
model_name="${model_name%"${model_name##*[![:space:]]}"}"

if [ -z "$model_name" ]; then
    echo "FAIL: voter-config $voter_config missing or malformed (model_name is empty string)" >&2
    exit 4
fi

# ----------------------------------------------------------------------------
# HTTP fetch: GET <base_url>/api/ps
# ----------------------------------------------------------------------------
api_url="${base_url}/api/ps"

if ! command -v curl >/dev/null 2>&1; then
    echo "FAIL: Ollama unreachable at $api_url (curl not found on PATH)" >&2
    exit 3
fi
if ! command -v jq >/dev/null 2>&1; then
    echo "FAIL: Ollama unreachable at $api_url (jq not found on PATH)" >&2
    exit 3
fi

response_file="$(mktemp)"
trap 'rm -f "$response_file"' EXIT INT TERM

if ! curl_err="$(curl --silent --show-error --fail --max-time 10 "$api_url" -o "$response_file" 2>&1)"; then
    echo "FAIL: Ollama unreachable at $api_url (${curl_err:-curl non-zero})" >&2
    exit 3
fi

if ! jq -e '.' "$response_file" >/dev/null 2>&1; then
    echo "FAIL: Ollama unreachable at $api_url (unparseable JSON response)" >&2
    exit 3
fi

# ----------------------------------------------------------------------------
# JSON parse: find the matched-model entry in `.models[]`.
# ----------------------------------------------------------------------------
matched="$(jq -c --arg n "$model_name" '(.models // []) | map(select(.name == $n)) | .[0] // empty' "$response_file" 2>/dev/null)"

if [ -z "$matched" ] || [ "$matched" = "null" ]; then
    echo "FAIL: extraction model \"$model_name\" not loaded in Ollama at $api_url" >&2
    exit 2
fi

# ----------------------------------------------------------------------------
# Placement check: PASS iff size_vram > 0 AND size_vram == size.
# ----------------------------------------------------------------------------
size="$(echo "$matched" | jq -r '.size // 0')"
size_vram="$(echo "$matched" | jq -r '.size_vram // 0')"

# Defensive integer coercion (strip trailing decimal if jq emitted a float).
size="${size%.*}"
size_vram="${size_vram%.*}"

# Reject non-numeric (yq/jq emitted "null" or text).
case "$size" in ''|*[!0-9]*) size=0 ;; esac
case "$size_vram" in ''|*[!0-9]*) size_vram=0 ;; esac

if [ "$size_vram" -le 0 ] || [ "$size_vram" -ne "$size" ]; then
    echo "FAIL: extraction model \"$model_name\" partially on GPU at $api_url (size_vram=$size_vram, size=$size)" >&2
    exit 1
fi

# ----------------------------------------------------------------------------
# PASS: emit single-line JSON to stdout.
# ----------------------------------------------------------------------------
timestamp_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

jq -nc \
    --arg status "pass" \
    --arg model_name "$model_name" \
    --argjson size "$size" \
    --argjson size_vram "$size_vram" \
    --arg base_url "$base_url" \
    --arg voter_config_path "$voter_config" \
    --arg timestamp_utc "$timestamp_utc" \
    '{status: $status, model_name: $model_name, size: $size, size_vram: $size_vram, base_url: $base_url, voter_config_path: $voter_config_path, timestamp_utc: $timestamp_utc}'

exit 0
