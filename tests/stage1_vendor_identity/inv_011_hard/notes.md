# Labeling Notes — inv_011_hard

## Difficulty rationale

Classified `hard` because the PDF text layer is a low-quality rasterized scan: several header glyphs are degraded and OCR drift is likely. The critical `low_quality_scan` tag is carried by this document.

## Key traps

- **Header vs. footer name drift.** Header wordmark reads "L.A. Grinding"; footer fine print expands to "LA Grinding Company" (no punctuation). Labelers should not over-normalize one form to the other — the canonical value chosen here is **"L.A. Grinding Company"**, combining the punctuated header brand with the expanded corporate form in the footer. Same convention as inv_002/inv_005.
- **Low-quality scan.** A model reading only the raster will likely mis-transcribe the period-separated "L.A." as "LA" or "L A". The `low_quality_scan` tag signals this is an expected model failure mode, not a labeler error.

## Labeler decisions

- Explicit name is `present: true` — both header and footer are human-readable in the source despite the low-quality raster.
- Website and email are present but no tax IDs, remit-to differential, or logo-only condition apply here.
