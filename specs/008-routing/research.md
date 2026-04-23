# Phase 0 Research: Deterministic Routing

This document resolves the unknowns surfaced in `plan.md`'s Technical Context
and pins down the small number of technical choices left open after the 2026-04-21
clarification session. Every decision below is scoped to what stage 1 actually
needs — one `edge_extraction_output.json` in, one `routing_decision.json` out,
deterministic, no model calls, no new third-party dependencies.

Clarifications already pinned in `spec.md` (not re-litigated here):

- **Confidence has no role in scores or decisions** (Q1 → FR-018 tightened).
- **Canonical score formulas** are per-category grounding fractions, equal-weight
  overall (Q2 → FR-017).
- **`reasons` array ordering** follows the FR-015 priority order, then
  affirmatives, then informational notes (Q3 → FR-015 extended).
- **CLI entry point** is `python -m ledgerlinc_ocr.router route <folder>` (Q4 →
  FR-025 pinned).

---

## Decision 1 — Input validation path: reuse `ledgerlinc_ocr.validator`

**Decision**: The router loads `edge_extraction_output.json` and validates it
against `contracts/stage1_vendor_identity/v1.0.0/edge_extraction_output.schema.json`
by delegating to the existing in-repo validator module
(`ledgerlinc_ocr.validator`). A validation failure is converted to a
`MalformedInputError`, which the CLI maps to exit code `2` with no
`routing_decision.json` written (FR-003, SC-006).

**Rationale**:
- Reuses a module already audited for correctness (001 / 002 / 003 all depend
  on it). Avoids a second copy of schema-loading logic that could drift.
- Keeps the contract-set boundary single-sourced: whoever bumps the validator's
  handling of `v1.0.0` schemas updates one code path, not two.
- Schema validation errors from `jsonschema` carry enough location info to
  produce a human-readable error message for stderr, satisfying FR-003's
  "human-readable error naming the specific failure cause".

**Alternatives considered**:
- **Ad hoc dict inspection in the router** (skip `jsonschema`): rejected because
  it silently passes inputs that violate the contract in ways routing doesn't
  look at (e.g., missing `invoice_header_fields` — routing wouldn't notice, but
  downstream slices would). The constitution's Schema-First principle requires
  treating the frozen contract as the boundary.
- **A thin new validation helper inside the router**: rejected as a duplicate of
  `ledgerlinc_ocr.validator`. No router-specific validation need justifies its
  existence.
- **`pydantic` models for the input**: rejected — pydantic's coercion is too
  permissive for a schema-first design (e.g., it would silently accept
  `"true"` for a boolean). `jsonschema` + the frozen schema is the authoritative
  shape.

---

## Decision 2 — Contract-version-drift is a hard error, not a warning

**Decision**: If `edge_extraction_output.json` reports `contract_set_version !=
"1.0.0"`, the router exits non-zero with a `VersionDriftError`, no
`routing_decision.json` is written, and a human-readable error names the
offending version. The router NEVER silently accepts a drifted input by
pretending it is `"1.0.0"`.

**Rationale**:
- FR-003 and SC-006 mandate a non-zero exit with no output on version drift.
- Drift is almost always a contract-set amendment in flight (governance path in
  `contracts/stage1_vendor_identity/AMENDMENTS.md`). Routing reading a future
  version as if it were `"1.0.0"` could silently emit structurally plausible
  but semantically wrong decisions — the worst possible failure mode for a
  deterministic gate.
- Matches the stance the validator already takes (`major-equal` rule in
  `validator/version.py`). Routing is stricter (exact-equal) because it is a
  decision-making component: minor-patch shifts that the validator would
  tolerate still warrant a policy review for routing.

**Alternatives considered**:
- **Major-equal compatibility** (mirror the validator's rule): rejected for
  routing because routing rules are coupled to the specific shape of the
  input, not just to the major version. A `1.1.0` input could introduce a new
  field that routing would need to inspect; silently running on it risks wrong
  decisions. When `1.1.0` lands, this rule gets a deliberate update.
- **Warn-and-continue**: rejected because FR-003 explicitly requires no artifact
  on drift. The constitution's Deterministic Control principle is undermined if
  unexpected inputs produce a decision.

---

## Decision 3 — `policy_version` string and lifecycle

**Decision**: `policy_version = "stage1-routing-policy-v1.0.0"` for this
feature's initial ship. A change to any routing rule, threshold, or canonical
review-reason string bumps the patch (`v1.0.1`) or minor (`v1.1.0`) component
per semver; an incompatible rule redesign bumps the major (`v2.0.0`).

**Rationale**:
- FR-005 requires `policy_version` to be a non-empty identifier that bumps on
  any rule change. Semver is the lightest convention that communicates
  back-compat intent to a reviewer looking at two `routing_decision.json` files
  from different runs.
- The `stage1-routing-policy-` prefix distinguishes routing policy from
  `pipeline_version` (which identifies the build, not the policy). When the
  ensemble routing policy lands, it will ship as `stage1-routing-policy-v2.0.0`
  or a new prefix.
- Canonical review-reason strings (`"company_name_inferred"`, etc.) are part of
  the policy. Changing any of them requires a bump (SC-010).

**Alternatives considered**:
- **Git SHA of the router module**: unstable across build environments (CI vs
  dev workstation), would force `processed_at`-like variance into a field that
  SC-004 requires to be deterministic.
- **Single opaque identifier** (e.g., `routing-policy-A`): rejected — opaque
  identifiers give a reviewer no hint about relative age or compatibility.
- **Package version of `ledgerlinc_ocr`**: conflates policy with code. A
  no-op refactor of the router module would bump policy version for no
  semantic reason.

---

## Decision 4 — `pipeline_version` string scheme (mirror 003)

**Decision**: `pipeline_version = "stage1-routing-v0.1.0"` for the initial
ship. The prefix + semver shape mirrors `003-pdf-preprocessing`'s
`stage1-preprocess-v0.1.0` convention. Unlike preprocessing, the router has
no model / DPI / weights to encode — the build identifier is intentionally
simple because the router has no inference-time dependencies.

**Rationale**:
- Mirrors a precedent already shipped (`src/ledgerlinc_ocr/preprocessing/version.py`),
  so a reviewer reading two stage 1 artifacts from different slices sees a
  consistent identifier shape.
- Keeps `pipeline_version` orthogonal to `policy_version`. A refactor of the
  router's Python code (no rule change) bumps `pipeline_version`; a rule change
  bumps both.
- No need to hash model weights or pin an external library version: the router
  has no third-party inference dependency (see Decision 1).

**Alternatives considered**:
- **Match 003's weight-hash scheme**: overkill; there are no weights.
- **Omit `pipeline_version` prefix**: rejected — consistency with 003 aids
  grep-ability across the corpus output set.

---

## Decision 5 — `address_score` denominator and `street` treatment

**Decision**: `address_score = count(grounded) / 5` where the denominator is
the fixed set `{street_1, city, state, postal_code, country}`. `street_2` is
excluded from the scoring denominator because it is a structurally optional
sub-component (e.g., "Apt 2B") and would bias every address score downward in
the common case where it is null. The clarification's "{street, city, state,
postal_code, country}" language maps to `street_1` in the actual schema.

The `checks.address_has_minimum_components` boolean uses a different
(narrower) rule — `city AND state AND postal_code` all grounded (FR-010). The
two rules are deliberately distinct: the score captures "how much of the
address did we find" (graded), the check captures "does the address count as
one secondary identifier for the floor" (binary).

**Rationale**:
- The `edge_extraction_output` schema splits street into `street_1` and
  `street_2` (inspected in `contracts/stage1_vendor_identity/v1.0.0/edge_extraction_output.schema.json`,
  `$defs.address`). Counting both separately would cap most real-world address
  scores at ~0.83 and make the score depend on whether a vendor happened to
  have an "Apt" line. Not a useful signal.
- Counting `street_1` only keeps the canonical 5-component set from the
  clarification without changing the numeric behavior implementers expect.
- The score denominator and the `address_has_minimum_components` threshold are
  intentionally different; the spec already pins this in FR-010 and the
  clarification fixed the scoring side. This decision just resolves the "which
  street field" ambiguity introduced by the schema layer.

**Alternatives considered**:
- **Denominator of 6 (street_1 + street_2 both count)**: rejected per above —
  biases scores downward for no signal.
- **Count `street` grounded iff either `street_1` or `street_2` is grounded**:
  rejected because it rewards a partial address (only `street_2`) as fully as a
  complete one, misaligning with the evaluator's "city+state+postal" stance.
- **Include country with a smaller weight**: rejected — the clarification pinned
  equal weight across the 5 components, and weighted components would reopen
  the formula question.

---

## Decision 6 — Phone's role in the secondary-identifier floor

**Decision**: `phone` counts as one independent secondary identifier for the
floor of 2 in FR-014, separate from `website_or_email_present`. The four
secondary-identifier slots the floor counts are:

1. `checks.address_has_minimum_components` (one slot)
2. `checks.at_least_one_tax_id_present` (one slot)
3. `checks.website_or_email_present` (one slot — website and email together
   count as one, per the aggregate boolean name and the edge case at
   `spec.md:113`)
4. `phone`-grounded (one slot — computed inline from the input, since there
   is no `checks.phone_present` boolean in the schema)

The floor requires `true_count(1..4) >= 2` for `edge_accept`. Strictly fewer
than 2 forces `edge_review_required` with canonical reason
`"secondary_identifiers_insufficient"`.

**Rationale**:
- The schema's `checks` block does NOT include a `phone_present` boolean, so
  the router must compute phone-grounding inline to participate in the floor.
  This matches the spec's explicit note in FR-014: "Phone-grounded is inspected
  as an additional identifier independently of the schema's aggregate
  boolean".
- The edge case at `spec.md:110` states "phone counts as one" secondary
  identifier, aligning with the evaluator's pinned definition.
- `website_or_email_present` as one slot (not two) matches the schema's
  aggregate boolean intent and the edge case at `spec.md:113`.

**Alternatives considered**:
- **Count `website` and `email` separately** (five slots): rejected — the
  schema's single aggregate boolean signals that the evaluator treats them as
  one "contact" identifier. Two slots would over-count documents with both.
- **Omit phone from the floor** (three slots): rejected — contradicts FR-014
  and the edge case at `spec.md:110`, and would silently drop one valid
  secondary identifier.
- **Publish `phone_grounded` as a new `checks` boolean**: rejected — the
  schema is frozen at `v1.0.0`; adding a key requires a contract-set amendment.
  Inline computation is correct and contract-compatible.

---

## Decision 7 — JSON dump settings for byte-identical determinism

**Decision**: `routing_decision.json` is written using
`json.dumps(artifact, indent=2, sort_keys=False, ensure_ascii=False)` followed
by a single trailing newline. Key ordering within the output dict is controlled
explicitly by the assembly order in `artifact.py` (a fixed key order matching
the schema's `required` list). `float` values in `scores` are serialized with
Python's default `repr`, which is deterministic for the finite-precision
fractions produced by the canonical formulas.

**Rationale**:
- SC-004 requires byte-identical output across reruns except for
  `processed_at`. `indent=2` + explicit assembly order + no dict-iteration
  surprises delivers this deterministically on any CPython ≥ 3.7 (dict
  insertion order is stable).
- `sort_keys=False` is used because the schema's `required` array imposes a
  natural read order (`contract_set_version`, `pipeline_version`, …) and
  alphabetical key sort would bury `decision` inside the artifact. Explicit
  assembly order matches how the other stage 1 artifacts are written.
- Per-category score fractions are exact rationals with small denominators
  (`/3`, `/4`, `/5`) plus their mean, so `float` serialization produces the
  same string on every Python run. No rounding rule is needed.

**Alternatives considered**:
- **`sort_keys=True`**: simpler but reorders the artifact in a way that hurts
  human readability (`consensus_summary` would appear before `contract_set_version`
  alphabetically is fine, but `decision` and `review_status` get separated).
- **`indent=None` (one-line JSON)**: rejected — makes artifact diffs unusable
  for human review.
- **Round scores to a fixed decimal precision**: not needed because the formulas
  produce exact fractions; rounding would introduce a new rule to pin in
  `policy_version` with no corresponding signal benefit.

---

## Decision 8 — `processed_at` format

**Decision**: `processed_at` is produced by
`datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` — UTC,
second precision, `Z` suffix. It is the single field exempt from SC-004's
byte-identical requirement.

**Rationale**:
- JSON Schema `format: date-time` requires RFC 3339, which this format
  satisfies.
- Matches the precedent in 003 preprocessing and the validator's expectations.
- Second precision is sufficient (wall-clock is not used for any decision and
  sub-second precision would add noise for no value).

**Alternatives considered**:
- **Millisecond precision**: unnecessary; routing is fast enough that every run
  in a single second is plausible, reducing debug value.
- **Local timezone**: rejected — corpus runs across environments would produce
  divergent artifacts that read as different decisions when they are identical.

---

## Decision 9 — Affirmative `edge_accept` reason strings vocabulary

**Decision**: The router emits a short closed vocabulary of affirmative reason
strings when writing `edge_accept`. The vocabulary is part of `policy_version`:

- `"company_name_explicit"` — `company_name.present == true AND inferred == false AND evidence non-empty`
- `"spam_gate_passed"` — `checks.post_extraction_spam_gate_passed == true`
- `"secondary_identifier_floor_met"` — at least 2 of the 4 FR-014 slots are true
- `"upstream_extraction_ok"` — input `status == "success"`

When `edge_accept` fires, all four strings appear in `reasons` in that order
(after the [empty] forcing-rules section, matching the FR-015 post-priority
ordering from clarification Q3). When `edge_review_required` fires, affirmative
strings are NOT emitted — only the firing forcing-rules plus any informational
entries.

**Rationale**:
- FR-016 requires `edge_accept` to be traceable (non-silent). A closed
  vocabulary keeps the artifact machine-grep-able (a future reviewer scan can
  count `"secondary_identifier_floor_met"` matches across the corpus).
- Four affirmatives parallel the four forcing rules: one-to-one mapping makes
  the priority ordering and reason traceability mechanically obvious.
- Including the strings in `policy_version` means renaming any of them bumps
  the policy (consistent with SC-010).

**Alternatives considered**:
- **Free-form strings**: rejected — defeats machine-grep-ability and silently
  drifts between runs.
- **Only emit affirmatives for the rules that had a meaningful decision
  path**: rejected — FR-016 requires `edge_accept` to name the affirmative
  conditions met; listing them all is no worse than listing a subset and
  removes a "when do we include which" rule.

---

## Decision 10 — Informational-reason strings (non-forcing)

**Decision**: Two informational reason strings are pinned for surfacing
non-decision-driving conditions:

- `"upstream_status_partial"` — emitted when input `status == "partial"`
  (added after forcing-rules, after affirmatives). FR-020.
- `"contract_violation_detected"` — emitted when the input reports an extractor
  invariant violation (FR-024) — e.g., `present == true AND inferred == true`
  or `present == false AND inferred == false`. Surfaced alongside `status ==
  "partial"` and a defensive `edge_review_required`.

Both strings are part of `policy_version`.

**Rationale**:
- FR-020 and FR-024 both require surfacing non-ideal input conditions without
  necessarily forcing review based on them alone. Pinning canonical strings
  here keeps the `reasons` array machine-readable for the evaluator (007) and
  future harness scripts.
- Keeping the informational vocabulary closed avoids free-form drift.

**Alternatives considered**:
- **Inline the extractor's `warnings` strings verbatim**: rejected — those
  strings are extractor-owned and not part of this policy. A canonical
  informational entry tagged via the policy's vocabulary is stable; the
  extractor's actual text can be folded in as a parenthetical if ever needed.

---

## Decision 11 — Upstream-failure handling: defensive `edge_review_required`, output `status` mirrors input when "partial", falls to `"partial"` or `"failure"` when input is `"failure"`

**Decision**:

- Input `status == "success"` → output `status = "success"` (unless the router
  itself flags a non-fatal issue such as a contract-violation input — in that
  case, `status = "partial"`).
- Input `status == "partial"` → output `status = "partial"`; routing rules
  still fire normally; `reasons` includes `"upstream_status_partial"`.
- Input `status == "failure"` → output `status = "partial"` (not `"failure"`,
  because the router succeeded at producing a schema-valid artifact);
  `decision = "edge_review_required"` defensively with canonical reason
  `"upstream_extraction_failed"`; `reasons` is exactly
  `["upstream_extraction_failed"]`. No other rules are evaluated because a
  failed extraction's structural booleans are untrustworthy. In particular,
  this short-circuit **subsumes FR-024**: even if the failed input also
  exhibits a forbidden `company_name` combo (`present == inferred`), the
  contract-violation informational entry is NOT emitted, because the
  `vendor_candidate` booleans the FR-024 check reads are exactly the ones
  this decision treats as untrustworthy. Affirmatives and
  `"upstream_status_partial"` are likewise suppressed.

**Rationale**:
- The schema allows `status ∈ {"success","partial","failure"}`. `"failure"` is
  reserved for the router itself crashing mid-run, which never happens on the
  happy path because failures exit before any file is written (Decision 2).
  Input `"failure"` produces a schema-valid artifact with `"partial"` status —
  the input failed, the router didn't.
- FR-020 and spec's US5 AC#3 pin this behavior.
- Defensive `edge_review_required` on upstream failure ensures no failed
  extraction is ever silently auto-accepted.

**Alternatives considered**:
- **Propagate `"failure"` directly to output**: rejected — misrepresents the
  router's own run state. Output `"failure"` should mean the router failed.
- **Still evaluate per-rule logic on a `"failure"` input**: rejected — the input's
  structural booleans are not meaningful when the extractor itself failed.
  Short-circuiting to a defensive review-required is clearer and aligns with
  US5 AC#3.

---

## Decision 12 — No corpus mode in this slice

**Decision**: The `route` subcommand only accepts a single per-document folder.
Corpus-wide orchestration (iterating `inv_001_easy`, `inv_002_easy`, …) is the
harness's concern and is deferred. `python -m ledgerlinc_ocr.router route
<folder>` is the complete public surface for this feature.

**Rationale**:
- Spec assumption (`spec.md:186`): "Corpus-level orchestration … lives in the
  harness and is not defined by this feature."
- A corpus mode would conflate two concerns: (a) the rule-based routing logic
  and (b) the iteration-and-report orchestration. Splitting them into two
  slices keeps this feature reviewable and lets the harness evolve
  independently.
- If a future need for `route-corpus` emerges, the `route` subcommand leaves
  room for it without renaming the module.

**Alternatives considered**:
- **Ship `route-corpus` in this slice**: rejected — would push this feature past
  the stage 1 "one slice at a time" model and duplicate harness
  responsibilities.

---

## Resolved NEEDS CLARIFICATION summary

Every `NEEDS CLARIFICATION` item surfaced during plan drafting is now resolved:

| Item | Resolution |
|------|------------|
| Address score denominator — which street field? | Decision 5 — `street_1` only, denominator of 5. |
| Phone's role in the secondary-identifier floor | Decision 6 — independent slot, total of 4 slots. |
| JSON dump settings for byte-identical determinism | Decision 7 — `indent=2, sort_keys=False`. |
| `processed_at` format | Decision 8 — UTC, second precision, `Z` suffix. |
| `policy_version` format and bump rules | Decision 3 — semver prefixed `stage1-routing-policy-`. |
| `pipeline_version` format | Decision 4 — `stage1-routing-v0.1.0`. |
| Contract-version-drift behavior | Decision 2 — hard error, exact-equal check. |
| Affirmative reason strings | Decision 9 — pinned closed vocabulary. |
| Informational reason strings | Decision 10 — pinned closed vocabulary. |
| Upstream failure handling | Decision 11 — defensive review-required; output status reflects router run, not input. |
| Corpus mode scope | Decision 12 — deferred to harness. |
| Input validation approach | Decision 1 — reuse `ledgerlinc_ocr.validator`. |
