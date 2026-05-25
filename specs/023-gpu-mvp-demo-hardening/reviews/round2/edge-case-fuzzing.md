# Edge-case fuzzing deep review — round 2

**Date:** 2026-05-25
**Reviewer:** edge-case-fuzzer-r2 (general-purpose, swarm round 2)
**Branch:** 023-gpu-mvp-demo-hardening @ 7f4aa00
**Scope:** unusual but reachable input/state combinations across
`src/dartwing_ocr/gpu_demo/` (orchestrator.py, cpu_fallback.py, serialization.py,
voter_config_loader.py, folder_canonicalize.py, readiness/runner.py, log.py)

## Summary
9 findings: 0 CRITICAL, 2 HIGH, 5 MEDIUM, 2 LOW.

## Findings

| ID  | Severity | Scenario                                                                            | Location                                                                                      | Behavior                                                                                                                  | Recommendation                                                                  |
|-----|----------|-------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| E1  | HIGH     | Broken `source.pdf` symlink (target gone)                                           | `orchestrator.py:513`                                                                         | `Path.exists()` returns `False` for a broken symlink → treated as "missing" with no diagnostic that hints "broken link"   | Distinguish `is_symlink() and not exists()` to surface a clearer diagnostic     |
| E2  | HIGH     | Circular reference in a `CheckDiagnostic.observed` dict                             | `serialization.py:44`                                                                         | `json.dumps` raises `ValueError("Circular reference detected")` from inside `_emit_report` → no JSON line emitted, FR-019 violation | Wrap `_truncate_observed_value` in try/except → fall back to `repr()` truncation |
| E3  | MEDIUM   | Multi-voter config with malformed extra voters (non-dict entries)                   | `voter_config_loader.py:153–156`                                                              | A bare scalar (e.g. `- "qwen2.5"`) at `voters[1:]` is silently skipped: `extra_voters_ignored` under-counts, no WARN line | Iterate every `voters[1:]` regardless of type; record `"<malformed>"` for non-dict |
| E4  | MEDIUM   | `OLLAMA_BASE_URL` env var with trailing whitespace                                  | `orchestrator.py:223` + `_validate_ollama_base_url`                                           | Validation strips; the **untrimmed** value is stored on `options` and threaded into every readiness HTTP call. httpx tolerates it on URL splice but the value is also echoed into stderr/JSON | Persist the trimmed value: `ollama_base_url=_validate_…(raw_value)` (assign return) |
| E5  | MEDIUM   | `OLLAMA_CONTEXT_LENGTH` env var is non-numeric                                      | `orchestrator.py:224–226`                                                                     | `int(os.environ.get(...))` raises `ValueError` BEFORE any JSON line is emitted → orchestrator crashes with stack trace, violates FR-019 always-emit | Wrap parse in try/except; map to `failure_kind="invalid-input"` + emitted report |
| E6  | MEDIUM   | Voter-config first voter is a dict with `model_name: ""` (empty string)             | `voter_config_loader.py:147`                                                                  | `not model_name` is True → `VoterConfigMissingModel` raised. Handled correctly. But if `model: 0` (int → truthy fallback via `or`) the check on `isinstance(str)` catches it. Net: OK — but `extra_voters` deduction loses fidelity when first voter's `name` key duplicates `model` | None — confirmed safe; document positive finding                                |
| E7  | MEDIUM   | Module-global `_BUFFERING_CONFIGURED` (log.py:17) and `_LAST_READOUT` (preflight.py:552) leak across in-process tests | `log.py:17`, `preflight.py:552` | Two consecutive `gpu_demo.run()` calls in the same Python process share both. `_LAST_READOUT` is the more harmful: the paddle post-run probe (`cpu_fallback.py:102`) calls `classify(attempt_ppstructurev3_init=True)` which mutates the global, so any harness that runs multiple back-to-back demos sees cross-run state | Add explicit `reset_cache()` call in orchestrator entry (or expose a session-id keyed cache) |
| E8  | LOW      | `quality_status_source` Literal closure violated when only evaluator runs           | `quality_status.py:67`                                                                        | The bi-conditional comment in orchestrator says quality non-null iff success, but `quality_status_source` returns `"evaluator"` even when evaluator agreed with gate — the `Literal["gate","evaluator"]` is preserved, but semantically the source is now ambiguous (evaluator confirmed but didn't change anything) | Cosmetic — document or split into a third source `"gate+evaluator-confirmed"` if a downstream consumer needs disambiguation |
| E9  | LOW      | Diagnostic with 4-byte UTF-8 emoji at the 2 KiB cap boundary                        | `serialization.py:48–53`                                                                      | The cut-back loop only retreats off **continuation** bytes (`0xC0 == 0x80`). For a 4-byte emoji whose **leading** byte sits at `encoded[2047]`, the loop doesn't move (no continuation bytes precede it), so the leading byte is kept and `decode(errors="ignore")` drops it — leaving the codepoint silently truncated mid-character (correct) but losing one full emoji at the boundary without indication | Acceptable per Q5; cosmetic note only — consider also retreating off a lead byte that would start a multi-byte sequence past the cap to make boundaries reproducible |

## Detailed findings

### E1 — Broken symlink at `source.pdf` produces "not found" instead of "broken symlink"
**Severity:** HIGH (operator triage / diagnostic clarity)
**Scenario:** Operator has `tests/stage1_vendor_identity/inv_001_easy/source.pdf` as a symlink to a sibling file that has since been deleted or renamed.
**Reachability:** Common after rebasing/cherry-picking corpus PDFs across branches or after a `git checkout` that drops the target.
**Behavior:** `orchestrator.py:513` does `if not source_pdf.exists():` — `Path.exists()` follows symlinks and returns `False` for broken links. The emitted diagnostic is `source.pdf not found in <folder>`. The operator wastes time looking for the file when it's right there as a dangling link.
**Spec impact:** FR-027 says "source.pdf missing → invalid-input". Letter of the requirement is met but spirit (actionable diagnostic) is degraded.
**Reproducer:**
```bash
cd /tmp && mkdir -p doc && ln -s /tmp/does-not-exist /tmp/doc/source.pdf
python -m dartwing_ocr.gpu_demo --document-folder /tmp/doc
# diagnostic: "source.pdf not found in /tmp/doc"  ← misleading
```
**Suggested fix:**
```python
if not source_pdf.exists():
    if source_pdf.is_symlink():
        diag_msg = f"source.pdf is a broken symlink in {canonical_folder} (target: {os.readlink(source_pdf)})"
    else:
        diag_msg = f"source.pdf not found in {canonical_folder}"
```

### E2 — Circular reference in `CheckDiagnostic.observed` crashes serialization
**Severity:** HIGH (FR-019 violation)
**Scenario:** A future readiness check that captures a Python object graph as `observed` (e.g. dataclass with backref) produces a circular dict. Or a test-side stub composer puts a self-referential structure into a phase result that ends up in `diagnostic.observed`.
**Reachability:** Low at HEAD (no current producer emits circular structures), but the `observed: Any` type signature is permissive — a contributor adding a new check could trip it.
**Behavior:** `serialization.py:44` calls `json.dumps(value, ...)` inside `_truncate_observed_value`. Python's `json` raises `ValueError("Circular reference detected")`. The exception escapes `_emit_report` → `run()` → the CLI returns the Python default `1` with NO JSON line emitted. FR-019 ("always emit a stable-shape JSON line on every path") is violated.
**Spec impact:** FR-019 + the "always-emit" guarantee enforced by triage B4 for SIGALRM but not enforced for arbitrary serialization errors.
**Reproducer:** Build a unit test that constructs a `DemoRunReport` with `readiness.checks[0].diagnostic.observed = {"self": <self-ref>}` and call `to_json_line` — observe `ValueError`.
**Suggested fix:** Wrap `json.dumps` in `_truncate_observed_value`:
```python
try:
    rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
except (TypeError, ValueError):
    rendered = repr(value)  # falls back; will still be truncated below
```

### E3 — Malformed extra voters silently dropped from `extra_voters_ignored`
**Severity:** MEDIUM
**Scenario:** A voter config with `voters: ["model-a", {model: "model-b"}]` (first entry is a scalar) — or `voters[1:]` containing a non-dict.
**Reachability:** Operator copy/paste error or auto-generated config from a sibling tool.
**Behavior:** `voter_config_loader.py:153–156` iterates `voters[1:]` and only records dict entries. A non-dict entry silently drops out, so the WARN line "voter config has multiple voters; demo uses the first" undercounts and the JSON report's eventual paper trail is incomplete.
**Spec impact:** Soft — no FR mandates exhaustive enumeration, but data-model.md §6 implies completeness.
**Reproducer:**
```yaml
voters:
  - {model: "ok-first"}
  - "stray-string"
  - {model: "ok-third"}
```
The "stray-string" is dropped from `extra_voters_ignored`.
**Suggested fix:** Record `"<malformed: type=str>"` for non-dict entries instead of skipping them.

### E4 — `OLLAMA_BASE_URL` whitespace stripped only inside the validator
**Severity:** MEDIUM
**Scenario:** `export OLLAMA_BASE_URL="http://localhost:11434 "` (trailing space — common when env vars are sourced from CSV/copy-paste).
**Reachability:** Real — happens when operators paste from a Slack message or a wiki cell with a trailing space.
**Behavior:** `_validate_ollama_base_url` returns the trimmed value but the caller (`orchestrator.py:451`) discards the return: `_validate_ollama_base_url(options.ollama_base_url)`. `options.ollama_base_url` keeps the trailing space. Then `ollama_reach.py:35` does `context.ollama_base_url.rstrip('/')` which strips slashes but NOT whitespace → final URL is `http://localhost:11434 /api/ps` → httpx URL parse splits incorrectly or 404s.
**Spec impact:** R-023.14 (`OLLAMA_BASE_URL` invalid-input handling). The validator should be the single source of truth for the cleaned value.
**Reproducer:**
```bash
OLLAMA_BASE_URL="http://localhost:11434 " python -m dartwing_ocr.gpu_demo --check-only
```
Observe the readiness check failure diagnostic embeds the trailing space.
**Suggested fix:** `options = dataclasses.replace(options, ollama_base_url=_validate_ollama_base_url(options.ollama_base_url))` — or assign at construction time in `_build_options_from_args`.

### E5 — `OLLAMA_CONTEXT_LENGTH` non-numeric env var crashes pre-validation
**Severity:** MEDIUM (FR-019 violation)
**Scenario:** `OLLAMA_CONTEXT_LENGTH="2k"` (operator types a unit suffix).
**Reachability:** Real — common error pattern in dotfiles/shell aliases.
**Behavior:** `orchestrator.py:225` calls `int(os.environ.get("OLLAMA_CONTEXT_LENGTH", str(DEFAULT_OLLAMA_CONTEXT_LENGTH)))`. `int("2k")` raises `ValueError` BEFORE `_build_options_from_args` returns — so no `_emit_report` runs and no JSON line is produced. The OS exit is whatever Python's traceback handler chooses (1).
**Spec impact:** FR-019 always-emit invariant. Also FR-021 closed exit-code table is bypassed.
**Reproducer:**
```bash
OLLAMA_CONTEXT_LENGTH=2k python -m dartwing_ocr.gpu_demo --check-only
# Python crashes; no JSON on stdout
```
**Suggested fix:** Wrap the `int(...)` in try/except, emit the `invalid-input` report with diagnostic `"OLLAMA_CONTEXT_LENGTH is not an integer: '2k'"`.

### E6 — Voter config `model: 0` / `model_name: 0` — positive finding (handled)
**Severity:** MEDIUM (positive)
**Scenario:** YAML `voters: [{model: 0}]` — bare integer 0 is yaml-truthy as a key value.
**Behavior:** `voter_config_loader.py:146` does `first.get("model") or first.get("model_name")` — `0` is falsy so the `or` falls through. Then `not model_name` and `not isinstance(model_name, str)` both fire. Net: handled correctly via `VoterConfigMissingModel`. **No fix needed.**
**Note:** `False` and `None` are also caught by the same chain. Confirmed safe.

### E7 — Module-global state leaks across in-process runs
**Severity:** MEDIUM
**Scenario:** A test harness or future "batch demo" CLI that invokes `gpu_demo.run()` twice within a single Python interpreter.
**Reachability:**
- Today: test-only (`tests/integration/gpu_demo/`). The suite passes because tests use stub composers that don't touch `preflight._LAST_READOUT`.
- Tomorrow: any operator who imports `gpu_demo.run` from a notebook (a plausible workstation flow given the demo's audience) will hit a stale `_LAST_READOUT` between calls.
**Behavior:**
- `log.py:17` `_BUFFERING_CONFIGURED` — only sets `sys.stderr.reconfigure(line_buffering=True)` once; harmless if tests replace `sys.stderr` because the second test's stream stays buffered (not line-buffered) but tests run sequentially so this rarely surfaces.
- `preflight.py:552` `_LAST_READOUT` — the paddle post-run probe (`cpu_fallback.py:102`) calls `classify(attempt_ppstructurev3_init=True)` which mutates the global. A second back-to-back demo will see `_LAST_READOUT` populated from the first run's post-run interrogation, and the SECOND run's `paddle-rocm-preflight` readiness check (which also calls `classify(...)`) could now return a stale-cached state.
**Spec impact:** Soft — no FR forbids in-process reuse, but R-023.15 ("post-run interrogation runs on every pipeline path") implicitly assumes a clean slate.
**Reproducer:** Run `gpu_demo.run(...)` twice in a single Python session against a real Paddle install; observe that the second run's `paddle-rocm-preflight` reflects state from the first run's post-run probe (which races with engine init).
**Suggested fix:** Either (a) call `preflight.reset_cache()` at the top of `orchestrator.run()`, or (b) document that `gpu_demo.run` is one-shot per process and add a guard.

### E8 — `quality_status_source = "evaluator"` even when evaluator only confirms
**Severity:** LOW (semantics)
**Scenario:** `--with-evaluator` runs; gate says "pass"; evaluator says "passed".
**Behavior:** `quality_status.py:67` returns `(base, "evaluator")` even though the evaluator didn't change the value. Downstream consumers might interpret `quality_status_source = "evaluator"` as "the evaluator was load-bearing in this outcome", which isn't true.
**Spec impact:** Minor — R-023.20 doesn't forbid this, and it's deterministic.
**Suggested fix:** Cosmetic; no action recommended unless a downstream consumer surfaces.

### E9 — UTF-8 truncation at exact 2 KiB boundary on lead byte
**Severity:** LOW (cosmetic)
**Scenario:** `observed` contains a string ending in a 4-byte emoji whose leading byte happens to fall at offset 2047 (after JSON encoding).
**Behavior:** `serialization.py:48–53` retreats `cut` by stripping CONTINUATION bytes (`(b & 0xC0) == 0x80`). If `encoded[2047]` is a LEAD byte (e.g., 0xF0 for a 4-byte sequence), no continuation bytes precede it — the loop doesn't trigger, the lead byte is retained, and `decode(errors="ignore")` drops it. Net result: one emoji is silently lost at the boundary, no marker. **Q5 spec accepts this** ("retreat to the last complete UTF-8 character boundary") but the implementation could be tightened to also retreat off a dangling lead byte for byte-exact reproducibility.
**Suggested fix:** After the continuation-byte retreat, additionally check if `cut[-1] & 0xC0 == 0xC0` (lead byte) and retreat one more position. Tighten the test in `test_serialization.py` to cover this case.

## Edge cases probed and confirmed correctly handled (positive findings)

| Prompt # | Scenario                                                                                  | Status                                                                                                                                                        |
|----------|-------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1        | Voter config has zero voters                                                              | Handled — `voters[]` triggers `VoterConfigMissingModel` ("`voters` is not a non-empty list") → exit 2. (`voter_config_loader.py:136–139`)                     |
| 2        | First voter `model_name: ""` (empty)                                                      | Handled — `not model_name` catches it → `VoterConfigMissingModel`. (Same path as #1.)                                                                         |
| 3        | First voter missing `model_name` key                                                      | Handled — `first.get("model") or first.get("model_name")` returns `None` → `isinstance(str)` rejects → `VoterConfigMissingModel`.                             |
| 4        | Document folder is a symlink to a real directory                                          | Handled — `canonicalize_document_folder` resolves it; subsequent operations consistently use the resolved path. (`folder_canonicalize.py:31`)                  |
| 5        | source.pdf is a broken symlink                                                            | **E1 — partial; diagnostic is misleading**.                                                                                                                   |
| 6        | SIGALRM fires during `_validate_ollama_base_url`                                          | Cannot happen — the alarm is installed AFTER readiness completes (`orchestrator.py:751`), validator runs at line 451. Order is correct.                       |
| 7        | SIGALRM fires inside `_extract_run_summary`                                               | The function is pure-Python dict/attr access — no system calls — and runs synchronously after the phase function returns. The alarm fires inside `_run_phase`'s phase function call (between `try:` and `except`), and the orchestrator's `except TimeoutError` correctly cancels the alarm at the top of the `except` block. Safe. |
| 8        | Composer phase returns in <1ms; `time.monotonic()` resolution                             | `time.monotonic()` on Linux has ~ns resolution; `timings[phase]` will be a positive float ≥0. Downstream code (`PhaseTimings`, serialization) treats `0.0` as a valid value (not "not run") — the "not run" sentinel is `None`. Safe.            |
| 9        | `/api/ps` returns 200 with `models: []`                                                   | Handled — `_find_model_entry` returns `None` → check 5 fails with `"entry with name '<model>' present"` expected line. Clear diagnostic.                       |
| 10       | `/api/ps` model entry missing `size_vram`                                                 | Handled — `not isinstance(size_vram, int)` returns False → check 5 fails with `"size_vram (int) > 0 AND size_vram == size (int)"`. Clear.                      |
| 11       | `/api/ps` entry name is substring of expected (`qwen2.5-vl` vs `qwen2.5-vl:7b`)            | Handled — `entry.get("name") == model_name` is **exact equality**, not substring. Substring entries are rejected → check 5 fails. Safe.                       |
| 12       | Slow-arrival HTTP body (chunked encoding)                                                 | `httpx.get(url, timeout=2.0)` applies the timeout to the overall request including body read. Slow trickle → `httpx.ReadTimeout` → caught as `HTTPError` → fail with diagnostic. Safe. |
| 13       | Per-document folder is read-only filesystem                                               | Eager-delete (`safe_eager_delete`) tries `target.unlink()` → `PermissionError` → `EagerDeleteError` → exit 2 with diagnostic. Correct order: delete fires first. |
| 14       | Eager-delete interrupted halfway (first unlink succeeds, second fails)                    | Partial state remains on disk. Next run's eager-delete is idempotent on missing files AND deletes the remaining one. **Contract-compliant.**                  |
| 15       | NFS/eventually-consistent FS, `target.exists()` after recent write                        | Out of scope per spec (local-disk operator workflow). No code path depends on read-after-write here.                                                          |
| 16       | Operator path contains 4-byte UTF-8 emoji                                                 | `log._sanitize` strips C0 controls only — emoji pass through unchanged. JSON serialization uses `ensure_ascii=False` (UTF-8 throughout). Safe.                |
| 17       | YAML key with embedded `\x00`                                                             | PyYAML accepts it; `_sanitize` in log.py strips it from stderr. On the JSON side, `json.dumps` with default settings emits `" "` — which is valid JSON. Some consumers reject NULLs in strings, but the demo doesn't. Soft issue — borderline finding. |
| 18       | Circular reference in `observed`                                                          | **E2 — crashes.**                                                                                                                                             |
| 19       | `_BUFFERING_CONFIGURED` module-global                                                     | **E7 — partial; mostly harmless but worth documenting.**                                                                                                      |
| 20       | `_LAST_READOUT` module-global                                                             | **E7 — same issue, more impactful for Paddle probe path.**                                                                                                    |
| 21       | Closed-enum closure for `f"failed_at_{phase}"`                                            | The `phase` value passed to `_run_phase` is always one of the four hardcoded literals ("preprocess", "extraction", "routing", "final_payload") at orchestrator.py:755–758. Thus `f"failed_at_{phase}"` always lands in the closed `RuntimeOutcome` set. Safe. |

## Sign-off
**NEEDS-ATTENTION.** The two HIGH findings (E1 broken symlink diagnostic; E2 circular-reference JSON crash) are real correctness/safety issues against FR-019's always-emit guarantee and operator-triage clarity. They are not release-blockers given the narrow workstation-demo audience, but they SHOULD be filed as follow-up issues before the next round of demo audiences. The MEDIUM findings (E3–E5, E7) are quality-of-life improvements; E5 also touches FR-019. E8/E9 are LOW/cosmetic.

Recommended pre-PR-merge actions:
1. Fix E2 (circular-ref serialization crash) — small, contained, prevents an FR-019 regression.
2. Fix E5 (`OLLAMA_CONTEXT_LENGTH` parse) — small, prevents the same FR-019 regression.
3. File E1 + E4 + E7 as follow-up issues for the next stacked PR.
