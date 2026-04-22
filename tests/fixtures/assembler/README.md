# Assembler fixtures

Minimal hand-crafted input pairs under `tests/fixtures/assembler/` consumed by the
`009-final-payload` test suite. Each folder holds `edge_extraction_output.json` and
`routing_decision.json`; the assembler never reads `source.pdf` or
`preprocess_output.json`, so those are omitted.

Per `specs/009-final-payload/research.md` §Decision 10:

| Fixture folder | Purpose | Extractor shape | Routing shape |
|---|---|---|---|
| `happy_grounded/` | US1–US5 golden path | Grounded company_name (`present=true, inferred=false`), full address, one EIN, email. | `decision=edge_accept`, `manual_review_required=false`, `review_reason=null`. |
| `missing_name_inferred/` | US4 AS-2 + SC-002 | company_name `present=false, inferred=true, confidence≤0.5`; partial address. | `decision=edge_review_required`, `manual_review_required=true`, `review_reason="company_name_inferred"`. |
| `empty_extraction_spam_gate/` | US4 AS-6 | All-null vendor_candidate. | `decision=edge_review_required`, `review_reason="post_extraction_spam_gate_failed"`. |
| `contract_drift/` | US6 AS-4 | Extractor `contract_set_version = "1.1.0"`. | Routing `contract_set_version = "1.0.0"`. |
| `document_id_mismatch/` | US6 AS-3 | `document_id = "inv_005"`. | `document_id = "inv_006"`. |
| `routing_contradiction/` | US6 AS-6 (FR-016) | Normal grounded extractor. | `decision=edge_accept` but `manual_review_required=true, review_reason="company_name_inferred"`. |
| `schema_invalid_extractor/` | US6 AS-5 | Extractor JSON missing required `status` field. | Valid routing. |

Fixtures satisfy only the fields the assembler reads realistically; other
schema-required fields are filled with valid defaults to keep diffs small.
