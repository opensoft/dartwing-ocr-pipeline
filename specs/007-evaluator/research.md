# Phase 0 Research: Evaluator & Reporting

**Feature**: 007-evaluator
**Date**: 2026-04-21

This document resolves every open decision needed before code is written. The spec's Clarifications section (`spec.md` §Clarifications, Session 2026-04-20) already answered the five highest-impact questions; this file captures the remaining implementation-level decisions the spec deferred ("documented in code") and a few build-quality decisions implicit in the Technical Context. Each entry follows the canonical Decision / Rationale / Alternatives form.

---

## 1. State abbreviation mapping (normalization)

**Decision**: Hard-code a dictionary of the 50 US states + DC + 5 US territories (PR, GU, AS, MP, VI) mapping 2-letter code ↔ full name (case-insensitive comparison). No third-party dependency. Non-US states (e.g. Canadian provinces) are compared via the default normalization path (lowercase + trim); if a future corpus introduces CA provinces the mapping is extended in place.

**Rationale**: The stage 1 corpus is US-only (`docs/stage1-vendor-identity/dataset-layout.md` and the 18-entry `challenge_tags` enum imply US invoices). A 56-entry static dict is trivial code, deterministic, and avoids locking us to an external library's update cadence. Works identically in devcontainer and host.

**Alternatives considered**:
- `us` package — adds a dependency and a wheel for a 56-entry table.
- Free-form Levenshtein / partial-match — violates `scoring.md` ("full name and 2-letter abbreviation are equal"); introduces false partials.
- `pycountry` — heavyweight, Unicode-collation-dependent, unnecessary for stage 1.

---

## 2. Phone normalization

**Decision**: Strip every non-digit character, then compare. If the prediction's digits-only representation is a proper prefix of the expected's digits-only representation, or vice versa, AND the expected includes an explicit extension marker (e.g. `ext`, `x`, `#`) that the prediction dropped, emit `partial_match`. Otherwise `match` (equal after strip) or `mismatch`. No `phonenumbers` dependency.

**Rationale**: `scoring.md` §Normalization pins "phone: digits only"; §Partial Match Policy pins "phone matches except extension". A 20-line regex-based normalizer covers both. `phonenumbers` would add weight (a 300+ kB wheel) and locale configuration for a problem the rubric has already simplified.

**Alternatives considered**:
- `phonenumbers` — over-engineered; returns parse-failure on US invoices with malformed punctuation that the digits-only rule handles cleanly.
- Compare with punctuation intact — explicitly rejected by `scoring.md`.

---

## 3. Website normalization

**Decision**: Deterministic pipeline: lowercase → strip leading `http://` or `https://` → strip leading `www.` → strip single trailing `/` → strip query string and fragment. Preserve path segments beyond the root. Compare string-equal. No partial match.

**Rationale**: `scoring.md` §Normalization enumerates "remove scheme / remove trailing slash / optionally remove www.". Emails are separate (`scoring.md` "email: lowercase"). Including a query-string strip handles the common `?utm_*` pollution without blurring the semantic identity of the site. Website is not in `scoring.md`'s partial-match list, so we only emit `match` / `mismatch` / `missing_prediction` / `unexpected_prediction`.

**Alternatives considered**:
- Use `urllib.parse.urlparse` + structured compare — clean but pulls in port/netloc normalization surprises (e.g. default-port handling) that are not required by the rubric.
- Compare raw strings — rejected; fails the test case pinned in US3 AC#3.

---

## 4. Postal-code partial-match rule

**Decision**: Exact string equality after trim ⇒ `match`. If one side is the 5-digit prefix of the other (ZIP vs ZIP+4), ⇒ `partial_match`. Any other difference ⇒ `mismatch`. Non-US postal codes (alphanumeric) fall through to string-equal-after-normalize only.

**Rationale**: Pinned by `scoring.md` ("allow ZIP+4 to compare to ZIP when needed") and US3 AC#2 ("94110-1234" vs "94110" → `partial_match`). The 5-digit-prefix rule is exact and testable.

**Alternatives considered**:
- Numeric compare — rejected; postal codes are strings (leading zeros, alpha segments).

---

## 5. Tax ID comparison

**Decision**: Strip spaces, hyphens, dots; compare the remaining digit string case-insensitively (some VAT IDs include country-letter prefixes). `match` or `mismatch` only; never `partial_match` (pinned by FR-006 and `scoring.md`).

**Rationale**: `scoring.md` §Partial Match Policy explicitly excludes tax IDs; any "close" tax ID is a different entity or a typo worth catching.

**Alternatives considered**:
- Levenshtein ≤ 1 → partial — rejected; hides typos that matter.

---

## 6. Street/address normalization

**Decision**: Normalize a fixed suffix map (`St/Street`, `Rd/Road`, `Ave/Avenue`, `Blvd/Boulevard`, `Dr/Drive`, `Ln/Lane`, `Ct/Court`, `Pl/Place`, `Pkwy/Parkway`, `Hwy/Highway`, `Ter/Terrace`, `Cir/Circle`, `Sq/Square`) plus directional prefix equivalences (`N/North`, `S/South`, `E/East`, `W/West`, and two-letter `NE/NW/SE/SW`). After suffix + direction + lowercase + whitespace-collapse + punctuation-strip, compare string-equal for `match`. If the street numbers match and the rest is similar under a token-set overlap ≥ 0.7 ⇒ `partial_match` (covers the US3 AC "imperfectly normalized street suffix" case). Otherwise `mismatch`.

**Rationale**: `scoring.md` requires suffix normalization; US3 names "imperfectly normalized street suffix" as an explicit partial-match case. A token-set overlap with the street-number gate (must match) is an objective, deterministic, easily unit-tested rule.

**Alternatives considered**:
- `usaddress` library — over-engineered; opaque on malformed inputs; introduces a training-data dependency.
- Pure string equality — rejected; would miss US3 AC cases by design.

---

## 7. Company-name partial match

**Decision**: After normalization (lowercase, trim, collapse whitespace, strip `, Inc.` / `LLC` / `Corp` / `Ltd` / `Co.` suffixes, strip non-alphanumeric), compare:
- exact-equal ⇒ `match`;
- one side is a proper token-subset of the other AND they share ≥ 3 characters of substantive overlap ⇒ `partial_match`;
- otherwise ⇒ `mismatch`.

**Rationale**: `scoring.md` §Partial Match Policy: "company name is clearly the same entity but not the exact legal rendering". "Acme Widgets Inc." vs "Acme Widgets Incorporated" is `match` after suffix strip. "Acme Widgets" vs "Acme Widget Co. of California" is `partial_match`. "Acme Widgets" vs "Omega Gadgets" is `mismatch`.

**Alternatives considered**:
- Levenshtein distance threshold — opaque, tunable-magic-number; rejected.
- Exact-equal only — rejected; violates US3 AC for legal-form rendering.

---

## 8. Floating-point epsilon for the 0.85 gate

**Decision**: `overall_passed = (document_score + 1e-9) >= 0.85`. Epsilon is declared as a module-level constant `GATE_EPSILON = 1e-9` in `gates.py` with a one-line comment pointing to the Edge Cases section of the spec.

**Rationale**: Spec Edge Cases ("Weighted `document_score` = 0.849999...") punts the epsilon choice to the implementation but requires it be documented in code. `1e-9` is well below the precision of any field-weight arithmetic (integer weights, halving from partials; worst-case denominator ~ 100) and well above IEEE-754 double-precision aggregation noise.

**Alternatives considered**:
- `math.isclose` — overkill; symmetric tolerance is wrong here (we want a one-sided bump).
- No epsilon — rejected; violates the spec's explicit guidance.

---

## 9. `run_id` generation

**Decision**: `run_id = "run_" + ISO-8601 UTC timestamp with microseconds + "_" + first 8 hex chars of `uuid.uuid4()`. Example: `run_2026-04-21T14:32:07.123456Z_9f3c1a20`. Generated once per corpus-mode invocation and written into `evaluation_run_summary.json`; not propagated into per-document `evaluation_document.json` (whose schema has no `run_id` field).

**Rationale**: The spec requires `run_id` to be unique across invocations even in the same second (Edge Cases → Run ID collision). Combining microsecond-precision UTC with 32 bits of random tail makes collision effectively impossible while keeping the string human-scannable in logs. UTC avoids devcontainer-vs-host tz drift.

**Alternatives considered**:
- Full `uuid4` — opaque in logs, harder to bisect regressions.
- Monotonic counter file — writes state on disk; violates "inputs are read-only" hygiene.
- Timestamp only — collides per Edge Cases.

---

## 10. Deterministic JSON serialization

**Decision**: Single writer in `evaluator/io.py`:
- `json.dumps(obj, indent=2, ensure_ascii=False, separators=(",", ": "), sort_keys=False)`;
- explicit key ordering in the dataclass → dict step (we emit `contract_set_version` first, matching the schemas' `required` order, then the rest);
- UTF-8 encoding with a single trailing `\n`;
- floating-point values rounded to 6 decimals before serialization (enough for 20-doc corpus arithmetic, eliminates `0.3333333333333333` run-to-run noise between Python minor versions).

**Rationale**: FR-018 and SC-005 require byte-identical output. `sort_keys=False` with explicit ordering preserves human-readable schema order. UTF-8 without BOM matches all other JSON files in the repo. Rounding to 6 decimals is far below the 0.01 resolution anyone reads from a pass-rate.

**Alternatives considered**:
- `sort_keys=True` — alphabetizes output, harder to read against the schema.
- Canonical JSON / JCS — heavyweight for an internal artifact.

---

## 11. Field iteration order in `field_results`

**Decision**: Emit `field_results` keys in the canonical order pinned in `scoring.md` §Fields To Score:
1. `company_name.value`, `company_name.present`, `company_name.inferred`
2. `address.street_1`, `.street_2`, `.city`, `.state`, `.postal_code`, `.country`
3. `tax_ids.ein`, `.state_tax_id`, `.vat_id`, `.other_tax_id`
4. `website`, `phone`, `email`
5. `manual_review_required`, `review_reason`

Defined as a tuple constant `SCORED_FIELDS` in `evaluator/scoring.py`.

**Rationale**: FR-017 + FR-018 require determinism; Python 3.7+ dicts preserve insertion order, so a single named tuple is sufficient. Putting the order in `scoring.py` keeps it next to the weight table, making "add a scored field" an N=1 change (SC-010).

**Alternatives considered**:
- Sort alphabetically — hides logical grouping; diverges from `scoring.md`'s presentation.

---

## 12. `by_field` key naming in the run summary

**Decision**: Use dotted names matching `field_results` (e.g. `"company_name.value"`, `"address.city"`, `"tax_ids.ein"`). One entry per scored field, same 18 keys as `SCORED_FIELDS`. Each value is the corpus-wide **unweighted** accuracy: `(match_count + 0.5 × partial_count) / applicable_field_count` aggregated across documents where the field is applicable.

**Rationale**: US2 AC#4 explicitly names the dotted keys. Using the same key shape as `field_results` makes debug diffs trivial ("this document's accuracy dragged the corpus accuracy down"). The unweighted formula is consistent with the per-document `comparison_summary.field_accuracy` definition pinned by the Q1 clarification.

**Alternatives considered**:
- Aggregate `address` into one bucket — loses diagnostic resolution; mismatches `field_results`.
- Flattened underscore names — divergent from everywhere else in the schemas.

---

## 13. Corpus-mode lazy evaluation strategy

**Decision**: Corpus mode calls `evaluate_document(folder)` directly (as a Python function, not via `subprocess`) for any folder lacking a readable `evaluation_document.json`. Results are collected in memory; the `evaluation_run_summary.json` is written only after every document succeeds. If any document hard-fails (missing inputs, schema drift, `document_id` mismatch), no summary is written and the CLI exits non-zero (FR-020, FR-022). Newly-written `evaluation_document.json` files are **not** rolled back on hard error — each per-document file is independently valid or absent.

**Rationale**: Q2 clarification says corpus mode auto-evaluates missing per-document results. In-process invocation avoids the overhead and determinism risk of a subprocess fan-out. Leaving successful per-document files on disk is the right tradeoff: they're valid evidence regardless of whether the corpus as a whole succeeded, and the next corpus run will pick them up without re-work.

**Alternatives considered**:
- Subprocess per document — slower and introduces a timestamp drift opportunity.
- Two-phase commit with rollback — complexity without benefit; each `evaluation_document.json` is independently correct.

---

## 14. Markdown report format

**Decision**: Two-column-free, wrap-free Markdown:

```
# Stage 1 Evaluation Run Summary

- Run ID: {run_id}
- Document count: {N}
- Overall pass rate: {x.xxx}
- Vendor identity pass rate: {x.xxx}
- Review routing pass rate: {x.xxx}
- Field accuracy: {x.xxx}

## By difficulty

| Difficulty | Docs | Field accuracy | Pass rate |
|---|---|---|---|
| easy | ... | ... | ... |
| medium | ... | ... | ... |
| hard | ... | ... | ... |
| missing_name | ... | ... | ... |

## Failing documents

- {doc_id} ({difficulty}) — {one-line reason}
- ...
```

If zero documents fail, the `## Failing documents` section renders "_All documents passed._" (literal underscores for italics).

**Rationale**: Renders cleanly in GitHub, VS Code, and terminal. Deterministic ordering (`easy` → `medium` → `hard` → `missing_name`; failing docs sorted by `document_id` ascending). No emoji, no ANSI codes, no wall-clock formatting — keeps SC-005 determinism intact.

**Alternatives considered**:
- Rich-formatted table (ANSI) for terminal — would diverge from the on-disk file and violate Q4's byte-identical requirement.
- HTML — overkill for a one-pager.

---

## 15. Reuse of `dartwing_ocr.validator.loader`

**Decision**: The evaluator imports `load_contract_set` and `validate_artifact` from `dartwing_ocr.validator` rather than re-implementing Draft-2020-12 validation. It uses them as a private dependency (no re-export) and passes through their exceptions for schema failures.

**Rationale**: The validator has already proven this path in the 001 feature; duplicating it would desync. Keeping the import one-way (evaluator → validator, never back) preserves the harness-boundary spirit of constitution §I.

**Alternatives considered**:
- Copy the schema-loading code — creates a maintenance fork.
- Fresh `jsonschema.Draft202012Validator` per call — drops the caching the loader already does.

---

## 16. Fixture authorship

**Decision**: Every fixture under `tests/evaluator_tests/fixtures/` is hand-authored JSON — no dependency on the upstream `006-corpus` feature. Fixtures are minimal (only the keys each test needs to flip) and use small-but-realistic vendor data. The 20-document `corpus_20/` fixture is generated once into the repo and committed; it does not shell out to the real pipeline.

**Rationale**: Keeps tests hermetic (no flakiness from upstream schema drift) and preserves the constitution's harness/pipeline separation: the evaluator's tests never run extraction. The committed fixtures are small (~40 JSON files under 10 kB each) — well within repo hygiene.

**Alternatives considered**:
- Generate fixtures at test-time from a factory — introduces non-determinism risk and obscures what each test is actually asserting.
- Reuse `tests/stage1_vendor_identity/` — that corpus is for end-to-end pipeline tests and doesn't have the pathological partial-match coverage this evaluator needs.

---

## Summary of resolved unknowns

All items above are **decided**. No `NEEDS CLARIFICATION` remains in the Technical Context. Phase 1 can proceed.
