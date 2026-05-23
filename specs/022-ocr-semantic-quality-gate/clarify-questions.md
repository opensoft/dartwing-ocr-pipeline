# Clarification Questions — 022-ocr-semantic-quality-gate

**Session**: 2026-05-22 (Round 2)
**Spec**: `specs/022-ocr-semantic-quality-gate/spec.md`
**Governing input**: `openspec/changes/add-ocr-semantic-quality-gate/specs/ocr-semantic-quality-gate/spec.md`

Round 1 (Q1–Q3) resolved fixture corpus home, minimum sidecar row shape, and the
runtime integration boundary. This round targets the still-underspecified
*how* of the deterministic gate — the decisions that materially change data
modeling, the matching algorithm, the report schema, and test design before
`/speckit.plan`. Questions are numbered Q4–Q15 to continue the session.

Reply with the option letter (e.g. `A`), `yes`/`recommended` to take the
recommendation, or a short free-form answer (≤5 words).

---

## Q4 — Semantic verdict aggregation rule

How is the per-document verdict decided between `passed` and `failed`?

**Recommended:** Option A — simplest, fully deterministic, matches FR-009–FR-012
wording ("MUST record a failed … check") and SC-002 ("every failed verdict names
at least one concrete failed check"). A weighted/threshold score reintroduces the
opaque scoring `design.md` Decision 4 explicitly rejected.

**Answer:** Option A — a document fails semantic table quality if any row has
any failed check. It passes only when there are zero failed checks across all
rows.

| Option | Description |
|--------|-------------|
| A | A document is `failed` if any row has any failed check; `passed` only when zero failed checks across all rows. |
| B | Each check category carries a severity; only "hard" categories fail the verdict, others are advisory evidence. |
| C | An aggregate weighted score over checks with a numeric pass threshold. |

---

## Q5 — Text-match normalization for content/coverage checks

When deciding whether a sidecar row's required text/value is "found" in observed
body OCR, what normalization is applied before comparison?

**Recommended:** Option B — exact raw matching false-fails on trivial spacing/case
differences; fuzzy similarity reintroduces a tuning threshold and nondeterminism
risk. The calibration errors (`Adgisted porinter lowrrert`) still fail under
normalized exact match because the letters themselves differ.

**Answer:** Option B — use normalized exact matching: NFKC, case-folding,
whitespace collapse, punctuation stripping, then exact token or substring
containment.

| Option | Description |
|--------|-------------|
| A | Exact raw substring match, no normalization. |
| B | Normalized exact match — NFKC + case-fold + whitespace-collapse + punctuation-strip, then exact token/substring containment. |
| C | Fuzzy similarity (edit-distance ratio) with a numeric threshold. |

---

## Q6 — Row-text-coverage gap definition

A `row-text-coverage-gap` (FR-011) is recorded when observed OCR covers only part
of a row's expected text. What counts as "only part"?

**Recommended:** Option A — keeps the check binary and deterministic, avoids a
tunable threshold, and aligns with the Q4 any-fail verdict. A numeric coverage
ratio can still be *recorded* as evidence without being the trigger.

**Answer:** Option A — a row-text-coverage gap is binary: any required/expected
text token absent from observed body OCR is a coverage gap. A coverage ratio may
be recorded as evidence, but it is not the trigger.

| Option | Description |
|--------|-------------|
| A | Any required/expected text token absent from observed body OCR → coverage gap (binary). |
| B | Coverage gap only when the matched fraction falls below a numeric threshold (specify, e.g. 0.8). |
| C | Coverage gap is evidence-only and never independently fails the verdict. |

---

## Q7 — Row-to-OCR association method (row-alignment)

The gate must associate each sidecar row with observed body OCR before it can
record a `row-alignment-failure`. How are rows anchored to observed OCR lines?

**Recommended:** Option B — pure declaration-order assumes the OCR preserved row
order, but the calibration shows split/shifted rows, so order alone is unreliable;
region anchors were already deferred (Round 1 Q2).

**Answer:** Option B — use text-anchored row association: locate each row by the
best normalized match of its description or row text, then verify required
values are present, in order, and not split in a way that prevents deterministic
reconstruction. If matches tie, break ties deterministically by earliest OCR
position and then declaration order.

| Option | Description |
|--------|-------------|
| A | Positional — match sidecar row N to the Nth detected body row in declared order. |
| B | Text-anchored — locate each row by best normalized match of its description/row text, then verify its values are present, in-order, and unsplit within that anchored span. |
| C | No row association — alignment is reported as evidence-only, not a failing check, in this feature. |

---

## Q8 — Required vs optional fields in a sidecar row

FR-002 lists `row_id`, `quantity`, `description`, `unit_price`, `amount`, and row
text. Which are mandatory in every row the validator accepts?

**Recommended:** Option B — not every invoice row has every column; forcing all
four cell fields would make the sidecar un-authorable for real fixtures. A missing
optional field means "no check for that cell"; a present field is checked.

**Answer:** Option B — `row_id` and row text are mandatory.
`quantity`/`description`/`unit_price`/`amount` are optional, and every present
field becomes a required-content check.

| Option | Description |
|--------|-------------|
| A | All six fields mandatory in every row. |
| B | `row_id` + row text mandatory; `quantity`/`description`/`unit_price`/`amount` optional, and each present field becomes a required-content check. |
| C | Only `row_id` mandatory; everything else optional. |

---

## Q9 — Currency representation in the sidecar

How are `unit_price` / `amount` stored in `semantic_table_truth.json`?

**Recommended:** Option B — keeps the truth canonical and locale-free, makes the
currency-shape check a pure comparison of expected canonical value vs observed
token, and avoids JSON float-precision pitfalls of a numeric type.

**Answer:** Option B — store currency truth as normalized decimal strings
without symbols, for example `"21.00"`.

| Option | Description |
|--------|-------------|
| A | JSON number (e.g. `21.00`). |
| B | Normalized decimal string, no symbol (e.g. `"21.00"`). |
| C | String with currency symbol exactly as expected on the invoice (e.g. `"$21.00"`). |

---

## Q10 — "Malformed currency shape" definition

FR-010 flags malformed money like `$21:00` or `$22:`. How is "malformed" defined
for the currency-shape check?

**Recommended:** Option A — makes SC-003 ("100% of calibration shapes flagged, 0%
of correct decimals flagged") directly testable and catches both colon-for-decimal
and truncated values without enumerating every defect.

**Answer:** Option A — a malformed currency shape is any observed
currency-position token that fails the canonical money regex
`^\$?\d{1,3}(,\d{3})*\.\d{2}$`.

| Option | Description |
|--------|-------------|
| A | Any observed currency-position token failing the canonical money regex `^\$?\d{1,3}(,\d{3})*\.\d{2}$` is malformed. |
| B | A fixed closed enumeration of defect patterns (colon-for-decimal, missing cents, etc.); anything unlisted is not flagged. |
| C | Malformed = observed currency value not byte-equal to the expected normalized value. |

---

## Q11 — `row_id` format and uniqueness

What constrains `row_id` in the row-truth contract?

**Recommended:** Option A — a string is more author-friendly and forward-compatible
than forcing integers; uniqueness is required so failed-check evidence can name
exactly one row (FR-015).

**Answer:** Option A — `row_id` is a non-empty string and must be unique within
the sidecar.

| Option | Description |
|--------|-------------|
| A | Non-empty string, unique within the sidecar. |
| B | Sequential 1-based integer matching declaration order. |
| C | Any JSON scalar; uniqueness not enforced. |

---

## Q12 — Where the whole-invoice / table-quality claim is surfaced

FR-025 says a failed semantic verdict makes any "whole-invoice / table-quality pass
claim" not-passed. Where is that claim represented in the reports?

**Recommended:** Option A — keeps the two verdicts side-by-side and explicit,
leaves `vendor_identity_passed` byte-unchanged (FR-024), and avoids inventing a
third combined field whose meaning could drift.

**Answer:** Option A — surface the table-quality claim as
`document_pass_fail.semantic_table_quality_passed` alongside the unchanged
`vendor_identity_passed`.

| Option | Description |
|--------|-------------|
| A | New `document_pass_fail.semantic_table_quality_passed` alongside the unchanged `vendor_identity_passed`. |
| B | New combined `document_pass_fail.whole_invoice_passed` = vendor AND semantic, plus the existing field. |
| C | No new `document_pass_fail` field — the claim lives only inside the `semantic_table_quality` object's `status`. |

---

## Q13 — How the semantic gate is invoked

Does the gate run automatically inside the existing evaluator, or behind an
explicit opt-in?

**Recommended:** Option A — the sidecar's presence is itself the opt-in, so no new
flag is needed and US3/US4 behave as written. A separate flag risks the surface
silently never running.

**Answer:** Option A — run the gate automatically inside the existing evaluator
when `semantic_table_truth.json` is present. Sidecar presence is the opt-in.

| Option | Description |
|--------|-------------|
| A | Automatic — sidecar presence triggers the gate inside the existing evaluator; no new flag. |
| B | Opt-in CLI flag/subcommand; gate runs only when explicitly requested. |
| C | Separate standalone CLI, not wired into the evaluator at all. |

---

## Q14 — Contract-set membership of the sidecar schema

Where does the `semantic_table_truth.json` JSON Schema live relative to the frozen
machine-readable contract set (`contracts/stage1_vendor_identity/v1.2.0/`)?

**Recommended:** Option A — it is a new per-document folder artifact the validator
enforces, so it belongs under one governed, versioned set with an amendment trail
rather than a side schema. The evaluation-report optional fields are additive and
tolerant (FR-019), consistent with a minor bump.

**Answer:** Option A — add `semantic_table_truth.json` to the governed contract
set with a minor version bump from `1.2.0` to `1.3.0` and an `AMENDMENTS.md`
entry.

| Option | Description |
|--------|-------------|
| A | New schema in the contract set; minor `contract_set` version bump (1.2.0 → 1.3.0) + `AMENDMENTS.md` entry. |
| B | Standalone schema outside the frozen contract set; no `contract_set` version change. |
| C | Major contract-set version bump (2.0.0). |

---

## Q15 — Name/path of the separate semantic-quality corpus root

Round 1 Q1 chose a separate corpus root but did not name it. What is its path?

**Recommended:** Option A — parallel naming with `tests/stage1_vendor_identity/`
makes the split obvious and keeps both roots discoverable under `tests/`.

**Answer:** Option A — name the separate semantic-quality corpus root
`tests/stage1_semantic_quality/`.

| Option | Description |
|--------|-------------|
| A | `tests/stage1_semantic_quality/` |
| B | `tests/semantic_quality/` |
| C | `tests/stage1_vendor_identity/calibration/` (a fixtures subtree) |

---

## Round 3 — Checklist resolution decisions

The release-gate checklists surfaced six spec-quality issues after Q4-Q15.
These answers resolve those issues inline and are reflected in
`specs/022-ocr-semantic-quality-gate/spec.md`.

## Q16 — Raw currency-token evaluation order

Does FR-010 run before or after punctuation-stripping normalization?

**Answer:** FR-010 runs before FR-009 punctuation stripping. Currency-shape
checks operate on raw observed OCR token text from `preprocess_output.json`.
FR-009 normalization remains the comparison rule for missing-content,
row-text coverage, and row anchoring.

## Q17 — Check ordering and short-circuiting

Can the gate stop after the first failed check?

**Answer:** No. The gate does not short-circuit. For every sidecar row, it
evaluates every applicable check and records failures in deterministic order:
`malformed-currency-shape`, `missing-required-content`,
`row-text-coverage-gap`, then `row-alignment-failure`.

## Q18 — Failed-check category boundaries

How are overlapping row defects attributed?

**Answer:** Use predicate-based attribution. `missing-required-content` means an
authored cell value is absent from the full observed body OCR after
normalization. `row-text-coverage-gap` means authored required row-text tokens
are absent from the full observed body OCR after normalization.
`row-alignment-failure` means required content is present somewhere but cannot
be reconstructed in the row's anchored span, order, or grouping.
`malformed-currency-shape` means a raw currency-position token exists but fails
the canonical money regex. A row may record more than one category when more
than one predicate is true.

## Q19 — Aggregate semantic metrics

Which run-summary semantic metrics are required?

**Answer:** New reports carry a `semantic_table_quality_metrics` object with
integer counts for applicable, not-applicable, evaluable, passed, failed, and
unevaluable documents; a nullable pass rate over evaluable documents; and
failed-check counts by category. They also carry per-document semantic status
entries for the run scope.

## Q20 — `semantic_table_quality_passed` value domain

What does `document_pass_fail.semantic_table_quality_passed` contain for
failed, unevaluable, and not-applicable cases?

**Answer:** Boolean or null. The field is `true` only for semantic status
`passed`, `false` for `failed` and `unevaluable`, and `null` for
`not applicable`. The string status is reported separately as
`semantic_table_quality.status` and in run-summary per-document entries.

## Q21 — Degraded-body fixture status

Is `inv_024_hard_degraded_body` promoted as committed scored corpus data in
this feature?

**Answer:** No. The named degraded-body folders remain calibration evidence
only. US2 uses a committed synthetic semantic-quality fixture under
`tests/stage1_semantic_quality/`, derived from the observed failure pattern,
unless a later dataset-amendment change explicitly promotes real degraded-body
samples.

---

<!-- Round 3 — Q22-Q26 — clarify session 2026-05-22, post release-gate-checklist sweep -->

## Q22 — Observed body-OCR selection rule

Which subset of `preprocess_output.json` counts as the "observed body OCR
evidence" the gate searches (FR-007/FR-009/FR-010/FR-011/FR-012)?

**Recommended:** Exclude the page-1 header band — lane-robust, no dependency on
fragile table detection.

**Answer:** All page OCR text minus the page-1 header band. "Observed body OCR
evidence" is every OCR line and token on every page of `preprocess_output.json`
EXCEPT the feature-020 page-1 header-band region. Lane-robust across the
OCR-only and PPStructureV3 lanes; does not depend on table-block detection.

## Q23 — Noncanonical-folder recognition rule

How does the validator decide a folder is calibration vs a scored corpus folder
(FR-027, US5, SC-009)?

**Recommended:** Canonical-pattern allowlist — default-exclude.

**Answer:** Canonical-pattern allowlist. A folder is a scored corpus folder ONLY
when its name fully matches the canonical `inv_NNN_<difficulty>` pattern
(`^inv_\d{3}_(easy|medium|hard)$`, closed difficulty vocabulary per
`dataset-layout.md`). Every non-matching name — including any extra suffix such
as `inv_024_hard_degraded_body` — is calibration material. An unrecognized name
is never silently scored.

## Q24 — "Earliest observed-OCR position" definition

What ordering does the FR-012 row-anchor tie-break "earliest observed-OCR
position" refer to?

**Recommended:** `preprocess_output.json` serialization order — byte-stable, no
geometry.

**Answer:** `preprocess_output.json` serialization order. "Earliest" is the
lowest index in the artifact's own ordering — page array order, then line/token
array order within each page. No geometry computation and no coordinate
tolerance is used.

## Q25 — Synthetic US2 fixture composition

What does the committed synthetic US2 fixture folder under
`tests/stage1_semantic_quality/` contain (FR-026, US2)?

**Recommended:** Hand-authored `preprocess_output.json` + sidecar, no
`source.pdf` — deterministic, CPU-only.

**Answer:** Hand-authored `preprocess_output.json` + `semantic_table_truth.json`,
no `source.pdf`. The fixture folder commits a hand-authored, schema-valid
`preprocess_output.json` reproducing the degraded-body pattern (high mean
detector confidence, materially wrong rows) and the matching authored sidecar.
It contains NO `source.pdf` and is NOT produced by running the preprocessing
pipeline.

## Q26 — Verdict status enum string values

What are the canonical JSON string values for the verdict status set
(FR-016/FR-017/FR-018/FR-025)?

**Recommended:** snake_case — matches the repo's existing status/decision enum
precedent.

**Answer:** snake_case. The four canonical JSON enum values are `passed`,
`failed`, `not_applicable`, and `unevaluable`, used verbatim wherever a semantic
status is serialized (`semantic_table_quality.status`, run-summary per-document
`semantic_table_quality_status`). The four failed-check category labels remain
kebab-case as already fixed by Q17/Q18.

---

<!-- Round 4 — Q27-Q44 — bulk block, post-checklist-reverification sweep 2026-05-22 -->
# Round 4 — Q27-Q44 (post-checklist re-verification)

The release-gate checklist re-verification (255/586 resolved → 331 open) surfaced
roughly 18 genuinely spec-level decisions still pending. Plan-time / schema-
authoring-only items are excluded. Reply with the option letter (A/B/C), `yes`
to accept the recommendation, or short free-form. You can answer all at once.

---

## Q27 — Sidecar top-level envelope shape

The spec pins per-row fields but never the sidecar's top-level keys beyond
`document_id`. What is the top-level shape of `semantic_table_truth.json`?

**Recommended:** Option A — optional `schema_version` keeps the sidecar
forward-compatible without burdening today's authors.

**Answer:** Option A — top-level shape is `{document_id, rows[],
schema_version?}`. `schema_version` is an optional string, for example
`"1.3.0"`, and the governed contract set remains authoritative when the field is
absent.

| Option | Description |
|--------|-------------|
| A | `{document_id, rows[], schema_version?}` — `schema_version` optional string (e.g. `"1.3.0"`). |
| B | `{document_id, rows[]}` only — no instance version field; contract-set governance handles versioning. |
| C | `{document_id, rows[], schema_version}` — `schema_version` always required. |

---

## Q28 — Row-text representation

FR-002 says "row text (or required text fragments)." Is the row-text field a
single string or an array of fragment strings?

**Recommended:** Option A — multi-token row text is naturally a list; a single
string forces authors to encode whitespace/order in one blob that must then be
re-split for the FR-011 token check.

**Answer:** Option A — represent required row text as a non-empty array field
named `required_row_text_tokens`, with each item a non-empty string. These are
the tokens used by the binary row-text-coverage check.

| Option | Description |
|--------|-------------|
| A | Array of required token strings, e.g. `required_row_text_tokens: ["Brand", "Wax", "Proper", "sead", "Table"]`. |
| B | Single string `row_text: "Brand Wax Proper sead Table"` — split on whitespace at read time. |
| C | Both forms supported — author's choice. |

---

## Q29 — `failed_checks` vs `row_reasons` structural relationship

FR-017 lists both keys on the `semantic_table_quality` object but never
specifies their relationship — the single most-cited cross-checklist ambiguity.

**Recommended:** Option A — flat ordered list + per-row aggregation gives both
machine-friendly iteration and reviewer-friendly grouping without duplicating
truth.

**Answer:** Option A — use the two-view structure. `failed_checks` is the flat
ordered array of full failure records and remains the source of truth.
`row_reasons` is a per-row aggregation keyed by `row_id`, derived from
`failed_checks`, containing the row's failed category set and a short
human-readable reason. Both are required when status is `failed`.

| Option | Description |
|--------|-------------|
| A | Two-view: `failed_checks` = flat ordered array of full records (FR-015 fields, FR-015 ordering); `row_reasons` = per-row aggregation keyed by `row_id` carrying that row's failed-check category set plus a short human-readable reason string. Both required when status is `failed`. |
| B | Single source: keep `failed_checks` only and remove `row_reasons` from FR-017. |
| C | Independent: `failed_checks` flat array + `row_reasons` independent human-readable strings authored separately from `failed_checks`. |

---

## Q30 — OCR-confidence placement in the report

FR-013 says OCR confidence is "supporting evidence only" but never says where
in the JSON the confidence values live.

**Recommended:** Option A — document-aggregate keeps confidence at the
"signal, not proof" level; row/check-level confidence invites misuse as
row-level proof, exactly what FR-013 prohibits.

**Answer:** Option A — record OCR confidence only as document-level supporting
evidence under `semantic_table_quality.supporting_evidence`, with
`body_confidence_mean`, `body_confidence_min`, `body_line_count`,
`body_token_count`, and `header_band_excluded`. Do not add per-row or
per-failed-check confidence fields.

| Option | Description |
|--------|-------------|
| A | Document-aggregate only on `semantic_table_quality.supporting_evidence`: `body_confidence_mean`, `body_confidence_min`, `body_line_count`, `body_token_count`, `header_band_excluded`. No per-row / per-check confidence. |
| B | Per-`failed_check` field `observed_confidence` PLUS document-aggregate. |
| C | Per-row inside `row_reasons` PLUS document-aggregate. |

---

## Q31 — `unevaluable` cause vocabulary

Edge cases require `unevaluable` records "a named cause." Closed vocabulary or
free-text?

**Recommended:** Option A — closed `cause` enum + free-text `cause_detail`
gives deterministic categorisation for run-summary aggregation while preserving
human-readable specifics.

**Answer:** Option A — use a closed `cause` enum with optional free-text
`cause_detail`. Legal causes are `preprocess_output_missing`,
`preprocess_output_invalid_json`, `preprocess_output_schema_invalid`, and
`body_ocr_unreadable`.

| Option | Description |
|--------|-------------|
| A | Closed `cause` enum {`preprocess_output_missing`, `preprocess_output_invalid_json`, `preprocess_output_schema_invalid`, `body_ocr_unreadable`} + free-text `cause_detail`. |
| B | Free-text `cause` only. |
| C | Closed enum only, no free-text detail. |

---

## Q32 — FR-009 punctuation-stripping Unicode category set

"Unicode punctuation" is named but never pinned to specific Unicode categories.

**Recommended:** Option A — the full Unicode `P*` set is the standard
"any-punctuation" category; deterministic across Python versions when paired
with a pinned `unicodedata` data file.

**Answer:** Option A — strip all Unicode punctuation categories whose general
category begins with `P`: `Pc`, `Pd`, `Pe`, `Pf`, `Pi`, `Po`, and `Ps`, after
NFKC normalization.

| Option | Description |
|--------|-------------|
| A | All Unicode `P*` categories (`Pc` connector, `Pd` dash, `Pe` close, `Pf` final quote, `Pi` initial quote, `Po` other, `Ps` open). |
| B | ASCII-only: Python `string.punctuation`. |
| C | All `P*` EXCEPT `Pc` (preserve underscores in identifiers/tokens). |

---

## Q33 — Comparison granularity (where "found anywhere" applies)

FR-009 says "exact token or substring containment." Does the gate match against
per-line text, or against a single concatenation of all body OCR?

**Recommended:** Option A — one normalized concatenation is the simplest fully
deterministic surface, makes "found anywhere in the observed body OCR" literal,
and is robust to PaddleOCR splitting a value across two lines.

**Answer:** Option A — build one body-OCR search string by joining every
body-OCR line on every page, in Q24 serialization order, with one ASCII space,
then applying the FR-009 normalization pipeline once. All "found anywhere"
checks operate against that normalized concatenation.

| Option | Description |
|--------|-------------|
| A | Single concatenation: every body-OCR line on every page joined in `preprocess_output.json` serialization order (per Q24) by one ASCII space, then normalized once. All "found anywhere" checks operate on this one normalized string. |
| B | Per-line: a value is "found" if it appears within any single normalized line (line boundaries matter). |
| C | Per-token bag: drop whitespace and ordering entirely; treat body OCR as a multiset of normalized tokens. |

---

## Q34 — Byte-identical serialization conventions (FR-014 / SC-007)

Newly written semantic objects must be byte-identical across re-runs. What JSON
serialization conventions does the spec lock?

**Recommended:** Option A — matches the repo's stable-JSON convention and
removes float-format nondeterminism from `pass_rate` / aggregated confidence.

**Answer:** Modified Option A — use sorted keys at every nesting level, UTF-8
encoding, LF line endings, a trailing newline at EOF, and no trailing whitespace.
Derived ratio/confidence numbers are rounded to six decimal places using
round-half-to-even and emitted as fixed-precision JSON numbers, not strings, so
numeric schema types remain numeric. Integer counts remain JSON numbers.

| Option | Description |
|--------|-------------|
| A | Sorted keys at every nesting level; UTF-8 + LF line endings; floats serialized as fixed-precision decimal strings (6 decimal places, round-half-to-even) for derived ratios such as `semantic_table_quality_pass_rate`; integer counts as JSON numbers; trailing newline at EOF; no trailing whitespace. |
| B | Sorted keys; native Python `repr()` for floats (no fixed precision). |
| C | Insertion-order keys (rely on Python 3.12 dict-order determinism). |

---

## Q35 — Currency-position-token identification

FR-010 evaluates malformed currency on a "currency-position token" but never
defines how the gate locates the candidate raw token inside the row's anchored
OCR span.

**Recommended:** Option A — explicit, deterministic, and matches the
calibration data's left-to-right token order; "no candidate → missing-content,
not malformed-currency" cleanly preserves the FR-018 category split.

**Answer:** Custom — identify a currency-position candidate per declared
currency field by matching the expected field's digit sequence. Within the
row's anchored OCR span, scan raw tokens in Q24 order for the first unmatched
token whose digit sequence equals the expected `unit_price` or `amount` digit
sequence after removing punctuation and currency symbols. Evaluate the
canonical money regex against that raw token. If no candidate exists for a
declared currency field, record `missing-required-content`, not
`malformed-currency-shape`. This avoids misclassifying quantity tokens as
currency tokens.

| Option | Description |
|--------|-------------|
| A | Within the row's anchored OCR span (FR-012), scan raw tokens left-to-right; the candidate is the FIRST raw token matching `^[\$\d][\$\d.,:]*$` (begins with `$` or a digit). For a row declaring both `unit_price` and `amount`, take the first such token as `unit_price` and the second as `amount`. If no candidate exists for a declared currency field, the failure is `missing-required-content`, NOT `malformed-currency-shape`. |
| B | Last raw token of the row's anchored span (invoices typically put amount at the right). |
| C | Every raw token in the anchored span matching `[\$\d.,:]` is a candidate; each is checked independently. |

---

## Q36 — `semantic_table_quality_metrics` location in run summary

Where in `evaluation_run_summary.json` does the new namespace live?

**Recommended:** Option A — top-level sibling matches FR-020's "separate from
vendor-identity scoring" and keeps run-summary surface discoverable.

**Answer:** Option A — place `semantic_table_quality_metrics` as a top-level
sibling in `evaluation_run_summary.json`, parallel to existing vendor-identity
and feature-020 fields.

| Option | Description |
|--------|-------------|
| A | Top-level sibling key `semantic_table_quality_metrics`, parallel to existing vendor-identity / feature-020 fields. |
| B | Nested inside a new top-level `quality_gates.semantic_table_quality` envelope (forward-compatible for future gates). |
| C | Nested inside the existing vendor-identity metrics object. |

---

## Q37 — `supporting_evidence` shape

FR-017 lists `supporting_evidence` as optional on the `semantic_table_quality`
object. Is its shape pinned at landing?

**Recommended:** Option A — a closed shape makes the evidence reviewer-
auditable without a future schema migration, and pairs with Q30.

**Answer:** Option A — pin `supporting_evidence` at landing to the closed shape
`{body_confidence_mean, body_confidence_min, body_line_count,
body_token_count, header_band_excluded}` with numeric confidence values, integer
counts, and a boolean header-band flag.

| Option | Description |
|--------|-------------|
| A | Closed shape pinned now: `{body_confidence_mean: float, body_confidence_min: float, body_line_count: int, body_token_count: int, header_band_excluded: bool}`. |
| B | Free-form object — any keys allowed at the gate's discretion. |
| C | Omitted entirely at landing; defined by a later amendment. |

---

## Q38 — Explicit Out-of-Scope additions

Several `[Gap]` items ask whether the absence of performance/NFR requirements
and configuration knobs is *intentional*. The spec says "no" implicitly but
never declares it in Out of Scope.

**Recommended:** Option A — closes both `[Gap]` items in one stroke and
prevents a reviewer assuming "you forgot" instead of "intentionally omitted".

**Answer:** Option A — explicitly add both Out-of-Scope bullets:
performance/latency/throughput targets are not part of this deterministic
in-memory comparison feature, and there is no new configuration surface: no CLI
flags, environment variables, config files, or tunable thresholds.

| Option | Description |
|--------|-------------|
| A | Add two Out-of-Scope bullets: (a) **Performance / latency / throughput targets** — the gate is a deterministic in-memory comparison; no NFR target this feature. (b) **New configuration surface** — no CLI flags, env vars, or config files; the gate has no tunable thresholds (consistent with Q13). |
| B | Add only the performance bullet. |
| C | Leave Out of Scope unchanged. |

---

## Q39 — Sidecar handling for calibration folders

A noncanonical (calibration) folder may contain a `semantic_table_truth.json`.
What does the gate do?

**Recommended:** Option A — runs the gate so authors can validate fixtures,
but the verdict is excluded from scored aggregation, preserving FR-027.

**Answer:** Option A — if a calibration folder has a sidecar, the gate runs and
writes per-document semantic quality output, but the document is excluded from
`semantic_table_quality_metrics` scored aggregation in the run summary.

| Option | Description |
|--------|-------------|
| A | Gate runs on the sidecar; the resulting `semantic_table_quality` object and per-document semantic status are emitted on `evaluation_document.json`, but EXCLUDED from `semantic_table_quality_metrics` aggregation in the run summary. |
| B | Gate is skipped entirely on noncanonical folders; semantic status is omitted from both per-doc and run-summary reports. |
| C | Gate runs and contributes to a SEPARATE `semantic_table_quality_calibration_metrics` namespace. |

---

## Q40 — `tests/stage1_semantic_quality/` subfolder naming convention

What is the canonical subfolder name pattern under the new corpus root?

**Recommended:** Option A — reusing the existing pattern lets the Q23 allowlist
apply uniformly to both roots.

**Answer:** Option A — use the same canonical `inv_NNN_<difficulty>` subfolder
pattern under `tests/stage1_semantic_quality/`, with the closed difficulty
vocabulary `easy`, `medium`, and `hard`. The synthetic US2 fixture can land as
`tests/stage1_semantic_quality/inv_001_hard/`.

| Option | Description |
|--------|-------------|
| A | Same `inv_NNN_<difficulty>` pattern as `tests/stage1_vendor_identity/` (`^inv_\d{3}_(easy\|medium\|hard)$`). Synthetic US2 fixture lands at e.g. `tests/stage1_semantic_quality/inv_001_hard/`. |
| B | `synth_NNN_<scenario>` — explicit "synthetic" prefix to signal hand-authored origin. |
| C | `semq_NNN_<scenario>` — semantic-quality prefix. |

---

## Q41 — Validator error message content

FR-003 / FR-004 require rejection-with-error. Is the required error content
pinned?

**Recommended:** Option A — pinning the diagnostic content makes US1 AS2 / AS3
testable.

**Answer:** Option A — a `document_id` mismatch error must name both the
declared `document_id` and the containing folder basename. A row-violation
error must name the offending `row_id`, or the row-array index when `row_id`
cannot be parsed, plus the failed field and a one-line machine-readable reason.

| Option | Description |
|--------|-------------|
| A | document_id-mismatch error MUST name both the declared `document_id` and the folder basename it lives in; row-violation error MUST name the offending `row_id` (or row-array index if `row_id` is unparseable), the specific field that failed, and a one-line machine-readable reason. |
| B | Only the document_id-mismatch error content is pinned; row-violation diagnostic format is plan-level. |
| C | Neither — leave error content entirely to implementer judgement. |

---

## Q42 — Validator-time vs gate-time error boundary

A sidecar that passes the validator at corpus-validate time but produces an
invariant violation at gate-time (e.g. duplicate row anchor under FR-012) —
hard error, or `unevaluable`?

**Recommended:** Option A — `unevaluable` is reserved for unreadable INPUT
files. A gate-time invariant violation is a bug, not an input fault.

**Answer:** Option A — gate-time invariant violations are hard errors. The run
fails, no `unevaluable` semantic status is recorded for that document, and the
document is excluded from semantic metrics.

| Option | Description |
|--------|-------------|
| A | Hard error: the gate raises and the run fails; status is NOT recorded as `unevaluable` and the document is excluded from semantic metrics. |
| B | `unevaluable` with a distinct cause code (e.g. `gate_invariant_violation`). |
| C | Either, at the gate's discretion. |

---

## Q43 — Pre-feature `document_pass_fail` reading

When the writer or schema-validator reads an old `evaluation_document.json`
produced before this feature (no `semantic_table_quality_passed` field), how
is the missing field interpreted?

**Recommended:** Option A — `null` matches the Edge Case interpretation
"absence of `semantic_table_quality` = gate did not run" and preserves FR-019
backward compatibility.

**Answer:** Option A — when reading old pre-feature reports, an absent
`document_pass_fail.semantic_table_quality_passed` field is interpreted as
`null`, meaning the semantic gate did not run on that document.

| Option | Description |
|--------|-------------|
| A | Absent field is treated as `null` (semantically: "semantic gate did not run on this document"). |
| B | Absent field is treated as `false` (fail-safe / conservative). |
| C | Absent field makes the artifact invalid against the post-feature schema. |

---

## Q44 — PII screening applicability to the new corpus root

Does `labeling-guide.md`'s PII / license pre-inclusion screening apply to
fixtures committed under `tests/stage1_semantic_quality/`?

**Recommended:** Option A — identical screening keeps governance uniform; the
synthetic US2 fixture (Q25) carries no real PII by construction, but any
future committed fixture must still pass screening.

**Answer:** Option A — the same `labeling-guide.md` PII/license screening
applies to both `tests/stage1_vendor_identity/` and
`tests/stage1_semantic_quality/`. The Q25 synthetic fixture has no real PII by
construction, but future committed fixtures still require screening.

| Option | Description |
|--------|-------------|
| A | Same `labeling-guide.md` PII/license screening applies to both corpus roots, unchanged. |
| B | Screening applies to vendor-identity root only; semantic-quality root is exempt because synthetic-only. |
| C | A new, separately-authored screening doc governs the semantic-quality root. |
