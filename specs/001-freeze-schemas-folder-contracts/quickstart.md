# Quickstart: Freeze Schemas & Folder Contracts

**Feature**: `001-freeze-schemas-folder-contracts`
**Audience**: Pipeline developers, harness/evaluator developers, and human labelers who will use the contract set.

This quickstart shows what you can do once the feature has shipped. All paths are relative to the repo root (`/workspace/projects/dartwing/dartwing-ocr-pipeline`).

---

## 1. Install dependencies

Inside the devcontainer (or any Python 3.12 environment):

```bash
pip install -e .
```

This installs `dartwing_ocr` with the `jsonschema`, `pydantic`, and `pytest` dependencies declared in `pyproject.toml`. No GPU, no Ollama, no PaddleOCR required for this slice.

## 2. Inspect the contract set

```bash
python -m dartwing_ocr.validator show contract-set --text
```

Expected: a summary of contract-set `1.0.0`: the seven artifact contracts, their schema file paths, the closed `challenge_tags` vocabulary, and the list of active cross-artifact rules.

## 3. Validate a hand-written artifact

**As a pipeline developer:** drop a sample `edge_extraction_output.json` onto disk and validate it.

```bash
python -m dartwing_ocr.validator validate artifact \
    /tmp/my_edge_extraction.json \
    --contract edge_extraction_output
```

- Exit `0` → your sample conforms.
- Exit `1` → the text output lists each violation with a code, field path, reason, and the FR / rule the violator broke.

To consume the structured report in tooling, pass `--json`:

```bash
python -m dartwing_ocr.validator validate artifact \
    /tmp/my_edge_extraction.json \
    --contract edge_extraction_output \
    --json > /tmp/report.json
```

`report.json` conforms to `specs/001-freeze-schemas-folder-contracts/contracts/report.schema.json`.

## 4. Start labeling a new document

**As a human labeler:**

```bash
mkdir -p tests/stage1_vendor_identity/inv_003_hard
cp ~/inbox/some-invoice.pdf tests/stage1_vendor_identity/inv_003_hard/source.pdf
$EDITOR tests/stage1_vendor_identity/inv_003_hard/expected.json   # shape via schemas.md + expected.schema.json
$EDITOR tests/stage1_vendor_identity/inv_003_hard/notes.md         # required for hard / missing_name

python -m dartwing_ocr.validator validate folder \
    tests/stage1_vendor_identity/inv_003_hard
```

For `easy` or `medium` documents, `notes.md` is a soft requirement — the folder validator emits a warning but still passes. For `hard` or `missing_name` documents, missing `notes.md` is an error.

Missing-name documents MUST set:

```json
{
  "expected_vendor_candidate": {
    "company_name": { "present": false, "inferred": true, "value": "<best guess>" }
  },
  "expected_review": { "manual_review_required": true, "review_reason": "company_name_inferred" }
}
```

The `expected` contract has `additionalProperties: false` everywhere — predictions, confidence values, and evaluation outcomes are rejected at validation time.

## 5. Validate the whole corpus

Once some documents are labeled:

```bash
python -m dartwing_ocr.validator validate corpus tests/stage1_vendor_identity --json \
  | jq '{passed, counts, failing_folders: [.sub_reports[] | select(.passed==false) | .target_summary]}'
```

The structured report is one `ValidationOutcome` with a `sub_reports` array — one entry per document folder plus one for the root `evaluation_run_summary.json` when present. The harness can aggregate failures without scraping text.

## 6. Verify the cross-artifact provenance triad

From a folder that has `expected.json`, `edge_extraction_output.json`, `routing_decision.json`, and `final_structured_payload.json` all present, `validate folder` runs the Tier 2 provenance-triad rule automatically. A violation in any one of those four files that breaks `company_name.present` / `inferred` / `manual_review_required` / `review_reason` consistency produces a `PROVENANCE_TRIAD_INCONSISTENT` or `MISSING_NAME_TRIAD_VIOLATION` entry.

## 7. Proposing a contract change (contributor path)

When you need to change a contract (add a field, a tag, a decision value):

1. Read `contracts/stage1_vendor_identity/AMENDMENTS.md` for the checklist.
2. Update the relevant document in `docs/stage1-vendor-identity/`.
3. Create `contracts/stage1_vendor_identity/v<new-version>/` (copy the previous version as the starting point).
4. Update the affected schema file(s) and `contract_set.json`.
5. If a Tier 2 rule changes, update `src/dartwing_ocr/validator/cross_artifact.py` and the fixtures in `tests/contract_tests/fixtures/`.
6. Add a new entry to `AMENDMENTS.md`.
7. Run `pytest tests/contract_tests/` — all existing fixtures must still validate under the prior version; new fixtures must validate under the new version.

## 8. Common failure modes

| Symptom | Meaning | Fix |
|---|---|---|
| `NULL_VS_EMPTY_STRING` | you used `"value": ""` instead of `"value": null`. | Absent fields are always `null`. |
| `CHALLENGE_TAG_UNKNOWN` | tag not in the closed vocabulary. | Use a tag from `dataset-layout.md`, or propose a new one via the amendment path. |
| `VOTE_METADATA_MISSING` | `vote_metadata` block missing from `edge_extraction_output`. | Add `{voter_id, voter_role, consensus_mode}`; use `consensus_mode = "single_voter_baseline"` in stage 1. |
| `MISSING_NAME_TRIAD_VIOLATION` | an artifact says `company_name.present = false` without also setting `inferred = true` and `manual_review_required = true`. | Restore the triad. This is a hard safety rule. |
| `CONTRACT_SET_VERSION_INCOMPATIBLE` | artifact was written against a different contract-set version than the validator was asked to use. | Either re-stamp the artifact or run the validator with `--contract-set-version` matching the stamp. |
| `FOLDER_NOTES_MISSING_SOFT` (warning) | `notes.md` missing on an easy/medium document. | Optional — fix if you have context to add; otherwise the folder still passes. |

## 9. What this feature does NOT give you

- No PDF rasterization. Use this contract set to validate `preprocess_output.json` produced by a future preprocessing component — not to produce it.
- No model inference. `edge_extraction_output.json` samples are hand-written until a real extractor ships.
- No scoring. `evaluation_document.json` / `evaluation_run_summary.json` shapes are frozen, but the evaluator that computes them is a separate feature.
- No line-item fields. Stage 1 is vendor-identity only.
