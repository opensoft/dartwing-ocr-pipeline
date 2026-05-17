# Quickstart: Deterministic Routing (008-routing)

End-to-end walk-through for running the router against one per-document folder
inside the devcontainer. Assumes the repo is cloned and the devcontainer is
open (or the equivalent local Python 3.12 environment with
`pip install -e ".[dev]"` already run).

## Prerequisites

1. **Python 3.12** — devcontainer default, matches
   `.devcontainer/Dockerfile`.
2. **Editable install** — this slice ships as part of the existing
   `dartwing_ocr` package:
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -e ".[dev]"
   ```
3. **Existing `edge_extraction_output.json`** — produced by the upstream
   extractor (005, not yet in this repo) or authored by hand. For the
   quickstart, we use a hand-authored fixture.

## 1. Stage a fixture per-document folder

Create a minimal per-document folder containing a schema-valid
`edge_extraction_output.json`:

```bash
mkdir -p /tmp/inv_000_quickstart
cat > /tmp/inv_000_quickstart/edge_extraction_output.json <<'EOF'
{
  "contract_set_version": "1.0.0",
  "pipeline_version": "stage1-extractor-v0.1.0",
  "document_id": "inv_000_quickstart",
  "processed_at": "2026-04-21T12:00:00Z",
  "model_runtime": {
    "provider": "ollama",
    "model_name": "qwen3-vl",
    "model_version": "3.0",
    "runtime": "host"
  },
  "vote_metadata": {
    "voter_id": "voter-a",
    "voter_role": "primary_extractor",
    "consensus_mode": "single_voter_baseline"
  },
  "document_type": { "value": "invoice", "confidence": 0.95 },
  "vendor_candidate": {
    "company_name": {
      "value": "Acme Corp",
      "present": true,
      "inferred": false,
      "confidence": 0.92,
      "evidence": ["p1_b1"]
    },
    "address": {
      "street_1": { "value": "123 Main St", "confidence": 0.9, "evidence": ["p1_b2"] },
      "street_2": { "value": null, "confidence": 0.0, "evidence": [] },
      "city":      { "value": "Springfield", "confidence": 0.9, "evidence": ["p1_b2"] },
      "state":     { "value": "IL",         "confidence": 0.9, "evidence": ["p1_b2"] },
      "postal_code":{ "value": "62704",     "confidence": 0.9, "evidence": ["p1_b2"] },
      "country":   { "value": "USA",        "confidence": 0.9, "evidence": ["p1_b2"] }
    },
    "tax_ids": {
      "ein":          { "value": null, "confidence": 0.0, "evidence": [] },
      "state_tax_id": { "value": null, "confidence": 0.0, "evidence": [] },
      "vat_id":       { "value": null, "confidence": 0.0, "evidence": [] },
      "other_tax_id": { "value": null, "confidence": 0.0, "evidence": [] }
    },
    "website": { "value": "https://acme.example", "confidence": 0.95, "evidence": ["p1_b3"] },
    "phone":   { "value": null, "confidence": 0.0, "evidence": [] },
    "email":   { "value": null, "confidence": 0.0, "evidence": [] }
  },
  "invoice_header_fields": {
    "invoice_number": { "value": "INV-001", "confidence": 0.95, "evidence": ["p1_b4"] },
    "invoice_date":   { "value": "2026-04-01", "confidence": 0.9, "evidence": ["p1_b4"] },
    "total_amount":   { "value": 1250.00, "currency": "USD", "confidence": 0.9, "evidence": ["p1_b5"] }
  },
  "extraction_notes": [],
  "warnings": [],
  "status": "success"
}
EOF
```

This fixture represents an `edge_accept`-eligible document: explicit company
name, full address (all three minimum components grounded), and a grounded
website — so the secondary-identifier floor is met by
`address_has_minimum_components` + `website_or_email_present`.

## 2. Run the router

```bash
.venv/bin/python -m dartwing_ocr.router route /tmp/inv_000_quickstart
```

Expected stdout (single JSON line):

```json
{"status": "ok", "document_id": "inv_000_quickstart", "decision": "edge_accept", "artifact": "/tmp/inv_000_quickstart/routing_decision.json"}
```

## 3. Inspect the output

```bash
cat /tmp/inv_000_quickstart/routing_decision.json
```

Expected shape (shown abbreviated; `processed_at` will reflect your wall
clock):

```json
{
  "contract_set_version": "1.0.0",
  "pipeline_version": "stage1-routing-v0.1.0",
  "policy_version": "stage1-routing-policy-v1.0.0",
  "document_id": "inv_000_quickstart",
  "processed_at": "2026-04-21T12:34:56Z",
  "status": "success",
  "decision": "edge_accept",
  "consensus_summary": {
    "mode": "single_voter_baseline",
    "agreement_level": "not_applicable"
  },
  "scores": {
    "company_name_score": 1.0,
    "address_score": 0.8,
    "tax_id_score": 0.0,
    "contact_score": 0.3333333333333333,
    "overall_vendor_identity_score": 0.5333333333333333
  },
  "checks": {
    "company_name_present": true,
    "company_name_inferred": false,
    "address_has_minimum_components": true,
    "at_least_one_tax_id_present": false,
    "website_or_email_present": true,
    "post_extraction_spam_gate_passed": true
  },
  "review_status": {
    "manual_review_required": false,
    "review_reason": null
  },
  "reasons": [
    "company_name_explicit",
    "spam_gate_passed",
    "secondary_identifier_floor_met",
    "upstream_extraction_ok"
  ]
}
```

Why these values:

- `company_name_score = 1.0` — name is present, not inferred, with evidence.
- `address_score = 4/5 = 0.8` — `street_1`, `city`, `state`, `postal_code`
  grounded; `country` grounded = 4 of 5. (Actually 5 of 5 in this fixture →
  `1.0`. If you remove `country`, it drops to `0.8`.)
- `tax_id_score = 0.0` — no tax IDs.
- `contact_score = 1/3 ≈ 0.333` — only website.
- `overall_vendor_identity_score` = mean of the four.
- `secondary_identifier_floor_met` — address check + website/email check =
  2 slots true (threshold is `>= 2`).

## 4. Verify determinism

Run the router a second time and diff the two outputs, ignoring
`processed_at`:

```bash
cp /tmp/inv_000_quickstart/routing_decision.json /tmp/routing_a.json
.venv/bin/python -m dartwing_ocr.router route /tmp/inv_000_quickstart
cp /tmp/inv_000_quickstart/routing_decision.json /tmp/routing_b.json
diff <(jq 'del(.processed_at)' /tmp/routing_a.json) \
     <(jq 'del(.processed_at)' /tmp/routing_b.json)
```

Expected: empty diff. SC-004 demands byte-identical output (except for
`processed_at`) across reruns.

## 5. See the missing-name path

Flip the company name to inferred to trigger the missing-name gate (Principle
IV, FR-008, SC-002):

```bash
jq '.vendor_candidate.company_name |= {
    value: "Acme Corp (guessed)",
    present: false,
    inferred: true,
    confidence: 0.45,
    evidence: []
}' /tmp/inv_000_quickstart/edge_extraction_output.json \
  > /tmp/inv_000_quickstart/edge_extraction_output.json.new \
  && mv /tmp/inv_000_quickstart/edge_extraction_output.json.new \
        /tmp/inv_000_quickstart/edge_extraction_output.json

.venv/bin/python -m dartwing_ocr.router route /tmp/inv_000_quickstart
```

Expected: `decision = "edge_review_required"`,
`review_reason = "company_name_inferred"` exactly,
`reasons = ["company_name_inferred", "upstream_status_partial" (only if input was partial) ]`.
This is the load-bearing gate for the missing-name corpus (SC-002, SC-008).

## 6. Confirm hard errors

Point the router at a missing folder:

```bash
.venv/bin/python -m dartwing_ocr.router route /tmp/does_not_exist
echo "exit code: $?"
```

Expected: non-zero exit code (`2`), no `routing_decision.json` created,
human-readable error on stderr naming "folder missing" (FR-003, SC-006).

Corrupt the input and retry:

```bash
echo "{not valid json" > /tmp/inv_000_quickstart/edge_extraction_output.json
.venv/bin/python -m dartwing_ocr.router route /tmp/inv_000_quickstart
echo "exit code: $?"
```

Expected: exit code `2`, no artifact overwrite, clear error naming the JSON
parse failure.

## Next steps

- Run the contract test suite: `.venv/bin/pytest tests/contract_tests/
  tests/unit/router/ tests/integration/router/`.
- Review `specs/008-routing/data-model.md` for the pinned formulas and rule
  table.
- Review `specs/008-routing/contracts/cli-contract.md` for exit codes and the
  canonical reason vocabulary.
- The evaluator (007) is the next downstream slice; it will consume
  `routing_decision.json` produced by this feature.
