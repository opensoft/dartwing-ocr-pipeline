"""Evidence-stripping flatten (research Decision 7, US2)."""

from __future__ import annotations

# Each entry: (extractor_path, final_payload_path, kind)
# kind ∈ {"value_confidence", "company_name"}
FIELDS_TO_FLATTEN: list[tuple[list[str], list[str], str]] = [
    (["vendor_candidate", "company_name"], ["vendor_candidate", "company_name"], "company_name"),
    (["vendor_candidate", "address", "street_1"], ["vendor_candidate", "address", "street_1"], "value_confidence"),
    (["vendor_candidate", "address", "street_2"], ["vendor_candidate", "address", "street_2"], "value_confidence"),
    (["vendor_candidate", "address", "city"], ["vendor_candidate", "address", "city"], "value_confidence"),
    (["vendor_candidate", "address", "state"], ["vendor_candidate", "address", "state"], "value_confidence"),
    (["vendor_candidate", "address", "postal_code"], ["vendor_candidate", "address", "postal_code"], "value_confidence"),
    (["vendor_candidate", "address", "country"], ["vendor_candidate", "address", "country"], "value_confidence"),
    (["vendor_candidate", "tax_ids", "ein"], ["vendor_candidate", "tax_ids", "ein"], "value_confidence"),
    (["vendor_candidate", "tax_ids", "state_tax_id"], ["vendor_candidate", "tax_ids", "state_tax_id"], "value_confidence"),
    (["vendor_candidate", "tax_ids", "vat_id"], ["vendor_candidate", "tax_ids", "vat_id"], "value_confidence"),
    (["vendor_candidate", "tax_ids", "other_tax_id"], ["vendor_candidate", "tax_ids", "other_tax_id"], "value_confidence"),
    (["vendor_candidate", "website"], ["vendor_candidate", "website"], "value_confidence"),
    (["vendor_candidate", "phone"], ["vendor_candidate", "phone"], "value_confidence"),
    (["vendor_candidate", "email"], ["vendor_candidate", "email"], "value_confidence"),
]


def _get(data: dict, path: list[str]) -> dict:
    node = data
    for key in path:
        node = node[key]
    return node


def _set(target: dict, path: list[str], value: dict) -> None:
    node = target
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value


def _flatten_entry(src: dict, kind: str) -> dict:
    if kind == "company_name":
        return {
            "value": src["value"],
            "present": src["present"],
            "inferred": src["inferred"],
            "confidence": src["confidence"],
        }
    if kind == "value_confidence":
        return {"value": src["value"], "confidence": src["confidence"]}
    raise ValueError(f"unknown flatten kind: {kind!r}")


def flatten_vendor_candidate(extractor: dict) -> dict:
    """Walk the FIELDS_TO_FLATTEN table. Evidence is never emitted.

    Returns `{"vendor_candidate": {...}}` — only the `vendor_candidate` subtree
    shaped in schema order (company_name, address, tax_ids, website, phone, email).
    """
    # Seed the shape in schema order so key emission is deterministic.
    shaped: dict = {
        "vendor_candidate": {
            "company_name": None,
            "address": {
                "street_1": None, "street_2": None, "city": None,
                "state": None, "postal_code": None, "country": None,
            },
            "tax_ids": {
                "ein": None, "state_tax_id": None, "vat_id": None, "other_tax_id": None,
            },
            "website": None, "phone": None, "email": None,
        }
    }
    for ext_path, final_path, kind in FIELDS_TO_FLATTEN:
        src = _get(extractor, ext_path)
        _set(shaped, final_path, _flatten_entry(src, kind))
    return shaped["vendor_candidate"]
