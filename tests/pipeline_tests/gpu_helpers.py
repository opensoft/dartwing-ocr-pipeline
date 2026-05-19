"""Shared helpers for feature 021 / US2 GPU end-to-end test conversions.

Used by:
- ``test_evidence_gate_skip_fallback.py`` (T009)
- ``test_evidence_gate_skip_fallback_borderline.py`` (T010)
- ``test_evidence_gate_all_suppressed_lazy_construction.py`` (T011)
- ``test_warmup_skip_fallback_exception.py`` (T012 GPU variant — deferred
  import inside the GPU test body per multi-agent-review MED-1)

These helpers are imported by ``pytest.mark.gpu``-marked tests only; CPU
CI skips the tests at collection time (root ``conftest.py`` skip-gate)
and never imports this module. The helpers therefore assume a GPU-capable
workstation is running them.

**Import-time invariant (MED-1)**: this module MUST stay side-effect-free
at import time. No print, no logging-config, no Paddle import, no Ollama
call. The CPU-only sibling tests in `tests/unit/preprocessing/` rely on
this so they can co-exist alongside the GPU subprocess test in their
file without dragging in import-time work. If you need to introduce a
side effect here, move the affected code into a function body and import
that function lazily from the GPU test bodies that use it.

The module name does not start with ``test_`` so pytest's
``python_files = ["test_*.py"]`` filter does not collect it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = REPO_ROOT / "tests" / "stage1_vendor_identity"


def setup_scratch_corpus(
    *, scratch_root: Path, doc_ids: Iterable[str]
) -> tuple[Path, list[Path]]:
    """Mirror ``source.pdf`` for each doc_id into a scratch tree.

    Returns ``(documents_file, doc_folders)``. The documents-file is
    written to ``<scratch_root>/docs.txt`` and lists each scratch
    per-doc folder absolute path, one per line, ready for
    ``--documents-file`` per research.md §R-021.14.
    """
    scratch_root.mkdir(parents=True, exist_ok=True)
    doc_folders: list[Path] = []
    for doc_id in doc_ids:
        src = CORPUS_ROOT / doc_id / "source.pdf"
        if not src.is_file():
            raise FileNotFoundError(
                f"corpus document missing: {src} — required by GPU test setup"
            )
        dst_dir = scratch_root / doc_id
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst_dir / "source.pdf")
        doc_folders.append(dst_dir)

    documents_file = scratch_root / "docs.txt"
    documents_file.write_text(
        "\n".join(str(f) for f in doc_folders) + "\n", encoding="utf-8"
    )
    return documents_file, doc_folders


def invoke_pipeline(
    *, documents_file: Path, extra_flags: Iterable[str] = (), timeout: float = 600.0
) -> subprocess.CompletedProcess[str]:
    """Run ``python -m dartwing_ocr.pipeline run`` with the GPU MVP profile set.

    Always uses ``--preprocess-profile ppstructurev3@gpu``,
    ``--preprocess-strategy ocr-only-v1``, ``--extract-profile stub``
    (stub extraction so the tests don't depend on Ollama for the
    preprocess-lane assertions). Additional flags
    (``--evidence-gate-skip-fallback``, ``--gpu-warmup``) are appended
    via ``extra_flags``.
    """
    cmd = [
        sys.executable,
        "-m",
        "dartwing_ocr.pipeline",
        "run",
        "--documents-file",
        str(documents_file),
        "--preprocess-profile",
        "ppstructurev3@gpu",
        "--preprocess-strategy",
        "ocr-only-v1",
        "--extract-profile",
        "stub",
        *extra_flags,
    ]
    return subprocess.run(
        cmd, capture_output=True, text=True, check=False, timeout=timeout
    )


def extract_run_summary(stdout: str) -> dict[str, Any]:
    """Find and parse the single ``kind: "run_summary"`` JSON line in stdout.

    Raises ``AssertionError`` (Pytest-friendly) if no run_summary line is
    found or if it is malformed.
    """
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("kind") == "run_summary":
            return obj
    raise AssertionError(
        "no `kind: \"run_summary\"` JSON line found in pipeline stdout:\n"
        + stdout
    )


def find_doc_record(run_summary: dict[str, Any], doc_id: str) -> dict[str, Any]:
    """Find a per-document record in ``run_summary["evidence_gate_documents"]``.

    Raises ``AssertionError`` if the document is missing — every benchmarked
    document MUST appear in the per-doc table (FR-017).
    """
    docs = run_summary.get("evidence_gate_documents", [])
    for record in docs:
        if isinstance(record, dict) and record.get("document_id") == doc_id:
            return record
    raise AssertionError(
        f"document_id={doc_id!r} not found in evidence_gate_documents "
        f"(have: {[r.get('document_id') for r in docs]!r})"
    )


def phase_keys(doc_record: dict[str, Any]) -> set[str]:
    """Return the set of ``phase_timings`` keys present on a per-doc record.

    A key is "absent" iff it is not in this set (FR-014 "when present"
    semantics; absence is itself observable per data-model.md §2 + plan.md
    Technical Context (f)).
    """
    phase_timings = doc_record.get("phase_timings", {})
    if not isinstance(phase_timings, dict):
        return set()
    return set(phase_timings.keys())
