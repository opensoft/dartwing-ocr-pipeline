"""T013: Unit tests for the six ``checks`` booleans.

Each test calls ``compute_checks`` with a minimal in-memory dict built to
isolate one slot. No filesystem, no pipeline, no rules.
"""
from __future__ import annotations

from dartwing_ocr.router.checks import (
    compute_checks,
    is_grounded,
    phone_is_grounded,
)


def _grounded(value, evidence_ids=("p0_b1",)):
    return {"value": value, "confidence": 0.9, "evidence": list(evidence_ids)}


def _null_field():
    return {"value": None, "confidence": 0.0, "evidence": []}


def _vendor_candidate(
    *,
    company_name=None,
    address=None,
    tax_ids=None,
    website=None,
    phone=None,
    email=None,
):
    return {
        "company_name": company_name
        or {
            "value": None,
            "present": False,
            "inferred": False,
            "confidence": 0.0,
            "evidence": [],
        },
        "address": address
        or {slot: _null_field() for slot in (
            "street_1", "street_2", "city", "state", "postal_code", "country",
        )},
        "tax_ids": tax_ids
        or {slot: _null_field() for slot in (
            "ein", "state_tax_id", "vat_id", "other_tax_id",
        )},
        "website": website or _null_field(),
        "phone": phone or _null_field(),
        "email": email or _null_field(),
    }


def _input(vendor_candidate):
    return {"vendor_candidate": vendor_candidate}


# -- is_grounded helper -----------------------------------------------------

def test_is_grounded_null_value_is_not_grounded():
    assert is_grounded({"value": None, "evidence": ["p0_b1"]}) is False


def test_is_grounded_empty_evidence_is_not_grounded():
    assert is_grounded({"value": "x", "evidence": []}) is False


def test_is_grounded_non_null_plus_nonempty_evidence_is_grounded():
    assert is_grounded({"value": "x", "evidence": ["p0_b1"]}) is True


def test_is_grounded_non_dict_is_not_grounded():
    assert is_grounded(None) is False
    assert is_grounded("x") is False


# -- company_name_present / company_name_inferred ---------------------------

def test_company_name_present_and_inferred_are_direct_copies():
    inp = _input(_vendor_candidate(company_name={
        "value": "Acme", "present": True, "inferred": False,
        "confidence": 0.9, "evidence": ["p0_b1"],
    }))
    checks = compute_checks(inp)
    assert checks["company_name_present"] is True
    assert checks["company_name_inferred"] is False


def test_company_name_inferred_true_reflects():
    inp = _input(_vendor_candidate(company_name={
        "value": "Guess", "present": False, "inferred": True,
        "confidence": 0.3, "evidence": ["p0_b1"],
    }))
    checks = compute_checks(inp)
    assert checks["company_name_present"] is False
    assert checks["company_name_inferred"] is True


# -- address_has_minimum_components -----------------------------------------

def test_address_requires_city_state_postal_all_grounded():
    address = {slot: _null_field() for slot in (
        "street_1", "street_2", "city", "state", "postal_code", "country",
    )}
    address["city"] = _grounded("Portland")
    address["state"] = _grounded("OR")
    address["postal_code"] = _grounded("97201")
    inp = _input(_vendor_candidate(address=address))
    assert compute_checks(inp)["address_has_minimum_components"] is True


def test_address_missing_postal_is_insufficient():
    address = {slot: _null_field() for slot in (
        "street_1", "street_2", "city", "state", "postal_code", "country",
    )}
    address["city"] = _grounded("Portland")
    address["state"] = _grounded("OR")
    inp = _input(_vendor_candidate(address=address))
    assert compute_checks(inp)["address_has_minimum_components"] is False


def test_address_country_only_is_insufficient():
    address = {slot: _null_field() for slot in (
        "street_1", "street_2", "city", "state", "postal_code", "country",
    )}
    address["country"] = _grounded("US")
    inp = _input(_vendor_candidate(address=address))
    assert compute_checks(inp)["address_has_minimum_components"] is False


# -- at_least_one_tax_id_present --------------------------------------------

def test_at_least_one_tax_id_grounded_passes():
    tax_ids = {slot: _null_field() for slot in (
        "ein", "state_tax_id", "vat_id", "other_tax_id",
    )}
    tax_ids["ein"] = _grounded("12-3456789")
    inp = _input(_vendor_candidate(tax_ids=tax_ids))
    assert compute_checks(inp)["at_least_one_tax_id_present"] is True


def test_tax_id_with_value_but_empty_evidence_does_not_count():
    tax_ids = {slot: _null_field() for slot in (
        "ein", "state_tax_id", "vat_id", "other_tax_id",
    )}
    tax_ids["ein"] = {"value": "12-3456789", "confidence": 0.9, "evidence": []}
    inp = _input(_vendor_candidate(tax_ids=tax_ids))
    assert compute_checks(inp)["at_least_one_tax_id_present"] is False


def test_all_tax_ids_null_is_false():
    inp = _input(_vendor_candidate())
    assert compute_checks(inp)["at_least_one_tax_id_present"] is False


# -- website_or_email_present -----------------------------------------------

def test_website_alone_satisfies_website_or_email():
    inp = _input(_vendor_candidate(website=_grounded("acme.example.com")))
    assert compute_checks(inp)["website_or_email_present"] is True


def test_email_alone_satisfies_website_or_email():
    inp = _input(_vendor_candidate(email=_grounded("a@b.example.com")))
    assert compute_checks(inp)["website_or_email_present"] is True


def test_both_website_and_email_counts_as_single_true():
    inp = _input(_vendor_candidate(
        website=_grounded("acme.example.com"),
        email=_grounded("a@b.example.com"),
    ))
    assert compute_checks(inp)["website_or_email_present"] is True


def test_neither_website_nor_email_is_false():
    inp = _input(_vendor_candidate())
    assert compute_checks(inp)["website_or_email_present"] is False


# -- post_extraction_spam_gate_passed ---------------------------------------

def test_spam_gate_fails_on_all_null():
    inp = _input(_vendor_candidate())
    inp["vendor_candidate"]["company_name"] = {
        "value": None, "present": False, "inferred": False,
        "confidence": 0.0, "evidence": [],
    }
    assert compute_checks(inp)["post_extraction_spam_gate_passed"] is False


def test_spam_gate_passes_when_any_field_has_non_null_value():
    inp = _input(_vendor_candidate(phone=_grounded("+1-503-555-0100")))
    assert compute_checks(inp)["post_extraction_spam_gate_passed"] is True


def test_spam_gate_passes_on_company_name_value_even_if_inferred():
    inp = _input(_vendor_candidate(company_name={
        "value": "Guess", "present": False, "inferred": True,
        "confidence": 0.3, "evidence": ["p0_b1"],
    }))
    assert compute_checks(inp)["post_extraction_spam_gate_passed"] is True


# -- phone_is_grounded helper -----------------------------------------------

def test_phone_grounded_true_when_value_and_evidence():
    inp = _input(_vendor_candidate(phone=_grounded("+1-503-555-0100")))
    assert phone_is_grounded(inp) is True


def test_phone_grounded_false_when_null():
    inp = _input(_vendor_candidate())
    assert phone_is_grounded(inp) is False


# -- key ordering -----------------------------------------------------------

def test_checks_keys_in_schema_required_order():
    inp = _input(_vendor_candidate())
    checks = compute_checks(inp)
    assert list(checks.keys()) == [
        "company_name_present",
        "company_name_inferred",
        "address_has_minimum_components",
        "at_least_one_tax_id_present",
        "website_or_email_present",
        "post_extraction_spam_gate_passed",
    ]
