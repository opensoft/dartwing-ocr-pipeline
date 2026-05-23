# Security Clarify Questions — Feature 022 (Pre-Implement Gate)

**Created**: 2026-05-23
**Purpose**: Resolve the 30 unchecked items in `checklists/security.md` before `/speckit.implement` begins. The MVP slice (T001–T042) is held until these are answered.
**How to answer**: Edit this file. Replace `→ ANSWER: <option>` lines with your chosen letter (and any free-text notes). For free-text questions, edit the placeholder. When done, tell me "answers ready" and I'll walk security.md to close each item per your decisions.

---

## Auto-close items (informational — no answer needed)

These 9 items are closing themselves and will be marked `[x]` with one-line rationale citing the existing artifact that addresses them. **You do not need to answer anything for these — they're listed only so you know what I'll close on your behalf.**

| CHK | Item | Why it's auto-closeable |
|-----|------|--------------------------|
| CHK012 | FR-008 scope (gate module vs wider evaluator) | MI-1 scopes the prohibition to the gate module only — already explicit |
| CHK014 | Network-blocking test mechanism | Tasks.md **T031** adds the socket-mock + Paddle-import-audit test |
| CHK015 | FR-008 / FR-029 overlap independently testable | MI-1 covers both under a single invariant; treating them as one is correct |
| CHK017 | SC-007 ↔ FR-008 cross-reference omission | Spec-quality only; both already covered by MI-1 in code |
| CHK027 | Sanitization/redaction in failed-check records | **FR-015 mandates FULL evidence** in each failed-check record; no redaction by design |
| CHK030 | Normalized strings ephemeral, not persisted | T039 returns the normalized search string as an in-memory `BodyOcrEvidence` field; never serialized |
| CHK037 | Concurrent-process race conditions | Existing evaluator pattern is single-process; no concurrent-write guard exists in any prior feature |
| CHK038 | Input provenance trust | R-022.13 step-3 (schema validation) IS the gate's chosen trust model; documented decision |
| CHK040 | Documented absence of security review requirement | Spec-quality only; the absence is implicit per the feature's harness-only scope |

---

## Q-SEC-1 — Bucket B governance items (bulk decision)

**Affects 12 items**: CHK004, CHK005, CHK006, CHK008, CHK009, CHK010, CHK020, CHK022, CHK024, CHK026, CHK028, CHK039

All 12 items ask whether feature 022 defines a security/PII/governance policy for some surface (sidecar sensitivity classification, scrubbing/anonymization, promotion authorization, data retention, evaluation-report PII handling, log-level redaction, provenance evidence, calibration screening, notes.md convention, tax-id token PII, real-vs-synthetic tiering, access-logging). The per-item annotations all say `STILL OPEN at impl-time: deferred to platform / corpus governance / outside feature 022 scope`. None of them block code; the question is how to mark them in `security.md`.

**How would you like these 12 items handled?**

- **A.** Bulk-close all 12 as `[x]` with the annotation: *"Closed 2026-05-23: deferred to platform/corpus governance per spec.md §Out of Scope; feature 022 is evaluator/harness-only and inherits the existing labeling-guide PII discipline for inputs."*
- **B.** Keep all 12 open as a permanent known-gap inventory; add a new bullet to spec.md §Out of Scope listing them collectively
- **C.** Mixed — bulk-close most but leave specific items open. Specify which in the free-text below.

→ **ANSWER**: A — bulk-close all 12 as deferred to platform/corpus governance
per spec.md §Out of Scope. Feature 022 is evaluator/harness-only and inherits
the existing labeling-guide PII/license discipline for inputs.

---

## Q-SEC-2 — Identifier safety: `row_id` + `document_id` validation rules

**Affects 3 items**: CHK007 (row_id PII), CHK029 (document_id PII), CHK031 (pathological row_id input like path-traversal sequences)

Current rule (spec.md FR-002 / FR-003 + schema `semantic_table_truth.schema.json`): `row_id` and `document_id` must be non-empty strings; `row_id` must be unique within the sidecar; `document_id` must match the folder basename. No character-class restriction. No length cap.

**Should the validator enforce additional safety constraints on these identifiers?**

- **A.** No additional constraint — folder-naming convention (canonical pattern `^inv_\d{3}_(easy|medium|hard)$` for `document_id`) plus labeling-guide naming conventions for `row_id` are sufficient. Pathological values are an author error caught at code-review time, not at validator time.
- **B.** Add a permissive pattern to both fields: e.g. `^[A-Za-z0-9_-]{1,64}$` (alphanumeric + dash/underscore, ≤64 chars). Catches path-traversal sequences, control characters, and runaway lengths without being onerous to authors.
- **C.** Length cap only — e.g. `maxLength: 128` on both fields; no character-class restriction.
- **D.** Other — describe in free-text below.

→ **ANSWER**: B — add a permissive safety pattern to both fields:
`^[A-Za-z0-9_-]{1,64}$`. This keeps canonical fixture names and ordinary row
IDs valid while rejecting path traversal, whitespace/control characters,
punctuation-heavy PII-style labels, and runaway identifier lengths.

---

## Q-SEC-3 — Resource guards on sidecar + `preprocess_output.json` size

**Affects 2 items**: CHK032 (sidecar size), CHK035 (`preprocess_output.json` body OCR size)

Q38 explicitly excludes performance/resource NFRs from feature 022. The gate currently has no upper bound on rows/tokens — an adversarially or accidentally large sidecar (10,000 rows) or `preprocess_output.json` (millions of tokens) would consume memory linearly.

**Should the impl add resource guards?**

- **A.** No — consistent with Q38 (no perf NFRs). Trust inputs; the operator is responsible for sane corpus sizes.
- **B.** Add advisory log warning if a sidecar exceeds N rows or `preprocess_output.json` exceeds M tokens — no hard fail. (Specify N, M if A is not chosen.)
- **C.** Add hard limits with specific values. Specify limits in free-text.
- **D.** Other — describe.

→ **ANSWER**: A — no resource guards in feature 022. This stays consistent with
Q38: no performance/resource NFRs and no tunable thresholds in this evaluator
slice. Corpus size discipline remains an operator/platform concern.

---

## Q-SEC-4 — File permissions on evaluator artifacts

**Affects 1 item**: CHK036

`evaluation_document.json` and `evaluation_run_summary.json` will carry row-level failed-check evidence that may include fragments of invoice OCR text (vendor names, amounts, descriptions). The existing feature 007 evaluator writes these artifacts with default umask permissions (typically `0644`).

**Should the impl write these artifacts with restricted permissions?**

- **A.** No — use OS umask default (consistent with feature 007 and the rest of the evaluator). Filesystem-level access control is a platform concern.
- **B.** Yes — chmod 0640 after write (owner read/write, group read, world none).
- **C.** Yes — chmod 0600 after write (owner only).
- **D.** Other — describe.

→ **ANSWER**: A — use OS umask/default permissions, consistent with feature 007
and existing evaluator artifacts. Filesystem-level access control remains a
platform concern.

---

## Q-SEC-5 — Gate behavior if a network call is attempted at runtime

**Affects 1 item**: CHK013

MI-1 mandates "no network I/O ever" in the gate. T031 verifies this with a socket-mock test at test-time. The spec is silent on what happens if a future regression introduces a network call at runtime (e.g. a transitive import adds an HTTP client that gets initialized).

**What should the runtime do if a network call is somehow attempted from gate code?**

- **A.** Nothing defensive at runtime — MI-1 is a code invariant; rely on T031 to catch regressions at CI time. Trust the test suite.
- **B.** Module-load-time defensive check — assert no Paddle/HTTP-client imports landed in `sys.modules` after `import dartwing_ocr.evaluator.semantic_quality`; raise `SemanticGateInvariantError` if any did. (Same check as T031, but always-on, not just in test mode.)
- **C.** Stronger runtime check — monkey-patch `socket.socket.connect` at gate-entry time to raise `SemanticGateInvariantError`, restore on exit. Hard guarantee but adds runtime cost and weird side-effect.
- **D.** Other — describe.

→ **ANSWER**: A — no always-on runtime monkey-patch or import sentinel. MI-1 is
a code invariant and T031 is the enforcement mechanism; CI/test-time socket and
import auditing should catch regressions without adding side effects to normal
evaluator execution.

---

## Q-SEC-6 — Localhost endpoints under FR-029

**Affects 1 item**: CHK016

FR-029 forbids "a remote service, a network call". The pipeline elsewhere uses localhost Ollama (feature 005 extractor). The semantic gate never calls Ollama by design — but the spec doesn't explicitly define whether "network call" includes `localhost`/loopback.

**How should the impl interpret FR-029 for the semantic gate?**

- **A.** All network I/O is forbidden, including localhost/loopback — the gate is fully offline; even a Unix socket or `127.0.0.1` call would violate FR-029. (Most restrictive; matches MI-1's "no network I/O" wording.)
- **B.** Only remote (non-loopback) endpoints are forbidden — localhost is fine. (Permissive; would allow gate to call localhost Ollama if a future feature wanted it.)
- **C.** Moot — the gate never makes any HTTP/socket call by design (Q-SEC-5 + MI-1), so localhost distinction is irrelevant. Document as moot in security.md closure note.
- **D.** Other — describe.

→ **ANSWER**: A — all network I/O is forbidden for the semantic gate, including
localhost, loopback, Unix sockets used as network transports, Ollama, and any
remote endpoint. The gate must remain fully offline.

---

## Q-SEC-7 — Add "air-gapped operation" as a named requirement?

**Affects 1 item**: CHK018

FR-008 + FR-029 + MI-1 together imply the gate operates correctly in an air-gapped/offline environment, but no requirement says this explicitly. An operator running the evaluator on a disconnected machine has no spec-level promise that it will work.

**Should air-gapped operation be added to the spec?**

- **A.** No — implied by FR-008 + FR-029; no need to restate. Operators relying on offline operation can infer the guarantee from those FRs.
- **B.** Yes — add a one-line FR (e.g. FR-034): *"The semantic gate MUST execute correctly in an air-gapped environment with no network access of any kind."*
- **C.** Yes — add a Success Criterion SC-011: *"The gate produces identical verdicts on a network-isolated host (verified by running the gate inside a container with `--network=none`)."*
- **D.** Other — describe.

→ **ANSWER**: B — add a one-line functional requirement: "The semantic gate MUST
execute correctly in an air-gapped environment with no network access of any
kind." Do not add a new SC/container-network test for this round; T031 remains
the concrete enforcement test.

---

## How to deliver your answers

When done, just say "answers ready" (or paste the file contents back). I'll:
1. Auto-close the 9 informational items per the table above
2. Apply your Q-SEC-1 decision to the 12 Bucket B items
3. Apply Q-SEC-2 through Q-SEC-7 decisions to the 9 impl-relevant items
4. Update security.md so all 40 items are `[x]`
5. If any of your decisions require spec/data-model/contracts/tasks changes (e.g. Q-SEC-2 = B adds a schema pattern; Q-SEC-7 = B adds FR-034), I'll surface those and pause for your confirmation before editing
6. Confirm security.md is 40/40 closed, then prompt for `/speckit.implement` MVP slice to proceed

Total questions: **7** (1 bulk + 6 focused). Free-text needed only if you pick an "Other" option or specify limits.
