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

from ledgerlinc_ocr.contract_versions import (
    ContractVersionError,
    require_stage1_contract_version,
)
from ledgerlinc_ocr.pipeline.filenames import ROUTING_DECISION_FILENAME
from ledgerlinc_ocr.router.errors import ContractAssertionError, MissingInputError
from ledgerlinc_ocr.validator import validate_artifact

_OUTPUT_ARTIFACT_NAME = "routing_decision"
_OUTPUT_FILE_NAME = ROUTING_DECISION_FILENAME


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
    # FR-022: routing writes only inside the target folder; do NOT silently
    # create a missing folder — that would let a wrong-path caller silently
    # succeed outside the per-document contract. The CLI gates on existence
    # earlier; library callers get a typed ``MissingInputError`` (exit 2 at
    # the CLI surface) rather than a bare stdlib ``FileNotFoundError`` that
    # the CLI would otherwise misclassify as "unexpected exception" (exit 1).
    if not folder.is_dir():
        raise MissingInputError(
            f"target folder does not exist or is not a directory: {folder}"
        )
    final_path = folder / _OUTPUT_FILE_NAME

    try:
        contract_set_version = require_stage1_contract_version(
            artifact.get("contract_set_version"),
            artifact_label="routing_decision.json",
        )
    except ContractVersionError as exc:
        raise ContractAssertionError(
            f"assembled routing_decision has unsupported contract_set_version: {exc}"
        ) from exc

    # Validate AFTER writing to a sibling temp file inside ``folder`` so the
    # later ``os.replace`` is guaranteed atomic on POSIX. On validation
    # failure we unlink the temp file before raising so the filesystem
    # never holds a routing_decision.json that doesn't match the schema.
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
            version=contract_set_version,
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

        # ``os.replace`` only updates the in-memory directory entry; on a
        # host crash between the rename and the kernel's next directory
        # flush, POSIX permits the rename to be lost OR the file to surface
        # with zero bytes. Fsync the containing directory's fd so the
        # "no partial/invalid routing_decision.json visible to readers"
        # guarantee in this module's docstring holds across crashes, not
        # only across clean shutdowns.
        dir_fd = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise

    return final_path
