"""Deterministic reconciliation pipeline.

Pure function over `(packet, parsed, config, now, pipeline_version,
repair_trail)`. No I/O, no Ollama, no file writes. Implements the 8-step
state machine from data-model.md.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .config import VoterConfig

_TOTAL_AMOUNT_PATH = "invoice_header_fields/total_amount"
_COMPANY_NAME_PATH = "vendor_candidate/company_name"

_EVIDENCE_ID = re.compile(r"^p\d+_[bl]\d+$")

_VCE_FIELDS = ("website", "phone", "email")
_ADDRESS_FIELDS = ("street_1", "street_2", "city", "state", "postal_code", "country")
_TAX_FIELDS = ("ein", "state_tax_id", "vat_id", "other_tax_id")
_HEADER_SCALAR_FIELDS = ("invoice_number", "invoice_date")


def _new_scalar() -> dict[str, Any]:
    return {"value": None, "confidence": 0.0, "evidence": []}


def _new_total_amount() -> dict[str, Any]:
    return {"value": None, "currency": None, "confidence": 0.0, "evidence": []}


def _new_company_name() -> dict[str, Any]:
    return {
        "value": None,
        "present": False,
        "inferred": False,
        "confidence": 0.0,
        "evidence": [],
    }


def _coerce_scalar(  # NOSONAR S3776 — multi-type scalar coercion — flat type-check branches are simpler than dispatch.
    raw: Any,
    path: str,
    warnings: list[str],
    soft: dict[str, bool],
) -> dict[str, Any]:
    """Normalize a model-proposed `{value, confidence, evidence}` field."""

    if not isinstance(raw, dict):
        warnings.append(f"sub-field defaulted (wrong-type): {path}")
        soft["defaulted"] = True
        return _new_scalar()

    out = _new_scalar()

    value = raw.get("value", None)
    if value is None or isinstance(value, str):
        out["value"] = value if value != "" else None
    else:
        warnings.append(f"sub-field defaulted (wrong-type value): {path}/value")
        soft["defaulted"] = True
        out["value"] = None

    confidence = raw.get("confidence", 0.0)
    if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
        out["confidence"] = max(0.0, min(1.0, float(confidence)))
    else:
        warnings.append(f"sub-field defaulted (wrong-type confidence): {path}/confidence")
        soft["defaulted"] = True
        out["confidence"] = 0.0

    evidence = raw.get("evidence", [])
    if isinstance(evidence, list) and all(isinstance(e, str) for e in evidence):
        out["evidence"] = list(evidence)
    else:
        warnings.append(f"sub-field defaulted (wrong-type evidence): {path}/evidence")
        soft["defaulted"] = True
        out["evidence"] = []

    return out


def _coerce_total_amount(
    raw: Any,
    warnings: list[str],
    soft: dict[str, bool],
) -> dict[str, Any]:
    path = _TOTAL_AMOUNT_PATH
    if not isinstance(raw, dict):
        warnings.append(f"sub-field defaulted (wrong-type): {path}")
        soft["defaulted"] = True
        return _new_total_amount()

    out = _new_total_amount()

    value = raw.get("value", None)
    if value is None or (isinstance(value, (int, float)) and not isinstance(value, bool)):
        out["value"] = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    else:
        warnings.append(f"sub-field defaulted (wrong-type value): {path}/value")
        soft["defaulted"] = True
        out["value"] = None

    currency = raw.get("currency", None)
    if currency is None or (isinstance(currency, str) and currency != ""):
        out["currency"] = currency
    else:
        warnings.append(f"sub-field defaulted (wrong-type currency): {path}/currency")
        soft["defaulted"] = True
        out["currency"] = None

    confidence = raw.get("confidence", 0.0)
    if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
        out["confidence"] = max(0.0, min(1.0, float(confidence)))
    else:
        warnings.append(f"sub-field defaulted (wrong-type confidence): {path}/confidence")
        soft["defaulted"] = True
        out["confidence"] = 0.0

    evidence = raw.get("evidence", [])
    if isinstance(evidence, list) and all(isinstance(e, str) for e in evidence):
        out["evidence"] = list(evidence)
    else:
        warnings.append(f"sub-field defaulted (wrong-type evidence): {path}/evidence")
        soft["defaulted"] = True
        out["evidence"] = []

    return out


def _coerce_company_name(
    raw: Any,
    warnings: list[str],
    soft: dict[str, bool],
) -> dict[str, Any]:
    path = _COMPANY_NAME_PATH
    if not isinstance(raw, dict):
        warnings.append(f"sub-field defaulted (wrong-type): {path}")
        soft["defaulted"] = True
        return _new_company_name()

    base = _coerce_scalar(raw, path, warnings, soft)
    out = _new_company_name()
    out["value"] = base["value"]
    out["confidence"] = base["confidence"]
    out["evidence"] = base["evidence"]
    # Model-supplied present/inferred are informational — Step 5 overrides deterministically.
    return out


def _walk_missing(
    parsed: dict[str, Any],
    keys: tuple[str, ...],
    warnings: list[str],
    soft: dict[str, bool],
    prefix: str,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key in keys:
        if key not in parsed:
            warnings.append(f"sub-field defaulted (missing): {prefix}/{key}")
            soft["defaulted"] = True
            out[key] = _new_scalar()
        else:
            out[key] = _coerce_scalar(parsed[key], f"{prefix}/{key}", warnings, soft)
    return out


def _build_evidence_index(packet: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for page in packet.get("pages", []) or []:
        for block in page.get("blocks", []) or []:
            bid = block.get("block_id")
            if isinstance(bid, str):
                ids.add(bid)
        for line in page.get("raw_ocr_lines", []) or []:
            lid = line.get("line_id")
            if isinstance(lid, str):
                ids.add(lid)
    return ids


def _filter_evidence(
    field: dict[str, Any],
    evidence_index: set[str],
    field_path: str,
    warnings: list[str],
    soft: dict[str, bool],
) -> None:
    raw = field.get("evidence", []) or []
    filtered: list[str] = []
    seen: set[str] = set()
    for eid in raw:
        if not isinstance(eid, str) or not _EVIDENCE_ID.match(eid):
            warnings.append(f"evidence dropped (format): {field_path} id={eid!r}")
            soft["evidence_dropped"] = True
            continue
        if eid not in evidence_index:
            warnings.append(f"evidence dropped (unresolved): {field_path} id={eid!r}")
            soft["evidence_dropped"] = True
            continue
        if eid in seen:
            continue
        seen.add(eid)
        filtered.append(eid)
    field["evidence"] = filtered


def _apply_cap(field: dict[str, Any], cap: float) -> None:
    if not field["evidence"]:
        field["confidence"] = min(field["confidence"], cap)


def _dedup_first_seen(items: list[str]) -> list[str]:  # NOSONAR S3776 — reconcile cascade — Sonar over-counts the per-field cascade; structural split is on the deferred list.
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not isinstance(item, str) or not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def reconcile(
    packet: dict[str, Any],
    parsed: dict[str, Any],
    config: VoterConfig,
    now: datetime,
    pipeline_version: str,
    repair_trail: list[str],
    contract_set_version: str = "1.0.0",
) -> dict[str, Any]:
    warnings: list[str] = []
    extraction_notes: list[str] = []
    soft = {"defaulted": False, "evidence_dropped": False, "repaired": False}

    if repair_trail:
        soft["repaired"] = True
        for step in repair_trail:
            warnings.append(f"model response repaired: {step}")

    # Step 1 — Metadata
    artifact: dict[str, Any] = {
        "contract_set_version": contract_set_version,
        "pipeline_version": pipeline_version,
        "document_id": packet["document_id"],
        "processed_at": now.isoformat().replace("+00:00", "Z"),
        "model_runtime": {
            "provider": config.model_runtime.provider,
            "model_name": config.model_runtime.model_name,
            "model_version": config.model_runtime.model_version,
            "runtime": config.model_runtime.runtime,
        },
        "vote_metadata": {
            "voter_id": config.voter_id,
            "voter_role": config.voter_role,
            "consensus_mode": config.consensus_mode,
        },
    }

    # Step 2 — Model-proposed field extraction
    parsed_vendor = parsed.get("vendor_candidate", {}) or {}
    if not isinstance(parsed_vendor, dict):
        warnings.append("sub-field defaulted (wrong-type): vendor_candidate")
        soft["defaulted"] = True
        parsed_vendor = {}

    if "company_name" in parsed_vendor:
        company_name = _coerce_company_name(parsed_vendor["company_name"], warnings, soft)
    else:
        warnings.append(f"sub-field defaulted (missing): {_COMPANY_NAME_PATH}")
        soft["defaulted"] = True
        company_name = _new_company_name()

    parsed_address = parsed_vendor.get("address", {}) or {}
    if not isinstance(parsed_address, dict):
        warnings.append("sub-field defaulted (wrong-type): vendor_candidate/address")
        soft["defaulted"] = True
        parsed_address = {}
    address = _walk_missing(
        parsed_address, _ADDRESS_FIELDS, warnings, soft, "vendor_candidate/address"
    )

    parsed_tax = parsed_vendor.get("tax_ids", {}) or {}
    if not isinstance(parsed_tax, dict):
        warnings.append("sub-field defaulted (wrong-type): vendor_candidate/tax_ids")
        soft["defaulted"] = True
        parsed_tax = {}
    tax_ids = _walk_missing(
        parsed_tax, _TAX_FIELDS, warnings, soft, "vendor_candidate/tax_ids"
    )

    vendor_scalars: dict[str, dict[str, Any]] = {}
    for key in _VCE_FIELDS:
        if key not in parsed_vendor:
            warnings.append(f"sub-field defaulted (missing): vendor_candidate/{key}")
            soft["defaulted"] = True
            vendor_scalars[key] = _new_scalar()
        else:
            vendor_scalars[key] = _coerce_scalar(
                parsed_vendor[key], f"vendor_candidate/{key}", warnings, soft
            )

    parsed_header = parsed.get("invoice_header_fields", {}) or {}
    if not isinstance(parsed_header, dict):
        warnings.append("sub-field defaulted (wrong-type): invoice_header_fields")
        soft["defaulted"] = True
        parsed_header = {}

    header_scalars: dict[str, dict[str, Any]] = {}
    for key in _HEADER_SCALAR_FIELDS:
        if key not in parsed_header:
            warnings.append(f"sub-field defaulted (missing): invoice_header_fields/{key}")
            soft["defaulted"] = True
            header_scalars[key] = _new_scalar()
        else:
            header_scalars[key] = _coerce_scalar(
                parsed_header[key], f"invoice_header_fields/{key}", warnings, soft
            )

    if "total_amount" in parsed_header:
        total_amount = _coerce_total_amount(parsed_header["total_amount"], warnings, soft)
    else:
        warnings.append(f"sub-field defaulted (missing): {_TOTAL_AMOUNT_PATH}")
        soft["defaulted"] = True
        total_amount = _new_total_amount()

    parsed_doctype = parsed.get("document_type", {}) or {}
    if not isinstance(parsed_doctype, dict):
        warnings.append("sub-field defaulted (wrong-type): document_type")
        soft["defaulted"] = True
        parsed_doctype = {}
    doctype_value_raw = parsed_doctype.get("value", None)
    doctype_conf_raw = parsed_doctype.get("confidence", 0.0)
    if isinstance(doctype_conf_raw, (int, float)) and not isinstance(doctype_conf_raw, bool):
        doctype_confidence = max(0.0, min(1.0, float(doctype_conf_raw)))
    else:
        doctype_confidence = 0.0
        warnings.append("sub-field defaulted (wrong-type confidence): document_type/confidence")
        soft["defaulted"] = True

    # Step 3 — Evidence reconciliation
    evidence_index = _build_evidence_index(packet)

    def _filter_block(field: dict[str, Any], path: str) -> None:
        _filter_evidence(field, evidence_index, path, warnings, soft)

    _filter_block(company_name, _COMPANY_NAME_PATH)
    for key in _ADDRESS_FIELDS:
        _filter_block(address[key], f"vendor_candidate/address/{key}")
    for key in _TAX_FIELDS:
        _filter_block(tax_ids[key], f"vendor_candidate/tax_ids/{key}")
    for key in _VCE_FIELDS:
        _filter_block(vendor_scalars[key], f"vendor_candidate/{key}")
    for key in _HEADER_SCALAR_FIELDS:
        _filter_block(header_scalars[key], f"invoice_header_fields/{key}")
    _filter_block(total_amount, _TOTAL_AMOUNT_PATH)

    # Step 4 — Ungrounded-confidence cap
    cap = config.reconciliation.ungrounded_confidence_cap
    _apply_cap(company_name, cap)
    for field in list(address.values()) + list(tax_ids.values()) + list(vendor_scalars.values()):
        _apply_cap(field, cap)
    for field in list(header_scalars.values()) + [total_amount]:
        _apply_cap(field, cap)
    # document_type has confidence but no evidence array; cap applies whenever
    # no other field in the artifact is grounded. Simpler rule: if the overall
    # artifact has no grounded evidence anywhere, cap document_type too.
    any_grounded = any(
        field["evidence"]
        for field in (
            [company_name, total_amount]
            + list(address.values())
            + list(tax_ids.values())
            + list(vendor_scalars.values())
            + list(header_scalars.values())
        )
    )
    if not any_grounded:
        doctype_confidence = min(doctype_confidence, cap)

    # Step 5 — company_name provenance override
    if company_name["evidence"]:
        company_name["present"] = True
        company_name["inferred"] = False
    else:
        company_name["present"] = False
        company_name["inferred"] = True
        extraction_notes.append(
            "company_name override: no grounded evidence after reconciliation"
        )

    # Step 6 — document_type coercion
    if doctype_value_raw not in (None, "invoice"):
        extraction_notes.append(
            f"document_type coerced to 'invoice' (model claimed {doctype_value_raw!r})"
        )
        doctype_confidence = min(doctype_confidence, 0.5)
        soft["defaulted"] = True
    document_type = {"value": "invoice", "confidence": doctype_confidence}

    # Assemble pre-status artifact shape.
    artifact["document_type"] = document_type
    artifact["vendor_candidate"] = {
        "company_name": company_name,
        "address": {key: address[key] for key in _ADDRESS_FIELDS},
        "tax_ids": {key: tax_ids[key] for key in _TAX_FIELDS},
        "website": vendor_scalars["website"],
        "phone": vendor_scalars["phone"],
        "email": vendor_scalars["email"],
    }
    artifact["invoice_header_fields"] = {
        "invoice_number": header_scalars["invoice_number"],
        "invoice_date": header_scalars["invoice_date"],
        "total_amount": total_amount,
    }

    # FR-023 — input-side partiality note
    input_warnings = packet.get("warnings") or []
    if input_warnings:
        extraction_notes.append(
            f"input preprocessing was partial: {len(input_warnings)} warnings"
        )
        soft["defaulted"] = True  # partial input → at most partial output
    ingestion = packet.get("ingestion_sources") or {}
    for name, src in ingestion.items():
        if isinstance(src, dict) and src.get("status") == "failure":
            extraction_notes.append(
                f"input ingestion_source failed: {name}"
            )
            soft["defaulted"] = True  # partial input → at most partial output

    # Step 7 — Status derivation
    any_value_non_null = (
        company_name["value"] is not None
        or any(address[k]["value"] is not None for k in _ADDRESS_FIELDS)
        or any(tax_ids[k]["value"] is not None for k in _TAX_FIELDS)
        or any(vendor_scalars[k]["value"] is not None for k in _VCE_FIELDS)
        or any(header_scalars[k]["value"] is not None for k in _HEADER_SCALAR_FIELDS)
        or total_amount["value"] is not None
    )

    any_soft = soft["defaulted"] or soft["evidence_dropped"] or soft["repaired"]

    if not any_value_non_null and not any_grounded:
        status = "failure"
        if not warnings:
            warnings.append("model produced no usable values and no grounded evidence")
    elif any_soft:
        status = "partial"
    else:
        status = "success"

    # Step 8 — warnings + extraction_notes normalization (first-seen, dedup)
    artifact["extraction_notes"] = _dedup_first_seen(extraction_notes)
    artifact["warnings"] = _dedup_first_seen(warnings)
    artifact["status"] = status

    # Post-conditions (belt-and-braces)
    cn = artifact["vendor_candidate"]["company_name"]
    assert cn["present"] != cn["inferred"], "company_name XOR invariant violated"
    for field_path, field in _iter_all_fields(artifact):
        for eid in field.get("evidence", []):
            assert eid in evidence_index, f"unresolved evidence id survived: {field_path} {eid}"

    return artifact


def _iter_all_fields(artifact: dict[str, Any]):
    vc = artifact["vendor_candidate"]
    yield _COMPANY_NAME_PATH, vc["company_name"]
    for key in _ADDRESS_FIELDS:
        yield f"vendor_candidate/address/{key}", vc["address"][key]
    for key in _TAX_FIELDS:
        yield f"vendor_candidate/tax_ids/{key}", vc["tax_ids"][key]
    for key in _VCE_FIELDS:
        yield f"vendor_candidate/{key}", vc[key]
    hf = artifact["invoice_header_fields"]
    for key in _HEADER_SCALAR_FIELDS:
        yield f"invoice_header_fields/{key}", hf[key]
    yield _TOTAL_AMOUNT_PATH, hf["total_amount"]
