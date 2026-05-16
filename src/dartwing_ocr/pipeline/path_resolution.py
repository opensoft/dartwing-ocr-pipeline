"""Deterministic path and document-id resolution. FR-002 through FR-004."""
from __future__ import annotations

import re
from pathlib import Path

_FOLDER_NAME_RE = re.compile(r"^inv_\d{3}_(easy|medium|hard|missing_name)$")


class PathResolutionError(ValueError):
    pass


class AmbiguousDocumentIdError(PathResolutionError):
    pass


def resolve_input_pdf(
    input_path: Path | None, document_folder: Path | None
) -> Path:
    if input_path is not None and document_folder is not None:
        raise PathResolutionError(
            "--input and --document-folder are mutually exclusive"
        )
    if input_path is None and document_folder is None:
        raise PathResolutionError(
            "one of --input or --document-folder is required"
        )
    if input_path is not None:
        return Path(input_path).expanduser().resolve()
    folder = Path(document_folder).expanduser().resolve()
    return folder / "source.pdf"


def resolve_destination(
    input_path: Path | None,
    document_folder: Path | None,
    output_dir: Path | None,
) -> Path:
    if output_dir is not None:
        return Path(output_dir).expanduser().resolve()
    if document_folder is not None:
        return Path(document_folder).expanduser().resolve()
    if input_path is not None:
        return Path(input_path).expanduser().resolve().parent
    raise PathResolutionError("cannot resolve destination without inputs")


def derive_document_id(dest_folder_name: str) -> str | None:
    """Return the corpus document_id for a matching folder name, else None."""
    m = _FOLDER_NAME_RE.match(dest_folder_name)
    if not m:
        return None
    return dest_folder_name
