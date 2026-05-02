# Quickstart: PPStructureV3 Preprocessing Migration

End-to-end walk-through for applying the engine migration in a devcontainer and verifying each of the spec's success criteria. Run these steps from the repository root.

## 0. Prerequisites

- Devcontainer from `.devcontainer/docker-compose.yml` (pipeline-dev) up and attached.
- Repository checked out on branch `010-pp-structurev3-preprocessing`.
- Clean working tree — regeneration commit (FR-010) should be the only artifact-touching commit in the feature.

## 1. Bump dependencies

Update the project declaration and lockfile to PaddleOCR 3.5:

- `pyproject.toml` — `paddleocr>=3.5,<4`, add `paddlex[ocr]>=3.5,<4`, keep `paddlepaddle>=3.0,<4`. Remove (don't comment out) the old `paddleocr>=2.8,<3` pin (FR-009).
- `requirements.txt` — pin exact versions: `paddleocr==3.5.0`, `paddlex[ocr]==3.5.1`, `paddlepaddle==3.3.1`.

Reinstall:

```bash
.venv/bin/pip install -e ".[dev]"
```

## 2. First-run model weight warm-up

The first `ledgerlinc-preprocess` invocation downloads ~500 MB of model weights into `~/.paddlex/official_models/`. Do this once explicitly so later steps don't block:

```bash
ledgerlinc-preprocess --document-folder tests/stage1_vendor_identity/inv_001_easy
```

This will print download progress for PP-DocBlockLayout, PP-DocLayout_plus-L, PP-OCRv5 server det/rec, SLANeXt_wired, SLANet_plus, and the RT-DETR-L cell detectors. Once finished, subsequent invocations run network-free (FR-015).

If the download fails (hoster unreachable, partial file, checksum mismatch), the CLI hard-fails per FR-016:

- exit code `3` (`EXIT_INTERNAL_ERROR`)
- stderr emits a JSON envelope with `"kind": "engine_init_failed"`, `"missing_weight"`, and `"weight_hoster_url"`
- **no** `preprocess_output.json` is written (not even a `status="failure"` stub)

Re-run once network is restored. No partial-state cleanup is needed.

## 3. Single-document smoke (SC-001)

Re-run preprocessing on `inv_001_easy` (now with warmed weights) and inspect the artifact:

```bash
ledgerlinc-preprocess --document-folder tests/stage1_vendor_identity/inv_001_easy
jq '.pipeline_version, (.pages[0].blocks | length), .document_text[0:80], .ingestion_sources.paddleocr_vl' \
    tests/stage1_vendor_identity/inv_001_easy/preprocess_output.json
```

Verify:

- `pipeline_version` is `"stage1-preprocess-v0.2.0+paddleocr3.5.0.0000000.dpi300"` (FR-008).
- `.pages[0].blocks | length` is `>= 3` (SC-001).
- `document_text`, lowercased, contains at least one lowercased token from the invoice's `expected.json` vendor-identity fields — i.e. case-insensitive substring match per SC-001. A quick one-liner:
  ```bash
  jq -r '.document_text | ascii_downcase' tests/stage1_vendor_identity/inv_001_easy/preprocess_output.json | \
      grep -F "$(jq -r '.company_name.value | ascii_downcase' tests/stage1_vendor_identity/inv_001_easy/expected.json)"
  ```
- `ingestion_sources.paddleocr_vl` is `{"enabled": true, "status": "success"}`.

## 4. Determinism smoke (SC-003)

Rerun the same invocation and compare digests:

```bash
sha256sum tests/stage1_vendor_identity/inv_001_easy/preprocess_output.json > /tmp/pp1.sha
ledgerlinc-preprocess --document-folder tests/stage1_vendor_identity/inv_001_easy
sha256sum tests/stage1_vendor_identity/inv_001_easy/preprocess_output.json > /tmp/pp2.sha
diff /tmp/pp1.sha /tmp/pp2.sha && echo "DETERMINISTIC"
```

Scope: the determinism assertion covers `preprocess_output.json` only. Debug `page_*.png` output (opt-in via `--write-page-images`, FR-022 / R-015) is explicitly outside FR-004 — do **not** sha256 the PNGs here.

If the digests differ, stop and audit per R-005 (threading, oneDNN, paddle seed, post-sort, warning ordering) and R-013 (confidence persisted as in-range floats or deterministic `null` values). Do NOT commit anything.

## 5. Regenerate the full corpus (FR-010, SC-002, SC-004)

Halt-on-fail sweep (per R-006):

```bash
set -e
for folder in tests/stage1_vendor_identity/inv_*/ ; do
    ledgerlinc-preprocess --document-folder "$folder"
done
```

If any document fails (FR-016 hard-fail or otherwise), the loop stops immediately. Fix the underlying cause (typically an env issue) and re-run from the top. Do NOT commit partial progress — git-level discard is the rollback mechanism.

After a successful sweep:

```bash
# SC-002 grep: every silent-empty page carries its category token
grep -rE '\[silent_empty_(layout|ocr)\]' tests/stage1_vendor_identity/inv_*/preprocess_output.json | \
    while IFS= read -r match; do
        folder=$(echo "$match" | cut -d/ -f1-3)
        status=$(jq -r '.ingestion_sources.paddleocr_vl.status' "$folder/preprocess_output.json")
        [ "$status" = "failure" ] || { echo "SC-002 violation: $folder has silent-empty warning but status=$status"; exit 1; }
    done
echo "SC-002 PASS"

# SC-004 validator
python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity
```

## 6. Tests (SC-008)

```bash
.venv/bin/pytest tests/contract_tests/           # MUST pass unchanged (FR-014)
.venv/bin/pytest tests/pipeline_tests/           # MUST pass unchanged (FR-014)
.venv/bin/pytest tests/integration/preprocessing/  # Updates allowed only for OCR-text shifts (FR-013)
.venv/bin/pytest tests/unit/preprocessing/       # Includes new test_warnings.py
```

For any integration test that required an update, verify the FR-013 free-form comment identifying the OCR-text delta is present (e.g. `# OCR-text delta: PP-OCRv5 renders "&" as "and"`).

## 6a. Record the PP-OCRv5 default recognition threshold (R-012)

Before moving on, capture the recognition-threshold default for `paddleocr==3.5.0` so FR-007's "engine default, no override" rule has a concrete value backing it. Start a Python REPL inside the devcontainer, construct the engine with the same flags used in `src/ledgerlinc_ocr/preprocessing/ocr.py`, and introspect the recognizer:

```python
from paddleocr import PPStructureV3
pipe = PPStructureV3(
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    use_formula_recognition=False,
    use_seal_recognition=False,
    use_chart_recognition=False,
    cpu_threads=1, enable_mkldnn=False, device="cpu", lang="en",
)
# Typical attributes: inspect whichever of these exists on pipe / pipe.text_recognizer:
#   text_rec_score_thresh, drop_score, rec_score_thresh
print({k: v for k, v in vars(pipe).items() if "score" in k.lower() or "thresh" in k.lower()})
```

Paste the result into `specs/010-pp-structurev3-preprocessing/research.md` under R-012 "Probe-derived default" with the date and `paddleocr` / `paddlex` versions. A future engine bump that changes this value will surface as a diff during FR-010 corpus regeneration.

## 7. Record baseline timings (SC-005)

Measure the first-run and second-run wall-clocks for `inv_001_easy` in the devcontainer and record them in `specs/010-pp-structurev3-preprocessing/research.md` under "Baseline timings":

```bash
# after a fresh engine warm-up, time a cold CLI invocation (fresh process = fresh engine init)
time ledgerlinc-preprocess --document-folder tests/stage1_vendor_identity/inv_001_easy
# and a warm rerun
time ledgerlinc-preprocess --document-folder tests/stage1_vendor_identity/inv_001_easy
```

Fill the table row in `research.md` with `pages`, both wall-clocks, `CPU` (e.g. `lscpu | grep "Model name"`), `RAM` (`free -h`), `OS` (`uname -srm`), and the paddleocr version (`pip show paddleocr | grep Version`). No absolute deadline is imposed.

## 8. Docs updates (FR-011, SC-006)

Verify these four surfaces reflect the new engine identity:

- `docs/stage1-vendor-identity/architecture.md` — processing flow mentions PPStructureV3 + PP-OCRv5, not PPStructure + PP-OCRv4.
- `docs/stage1-vendor-identity/ollama-runtime.md` — any PaddleOCR version reference is updated.
- `specs/003-pdf-preprocessing/research.md` — a migration decision entry citing `010` is added.
- `specs/003-pdf-preprocessing/quickstart.md` (preprocessing quickstart) — PaddleOCR version + first-run weight list are updated.

Grep for lingering `paddleocr2.10` / `PPStructure(` / `PaddleOCR(` references in those files and fix any.

## 9. Commit (FR-010)

Single commit that lands:

- Code changes (`src/ledgerlinc_ocr/preprocessing/*.py`)
- Dep pins (`pyproject.toml`, `requirements.txt`)
- Regenerated baselines (all 20 `preprocess_output.json` files)
- Docs updates per step 8
- Research / baseline-timings update (step 7)

Commit body includes a per-document shift summary, free-form prose per line (Clarifications Q3), one line per doc with a nonzero `document_text` delta, classifying the kind of shift. Documents without an OCR-text delta are omitted. Example:

```
Migrate stage 1 preprocessing to PPStructureV3 + PP-OCRv5

Regeneration notes (document_text deltas only):
- inv_003: ampersand → "and" (PP-OCRv5 tokenizer)
- inv_007: all-caps title now title-case (PP-OCRv5 casing)
- inv_012: "ltd." suffix now "LTD" (casing)
- inv_018: address zip collapsed one space (whitespace)
```

No separate regeneration-notes file; the commit body is the record.

## Troubleshooting

- **Engine init crashes with `ConvertPirAttribute2RuntimeAttribute` error** — the `enable_mkldnn=False` workaround is missing from `src/ledgerlinc_ocr/preprocessing/ocr.py`. See R-001.
- **Determinism diff after rerun** — check that `cpu_threads=1`, `use_mp=False`, `enable_mkldnn=False`, and `paddle.seed(0)` are all set before the first engine construction. See R-005.
- **Multi-page fixture OOMs during preprocessing** — verify `src/ledgerlinc_ocr/preprocessing/rasterize.py` is yielding one page at a time and `pipeline.py` is not retaining a document-wide raster list. V3 is too heavy for whole-document raster materialization on this workstation; see R-011.
- **`document_text` is empty but blocks exist** — a page with text-type blocks but zero OCR lines; FR-019 fires. Verify the `[silent_empty_ocr]` warning is present and `ingestion_sources.paddleocr_vl.status` is `"failure"`.
- **Unknown V3 label warnings dominate `warnings[]`** — new V3 labels have appeared that aren't in `PPSTRUCTURE_LABEL_TO_BLOCK_TYPE`. Extend the map per R-003, confirm the mapping is defensible, and re-run the sweep.
