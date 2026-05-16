"""Assembler pipeline — reads inputs, validates, assembles, validates, writes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from dartwing_ocr.assembler.errors import InternalError
from dartwing_ocr.assembler.flatten import flatten_vendor_candidate
from dartwing_ocr.assembler.io import validate_output
from dartwing_ocr.assembler.quality import build_quality_summary
from dartwing_ocr.assembler.trace import build_trace
from dartwing_ocr.assembler.validation import (
    check_contract_versions,
    check_document_ids_match,
    check_inputs_readable,
    check_routing_internal_consistency,
    check_schemas_valid,
)
from dartwing_ocr.assembler.version import build_pipeline_version
from dartwing_ocr.assembler.write import write_final_payload

OUTPUT_FILENAME = "final_structured_payload.json"
DOCUMENT_TYPE = "invoice"


@dataclass(frozen=True)
class Invocation:
    """Caller-supplied parameters for a single assembler run."""

    document_folder: Path
    pipeline_version: str | None = None
    contract_set_version: str | None = None
    now_utc: Callable[[], datetime] | None = None


def _format_processed_at(now: datetime) -> str:
    """Decision 2: ISO-8601 UTC, second precision, Z suffix."""
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _copy_review_status(routing: dict) -> dict:
    """US3 — verbatim copy, no normalization."""
    src = routing["review_status"]
    return {
        "manual_review_required": src["manual_review_required"],
        "review_reason": src["review_reason"],
    }


def run(invocation: Invocation) -> Path:
    """Read, validate, assemble, validate, write. Return the path of the written file."""
    folder = Path(invocation.document_folder)

    # H5: capture processed_at FIRST, before any invariants. FR-007 says it
    # "reflects when the assembly ran" — run-start is a more honest reading
    # than "some moment mid-assembly after 6 invariants passed." A single
    # clock call up front also removes the ambiguity the prior layout had:
    # a post-invariant clock failure would leak through the CLI's generic
    # Exception arm as exit 1 "unexpected" even though the invariants had
    # already passed. Clock failures are environmental (not input-shape),
    # so route them to InternalError (exit 3) — the honest taxonomy.
    now_fn = invocation.now_utc or (lambda: datetime.now(timezone.utc))
    try:
        processed_at = _format_processed_at(now_fn())
    except Exception as exc:
        raise InternalError(f"clock failure capturing processed_at: {exc}") from exc

    pipeline_version = invocation.pipeline_version or build_pipeline_version()

    # Invariants 1–2: existence + JSON-parseable
    extractor, routing = check_inputs_readable(folder)
    # Invariant 3: input contract sets are supported, matching, and honor any
    # controller-selected contract set.
    contract_set_version = check_contract_versions(
        extractor,
        routing,
        contract_set_version=invocation.contract_set_version,
    )
    # Invariant 4: each input schema-valid under that contract set.
    check_schemas_valid(
        extractor,
        routing,
        contract_set_version=contract_set_version,
    )
    # Invariant 5: document_id agreement
    document_id = check_document_ids_match(extractor, routing)
    # Invariant 6: routing internal consistency (FR-016)
    check_routing_internal_consistency(routing)

    # Assemble — insertion order matches FINAL_KEY_ORDER.
    payload: dict = {
        "contract_set_version": contract_set_version,
        "pipeline_version": pipeline_version,
        "document_id": document_id,
        "processed_at": processed_at,
        "document_type": DOCUMENT_TYPE,
        "vendor_candidate": flatten_vendor_candidate(extractor),
        "review_status": _copy_review_status(routing),
        "quality_summary": build_quality_summary(extractor),
        "trace": build_trace(),
    }

    # Invariant 7: output schema-valid (exit 3 on failure, no write)
    validate_output(payload, contract_set_version=contract_set_version)

    out_path = (folder / OUTPUT_FILENAME).resolve()
    write_final_payload(out_path, payload)
    return out_path
