# Contract-realignment deep review — round 2

**Date:** 2026-05-25
**Reviewer:** contract-realignment-r2 (general-purpose, swarm round 2)
**Branch:** 023-gpu-mvp-demo-hardening @ 7f4aa00
**Scope:** re-verify K1-K7 fixes against contracts + look for new drift introduced by the fixes

---

## Summary

All seven round-1 K-findings (K1-K7) are correctly addressed in commit `7f4aa00`. The fixes also resolved an implicit sub-finding of K1 (the CPU-fallback rewrite no longer leaves `quality_status` populated when `runtime_outcome` is rewritten from `success` to `failed_at_extraction`, because quality derivation now runs AFTER the rewrite at orchestrator.py:909 — the bi-conditional invariant 5 now holds across all 7 outcome classes).

Two new findings (N1, N2) arise from the M-bundle/security tightening:

- **N1 (LOW):** `document_folder` outcome-matrix cell `str-or-null` for invalid-input is now imprecise — the code always emits a string under K5, matching the field-reference text but not the looser matrix.
- **N2 (LOW):** `_cap_snapshot_dicts` runs the projected dict through `_truncate_observed_value`. In the (extreme) case where the 4-key projection still exceeds 2 KiB, the result is a string sentinel — violating the `dict | None` type contract for `pre_run_ollama_snapshot` / `post_run_ollama_snapshot`.

Two new behaviors (S1 symlink rejection at canonical basenames, S2 stderr control-char sanitization) tighten beyond the documented contract and should be added as named FRs.

**Sign-off: PASS** — the K-bundle and M-bundle fixes are contract-aligned. The two new low-severity findings + two new-FR candidates do not block PR; they should be addressed by a small spec follow-up.

---

## K1-K7 verification

| ID  | Fix landed | Contract-matched? | Notes |
|---|---|---|---|
| K1  | orchestrator.py:817 `if runtime_outcome is None:` guards the post-pipeline schema-validation rewrite. | YES | Walked outcome matrix: `success+schema-fail` → exit 5 (rewrite runs because `runtime_outcome is None`, then becomes `failed_at_final_payload` + `artifact-schema-validation-failed`); `failed_at_extraction+missing-artifacts` → exit 4 preserved (rewrite skipped, schema check still appears as `fail` in `readiness.checks[]` for triage but does not corrupt the outcome); `failed_at_routing+schema-fail` → exit 4 preserved; `timeout+schema-fail` → exit 3 preserved (runtime_outcome already `"timeout"`). Implicit sub-finding (CPU-fallback rewrite + quality_status drift) is also closed because lines 871-877 run BEFORE lines 909-945 — invariant 5 holds. |
| K2  | `_validate_ollama_base_url` at orchestrator.py:242-273; invoked at line 451 before readiness; non-localhost INFO at line 477-480. | YES | `_InvalidOllamaBaseURL` → `failure_kind="invalid-input"` + `ExitCode.INVALID_INPUT` per R-023.14. URL trimmed before parse; scheme check requires `http`/`https`; host non-empty via `parsed.hostname`. Ordering: voter-config load (line 415) → URL validation (line 451) → canonicalize → readiness. cli-contract.md doesn't pin URL-vs-voter-config order, so either-first is acceptable. INFO text: `"using non-localhost Ollama base URL: <url>"` — R-023.14 leaves the exact text unspecified; current wording is operator-clear. |
| K3  | cpu_fallback.py:139-153 forces BOTH probes to `"unreachable"` + sets `budget_exceeded=True`; orchestrator.py:864-869 emits the prescribed WARN line. | YES | Exact WARN string match: `"post-run interrogation exceeded 5s budget; CPU-fallback detection inconclusive"` matches R-023.15 byte-for-byte. Both probes forced (Paddle is no longer probed at all when budget is blown after Ollama — the early return at line 145 short-circuits before `_probe_paddle_post_run`). `paddle_post_run="unreachable"` is correct since the probe didn't run. |
| K4  | `_extract_pre_run_snapshot` at orchestrator.py:169-192 reads `base_context.cached_api_ps_body`; passed to `interrogate(pre_run_snapshot=...)` at line 852-855; echoed back to `CPUFallbackDetection.pre_run_ollama_snapshot` at line 860. | YES | Field name `cached_api_ps_body` matches what `OllamaReachabilityCheck` publishes via `side_channel` and what `runner.py:90` writes via `dataclasses.replace(ctx, cached_api_ps_body=...)`. Helper handles three defensive cases (non-dict body, non-list `models`, no matching entry) — returns None. Snapshot is non-null in success report (subject to the schema-projection step in serialization.py). |
| K5  | `_format_document_folder_for_report(options)` at orchestrator.py:319-340; used in `_build_report` at line 386. | YES | `--check-only` → None (line 332-333). Folder exists → resolved absolute path (line 335-336). Folder missing or OSError → raw operator-supplied string (line 340). Matches data-model.md §1 (`document_folder: str \| None`) field-reference at demo-report-schema.md:71 ("captures the path that was *attempted*"). See **N1** for the matrix imprecision. |
| K6  | `diagnostic_msg` assigned at orchestrator.py:885-888 in the `outcome.unreachable` branch. | YES | Cross-field invariant 1 (`failure_kind != null → diagnostic != null`) now holds on the post-run-interrogation-unreachable branch. Message format: `"post-run interrogation could not confirm GPU placement (ollama=<probe>, paddle=<probe>)"`. |
| K7  | `log.info(run_id, "post-run: ollama still GPU-placed; paddle still rocm_gpu")` at orchestrator.py:898-901 in the consistent/consistent branch. | YES | Exact byte-for-byte match with cli-contract.md:209 worked example. |

---

## New findings (round 2)

| ID  | Severity | Contract source | Code location | Drift | Recommendation |
|---|---|---|---|---|---|
| N1  | LOW | demo-report-schema.md:230 outcome matrix (says `document_folder: str-or-null` for invalid-input) vs demo-report-schema.md:71 field reference (says "not null"). | orchestrator.py:319-340 always returns a string when `check_only=False`. | The matrix is now looser than the field reference + code. After K5, `document_folder` is **never null** on any invalid-input outcome (voter-config failure, OLLAMA_BASE_URL failure, canonicalize failure, source.pdf missing, eager-delete failure). | Tighten the matrix cell at demo-report-schema.md:230 from `str-or-null` to `str` for the invalid-input column. (Alternative: leave matrix lax for forward-compat; but the field-reference and code are stricter.) |
| N2  | LOW | data-model.md:168 `pre_run_ollama_snapshot: dict \| None`; demo-report-schema.md:213 "small dict with name, size, size_vram, context_length". | serialization.py:122-139 `_cap_snapshot_dicts` runs the 4-key-projected dict through `_truncate_observed_value`. | If a projected snapshot dict's JSON form exceeds 2048 bytes (e.g., a pathological `name` string), `_truncate_observed_value` returns a **string** (the sentinel-suffixed form). The field type contract is `dict \| None`, never `str`. This is an edge case but a type-shape violation. | Either (a) remove the secondary `_truncate_observed_value` call in `_cap_snapshot_dicts` (the 4-key projection already bounds the size); or (b) document this as a known-shape exception in the schema with a `dict \| str \| None` widening; option (a) is cleaner. |
| N3  | LOW | FR-017 text: "never following symlinks out of that folder" — implicitly allows non-escaping symlinks. | folder_canonicalize.py:57-60 rejects ALL symlinks at canonical basenames, even non-escaping ones. | The S1 fix tightens FR-017 — a symlink whose target sits inside the folder is now rejected with `EagerDeleteError`. Operators with legitimate symlink-based fixture setups (e.g., `tests/integration/gpu_demo/fixtures/ok/source.pdf` which IS a symlink per R-023.18) would be blocked **if** that pattern were used at one of the four canonical basenames. Source.pdf is not one of the four canonical basenames, so the existing fixture is safe — but a future fixture symlinking, say, `preprocess_output.json` would break. | Add a new FR or amend FR-017 to read: "The four canonical basenames MUST NOT be symlinks at run start; the eager-delete pre-flight rejects any symlink at those exact paths regardless of target. Symlinks at other basenames (e.g., source.pdf) are unaffected." Closes the TOCTOU gap explicitly. |
| N4  | LOW | cli-contract.md:109-121 stderr discipline — doesn't speak to embedded control characters. | log.py:25-36 `_sanitize` strips C0 controls (except `\t`) + DEL. | New defensive behavior. cli-contract.md doesn't permit OR forbid control chars; the S2 fix tightens beyond the documented contract. Operator-supplied paths or model names containing `\n` / `\x1b` are silently replaced with the Unicode replacement marker `�`. | Add to cli-contract.md "stderr discipline" section: "Control characters (C0 0x00-0x1F except tab, and 0x7F DEL) in interpolated values are replaced with the Unicode replacement marker `U+FFFD`. This prevents stderr-line forgery via embedded newlines or ANSI escape sequences in operator-supplied paths or model names." |
| N5  | LOW | data-model.md §5 (CPUFallbackDetection invariants) + R-023.15. | cpu_fallback.py:85-88 returns `"fell_back"` when `pre_size_vram > size_vram`. | M3 change: the pre→post `size_vram` diff returns `"fell_back"` on **any drop**, even if the current `size_vram == size > 0` (post-run is fully GPU but lower than pre-run). R-023.15 says "any deviation flips the run" — a drop is a deviation, so this is contract-compliant. The decision is a real tightening but documented; the contract text supports it. Marking as a finding only because it changes the semantic from "current state is GPU" to "current state is GPU AND no pre-vs-post regression". | None required — the behavior matches R-023.15 spirit. Optionally pin in data-model.md §5 "Invariants": "Either probe returns `fell_back` if (a) current `size_vram` < current `size`, OR (b) current `size_vram` < pre-run `size_vram` (when pre-run snapshot is available)." |
| N6  | LOW | data-model.md §5 line 168 "full /api/ps entry"; demo-report-schema.md:213 "small dict with name, size, size_vram, context_length". | serialization.py:114-118 + 122-139 projects to 4 keys at serialization time. | Internal contract inconsistency: data-model.md says "full /api/ps entry"; demo-report-schema.md says "small dict with [4 keys]". The code follows demo-report-schema.md (the more specific, narrower contract). Either contract document is "right" but they disagree. | Update data-model.md:168 to read: "`pre_run_ollama_snapshot: dict \| None — projected /api/ps entry (4 keys: name, size, size_vram, context_length) captured at readiness (when known)`". Aligns the two contract docs to what the code does. |

---

## R-023.* decision walk

| Decision | Status | Notes |
|---|---|---|
| R-023.1  | PASS | Default composer remains stubbed; tests substitute. M2 fix added canonical StalledPhase literals to the stub exceptions. |
| R-023.2  | PASS | `version.py:8-13` unchanged from round 1. |
| R-023.3  | PARTIAL PASS (unchanged from round 1) | Generic `except Exception` catch-all at orchestrator.py:715. Explicit exception classes deferred to follow-on workstation session. |
| R-023.4  | PASS | Test infrastructure unchanged. |
| R-023.5  | PASS | `gpu` pytest marker still declared in `pyproject.toml`. |
| R-023.6  | PASS | UUID4 run_id + 8-char prefix unchanged. |
| R-023.7  | PASS | INFO/WARN/ERROR severity prefix; line-buffering. Tightened with control-char sanitization (see N4). |
| R-023.8  | PASS | Single 600 s SIGALRM remains the only timeout. |
| R-023.9  | PASS | Runbook-only; no code obligation. |
| R-023.10 | PASS | `MIN_OLLAMA_VERSION = "0.4.0"` unchanged. |
| R-023.11 | PASS | CheckDiagnostic key set + stderr mirror via `diagnostics.format_diagnostic_line` unchanged. |
| R-023.12 | PASS | `sort_keys=False, ensure_ascii=False, compact separators` in `to_json_line`. Stable order preserved across all 17 keys. |
| R-023.13 | PASS | Evaluator subprocess argv unchanged. |
| R-023.14 | **DRIFT-CLOSED** | K2 fix landed `_validate_ollama_base_url` + INFO line on non-localhost. |
| R-023.15 | **DRIFT-CLOSED** | K3 + K4 + K6 + K7 fixes all close R-023.15 sub-requirements. The pre→post `size_vram` diff (M3) is a tightening within R-023.15's "any deviation" envelope (see N5). |
| R-023.16 | N/A | Test infrastructure. |
| R-023.17 | N/A | Runbook. |
| R-023.18 | N/A | Test infrastructure. R-023.18's fixture-symlink pattern remains safe because `source.pdf` is NOT a canonical basename — N3 would only matter if a future fixture symlinked one of the four canonical artifact basenames. |
| R-023.19 | PASS | No feature-011 imports. |
| R-023.20 | PASS | Truth-table unchanged. Now runs AFTER the CPU-fallback rewrite, which keeps invariant 5 clean. |
| R-023.21 | PASS | 3-dp rounding unchanged. |

---

## Specs that should be updated

- **spec.md**: Add to FR-017: "Symlinks at any of the four canonical basenames (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`) MUST be rejected outright by the eager-delete pre-flight with exit 2, regardless of where the symlink target resolves. This eliminates the TOCTOU window between symlink-resolution and unlink. Symlinks at other basenames (e.g., `source.pdf`) are unaffected by this rule." (Closes **N3** — incorporates S1.)
- **contracts/cli-contract.md**: Append a paragraph to "stderr / stdout discipline (FR-019)" stating that control characters in interpolated stderr text are replaced with `U+FFFD` to prevent line-forgery. (Closes **N4** — incorporates S2.)
- **contracts/demo-report-schema.md**: (a) Tighten the outcome-matrix cell at line 230: change `str-or-null` → `str` in the invalid-input column for `document_folder` (closes **N1**). (b) Optional: document N2's edge case or remove the secondary truncation call in `_cap_snapshot_dicts`.
- **data-model.md**: Update line 168 (and the matching post_run_ollama_snapshot line) to read "projected /api/ps entry (4 keys: name, size, size_vram, context_length)" instead of "full /api/ps entry" — aligns with demo-report-schema.md:213 and what the code emits. (Closes **N6**.)
- **research.md**: Optional — add a sentence to R-023.15 noting "`fell_back` is also returned when current `size_vram` is less than pre-run `size_vram` (a mid-run reload that lowered VRAM placement)." Pins what the code does. (Closes **N5**.)

---

## Sign-off

**PASS** — all seven K-findings from round 1 are correctly fixed; the M-bundle changes are contract-aligned; the new findings (N1-N6) are LOW-severity follow-ups (matrix tightening, type-edge-case, three new-FR candidates documenting the S1/S2/N5 tightening) that do NOT block the PR. Recommend a small doc-only follow-up PR to close N1-N6 in the spec.
