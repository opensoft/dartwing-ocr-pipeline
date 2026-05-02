# Stage 1 Schemas

This document records the first draft JSON contracts for stage 1.

> **Machine-readable layer**: the JSON shapes described below are enforced in code by the validator in `src/ledgerlinc_ocr/validator/` against JSON Schema files under `contracts/stage1_vendor_identity/v1.1.0/` (current). The frozen v1.0.0 artifacts are preserved unchanged under `contracts/stage1_vendor_identity/v1.0.0/`. Both layers are updated together via the amendment path in `contracts/stage1_vendor_identity/AMENDMENTS.md`. Every persisted artifact carries a `contract_set_version` field (semver, currently `1.1.0`) distinct from `pipeline_version` (pipeline build) and `policy_version` (routing policy).
>
> **Evidence packet (v1.1.0 addition)**: an additional artifact shape is defined at `contracts/stage1_vendor_identity/v1.1.0/evidence_packet.schema.json`, produced by `ledgerlinc_ocr.evidence_packet.assemble_from_preprocess` and — at DEBUG logger level only — persisted as `<folder>/evidence_packet.json`. The folder contract treats `evidence_packet.json` as an *optional* reserved filename (unlike the four required per-document artifacts), so folders without it still validate.

## Design Principles

- keep preprocessing deterministic and model-agnostic
- keep extraction rich enough for debugging and evidence tracing
- keep routing deterministic and rule-based
- keep final payload clean enough for downstream systems
- preserve whether company name was explicit or inferred
- use `null` for missing fields rather than empty strings

## Architecture Note

The target pipeline architecture is now ensemble-based.

That means the long-term design expects:

- a Trijunction evidence packet
- multiple model votes
- deterministic consensus before final routing

The stage 1 schema drafts below remain the baseline contracts to code against first. They should be implemented so they can later carry richer Trijunction evidence and multi-voter metadata without breaking the downstream final payload.

## `preprocess_output`

Purpose:

- represent OCR and layout structure before business interpretation
- provide the basis for a future Trijunction evidence packet

```json
{
  "document_id": "inv_001",
  "source_type": "pdf",
  "source_file": "source.pdf",
  "page_count": 2,
  "pages": [
    {
      "page_number": 1,
      "width": 2550,
      "height": 3300,
      "rotation_detected": 0,
      "blocks": [
        {
          "block_id": "p1_b1",
          "block_type": "text",
          "bbox": [120, 80, 980, 210],
          "reading_order": 1,
          "text": "ACME Industrial Supply LLC",
          "confidence": 0.97
        }
      ],
      "raw_ocr_lines": [
        {
          "line_id": "p1_l1",
          "bbox": [120, 80, 980, 210],
          "text": "ACME Industrial Supply LLC",
          "confidence": 0.97
        }
      ]
    }
  ],
  "document_text": "full text in reading order",
  "tables": [],
  "quality": {
    "scan_quality": "good",
    "skew_detected": false,
    "noise_level": "low"
  },
  "ingestion_sources": {
    "paddleocr_vl": {
      "enabled": true,
      "status": "success"
    },
    "falcon_ocr": {
      "enabled": false,
      "status": "not_implemented"
    },
    "falcon_perception": {
      "enabled": false,
      "status": "not_implemented"
    }
  },
  "warnings": []
}
```

**Confidence null allowance (v1.2.0 AMENDMENTS, 2026-04-23)**: `blocks[*].confidence` and `raw_ocr_lines[*].confidence` both accept `null` in addition to a number in `[0.0, 1.0]`; the same allowance applies to the mirrored structural confidence fields in `evidence_packet`. Preprocessing emits `null` (never `0.0`) when the upstream engine omits or cannot provide a schema-valid score for a given block or line — most commonly on a rare parallel-array mismatch where PP-OCRv5 returns one fewer `rec_scores` than `rec_texts`. Numeric values remain bounded to `[0.0, 1.0]`; the widening applies only to the missing/unusable-score case. See `contracts/stage1_vendor_identity/AMENDMENTS.md` v1.2.0 entry and `specs/010-pp-structurev3-preprocessing/spec.md` FR-004 / research R-013.

## `edge_extraction_output`

Purpose:

- represent the edge model's structured extraction before routing rules flatten the output
- preserve either a single extracted result or later multiple voter results and consensus evidence

```json
{
  "document_id": "inv_001",
  "pipeline_version": "stage1-edge-v0.1",
  "processed_at": "2026-04-12T13:15:00Z",
  "model_runtime": {
    "provider": "ollama",
    "model_name": "gemma4-edge",
    "model_version": "current",
    "runtime": "host_ollama_rocm"
  },
  "vote_metadata": {
    "voter_id": "gemma_vote_a",
    "voter_role": "primary_extractor",
    "consensus_mode": "single_voter_baseline"
  },
  "document_type": {
    "value": "invoice",
    "confidence": 0.99
  },
  "vendor_candidate": {
    "company_name": {
      "value": "ACME Industrial Supply LLC",
      "present": true,
      "inferred": false,
      "confidence": 0.94,
      "evidence": ["p1_l1", "p1_b1"]
    },
    "address": {
      "street_1": {
        "value": "123 Main St",
        "confidence": 0.84,
        "evidence": ["p1_l3"]
      },
      "street_2": {
        "value": null,
        "confidence": 0.0,
        "evidence": []
      },
      "city": {
        "value": "Phoenix",
        "confidence": 0.86,
        "evidence": ["p1_l4"]
      },
      "state": {
        "value": "AZ",
        "confidence": 0.90,
        "evidence": ["p1_l4"]
      },
      "postal_code": {
        "value": "85001",
        "confidence": 0.88,
        "evidence": ["p1_l4"]
      },
      "country": {
        "value": "US",
        "confidence": 0.80,
        "evidence": ["p1_l4"]
      }
    },
    "tax_ids": {
      "ein": {
        "value": "12-3456789",
        "confidence": 0.73,
        "evidence": ["p1_l6"]
      },
      "state_tax_id": {
        "value": null,
        "confidence": 0.0,
        "evidence": []
      },
      "vat_id": {
        "value": null,
        "confidence": 0.0,
        "evidence": []
      },
      "other_tax_id": {
        "value": null,
        "confidence": 0.0,
        "evidence": []
      }
    },
    "website": {
      "value": "acmeindustrial.com",
      "confidence": 0.76,
      "evidence": ["p1_l7"]
    },
    "phone": {
      "value": "602-555-0199",
      "confidence": 0.71,
      "evidence": ["p1_l8"]
    },
    "email": {
      "value": "billing@acmeindustrial.com",
      "confidence": 0.78,
      "evidence": ["p1_l9"]
    }
  },
  "invoice_header_fields": {
    "invoice_number": {
      "value": "INV-20481",
      "confidence": 0.96,
      "evidence": ["p1_l12"]
    },
    "invoice_date": {
      "value": "2026-03-18",
      "confidence": 0.95,
      "evidence": ["p1_l13"]
    },
    "total_amount": {
      "value": 1824.55,
      "currency": "USD",
      "confidence": 0.97,
      "evidence": ["p1_l27"]
    }
  },
  "extraction_notes": [],
  "warnings": [],
  "status": "success"
}
```

Missing-name example:

```json
{
  "company_name": {
    "value": "Acme Industrial Supply LLC",
    "present": false,
    "inferred": true,
    "confidence": 0.61,
    "evidence": []
  }
}
```

## `routing_decision`

Purpose:

- represent the deterministic decision about whether the edge result can be accepted or requires manual review
- later, represent field-level or document-level consensus outcomes before final routing

```json
{
  "document_id": "inv_001",
  "pipeline_version": "stage1-edge-v0.1",
  "processed_at": "2026-04-12T13:15:02Z",
  "status": "success",
  "decision": "edge_accept",
  "policy_version": "stage1-routing-v0.1",
  "consensus_summary": {
    "mode": "single_voter_baseline",
    "agreement_level": "not_applicable"
  },
  "scores": {
    "company_name_score": 0.94,
    "address_score": 0.84,
    "tax_id_score": 0.73,
    "contact_score": 0.75,
    "overall_vendor_identity_score": 0.86
  },
  "checks": {
    "company_name_present": true,
    "company_name_inferred": false,
    "address_has_minimum_components": true,
    "at_least_one_tax_id_present": true,
    "website_or_email_present": true,
    "post_extraction_spam_gate_passed": true
  },
  "review_status": {
    "manual_review_required": false,
    "review_reason": null
  },
  "reasons": [
    "explicit company name found",
    "multiple secondary vendor identifiers found"
  ]
}
```

Inferred-name example:

```json
{
  "decision": "edge_review_required",
  "review_status": {
    "manual_review_required": true,
    "review_reason": "company_name_inferred"
  }
}
```

## `final_structured_payload`

Purpose:

- provide the clean downstream handoff object for later system integration and evaluation

```json
{
  "document_id": "inv_001",
  "pipeline_version": "stage1-edge-v0.1",
  "processed_at": "2026-04-12T13:15:00Z",
  "document_type": "invoice",
  "vendor_candidate": {
    "company_name": {
      "value": "ACME Industrial Supply LLC",
      "present": true,
      "inferred": false,
      "confidence": 0.94
    },
    "address": {
      "street_1": {
        "value": "123 Main St",
        "confidence": 0.84
      },
      "street_2": {
        "value": null,
        "confidence": 0.0
      },
      "city": {
        "value": "Phoenix",
        "confidence": 0.86
      },
      "state": {
        "value": "AZ",
        "confidence": 0.90
      },
      "postal_code": {
        "value": "85001",
        "confidence": 0.88
      },
      "country": {
        "value": "US",
        "confidence": 0.80
      }
    },
    "tax_ids": {
      "ein": {
        "value": "12-3456789",
        "confidence": 0.73
      },
      "state_tax_id": {
        "value": null,
        "confidence": 0.0
      },
      "vat_id": {
        "value": null,
        "confidence": 0.0
      },
      "other_tax_id": {
        "value": null,
        "confidence": 0.0
      }
    },
    "website": {
      "value": "acmeindustrial.com",
      "confidence": 0.76
    },
    "phone": {
      "value": "602-555-0199",
      "confidence": 0.71
    },
    "email": {
      "value": "billing@acmeindustrial.com",
      "confidence": 0.78
    }
  },
  "review_status": {
    "manual_review_required": false,
    "review_reason": null
  },
  "quality_summary": {
    "overall_vendor_confidence": 0.86,
    "explicit_name_found": true,
    "consensus_level": "single_voter_baseline",
    "secondary_identifiers_found": [
      "address",
      "ein",
      "website",
      "phone",
      "email"
    ]
  },
  "trace": {
    "source_file": "source.pdf",
    "preprocess_output_file": "preprocess_output.json",
    "edge_extraction_output_file": "edge_extraction_output.json",
    "routing_decision_file": "routing_decision.json"
  }
}
```

## `expected.json`

Purpose:

- hold the human-labeled truth for one document

```json
{
  "document_id": "inv_001",
  "difficulty": "easy",
  "challenge_tags": [
    "explicit_company_name",
    "header_address",
    "clear_ein"
  ],
  "expected_review": {
    "manual_review_required": false,
    "review_reason": null
  },
  "expected_vendor_candidate": {
    "company_name": {
      "value": "ACME Industrial Supply LLC",
      "present": true,
      "inferred": false
    },
    "address": {
      "street_1": "123 Main St",
      "street_2": null,
      "city": "Phoenix",
      "state": "AZ",
      "postal_code": "85001",
      "country": "US"
    },
    "tax_ids": {
      "ein": "12-3456789",
      "state_tax_id": null,
      "vat_id": null,
      "other_tax_id": null
    },
    "website": "acmeindustrial.com",
    "phone": "602-555-0199",
    "email": "billing@acmeindustrial.com"
  },
  "notes": "Vendor name appears clearly in header."
}
```

## `evaluation_document.json`

Purpose:

- record per-document comparison results between expected truth and pipeline output

```json
{
  "document_id": "inv_001",
  "difficulty": "easy",
  "challenge_tags": [
    "explicit_company_name",
    "clear_ein"
  ],
  "comparison_summary": {
    "applicable_field_count": 18,
    "matched_field_count": 17,
    "mismatched_field_count": 1,
    "missing_prediction_count": 0,
    "unexpected_prediction_count": 0,
    "field_accuracy": 0.9444
  },
  "document_pass_fail": {
    "vendor_identity_passed": true,
    "review_routing_passed": true,
    "overall_passed": true
  },
  "field_results": {
    "vendor_candidate.company_name.value": {
      "expected": "ACME Industrial Supply LLC",
      "actual": "ACME Industrial Supply LLC",
      "result": "match"
    },
    "review_status.manual_review_required": {
      "expected": false,
      "actual": false,
      "result": "match"
    }
  },
  "notes": []
}
```

## `evaluation_run_summary.json`

Purpose:

- summarize performance across the entire stage 1 test suite

```json
{
  "run_id": "stage1_eval_2026-04-12_01",
  "pipeline_version": "stage1-edge-v0.1",
  "document_count": 20,
  "overall_metrics": {
    "field_accuracy": 0.87,
    "vendor_identity_pass_rate": 0.80,
    "review_routing_pass_rate": 0.95,
    "overall_document_pass_rate": 0.75
  },
  "consensus_metrics": {
    "single_voter_baseline_runs": 20,
    "majority_vote_documents": 0,
    "split_decision_documents": 0
  },
  "by_difficulty": {
    "easy": {
      "document_count": 5,
      "field_accuracy": 0.96,
      "overall_document_pass_rate": 1.0
    },
    "medium": {
      "document_count": 5,
      "field_accuracy": 0.88,
      "overall_document_pass_rate": 0.8
    },
    "hard": {
      "document_count": 5,
      "field_accuracy": 0.77,
      "overall_document_pass_rate": 0.6
    },
    "missing_name": {
      "document_count": 5,
      "field_accuracy": 0.72,
      "overall_document_pass_rate": 0.6
    }
  },
  "by_field": {
    "company_name.value": 0.80,
    "company_name.present": 0.95,
    "company_name.inferred": 0.95,
    "address.street_1": 0.85,
    "address.city": 0.90,
    "address.state": 0.95,
    "address.postal_code": 0.88,
    "tax_ids.ein": 0.70,
    "tax_ids.state_tax_id": 0.92,
    "tax_ids.vat_id": 1.0,
    "tax_ids.other_tax_id": 0.95,
    "website": 0.84,
    "phone": 0.81,
    "email": 0.79,
    "manual_review_required": 1.0,
    "review_reason": 0.95
  },
  "documents": [
    {
      "document_id": "inv_001",
      "overall_passed": true,
      "field_accuracy": 0.93
    },
    {
      "document_id": "inv_016",
      "overall_passed": false,
      "field_accuracy": 0.67
    }
  ]
}
```
