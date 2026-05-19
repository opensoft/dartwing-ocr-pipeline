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

# yq's -r/-e behavior differs between mikefarah/yq (v4 Go) and kislyuk/yq
# (Python wrapper around jq). Both accept `'.model_name'`. We tolerate either
# by trimming and treating "null"/"" as absence.
model_name="$(yq -r '.model_name // ""' "$voter_config" 2>/dev/null | head -n1 || echo "")"
# Strip any surrounding whitespace just in case.
model_name="${model_name#"${model_name%%[![:space:]]*}"}"
model_name="${model_name%"${model_name##*[![:space:]]}"}"

if [ -z "$model_name" ] || [ "$model_name" = "null" ]; then
    echo "FAIL: voter-config $voter_config missing or malformed (no model_name key or empty)" >&2
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
