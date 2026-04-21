"""Validate and atomically write ``routing_decision.json``.

Split into two concerns:

1. **Schema validation** — BEFORE any filesystem write, the assembled dict is
   validated against ``routing_decision.schema.json`` via the in-repo
   validator. A violation raises ``ContractAssertionError`` (exit code 3 at
   the CLI surface) because it means the router's code and the frozen
   contract have drifted; this must be fixed, not hidden.

2. **Atomic write** — serialize with ``json.dumps(..., indent=2,
   sort_keys=False, ensure_ascii=False)`` plus a trailing ``"\n"`` (research
   Decision 7), write into a sibling temp file inside the target folder, then
   ``os.replace(temp, final)``. A failed or interrupted write therefore
   cannot leave a partial ``routing_decision.json`` visible to readers.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ledgerlinc_ocr.router.errors import ContractAssertionError
from ledgerlinc_ocr.validator import validate_artifact

_OUTPUT_ARTIFACT_NAME = "routing_decision"
_OUTPUT_FILE_NAME = "routing_decision.json"
_CONTRACT_SET_VERSION = "1.0.0"


def _serialize(artifact: dict) -> bytes:
    text = json.dumps(artifact, indent=2, sort_keys=False, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def assemble_and_write(folder: str | Path, artifact: dict) -> Path:
    """Validate ``artifact`` against the frozen schema and write it atomically.

    ``folder`` is the per-document folder; the file is always written as
    ``<folder>/routing_decision.json`` per FR-001. Returns the final path.

    Raises ``ContractAssertionError`` if the assembled artifact fails
    ``routing_decision.schema.json`` validation. The filesystem is NOT
    touched when this happens.
    """
    folder = Path(folder)
    final_path = folder / _OUTPUT_FILE_NAME

    # 1. Validate BEFORE touching the filesystem. The validator only accepts
    # a file path, so we round-trip through a temp file that we delete before
    # raising / before the atomic write. The temp file is created inside
    # ``folder`` so the later ``os.replace`` is guaranteed atomic on POSIX.
    folder.mkdir(parents=True, exist_ok=True)
    payload = _serialize(artifact)

    fd, tmp_name = tempfile.mkstemp(
        prefix=".routing_decision.", suffix=".json.tmp", dir=folder
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())

        outcome = validate_artifact(
            tmp_path,
            _OUTPUT_ARTIFACT_NAME,
            version=_CONTRACT_SET_VERSION,
        )
        if not outcome.passed:
            first = outcome.violations[0] if outcome.violations else None
            detail = (
                f"{first.violation_code} at {first.field_path}: {first.reason}"
                if first is not None
                else "unknown violation"
            )
            raise ContractAssertionError(
                f"assembled routing_decision failed "
                f"routing_decision.schema.json: {detail} "
                f"(total violations: {len(outcome.violations)})"
            )

        os.replace(tmp_path, final_path)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise

    return final_path
