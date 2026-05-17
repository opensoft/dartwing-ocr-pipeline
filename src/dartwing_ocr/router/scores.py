"""Derive the five ``scores`` values for ``routing_decision.json``.

Formulas are pinned by FR-017 + clarification Q2 + research.md Decision 5:

- ``company_name_score`` = 1.0 iff ``present == true`` AND ``inferred == false``
  AND evidence non-empty; else 0.0 (binary).
- ``address_score`` = grounded components out of 5 over
  ``{street_1, city, state, postal_code, country}``. ``street_2`` does NOT
  contribute (research Decision 5).
- ``tax_id_score`` = grounded slots out of 4 over
  ``{ein, state_tax_id, vat_id, other_tax_id}``.
- ``contact_score`` = grounded fields out of 3 over ``{website, phone, email}``.
- ``overall_vendor_identity_score`` = arithmetic mean of the four above
  (equal weight).

Confidence values MUST NOT appear anywhere here (FR-018).
"""
from __future__ import annotations

from dartwing_ocr.router.checks import is_grounded

_ADDRESS_SCORE_SLOTS = ("street_1", "city", "state", "postal_code", "country")
_TAX_ID_SCORE_SLOTS = ("ein", "state_tax_id", "vat_id", "other_tax_id")
_CONTACT_SCORE_SLOTS = ("website", "phone", "email")


def _company_name_score(input_dict: dict) -> float:
    cn = input_dict.get("vendor_candidate", {}).get("company_name", {})
    if not isinstance(cn, dict):
        return 0.0
    if not cn.get("present", False):
        return 0.0
    if cn.get("inferred", False):
        return 0.0
    evidence = cn.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 1:
        return 0.0
    return 1.0


def _address_score(input_dict: dict) -> float:
    address = input_dict.get("vendor_candidate", {}).get("address", {})
    grounded = sum(1 for slot in _ADDRESS_SCORE_SLOTS if is_grounded(address.get(slot)))
    return grounded / len(_ADDRESS_SCORE_SLOTS)


def _tax_id_score(input_dict: dict) -> float:
    tax_ids = input_dict.get("vendor_candidate", {}).get("tax_ids", {})
    grounded = sum(1 for slot in _TAX_ID_SCORE_SLOTS if is_grounded(tax_ids.get(slot)))
    return grounded / len(_TAX_ID_SCORE_SLOTS)


def _contact_score(input_dict: dict) -> float:
    vc = input_dict.get("vendor_candidate", {})
    grounded = sum(1 for slot in _CONTACT_SCORE_SLOTS if is_grounded(vc.get(slot)))
    return grounded / len(_CONTACT_SCORE_SLOTS)


def compute_scores(input_dict: dict) -> dict:
    """Return the five scores in the schema's ``required`` order."""
    cns = _company_name_score(input_dict)
    adr = _address_score(input_dict)
    tid = _tax_id_score(input_dict)
    ctc = _contact_score(input_dict)
    overall = (cns + adr + tid + ctc) / 4.0
    return {
        "company_name_score": cns,
        "address_score": adr,
        "tax_id_score": tid,
        "contact_score": ctc,
        "overall_vendor_identity_score": overall,
    }
