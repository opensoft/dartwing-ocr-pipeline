# Quickstart: Stage 1 Evaluator & Reporting

**Feature**: 007-evaluator
**Audience**: a developer who has a stage 1 corpus with per-document folders containing `expected.json` and `final_structured_payload.json`, and wants a scored evaluation.

This quickstart runs the evaluator end-to-end in the devcontainer (or any Linux host with Python 3.12 and the project installed in editable mode).

---

## 0. One-time setup

From the repo root:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

No other install steps — the evaluator adds no new third-party dependencies beyond those already pinned in `pyproject.toml`.

Verify the CLI is wired up:

```bash
.venv/bin/python -m dartwing_ocr.evaluator --help
```

You should see the two subcommands: `evaluate document` and `evaluate corpus`.

---

## 1. Evaluate a single document

Assume a per-document folder at `tests/stage1_vendor_identity/inv_001_easy/` containing `expected.json` and `final_structured_payload.json`.

```bash
.venv/bin/python -m dartwing_ocr.evaluator evaluate document \
    tests/stage1_vendor_identity/inv_001_easy
```

On success (exit code `0`):
- `tests/stage1_vendor_identity/inv_001_easy/evaluation_document.json` is written.
- A short human-readable summary is printed to stdout (field accuracy, pass gates, any failing fields).

On hard error (exit code `3`):
- No `evaluation_document.json` is written.
- stderr names the offending file (missing input, schema drift, `document_id` mismatch, or `contract_set_version` drift).

To get the machine-readable outcome instead of the text summary, pass `--json`:

```bash
.venv/bin/python -m dartwing_ocr.evaluator evaluate document \
    tests/stage1_vendor_identity/inv_001_easy --json
```

---

## 2. Inspect `evaluation_document.json`

```bash
jq . tests/stage1_vendor_identity/inv_001_easy/evaluation_document.json
```

Notable structure (full schema: `contracts/stage1_vendor_identity/v1.1.0/evaluation_document.schema.json`):

```json
{
  "contract_set_version": "1.1.0",
  "document_id": "inv_001_easy",
  "difficulty": "easy",
  "challenge_tags": [...],
  "comparison_summary": {
    "applicable_field_count": 14,
    "matched_field_count": 13,
    "mismatched_field_count": 0,
    "missing_prediction_count": 0,
    "unexpected_prediction_count": 0,
    "field_accuracy": 0.964286
  },
  "document_pass_fail": {
    "vendor_identity_passed": true,
    "review_routing_passed": true,
    "overall_passed": true
  },
  "field_results": {
    "company_name.value": {"expected": "Acme Widgets Inc.", "actual": "acme widgets inc", "result": "match"},
    ...
  },
  "notes": []
}
```

Quick interpretation:
- `applicable_field_count` excludes fields that were `null` on both sides (e.g., no VAT ID on a US invoice).
- `matched_field_count` counts **strict** matches only. Partial matches do NOT appear in any `_count` field — they influence `field_accuracy` via the 0.5 weight.
- The `partial_match` count is derivable from `field_results`: count entries whose `result == "partial_match"`.

---

## 3. Evaluate the whole corpus

```bash
.venv/bin/python -m dartwing_ocr.evaluator evaluate corpus \
    tests/stage1_vendor_identity
```

What happens:
1. The evaluator walks each per-document folder under the root.
2. Any folder missing `evaluation_document.json` is evaluated in-process (lazy mode; default).
3. When every per-document result is available, the aggregator writes:
   - `tests/stage1_vendor_identity/evaluation_run_summary.json` (machine-readable; schema pinned).
   - `tests/stage1_vendor_identity/evaluation_run_summary.md` (human-readable; byte-identical to stdout).
4. The same Markdown content is streamed to stdout.

Exit codes:
- `0` — clean completion.
- `3` — any folder's `expected.json` or `final_structured_payload.json` is missing or schema-invalid. No partial summary is written.

To enforce strict aggregation (every folder must already have `evaluation_document.json`):

```bash
.venv/bin/python -m dartwing_ocr.evaluator evaluate corpus \
    tests/stage1_vendor_identity --no-lazy
```

To force full re-evaluation and ignore any cached `evaluation_document.json` (e.g., after evaluator code or scoring weights change without a contract-set-version bump):

```bash
.venv/bin/python -m dartwing_ocr.evaluator evaluate corpus \
    tests/stage1_vendor_identity --refresh
```

---

## 4. Read the run summary

Sample `evaluation_run_summary.md` (the content you see on stdout):

```markdown
# Stage 1 Evaluation Run Summary

- Run ID: run_2026-04-21T14:32:07.123456Z_9f3c1a20
- Document count: 20
- Overall pass rate: 0.850
- Vendor identity pass rate: 0.900
- Review routing pass rate: 0.950
- Field accuracy: 0.927

## By difficulty

| Difficulty | Docs | Field accuracy | Pass rate |
|---|---|---|---|
| easy | 5 | 0.985 | 1.000 |
| medium | 5 | 0.940 | 0.800 |
| hard | 5 | 0.885 | 0.800 |
| missing_name | 5 | 0.910 | 0.800 |

## Failing documents

- inv_007_medium (medium) — company_name.value mismatch; review_reason wrong
- inv_012_hard (hard) — ein missing_prediction; overall score 0.73
- inv_018_missing_name (missing_name) — company_name.present mismatch (predicted true, expected false)
```

The machine-readable `evaluation_run_summary.json` has the same headline numbers plus `by_field` (per-field corpus-wide accuracy) and the full `documents[]` list.

---

## 5. Re-run and verify determinism

```bash
.venv/bin/python -m dartwing_ocr.evaluator evaluate corpus \
    tests/stage1_vendor_identity
cp tests/stage1_vendor_identity/evaluation_run_summary.json /tmp/run_a.json

.venv/bin/python -m dartwing_ocr.evaluator evaluate corpus \
    tests/stage1_vendor_identity
cp tests/stage1_vendor_identity/evaluation_run_summary.json /tmp/run_b.json

# Everything except run_id should match:
diff <(jq 'del(.run_id)' /tmp/run_a.json) <(jq 'del(.run_id)' /tmp/run_b.json)
```

The `diff` should produce no output. Per-document `evaluation_document.json` files are byte-identical across runs (they have no `run_id` field).

---

## 6. Common gotchas

- **`contract_set_version` drift** — if either input reports a version not compatible with the pin (different MAJOR, or MINOR greater than the pin; default pin `"1.1.0"`), the evaluator refuses to run (exit `3`). Older MINORs within the same major (e.g. a `"1.0.0"` artifact under a `"1.1.0"` pin) are accepted automatically under FR-013. Fix the upstream producer if the version is truly incompatible.
- **`document_id` mismatch** — `expected.json` and `final_structured_payload.json` must agree on `document_id`. If they don't, the wrong `final_structured_payload.json` is in the folder.
- **Missing `expected.json`** — this feature does not scaffold labels; bring them from feature 006 (Corpus Scaffolding & Human Labeling).
- **`final_structured_payload.json` with extra fields** — blocked by the schema (`additionalProperties: false`) and rejected before evaluation starts. Fix the pipeline.
- **Corpus lazy mode surprise** — a corpus run may "look slow" because it is silently evaluating every folder. Pass `--json` once and inspect `per_document[*].output_path` to see what was written.

---

## 7. Run the evaluator's own tests

```bash
.venv/bin/pytest tests/evaluator_tests/
.venv/bin/pytest tests/contract_tests/test_evaluation_artifacts.py
```

Both should pass with zero network access (`pytest-socket` is enabled globally).
