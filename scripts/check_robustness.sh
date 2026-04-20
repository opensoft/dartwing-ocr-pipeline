#!/usr/bin/env bash
# SC-004 robustness sweep (T062).
#
# Reports exit code + artifact-written status per document across the
# 20-document corpus. Asserts ≥ 90% success (exit 0 with artifact
# present).
#
# Deferred gate: corpus not yet present in this worktree. Script is
# ready to run once the corpus lands.

set -euo pipefail

CORPUS="${CORPUS:-tests/stage1_vendor_identity}"
PY="${PY:-.venv/bin/python}"
THRESHOLD="${THRESHOLD:-90}"

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

total=0
ok=0
printf '%-40s  %4s  %s\n' "document" "exit" "artifact"
for d in "${dirs[@]}"; do
    [[ -d "$d" && -f "$d/source.pdf" ]] || continue
    total=$((total + 1))

    rm -f "$d/preprocess_output.json"
    set +e
    "$PY" -m ledgerlinc_ocr.preprocessing --document-folder "$d" >/dev/null 2>&1
    rc=$?
    set -e

    if [[ $rc -eq 0 && -f "$d/preprocess_output.json" ]]; then
        ok=$((ok + 1))
        printf '%-40s  %4d  %s\n' "$(basename "$d")" "$rc" "yes"
    else
        printf '%-40s  %4d  %s\n' "$(basename "$d")" "$rc" "no"
    fi
done

pct=$(( ok * 100 / (total > 0 ? total : 1) ))
echo "Robustness: $ok/$total (${pct}%) — threshold ${THRESHOLD}%"
if (( pct < THRESHOLD )); then
    exit 1
fi
