#!/usr/bin/env python3
"""SC-003 line_id stability sweep (T069).

Runs preprocessing twice over the 5 easy-corpus docs, extracts every
line_id on the page containing the vendor name, and asserts the set is
identical between runs. Any divergence is a determinism failure.

Deferred gate: the 5 `inv_*_easy/` docs are not yet present in this
worktree. Script is ready to run once the corpus lands.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS = REPO_ROOT / "tests" / "stage1_vendor_identity"
PY = sys.executable


def _run(doc: Path) -> dict:
    subprocess.run(
        [PY, "-m", "dartwing_ocr.preprocessing", "--document-folder", str(doc)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    with (doc / "preprocess_output.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def _line_ids_on_vendor_page(artifact: dict) -> list[str]:
    # Heuristic: the vendor block is expected on page 1 for easy docs.
    # If a richer rule is needed once the corpus lands, extend this.
    page1 = next(p for p in artifact["pages"] if p["page_number"] == 1)
    return sorted(line["line_id"] for line in page1["raw_ocr_lines"])


def main() -> int:
    if not CORPUS.exists():
        print(f"corpus not found: {CORPUS} — deferred, nothing to sweep")
        return 0

    easy_docs = sorted(p for p in CORPUS.glob("inv_*_easy") if p.is_dir())
    if not easy_docs:
        print("no easy-corpus docs found — deferred, skipping")
        return 0

    failures: list[str] = []
    for doc in easy_docs:
        art1 = _run(doc)
        ids1 = _line_ids_on_vendor_page(art1)

        # Preserve the first run's artifact before the second run overwrites it.
        saved = doc / "preprocess_output.run1.json"
        shutil.copy(doc / "preprocess_output.json", saved)
        try:
            art2 = _run(doc)
            ids2 = _line_ids_on_vendor_page(art2)
            if ids1 != ids2:
                failures.append(
                    f"{doc.name}: line_id set changed\n  run1: {ids1}\n  run2: {ids2}"
                )
        finally:
            saved.unlink(missing_ok=True)

    if failures:
        print("FAIL — line_id instability detected:", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
        return 1

    print(f"OK — {len(easy_docs)} easy-corpus docs, line_ids stable across reruns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
