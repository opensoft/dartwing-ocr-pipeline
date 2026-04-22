"""Schema-validate, then atomically write `edge_extraction_output.json`."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from ledgerlinc_ocr.validator import (
    ArtifactName,
    validate_artifact,
)

from .errors import ArtifactAssemblyError, FolderWriteError

_OUTPUT_NAME = "edge_extraction_output.json"


def assemble_and_write(artifact_dict: dict[str, Any], folder_path: Path) -> Path:
    """Write `artifact_dict` as `<folder_path>/edge_extraction_output.json`.

    Order of operations:
    1. Serialize to JSON in-memory (fail fast on non-serializable values).
    2. Run the frozen v1.0.0 validator against the serialized artifact.
    3. `os.replace` from a sibling `.tmp-<pid>` file for atomic rename.

    Raises `ArtifactAssemblyError` on schema failures (should be unreachable —
    reconcile.py's post-conditions prevent it) and `FolderWriteError` on I/O
    errors.
    """

    folder = Path(folder_path)
    try:
        serialized = json.dumps(artifact_dict, indent=2, ensure_ascii=False, sort_keys=False)
    except (TypeError, ValueError) as exc:
        raise ArtifactAssemblyError(
            "artifact contains non-JSON-serializable values",
            detail={"error": str(exc)},
        ) from exc

    if not folder.is_dir():
        raise FolderWriteError(
            f"target folder is not a directory: {folder}",
            detail={"path": str(folder)},
        )

    fd, tmp_path_str = tempfile.mkstemp(
        prefix=".edge_extraction_output.",
        suffix=f".tmp-{os.getpid()}",
        dir=str(folder),
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(serialized)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise FolderWriteError(
            f"failed to write temporary artifact: {tmp_path}",
            detail={"path": str(tmp_path), "error": str(exc)},
        ) from exc

    # Run the in-repo validator against the serialized file — proves what is
    # about to hit disk is schema-valid, not just the in-memory dict.
    outcome = validate_artifact(tmp_path, ArtifactName.EDGE_EXTRACTION_OUTPUT)
    if not outcome.passed:
        tmp_path.unlink(missing_ok=True)
        raise ArtifactAssemblyError(
            "assembled artifact failed v1.0.0 schema validation before write",
            detail={
                "errors": [
                    {
                        "field_path": v.field_path,
                        "violation_code": v.violation_code,
                        "reason": v.reason,
                    }
                    for v in outcome.violations
                ],
            },
        )

    final_path = folder / _OUTPUT_NAME
    try:
        os.replace(tmp_path, final_path)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise FolderWriteError(
            f"failed to rename artifact into place: {final_path}",
            detail={"path": str(final_path), "error": str(exc)},
        ) from exc

    # Durability: fsync the parent directory so the rename is persisted to
    # disk (metadata), not just the file bytes. Guards against torn/zero-length
    # artifacts after a power loss between os.replace and disk flush.
    dir_fd = None
    try:
        dir_fd = os.open(str(folder), os.O_RDONLY)
        os.fsync(dir_fd)
    except OSError:
        # fsync on a directory is best-effort (not all platforms/filesystems
        # support it). Do not fail the write if the durability hint failed.
        pass
    finally:
        if dir_fd is not None:
            try:
                os.close(dir_fd)
            except OSError:
                pass

    return final_path
