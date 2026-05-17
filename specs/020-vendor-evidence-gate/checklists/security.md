# Security Checklist: Deterministic Vendor-Identity Signals And Early Accept Gate

**Purpose**: Release-gate validation that the spec defines security-relevant
requirements with the rigor needed for a pure-Python data-handling layer:
input validation on the consumed `preprocess_output.json` dict, ReDoS-safety
of the three pinned regex patterns, PII handling for tax-id / vendor-name
tokens that land on operator surfaces, information-leakage discipline for
`run_summary` and stderr emissions, supply-chain hygiene, and least-privilege
discipline appropriate to a local-pipeline component with no network or
auth surface. Every item validates the **requirements**, not the
implementation.
**Created**: 2026-05-16
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + security reviewer)

## Threat Model and Scope

- [x] CHK001 Is the threat model for this feature documented (in spec, plan, or research) — specifically that the gate is a pure-Python read over operator-trusted `preprocess_output.json` content with no network surface, no auth surface, no credential handling, and no remote data exfiltration path? [Gap, Spec §FR-001 / Plan §Storage]
- [x] CHK002 Is the rule "no network call, no external API, no remote model call" stated for the gate computation, so the read-only-from-disk closure is auditable? [Clarity, Plan §Technical Context / Spec §Out of Scope]
- [x] CHK003 Is the trust boundary between the gate (consumes `preprocess_output.json`) and its producers (preprocessing strategies in features 018/019) documented, so a future contributor knows the gate trusts the producer's schema validation? [Gap, module-invariants.md MI-1 / MI-2]
- [x] CHK004 Is the rule "no new external API, no new escalation surface, no new remote model call" stated as out-of-scope for this feature so a future maintainer cannot smuggle one in under the gate banner? [Clarity, Spec §Out of Scope]
- [x] CHK005 Is the threat boundary "the gate runs in the same process as preprocessing and pipeline; same trust level" stated so a reviewer doesn't expect IPC/serialization isolation? [Gap, Plan §Constitution Check row I]

## Input Validation on `preprocess_output.json`

- [x] CHK006 Does the spec or contract define what the gate does when `preprocess_output.json` is malformed (missing required keys, wrong types, extra keys, deeply nested unexpected structures)? [Coverage, Gap — failure-handling.md CHK016]
- [x] CHK007 Does the spec define whether the gate trusts the producer's schema validation (i.e., the canonical `contracts/stage1_vendor_identity/v1.2.0/preprocess_output.schema.json` already validated it) or re-validates inside the gate? [Clarity, Gap]
- [x] CHK008 Is the rule "the gate consumes only the `preprocess_output` dict — never `edge_extraction_output`, `routing_decision`, or `final_structured_payload`" enforced at the type-signature level, so a privilege-creep regression is structurally impossible? [Clarity, module-invariants.md MI-2 / MI-3]
- [x] CHK009 Does the spec define a maximum size or page count for a `preprocess_output.json` the gate will accept, or is the gate documented as scaling linearly with input size with no upper bound? [Gap, Coverage]
- [x] CHK010 Is the rule "the gate writes nothing to disk, makes no environment mutation, and has no in-process mutable globals" stated so a future maintainer cannot accidentally add a side-effecting cache? [Clarity, data-model.md §10 / module-invariants.md MI-1]
- [x] CHK011 Does the spec define behavior when a block/box's recognized text contains control characters, null bytes, or other non-printable sequences (after NFKC normalization)? [Gap, R-020.3]

## Regex Safety (ReDoS Resistance)

- [x] CHK012 Are the three regex patterns (`BUSINESS_SUFFIX_RE`, `TAX_ID_EIN_RE`, `TAX_ID_VAT_RE`) documented with their literal source code so a reviewer can audit them for catastrophic-backtracking risk without reading code? [Clarity, R-020.4 / data-model.md §6]
- [x] CHK013 Is each pattern bounded in repetition (no unbounded `.*` or `.+` outside word boundaries) — specifically `BUSINESS_SUFFIX_RE` is a fixed alternation with `(?![\w-])` end-lookahead, `TAX_ID_EIN_RE` is `\d{2}-\d{7}` with `(?<![\w-])` / `(?![\w-])` lookarounds (fully bounded), `TAX_ID_VAT_RE` is `[A-Z]{2}(?=[A-Z0-9]{2,12}\b)[A-Z0-9]*\d[A-Z0-9]*` (bounded to 14 chars via the lookahead AND requires ≥1 digit per B2 post-review)? [Clarity, R-020.4]
- [x] CHK014 Does the spec state that patterns are applied to whitespace-tokenized strings (not to whole-document text), so worst-case match time scales with token count and per-token length, not document size squared? [Clarity, R-020.3 / R-020.4]
- [x] CHK015 Does the spec define the maximum token length the gate accepts before NFKC normalization, so a maliciously long single token cannot cause unbounded regex work? [Gap, R-020.3 / data-model.md §6]
- [x] CHK016 Is the rule "patterns MUST compile at module load (a regex compilation error is a developer error, not a runtime error)" stated as a hard contract so a malformed pattern cannot reach production? [Clarity, data-model.md §6]
- [x] CHK017 Does the spec discuss why catastrophic-backtracking is not a concern for the three patterns (no nested quantifiers, no alternation with overlapping prefixes, bounded repetition) — or is this analysis a gap? [Gap, R-020.4]
- [x] CHK018 Is the rationale for using whole-token `\b` boundary matching (rather than substring matching or lookarounds) documented as a deliberate ReDoS-mitigation choice? [Clarity, R-020.4 §Alternatives considered]

## PII Handling on Operator Surfaces

- [x] CHK019 Does the spec document what vendor-name candidate tokens (which may include identifiable business names) get serialized into `evidence_gate_documents[i].signals` and emitted on `run_summary` stdout? Specifically: `vendor_name_candidate_count` is an INTEGER (no PII), but the spec is silent on whether the actual candidate tokens are ever logged. [Clarity, R-020.10 / data-model.md §4]
- [x] CHK020 Is the rule "only counts and booleans appear in `evidence_gate_documents[i].signals` — never raw token text, never raw EIN/VAT values, never the matched candidate strings" stated explicitly so a future "add `vendor_name_candidate_tokens: list[str]` to signals" change is auditably forbidden? [Gap, Clarity]
- [x] CHK021 Does the spec define how `business_suffix_present` and `tax_id_shaped_present` (booleans) avoid leaking the matched value into operator-facing output? Specifically: do these signals leak whether a specific business suffix or tax-id pattern matched, or only that some match occurred? [Clarity, R-020.3]
- [x] CHK022 Is the rejection of UK NI / SSN-shaped tax-id patterns (R-020.4 §Alternatives considered) documented as a PII-safety decision tied to the `labeling-guide.md` PII screening checklist — so a future maintainer cannot add them without revisiting the screening rule? [Clarity, R-020.4 §Alternatives considered]
- [x] CHK023 Does the spec document whether `document_id` (per-document folder name like `inv_017_missing_name`) can itself carry PII — e.g., if a folder ever gets named after a real customer / vendor? [Gap, R-020.11]
- [x] CHK024 Is the rule "PII screening of the corpus follows `docs/stage1-vendor-identity/labeling-guide.md`" carried forward in this feature so signal computation cannot accidentally surface fixtures that violate the screening rule? [Consistency, R-020.4 §Alternatives considered]
- [x] CHK025 Does the spec define whether stderr warnings (e.g., `--evidence-gate-skip-fallback ignored:`) include any path or document content that could leak via CI/operator logs? [Gap, R-020.12]

## Information Leakage via Operator-Facing Surfaces

- [x] CHK026 Is the rule "only signal types (`int` / `int` / `float` / `bool` / `bool`) and the gate decision (one of three string literals) appear on `run_summary`" stated, so accidental serialization of richer objects is forbidden? [Clarity, data-model.md §4]
- [x] CHK027 Does the spec define whether the recorded `ocr_detection_confidence_mean` (a float) could be combined with `vendor_name_candidate_count` (an int) to fingerprint a specific document — and if so, whether that's an acceptable disclosure for the operator audience? [Gap, R-020.3]
- [x] CHK028 Is the rule "stderr warning fires exactly ONCE per run when the warn-and-proceed path triggers" stated so an attacker-induced warn-spam cannot flood operator logs? [Clarity, module-invariants.md MI-22]
- [x] CHK029 Does the spec define what happens if `evidence_gate_documents` is emitted with thousands of documents — does the run_summary stdout line have a size cap, or is it documented as scaling linearly with corpus size? [Gap, R-020.10]
- [x] CHK030 Is the rule "the warn message contains only the grep-able marker plus the active profile name (no document content, no file paths)" stated explicitly? [Clarity, R-020.12 / contracts/cli-contract.md §Help text]
- [x] CHK031 Does the spec define whether `run_summary` content is considered sensitive enough to redact before sharing externally (e.g., in a bug report) — or is it explicitly considered safe to share? [Gap]

## Supply Chain and Dependency Hygiene

- [x] CHK032 Is the rule "No new pinned dependency" stated explicitly so a reviewer can verify `pyproject.toml` is untouched by this feature's PR? [Clarity, Plan §Technical Context / §Primary Dependencies]
- [x] CHK033 Are the dependencies the gate uses at module load enumerated (`re`, `typing`, `dataclasses`, `collections.abc`, stdlib only — no third-party packages required for the gate body)? [Completeness, Plan §Technical Context]
- [x] CHK034 Does the spec define which Python version constrains `re` behavior (Python 3.12 per devcontainer), so a regex feature regression in an older Python wouldn't slip through? [Clarity, Plan §Technical Context]
- [x] CHK035 Is the rule "no new third-party package is imported by `evidence_gate.py` or `evidence_gate_optin.py`" enforced by a static check (e.g., the MI-4/MI-5 import-safety test from T008)? [Measurability, module-invariants.md MI-4 / MI-5]

## Least Privilege and Privilege Escalation

- [x] CHK036 Is the rule "the gate has no filesystem write access, no environment-variable mutation, no subprocess invocation" stated so the gate's privilege footprint is auditable as read-only-in-memory? [Clarity, data-model.md §10]
- [x] CHK037 Is the rule "the gate reads no environment variables at runtime — the only env var the feature touches is `LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK`, which is read once at CLI parse time in `evidence_gate_optin.py`" stated explicitly? [Clarity, R-020.1 / data-model.md §10]
- [x] CHK038 Is the rule "the gate does NOT consult `edge_extraction_output.json`, `routing_decision.json`, or `final_structured_payload.json`" stated as a structural privilege constraint (gate cannot see downstream artifacts that might contain richer PII)? [Clarity, module-invariants.md MI-2 / MI-3]
- [x] CHK039 Does the spec define whether the gate can be invoked outside the pipeline context (e.g., as a standalone CLI on an arbitrary `preprocess_output.json`), and if so, whether the operator running it has the same trust level as a pipeline operator? [Gap]

## Authentication and Authorization (N/A but Documented)

- [x] CHK040 Is "no authentication requirements" stated explicitly (the gate is a local pure-Python function, not a network surface), so a future reviewer doesn't expect auth wiring? [Clarity, Gap]
- [x] CHK041 Is "no authorization requirements" stated explicitly (no privileged operations, no per-user gating), so a future reviewer doesn't expect role-based controls? [Clarity, Gap]
- [x] CHK042 Does the spec document that the opt-in flag (`--evidence-gate-skip-fallback`) is operator-controlled, not user-controlled, and there is no per-document authorization decision — so the opt-in's threat model is "trusted operator with CLI access"? [Clarity, R-020.1 / cli-contract.md]

## Failure-Mode Security (Fail-Safe vs. Fail-Open)

- [x] CHK043 Is the rule "gate evaluation failure (e.g., malformed input) MUST NOT silently allow suppression — when the gate cannot produce a decision, suppression MUST NOT fire" stated as a fail-safe invariant? [Gap, R-020.8 / module-invariants.md MI-13]
- [x] CHK044 Does the spec define what `decision` value (if any) gets recorded in `evidence_gate_documents` when the gate fails on a document mid-corpus run — does the document drop out, get a sentinel decision, or fail the entire run? [Gap, failure-handling.md CHK013-CHK016]
- [x] CHK045 Is the rule "GPU bind failure when behavioral shape is selected MUST fail fast, NOT silently fall back" stated as a fail-safe (vs. fail-open) discipline? [Clarity, Spec §Edge Cases / failure-handling.md CHK009-CHK011]

## Audit and Traceability

- [x] CHK046 Is the rule "every gate decision is re-derivable from the recorded signal values plus the documented v1 decision table" stated so an audit trail to disk exists for every decision? [Clarity, Spec §SC-002 §SC-012 / evidence-gate-rule.md]
- [x] CHK047 Is the rule "the gate decision and signals are recorded on `run_summary` exactly once per document" stated, so audit reconstruction is unambiguous (no per-document gate spam, no duplicate records)? [Clarity, R-020.10 / module-invariants.md MI-18]
- [x] CHK048 Does the spec define whether `run_summary` lines are timestamped or otherwise correlatable with the run that produced them, so audit linking back to a specific invocation is possible? [Gap, R-020.10]
- [x] CHK049 Is the rule "promotion of a non-default opt-in requires recording quality-gate evidence in `research.md` Appendix B" stated as an audit requirement so a default flip cannot happen undocumented? [Clarity, Spec §FR-016 §FR-017 / R-020.14]

## Constitution and Provenance Alignment

- [x] CHK050 Does the spec confirm that this feature does NOT change how `company_name.present` / `company_name.inferred` / `manual_review_required` are computed (constitution Principle IV — Provenance and Review Safety)? [Consistency, Plan §Constitution Check row IV]
- [x] CHK051 Is the rule "the gate's `borderline` and `insufficient` states preserve feature 019's fallback unchanged — operators still see the same review-required signals downstream" stated, so the review-safety surface is not weakened? [Clarity, Spec §FR-009 §SC-011 / Plan §Constitution Check row IV]
- [x] CHK052 Does the spec document that the gate provides no shortcut around `manual_review_required` — i.e., even a `sufficient` gate decision does NOT clear or suppress downstream review flags? [Gap, Clarity]

## Verifiability of Security Claims

- [x] CHK053 For every claim (input validation, no-PII-leak, regex safety, no-new-dependency, least-privilege), is there a named test, audit task, or CI check that verifies it before merge? [Measurability, Plan §Testing]
- [x] CHK054 Is the import-safety static check (`test_evidence_gate_module_safety_unit.py`, T008) named as the enforcement mechanism for "no Paddle / no GPU dependency at module load"? [Measurability, tasks.md T008]
- [x] CHK055 Does the spec name a manual review step for the three regex patterns (a security review checkpoint before merge), or rely on the test suite alone? [Gap]

## Notes

- Check items off as completed: `[x]`
- Add comments or findings inline; reference the spec/plan/research/data-model/contract line when raising a defect
- This checklist tests **requirements quality** in the security domain, not implementation correctness
- Many items will surface as `[Gap]` because this feature is a narrow, local pure-Python component — gaps here are mostly "the spec doesn't explicitly address X because X is implicitly out of scope". For each `[Gap]`, the reviewer should decide whether to add explicit out-of-scope text to spec/plan or accept the silence
