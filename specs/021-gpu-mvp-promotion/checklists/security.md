# Security & PII Discipline Checklist: GPU MVP Promotion

**Purpose**: Validate that the security and PII-discipline requirements (no remote cloud, no new credential surface, scratch-root PII handling, inherited feature-020 PII rules, no committed-corpus mutation, runbook safety) are written with the precision needed to keep stage-1 vendor-identity processing within the established trust boundary.
**Created**: 2026-05-18
**Feature**: [spec.md](../spec.md), [plan.md](../plan.md), Constitution §I, §IV

This checklist tests the *writing quality of security and PII requirements*, not penetration-testing posture. Items target whether security surfaces are explicit, whether the trust boundary is unambiguous, and whether inherited PII discipline from feature 020 is preserved.

## Trust Boundary

- [X] CHK001 Is the trust boundary stated explicitly (workstation-local execution; host Ollama on localhost; no remote network calls beyond `127.0.0.1:11434`)? [Clarity, Spec §FR-002, §FR-032]
- [X] CHK002 Is the prohibition on remote cloud execution stated as MUST NOT in FR-032, with no implicit allowance for a "cloud-hybrid" mode? [Clarity, Spec §FR-032]
- [X] CHK003 Is the workstation GPU lane (`cloud-workstation` per Constitution §III) distinguished from a remote cloud provider (forbidden) — same artifact contract, no provider-managed deployment? [Clarity, Consistency, Constitution §I, Stage 1 Scope Constraint #5]
- [X] CHK004 Is the prohibition on adding remote endpoints / credentials enumerated (no API keys, no service accounts, no OAuth flows introduced by this feature)? [Completeness, Spec §FR-032]

## Credential & Secret Surface

- [X] CHK005 Is the requirement that no new credential surface is introduced (no environment variable holding a secret, no config file with sensitive defaults) stated explicitly? [Completeness, Spec §FR-032]
- [X] CHK006 Is the existing `OLLAMA_BASE_URL` environment variable (already established by feature 011/020) used as-is, with no additional secret-bearing env var added by this feature? [Consistency, Spec §FR-032]
- [X] CHK007 Is the new `configs/voter/ollama-gpu.yaml` (R-021.7) explicitly NOT a secret-bearing file (only `model_name: string` — a public Ollama model identifier)? [Clarity, Spec §R-021.7]
- [X] CHK008 Are requirements present that prevent the readiness helper from logging credentials, tokens, or environment variables in its stdout/stderr output? [Coverage, contracts/ollama-readiness-helper.md]

## Network Surface

- [X] CHK009 Is the helper's HTTP call surface bounded (`GET http://localhost:11434/api/ps` only, no other paths, no other verbs)? [Clarity, contracts/ollama-readiness-helper.md]
- [X] CHK010 Is the helper free of authentication headers (no `Authorization: Bearer ...`, no client certificates) — Ollama on localhost is unauthenticated by design? [Clarity, contracts/ollama-readiness-helper.md]
- [X] CHK011 Is the `--base-url` flag's intended use bounded — a future remote Ollama would be out of scope (FR-032), so the flag's default-`localhost` is the recommended-only path? [Coverage, Spec §FR-032, contracts/ollama-readiness-helper.md]
- [X] CHK012 Is the prohibition on outbound network calls outside the Ollama localhost endpoint stated, so a future addition to the helper or pipeline path requires explicit security review? [Coverage, Gap]

## Scratch-Root PII Handling

- [X] CHK013 Is the scratch-root directory (`/tmp/021-bench/`) location explicit, with awareness that `/tmp` may be world-readable on multi-user systems? [Coverage, Spec §FR-018, §R-021.1]
- [X] CHK014 Are requirements present that prevent the four-run benchmark from copying PII-bearing PDFs into a scratch location with weaker permissions than the committed corpus? [Coverage, Gap]
- [X] CHK015 Is the cleanup discipline explicit — does the spec or runbook say `rm -rf /tmp/021-bench/` after the demo/benchmark, or is post-run scratch retention indefinite? [Coverage, Gap]
- [X] CHK016 Are requirements present for shared-workstation scenarios — i.e., is the scratch directory permission-restricted to the running operator? [Gap, Coverage]
- [X] CHK017 Is the labeling-guide PII screening (feature 006 lineage) preserved — does the spec implicitly trust that committed corpus already passed PII screening, and that the scratch copy doesn't reintroduce unscreened content? [Traceability, Gap]

## Committed-Corpus Protection

- [X] CHK018 Is FR-033's prohibition on regenerating committed corpus baselines from GPU output stated as MUST NOT, with no allowance for "small" baseline updates? [Clarity, Spec §FR-033]
- [X] CHK019 Is the Edge Case "benchmark run accidentally targets committed corpus folders" mapped to a procedural finding that invalidates the appendix entry? [Consistency, Spec §Edge Cases]
- [X] CHK020 Is the runbook required to direct scratch use (FR-025(f)) AND include a self-check (e.g., `git status tests/stage1_vendor_identity/` after the demo)? [Coverage, contracts/runbook.md]
- [X] CHK021 Are requirements present that prevent the pipeline `--output-dir` flag from accidentally defaulting to a path under `tests/stage1_vendor_identity/`? [Coverage, Gap]

## Inherited PII Discipline (from feature 020)

- [X] CHK022 Is the PII discipline established by feature 020 (no PII content in `evidence_gate_documents` records, redacted vendor strings where required) preserved without modification by this feature? [Consistency, Spec §FR-032]
- [X] CHK023 Are the converted GPU tests required to use only the existing labeled corpus (which already passed PII screening per feature 006), with no new test fixtures introducing un-screened content? [Coverage, contracts/gpu-test-marker.md]
- [X] CHK024 Are Appendix A / B documents required to NOT contain raw vendor-identity values from any document — only document IDs, scores, and observability fields? [Coverage, contracts/appendix-recording.md, Gap]
- [X] CHK025 Is the runbook required to NOT include sample output containing real vendor names, addresses, or other PII — only synthetic examples or document-ID references? [Coverage, Gap]

## Logging & Forensics Discipline

- [X] CHK026 Are the readiness `*.log` capture files (`readiness-paddle.log`, `readiness-ollama.log`) required to NOT contain credential or PII content (only blocker descriptions)? [Coverage, contracts/runbook.md]
- [X] CHK027 Is the helper's stderr template free of PII (the model name in templates is a public Ollama model identifier, not customer data)? [Clarity, contracts/ollama-readiness-helper.md]
- [X] CHK028 Is the `run_summary` line free of PII (feature 020 already enforces this — verify the spec inherits the rule without weakening)? [Consistency, Spec §FR-032]

## Threat-Model Coverage

- [X] CHK029 Is the threat model for this feature implicit-but-explicit (workstation-local; no adversarial network reach; trust model = "operator who can read `/tmp` is trusted")? [Coverage, Gap]
- [X] CHK030 Are requirements present for the case "another user on the same workstation reads `/tmp/021-bench/` mid-run" — does the threat model permit this, or require restricted permissions? [Gap, Coverage]
- [X] CHK031 Are requirements present for the case "host Ollama is compromised / sends crafted `/api/ps` responses" — does the helper's input parsing reject malformed JSON deterministically (per R-021.9 exit code 3)? [Coverage, Spec §R-021.9]
- [X] CHK032 Are requirements present for the case "voter-config YAML is mutated by another process between read and demo" — does the helper read the YAML once and pin the model name for that invocation? [Coverage, contracts/ollama-readiness-helper.md]

## Audit & Review

- [X] CHK033 Is the FR-026 promotion-decision record's `decided_by` field present, so an auditor can identify the recording team? [Traceability, data-model.md §5]
- [X] CHK034 Is the FR-026 promotion-decision record's `decided_at` field required, so an auditor can correlate decisions to workstation snapshots? [Traceability, data-model.md §5]
- [X] CHK035 Is the gating-verdict reference (FR-026) required to point at a specific dated Appendix B subsection, so audit trails are reconstructable? [Traceability, contracts/appendix-recording.md]
- [X] CHK036 Are the four converted GPU tests required to NOT log credential-bearing content even on failure? [Coverage, Gap]

## CI / CD Security

- [X] CHK037 Is CPU CI's separation from GPU validation explicit (CPU CI = `pytest -m 'not gpu'`), so the workstation GPU lane's credential surface (if any) never reaches the CI environment? [Consistency, Spec §FR-005, contracts/gpu-test-marker.md]
- [X] CHK038 Are requirements present that prevent the readiness helper from being invoked by CI (CI lacks ROCm; the helper would exit 3, which is acceptable, but CI should not run the GPU-marker tests)? [Coverage, contracts/gpu-test-marker.md]
- [X] CHK039 Are the changes to `pyproject.toml` (gpu marker registration) free of security implications (no new dependency, no permission grant)? [Coverage, contracts/gpu-test-marker.md]

## Gaps to Flag

- [X] CHK040 Are PII-handling guarantees during a partial-progress benchmark run (R-021.12) explicit — does Appendix A's "Partial Benchmark Run" subsection redact PII as carefully as a full run? [Gap]
- [X] CHK041 Is the demo audience's permission to see `run_summary` output addressed — are there cases where the audience should not see per-document fallback counts (e.g., external stakeholders)? [Gap]
- [X] CHK042 Are requirements present for cryptographic verification of the recorded Appendix A/B (e.g., signed commit, hash chain)? Almost certainly out of scope, but worth flagging. [Gap]
- [X] CHK043 Is the readiness helper's response to a man-in-the-middle attack on localhost Ollama addressed — typically out of threat model, but worth confirming explicitly. [Gap, Coverage]

## Notes

- This checklist tests the *security and PII-discipline writing quality*. It is NOT a penetration test or threat-modeling exercise; those are separate concerns.
- The principal security failure modes for this feature are: (a) accidental introduction of a remote-cloud or credential surface (FR-032 is the defense); (b) PII leakage into the scratch tree or appendices (CHK013–CHK017, CHK024–CHK025 are the defenses); (c) credentialed helper output (CHK008, CHK026–CHK028 are the defenses).
- Items CHK040–CHK043 flag genuine gaps that may benefit from a future spec amendment, but most are out-of-scope for this validation/promotion slice.
