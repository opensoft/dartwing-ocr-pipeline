"""Derive the six ``checks`` booleans for ``routing_decision.json``.

All booleans follow the same grounding rule (research.md + FR-009–FR-013):
a field is "grounded" iff ``value is not None AND len(evidence) >= 1``. The
extractor's ``confidence`` numbers are never consulted (FR-018).

Functions here are pure — they take the parsed input dict and return a plain
dict of booleans. No filesystem, no rule logic, no policy decisions.
"""
from __future__ import annotations

from typing import Any

_ADDRESS_MINIMUM_COMPONENTS = ("city", "state", "postal_code")
_TAX_ID_SLOTS = ("ein", "state_tax_id", "vat_id", "other_tax_id")


def is_grounded(field: Any) -> bool:
    """Return True iff ``field`` is a dict with non-null value and >=1 evidence."""
    if not isinstance(field, dict):
        return False
    if field.get("value") is None:
        return False
    evidence = field.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 1:
        return False
    return True


def _company_name_present(input_dict: dict) -> bool:
    cn = input_dict.get("vendor_candidate", {}).get("company_name", {})
    return bool(cn.get("present", False))


def _company_name_inferred(input_dict: dict) -> bool:
    cn = input_dict.get("vendor_candidate", {}).get("company_name", {})
    return bool(cn.get("inferred", False))


def _address_has_minimum_components(input_dict: dict) -> bool:
    address = input_dict.get("vendor_candidate", {}).get("address", {})
    return all(is_grounded(address.get(slot)) for slot in _ADDRESS_MINIMUM_COMPONENTS)


def _at_least_one_tax_id_present(input_dict: dict) -> bool:
    tax_ids = input_dict.get("vendor_candidate", {}).get("tax_ids", {})
    return any(is_grounded(tax_ids.get(slot)) for slot in _TAX_ID_SLOTS)


def _website_or_email_present(input_dict: dict) -> bool:
    vc = input_dict.get("vendor_candidate", {})
    return is_grounded(vc.get("website")) or is_grounded(vc.get("email"))


def _post_extraction_spam_gate_passed(input_dict: dict) -> bool:
    """Pass iff ANY structural vendor_candidate field has a non-null value.

    Fails iff every structural field is null simultaneously (FR-013):
    ``company_name.value is None`` AND every address component value is null
    AND every tax_id value is null AND ``website`` / ``phone`` / ``email``
    values are all null.
    """
    vc = input_dict.get("vendor_candidate", {})

    def _value_is_null(field: Any) -> bool:
        return not isinstance(field, dict) or field.get("value") is None

    if not _value_is_null(vc.get("company_name")):
        return True
    address = vc.get("address", {})
    for slot in ("street_1", "street_2", "city", "state", "postal_code", "country"):
        if not _value_is_null(address.get(slot)):
            return True
    tax_ids = vc.get("tax_ids", {})
    for slot in _TAX_ID_SLOTS:
        if not _value_is_null(tax_ids.get(slot)):
            return True
    for slot in ("website", "phone", "email"):
        if not _value_is_null(vc.get(slot)):
            return True
    return False


def phone_is_grounded(input_dict: dict) -> bool:
    """Whether ``vendor_candidate.phone`` is grounded (independent floor slot)."""
    return is_grounded(input_dict.get("vendor_candidate", {}).get("phone"))


def compute_checks(input_dict: dict) -> dict:
    """Return the six ``checks`` booleans in the schema's ``required`` order."""
    return {
        "company_name_present": _company_name_present(input_dict),
        "company_name_inferred": _company_name_inferred(input_dict),
        "address_has_minimum_components": _address_has_minimum_components(input_dict),
        "at_least_one_tax_id_present": _at_least_one_tax_id_present(input_dict),
        "website_or_email_present": _website_or_email_present(input_dict),
        "post_extraction_spam_gate_passed": _post_extraction_spam_gate_passed(
            input_dict
        ),
    }
