#!/usr/bin/env bash
# SC-001 schema sweep (T061).
#
# Runs preprocessing over every corpus document, then validates every
# emitted preprocess_output.json against the frozen v1.0.0 contract via
# `python -m ledgerlinc_ocr.validator validate corpus ...`. Asserts zero
# schema errors.
#
# Deferred gate: the 20-document corpus does not yet exist in this
# worktree. Script is ready to run once the corpus lands.

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

for d in "${dirs[@]}"; do
    [[ -d "$d" && -f "$d/source.pdf" ]] || continue
    "$PY" -m ledgerlinc_ocr.preprocessing --document-folder "$d" >/dev/null
done

exec "$PY" -m ledgerlinc_ocr.validator validate corpus "$CORPUS"
