"""T015 (US1): contract-level tests for the v1.3.0 ``semantic_table_truth.schema.json``.

Covers the 24 accept/reject cases pinned by spec FR-002 / FR-003 / FR-004,
Clarifications Q9 / Q11 / Q27 / Q28 / Q41, and security-clarify Q-SEC-2/B
(cases ``q``-``x``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    REPO_ROOT
    / "contracts"
    / "stage1_vendor_identity"
    / "v1.3.0"
    / "semantic_table_truth.schema.json"
)


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _is_valid(validator: Draft202012Validator, doc: dict) -> bool:
    return not list(validator.iter_errors(doc))


# ---------------------------------------------------------------------------
# Cases (a)-(p): top-level + row shape acceptance/rejection.
# ---------------------------------------------------------------------------


def test_a_good_single_row_with_all_optional_cells(validator: Draft202012Validator) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [
            {
                "row_id": "row-1",
                "required_row_text_tokens": ["widget"],
                "quantity": "1",
                "description": "widget assembly",
                "unit_price": "21.00",
                "amount": "21.00",
            }
        ],
    }
    assert _is_valid(validator, doc)


def test_b_good_multi_row_text_tokens_only(validator: Draft202012Validator) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [
            {"row_id": "row-1", "required_row_text_tokens": ["alpha"]},
            {"row_id": "row-2", "required_row_text_tokens": ["beta", "gamma"]},
        ],
    }
    assert _is_valid(validator, doc)


def test_c_missing_top_level_document_id(validator: Draft202012Validator) -> None:
    doc = {"rows": [{"row_id": "row-1", "required_row_text_tokens": ["x"]}]}
    assert not _is_valid(validator, doc)


def test_d_missing_top_level_rows(validator: Draft202012Validator) -> None:
    doc = {"document_id": "inv_001_hard"}
    assert not _is_valid(validator, doc)


def test_e_empty_rows_array(validator: Draft202012Validator) -> None:
    doc = {"document_id": "inv_001_hard", "rows": []}
    assert not _is_valid(validator, doc)


def test_f_row_missing_row_id(validator: Draft202012Validator) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [{"required_row_text_tokens": ["x"]}],
    }
    assert not _is_valid(validator, doc)


def test_g_row_missing_required_row_text_tokens(validator: Draft202012Validator) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [{"row_id": "row-1"}],
    }
    assert not _is_valid(validator, doc)


def test_h_row_with_empty_required_row_text_tokens_array(
    validator: Draft202012Validator,
) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [{"row_id": "row-1", "required_row_text_tokens": []}],
    }
    assert not _is_valid(validator, doc)


def test_i_row_with_empty_string_token_inside_tokens(
    validator: Draft202012Validator,
) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [{"row_id": "row-1", "required_row_text_tokens": [""]}],
    }
    assert not _is_valid(validator, doc)


def test_j_row_with_unit_price_currency_symbol_rejected(
    validator: Draft202012Validator,
) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [
            {
                "row_id": "row-1",
                "required_row_text_tokens": ["x"],
                "unit_price": "$21.00",
            }
        ],
    }
    assert not _is_valid(validator, doc)


def test_k_row_with_unit_price_insufficient_cents_rejected(
    validator: Draft202012Validator,
) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [
            {
                "row_id": "row-1",
                "required_row_text_tokens": ["x"],
                "unit_price": "21.0",
            }
        ],
    }
    assert not _is_valid(validator, doc)


def test_l_row_with_unit_price_two_decimals_accepted(
    validator: Draft202012Validator,
) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [
            {
                "row_id": "row-1",
                "required_row_text_tokens": ["x"],
                "unit_price": "21.00",
            }
        ],
    }
    assert _is_valid(validator, doc)


def test_m_row_with_amount_comma_grouping_rejected(
    validator: Draft202012Validator,
) -> None:
    # Sidecar requires ``^\d+\.\d{2}$`` (no commas authored).
    doc = {
        "document_id": "inv_001_hard",
        "rows": [
            {
                "row_id": "row-1",
                "required_row_text_tokens": ["x"],
                "amount": "1,234.56",
            }
        ],
    }
    assert not _is_valid(validator, doc)


def test_n_row_with_additional_unknown_property_rejected(
    validator: Draft202012Validator,
) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [
            {
                "row_id": "row-1",
                "required_row_text_tokens": ["x"],
                "color": "red",
            }
        ],
    }
    assert not _is_valid(validator, doc)


def test_o_sidecar_with_additional_top_level_property_rejected(
    validator: Draft202012Validator,
) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [{"row_id": "row-1", "required_row_text_tokens": ["x"]}],
        "unexpected": "value",
    }
    assert not _is_valid(validator, doc)


def test_p_optional_schema_version_accepted(validator: Draft202012Validator) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "schema_version": "1.3.0",
        "rows": [{"row_id": "row-1", "required_row_text_tokens": ["x"]}],
    }
    assert _is_valid(validator, doc)


# ---------------------------------------------------------------------------
# Cases (q)-(x): security-clarify Q-SEC-2/B safety-pattern assertions for
# `document_id` and `row_id`.
# ---------------------------------------------------------------------------


def test_q_canonical_document_id_accepted(validator: Draft202012Validator) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [{"row_id": "row-1", "required_row_text_tokens": ["x"]}],
    }
    assert _is_valid(validator, doc)


def test_r_canonical_row_id_accepted(validator: Draft202012Validator) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [{"row_id": "row-1", "required_row_text_tokens": ["x"]}],
    }
    assert _is_valid(validator, doc)


def test_s_path_traversal_document_id_rejected(
    validator: Draft202012Validator,
) -> None:
    doc = {
        "document_id": "../etc/passwd",
        "rows": [{"row_id": "row-1", "required_row_text_tokens": ["x"]}],
    }
    assert not _is_valid(validator, doc)


def test_t_row_id_exceeds_max_length_rejected(
    validator: Draft202012Validator,
) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [
            {
                "row_id": "a" * 65,
                "required_row_text_tokens": ["x"],
            }
        ],
    }
    assert not _is_valid(validator, doc)


def test_u_row_id_with_internal_whitespace_rejected(
    validator: Draft202012Validator,
) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [{"row_id": "row 1", "required_row_text_tokens": ["x"]}],
    }
    assert not _is_valid(validator, doc)


def test_v_row_id_with_period_rejected(validator: Draft202012Validator) -> None:
    doc = {
        "document_id": "inv_001_hard",
        "rows": [{"row_id": "row.1", "required_row_text_tokens": ["x"]}],
    }
    assert not _is_valid(validator, doc)


def test_w_row_id_with_trailing_whitespace_rejected(
    validator: Draft202012Validator,
) -> None:
    # Trailing space — outside [A-Za-z0-9_-]; covers Q-SEC-2/B whitespace rejection.
    doc = {
        "document_id": "inv_001_hard",
        "rows": [{"row_id": "row ", "required_row_text_tokens": ["x"]}],
    }
    assert not _is_valid(validator, doc)


def test_x_empty_document_id_rejected(validator: Draft202012Validator) -> None:
    doc = {
        "document_id": "",
        "rows": [{"row_id": "row-1", "required_row_text_tokens": ["x"]}],
    }
    assert not _is_valid(validator, doc)
