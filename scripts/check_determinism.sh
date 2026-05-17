#!/usr/bin/env bash
# SC-002 determinism sweep (T060).
#
# Runs preprocessing twice over every `tests/stage1_vendor_identity/inv_*/`
# document and diffs the two preprocess_output.json files byte-for-byte.
# Fails (exit 1) if any document's pair differs. Passes (exit 0) if every
# pair is byte-identical.
#
# Deferred gate: the 20-document corpus does not yet exist in this worktree
# (only tests/stage1_vendor_identity/README.md). This script is wired to
# run as soon as the corpus lands — no edits required then.

set -euo pipefail

CORPUS="${CORPUS:-tests/stage1_vendor_identity}"
PY="${PY:-.venv/bin/python}"

if [[ ! -d "$CORPUS" ]]; then
    echo "error: corpus directory $CORPUS not found" >&2
    exit 2
fi

shopt -s nullglob
dirs=("$CORPUS"/inv_*)
if (( ${#dirs[@]} == 0 )); then
    echo "no documents found under $CORPUS/inv_*/ — corpus deferred, skipping sweep"
    exit 0
fi

failures=0
total=0
for d in "${dirs[@]}"; do
    [[ -d "$d" ]] || continue
    [[ -f "$d/source.pdf" ]] || continue
    total=$((total + 1))

    tmp1="$(mktemp)"
    trap 'rm -f "$tmp1"' RETURN

    "$PY" -m dartwing_ocr.preprocessing --document-folder "$d" >/dev/null
    cp "$d/preprocess_output.json" "$tmp1"

    "$PY" -m dartwing_ocr.preprocessing --document-folder "$d" >/dev/null
    if ! diff -q "$tmp1" "$d/preprocess_output.json" >/dev/null; then
        echo "DIFF: $d"
        failures=$((failures + 1))
    fi
    rm -f "$tmp1"
done

echo "Determinism sweep: $((total - failures))/$total byte-identical"
if (( failures > 0 )); then
    exit 1
fi
