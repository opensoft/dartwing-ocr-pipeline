"""Artifact assembly, schema validation, and atomic write (FR-017..FR-020, Decision 7)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from dartwing_ocr.preprocessing.document_text import join_document_text
from dartwing_ocr.preprocessing.errors import ArtifactInvalidError

ARTIFACT_FILENAME = "preprocess_output.json"

TABLE_REQUIRED_KEYS = ("page_number", "block_id", "bbox", "rows", "columns")
TABLE_OPTIONAL_KEYS = ("cells",)
TABLE_ALLOWED_KEYS = set(TABLE_REQUIRED_KEYS) | set(TABLE_OPTIONAL_KEYS)
CELL_ALLOWED_KEYS = {"row", "column", "bbox", "text"}


def _normalize_table(entry: dict[str, Any]) -> dict[str, Any]:
    """FR-011a: keep exactly the pinned key set; drop any unexpected keys."""
    missing = [k for k in TABLE_REQUIRED_KEYS if k not in entry]
    if missing:
        raise ArtifactInvalidError(
            f"table entry missing required keys {missing}: {entry!r}"
        )
    normalized: dict[str, Any] = {k: entry[k] for k in TABLE_REQUIRED_KEYS}
    cells = entry.get("cells")
    if cells is not None:
        if not isinstance(cells, list):
            raise ArtifactInvalidError(f"table cells must be a list, got {type(cells)!r}")
        normalized_cells: list[dict[str, Any]] = []
        for cell in cells:
            if not isinstance(cell, dict):
                raise ArtifactInvalidError(f"table cell must be an object: {cell!r}")
            normalized_cells.append({k: cell[k] for k in CELL_ALLOWED_KEYS if k in cell})
        normalized["cells"] = normalized_cells
    return normalized
SCHEMA_PATH = Path(__file__).resolve().parents[3] / (
    "contracts/stage1_vendor_identity/v1.2.0/preprocess_output.schema.json"
)


def _load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


_SCHEMA_CACHE: dict[str, Any] | None = None


def _schema() -> dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        _SCHEMA_CACHE = _load_schema()
    return _SCHEMA_CACHE


def assemble(
    *,
    contract_set_version: str,
    pipeline_version: str,
    document_id: str,
    source_file: str,
    pages: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    quality: dict[str, Any],
    ingestion_sources: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    ordered_pages = sorted(pages, key=lambda p: p["page_number"])
    normalized_tables = [_normalize_table(t) for t in tables]
    artifact: dict[str, Any] = {
        "contract_set_version": contract_set_version,
        "pipeline_version": pipeline_version,
        "document_id": document_id,
        "source_type": "pdf",
        "source_file": source_file,
        "page_count": len(ordered_pages),
        "pages": ordered_pages,
        "document_text": join_document_text(ordered_pages),
        "tables": normalized_tables,
        "quality": quality,
        "ingestion_sources": ingestion_sources,
        "warnings": warnings,
    }
    return artifact


def validate(artifact: dict[str, Any]) -> None:
    validator = Draft202012Validator(_schema())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: list(e.path))
    if errors:
        messages = [f"{'/'.join(str(p) for p in e.path)}: {e.message}" for e in errors]
        raise ArtifactInvalidError(
            "preprocess_output.json failed schema validation: " + "; ".join(messages)
        )


def write_atomic(artifact: dict[str, Any], out_path: Path) -> None:
    out_path = Path(out_path)
    tmp_path = out_path.with_name(f"{out_path.name}.tmp-{os.getpid()}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, out_path)


def validate_and_write(artifact: dict[str, Any], out_path: Path) -> Path:
    validate(artifact)
    write_atomic(artifact, out_path)
    return out_path
