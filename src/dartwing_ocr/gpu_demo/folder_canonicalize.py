"""Path canonicalization + safe eager-delete for the demo (T018, FR-017).

Enforces the FR-017 contract:
- The per-document folder is canonicalized (symlinks resolved) before any
  delete; otherwise a symlink-escape outside the folder would bypass the
  "only the four canonical artifacts" guarantee.
- The eager-delete targets exact basenames only (no glob, no recursion).
- Any of the four basenames resolving outside the canonical folder, or any
  delete failure (permission, I/O), aborts with ``EagerDeleteError`` —
  mapped by the orchestrator to exit 2 (invalid input/usage).
- The delete is idempotent on missing files (FR-017 + CHK007 cluster).
"""

from __future__ import annotations

from pathlib import Path


class EagerDeleteError(Exception):
    """Eager-delete pre-flight or operation failed; mapped to exit 2."""


def canonicalize_document_folder(path: Path) -> Path:
    """Resolve symlinks and verify the folder exists.

    Returns the canonical absolute path. Raises ``EagerDeleteError`` if the
    path does not exist or is not a directory.
    """
    if not path.exists():
        raise EagerDeleteError(f"document folder does not exist: {path}")
    resolved = path.resolve()
    if not resolved.is_dir():
        raise EagerDeleteError(f"document folder is not a directory: {resolved}")
    return resolved


def safe_eager_delete(folder: Path, basenames: tuple[str, ...]) -> None:
    """Delete the named basenames from the canonicalized folder, abort-on-fail.

    Pre-flight (no side effects):
      - Folder must already be canonicalized (caller's responsibility).
      - Each ``basename`` MUST resolve (after symlink resolution) to a path
        inside ``folder`` — symlink-escape aborts before any delete.

    Then, in basename order, delete each existing file. Missing files are
    skipped (idempotent). Any OS error aborts immediately with
    ``EagerDeleteError``.
    """
    folder_str = str(folder)
    targets: list[Path] = []
    for basename in basenames:
        target = folder / basename
        # If the path doesn't exist yet, no symlink resolution applies — skip the
        # escape check (we'll skip the delete below too).
        if target.exists() or target.is_symlink():
            resolved = target.resolve()
            try:
                resolved.relative_to(folder_str)
            except ValueError as exc:
                raise EagerDeleteError(
                    f"eager-delete target resolves outside the per-document folder: "
                    f"{target} -> {resolved}"
                ) from exc
        targets.append(target)

    # No escape detected; proceed with deletes in basename order.
    for target in targets:
        try:
            if target.is_symlink() or target.exists():
                target.unlink()
        except OSError as exc:
            raise EagerDeleteError(
                f"eager-delete failed on {target}: {exc}"
            ) from exc
