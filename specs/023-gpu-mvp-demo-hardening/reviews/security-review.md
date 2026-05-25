# Security review — feature 023

**Date:** 2026-05-25
**Reviewer:** security-reviewer-023 agent (general-purpose, swarm review)
**Branch:** 023-gpu-mvp-demo-hardening @ 1d56554
**Threat model:** Single-user workstation; no network-facing surface; multi-tenancy out of scope.

## Summary
8 findings: 0 CRITICAL, 0 HIGH, 2 MEDIUM, 6 LOW.

Status: **PASS** (with minor hardening recommendations). No issues block PR. The eager-delete safety guard, YAML loading, and subprocess invocation all use the correct defensive primitives. The remaining items are sharp-edge cleanups that the operator-only threat model already absorbs.

## Findings

| ID | Severity | Category | Location | Summary | Recommendation |
|----|----------|----------|----------|---------|----------------|
| S1 | MEDIUM | TOCTOU / symlink-escape | folder_canonicalize.py:55–70 | Two-phase resolve-then-delete leaves a small TOCTOU window between the escape check and `target.unlink()`. The check resolves symlinks, but `target.unlink()` operates on the path-with-symlink, not the resolved target — so an attacker who can race the directory between the two loops can still escape. | Either re-resolve and re-check inside the delete loop, or `os.unlink` the basename via a folder file-descriptor with `dir_fd=` (POSIX `openat`-style). For the workstation threat model, the simpler fix is to also reject the case where `target.is_symlink()` is true after the escape check passes — i.e. forbid symlinks at the canonical basenames outright (FR-017 only sanctions plain files). |
| S2 | MEDIUM | log-injection / control-char | log.py:34–37 + diagnostics.py:18–22 + orchestrator.py (many sites) | All stderr emission is `f"{severity}:[{prefix}] {msg}\n"` with no sanitization. Operator-supplied paths, model names from `/api/ps`, voter-config error messages, and subprocess stderr tails (last 256 bytes) flow into `msg` unescaped. A model name containing `\n` or `\r` could forge stderr lines (terminal log spoof) or inject ANSI escapes. The `subprocess_stderr_tail` is only surfaced in the JSON report (good — `json.dumps` escapes), but model names and YAML error strings reach stderr directly. | Add a `_sanitize(msg)` helper in `log.py` that strips control chars (codepoints < 0x20 except a single trailing `\n`, plus 0x7F, plus the ANSI CSI introducer `\x1b`). The helper is one regex; apply it inside `_emit` so every INFO/WARN/ERROR line is sanitized uniformly. Workstation impact is low (operator reads their own terminal), but the diagnostic-fidelity story benefits — a real failure with embedded newlines currently shows up split across "lines" and breaks log-grep tooling. |
| S3 | LOW | info-disclosure | orchestrator.py:247 + report.py:94 | `DemoRunReport.interpreter_path` is `os.path.realpath(sys.executable)`, which on a workstation typically encodes `/home/<username>/...`. The JSON line is intended for local consumption, but spec/quickstart docs sometimes paste sample reports — usernames could leak via copy-paste. | Acceptable as-is for the workstation threat model. If the report is ever pasted in PRs/issues, document the username-leak surface in the runbook so the operator scrubs before sharing. No code change required. |
| S4 | LOW | info-disclosure | orchestrator.py:250 | `document_folder` in the report is `options.document_folder.resolve()` — absolute path. Same copy-paste concern as S3 (encodes `/home/<username>/projects/...`). | Same as S3 — document in runbook; no code change. |
| S5 | LOW | DoS / resource-exhaustion | serialization.py:36–53 (`_truncate_observed_value`) | The 2 KiB cap applies only to `CheckDiagnostic.observed`. Other free-form fields — `CheckDiagnostic.checked`, `CheckDiagnostic.expected`, `CheckDiagnostic.remediation`, `DemoRunReport.diagnostic`, `subprocess_stderr_tail` — are uncapped. If an Ollama error surfaces an unusually large message (e.g. an HTML response from a misconfigured reverse proxy that fails JSON parsing), `f"non-JSON body: {exc}"` could be megabytes. Not a security boundary, but unbounded JSON on stdout breaks downstream parsers. | Either apply the 2 KiB cap to all string fields in `_report_to_dict`, or document the cap as observed-only. The `subprocess_stderr_tail` is already bounded to 256 bytes in `evaluator_subprocess.py:73` — good — but the YAML error path (voter_config_loader.py:113) and httpx exception path (ollama_reach.py:46) have no equivalent. |
| S6 | LOW | symlink behavior | voter_config_loader.py:94 (`override.resolve()`) | `--voter-config /etc/passwd` is harmless because `yaml.safe_load` will reject it (it's not a YAML mapping) — verified. But `override.resolve()` follows symlinks; an operator passing a symlink that points at `/dev/zero` or a FIFO would hang `read_text()` indefinitely (no timeout on the read). | Acceptable as-is — operator can ^C. If hardening, add `if not resolved.is_file(): raise VoterConfigUnreadable(...)` after `resolve()` (currently only the pre-resolve `override.is_file()` check fires, before symlinks are followed). |
| S7 | LOW | env-inheritance | evaluator_subprocess.py:57 (`env=os.environ.copy()`) | The subprocess inherits the full parent environment, including `OLLAMA_BASE_URL`, `HOME`, `PATH`, etc. For the workstation threat model this is correct (the evaluator needs the same env). But there's no allowlist — anything the operator's shell exports flows in. | Acceptable. `os.environ.copy()` is the textbook safe call when full inheritance is intentional (vs `env=None`, which can cause CPython to inherit only a subset on some platforms). Document the intent inline. |
| S8 | LOW | misc nits | various | Aggregated minor items: (a) `_BUFFERING_CONFIGURED` is module-global and never reset — fine because the demo is one-shot, but defensive code should not assume that. (b) `ollama_reach.py` uses `httpx.get(url, timeout=2.0)` with no `verify=` — defaults to True (good); `OLLAMA_BASE_URL` is hardcoded to `http://localhost:11434` so TLS is moot, but if someone sets `OLLAMA_BASE_URL=https://...` they get default cert validation, which is correct. (c) `cpu_fallback.py:39` swallows all `httpx.HTTPError` into `"unreachable"` — fine, but loses the diagnostic. (d) `paddle_preflight.py:53` uses bare `except Exception` — justified by comment, but suppresses programming errors silently. | No action required individually. Track as documentation/style cleanup. |

## Detailed findings

### S1 — TOCTOU window between escape check and unlink in `safe_eager_delete`

**Severity:** MEDIUM (downgrade to LOW under the workstation threat model)
**Category:** TOCTOU / symlink-escape
**Location:** `src/dartwing_ocr/gpu_demo/folder_canonicalize.py:55–70`

**Threat:** An adversary with write access to the per-document folder (or any directory between the operator-supplied folder and `/`) can race the two loops in `safe_eager_delete`:

```python
for basename in basenames:
    target = folder / basename
    if target.exists() or target.is_symlink():
        resolved = target.resolve()
        try:
            resolved.relative_to(folder_str)  # passes — symlink points inside
        except ValueError:
            raise EagerDeleteError(...)
    targets.append(target)

# attacker swap window here

for target in targets:
    try:
        if target.is_symlink() or target.exists():
            target.unlink()       # follows the new symlink
```

Between the two loops, an attacker who can swap `<folder>/preprocess_output.json` from a benign symlink to one pointing at `/etc/important_file` would cause `target.unlink()` to delete the *outside-folder* target. `Path.unlink()` on a symlink unlinks the symlink itself (not the target), but the timing window also covers swapping a regular file in for a symlink and vice versa.

**Why it matters (or doesn't, given threat model):** The workstation threat model says the operator is trusted and there is no concurrent untrusted process. Under that model, this is theoretical — no attacker exists to race. The finding is documented so future evolution (e.g., moving the demo into a CI runner shared with other users) doesn't silently inherit a TOCTOU bug.

Also note that `Path.unlink()` does not follow symlinks (it removes the symlink itself), so the worst-case impact is "attacker confuses the demo about which file it just deleted" rather than "attacker deletes arbitrary file outside the folder." The escape check is doing real work — it prevents the demo from following a malicious symlink during *resolution*, which is the bigger risk if the resolved path were then used for a `write` or `read` operation.

**Suggested fix:**

Either (preferred for clarity) reject symlinks at canonical basenames entirely — FR-017 only sanctions the four canonical artifact filenames as plain files, so a symlink at `<folder>/preprocess_output.json` should already be a malformed state:

```python
if target.is_symlink():
    raise EagerDeleteError(
        f"eager-delete target is a symlink (forbidden): {target}"
    )
```

Or (more defensive) re-check inside the delete loop:

```python
for target in targets:
    if target.is_symlink():
        # symlinks at canonical basenames are forbidden post-check; abort
        raise EagerDeleteError(f"symlink reappeared at canonical basename: {target}")
    if target.exists():
        target.unlink()
```

### S2 — Log injection via unsanitized stderr content

**Severity:** MEDIUM (downgrade to LOW under the workstation threat model)
**Category:** log-injection / control-character
**Location:** `src/dartwing_ocr/gpu_demo/log.py:34–37`; injection sites throughout `orchestrator.py`, `diagnostics.py`

**Threat:** Every stderr line is formatted as `f"{severity}:[{prefix}] {msg}\n"`. The `msg` argument is f-string-interpolated content that can include:

1. **Operator paths** — `f"invalid input: source.pdf not found in {canonical_folder}"` (orchestrator.py:343–346). The folder is canonicalized but the basename can contain newlines on Linux (POSIX allows everything except `/` and NUL).
2. **Model names from Ollama `/api/ps`** — surfaced in `diagnostics.format_diagnostic_line`'s `observed` rendering and in `cpu_fallback`'s `f"(ollama={...}, paddle={...})"`. If an attacker controls the Ollama response (they don't, under the threat model), `name` could include `\n` or ANSI codes.
3. **YAML error strings** — `f"voter-config is not parseable YAML: {resolved} ({exc})"` — the `exc.__str__()` of a `yaml.YAMLError` includes the line content that failed parsing, which is operator-controlled.
4. **Subprocess error tails** — only via the JSON report (`json.dumps` escapes), not via stderr. Good.

The risk is two-fold: (a) terminal-spoof (ANSI codes that overwrite earlier lines), (b) log-grep breakage (split lines confuse `grep INFO:` / `grep ERROR:`).

**Why it matters (or doesn't, given threat model):** Under the single-user workstation model, the operator types their own input — they would have to social-engineer themselves to inject control characters. The relevant scenario is: the operator runs the demo against a real-invoice fixture where the *PDF filename* (not even our domain — file's resident in `tests/`) contains an exotic character; or the host Ollama is misconfigured and emits an HTML error page. Neither is an attack.

But: this CLI is intended to produce a clean operator report. Garbage on stderr undermines that. Sanitization is cheap.

**Suggested fix:** Add a `_sanitize` helper in `log.py`:

```python
import re
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

def _sanitize(s: str) -> str:
    return _CONTROL_RE.sub("?", s)

def _emit(severity, run_id, msg, *, stream=None):
    target = stream if stream is not None else sys.stderr
    target.write(f"{severity}:[{prefix_for(run_id)}] {_sanitize(msg)}\n")
```

This preserves `\t` (0x09), `\n` only at end-of-message (handled by the format string), and strips the rest. ANSI CSI is `\x1b` (in 0x00–0x1f) so it gets caught too.

### S3 / S4 — Username leakage via interpreter_path and document_folder

**Severity:** LOW
**Category:** info-disclosure
**Location:** `src/dartwing_ocr/gpu_demo/orchestrator.py:247, 250`

**Threat:** `interpreter_path = os.path.realpath(sys.executable)` and `document_folder = str(options.document_folder.resolve())` both encode the operator's home directory path. The report JSON line is intended for stdout consumption but ends up pasted into specs, runbooks, and PR descriptions during the feature's lifecycle. Username encoded.

**Why it matters (or doesn't):** Workstation-only, single operator, no public surface. The username is presumably the operator's known identity. No code change recommended.

**Suggested fix:** Add a one-line note to `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` mentioning that report JSON pastes may include the operator's home path and to scrub `interpreter_path` / `document_folder` before sharing externally.

### S5 — Unbounded string fields in DemoRunReport beyond `CheckDiagnostic.observed`

**Severity:** LOW
**Category:** DoS / resource-exhaustion
**Location:** `src/dartwing_ocr/gpu_demo/serialization.py:36–53`

**Threat:** The Q5 truncation only fires inside `_diagnostic_to_dict` for the `observed` field. Other fields that flow operator-or-network content into the JSON line are uncapped:

- `CheckDiagnostic.checked`, `.expected`, `.remediation` — all f-strings that interpolate URLs and model names.
- `DemoRunReport.diagnostic` — orchestrator builds this from `str(exc)` and similar, with no cap.
- Voter-config error messages, YAML exception strings — same.

If an Ollama deployment returns an unusually large error body (an HTML stack trace from a misconfigured proxy), the resulting `f"non-JSON body: {exc}"` could be megabytes.

**Why it matters:** The single-line JSON on stdout is intended to be machine-consumable. A multi-megabyte line breaks `jq -c` consumers and confuses anyone reading the stdout. Not a security boundary in the traditional sense, but it's a robustness gap that the 2 KiB cap was meant to close.

**Suggested fix:** Apply a per-field cap in `_diagnostic_to_dict`:

```python
def _cap_str(s, cap=_OBSERVED_BYTE_CAP):
    if not isinstance(s, str):
        return s
    encoded = s.encode("utf-8")
    if len(encoded) <= cap:
        return s
    cut = encoded[:cap]
    while cut and (cut[-1] & 0xC0) == 0x80:
        cut = cut[:-1]
    return cut.decode("utf-8", errors="ignore") + _TRUNCATION_SENTINEL
```

Apply to `checked`, `expected`, `remediation`, and `DemoRunReport.diagnostic`.

### S6 — Voter-config symlink to FIFO / `/dev/zero`

**Severity:** LOW
**Category:** denial-of-service via path
**Location:** `src/dartwing_ocr/gpu_demo/voter_config_loader.py:88–104`

**Threat:** `override.is_file()` is checked at line 90, but `override.resolve()` (line 94) then follows symlinks. If the operator types `--voter-config /tmp/link` where `/tmp/link` is a symlink to a FIFO (or `/dev/zero` — Linux exposes character devices that masquerade as files), `read_text()` at line 104 hangs (FIFO) or returns gigabytes (`/dev/zero`).

**Why it matters:** Operator misuse / typo. Operator ^C recovers. No security boundary crossed.

**Suggested fix:** After `resolved = override.resolve()`, re-check `if not resolved.is_file()`:

```python
resolved = override.resolve()
if not resolved.is_file():
    raise VoterConfigUnreadable(
        f"voter-config resolves to non-file: {override} -> {resolved}"
    )
```

### S7 — Full env inheritance into evaluator subprocess

**Severity:** LOW (acceptable design)
**Category:** subprocess
**Location:** `src/dartwing_ocr/gpu_demo/evaluator_subprocess.py:57`

**Threat:** `env=os.environ.copy()` passes the full parent environment to the evaluator subprocess. If the evaluator is ever extended to read env vars the demo doesn't expect, the operator's shell exports flow in.

**Why it matters (or doesn't):** Single-user workstation. The evaluator is from feature 022 (same project, same trust boundary). `PATH`, `HOME`, `OLLAMA_BASE_URL`, `OLLAMA_CONTEXT_LENGTH` are all expected. Full inheritance is the right default.

**Suggested fix:** None. Add an inline comment confirming the intent:

```python
# Full env inheritance is intentional — evaluator (feature 022) reads OLLAMA_BASE_URL
# and OLLAMA_CONTEXT_LENGTH from env when not overridden. Workstation threat model
# treats parent env as trusted.
env=os.environ.copy(),
```

### S8 — Aggregated minor items

**Severity:** LOW
**Category:** misc

(a) `log._BUFFERING_CONFIGURED` is a module-global side-effect flag. Fine for one-shot CLI; documented as such.

(b) `ollama_reach.py` and friends rely on `httpx` defaults for cert verification (`verify=True`). Since `OLLAMA_BASE_URL` defaults to `http://localhost:11434` (no TLS), this is moot. If an operator sets `OLLAMA_BASE_URL=https://corporate-ollama.example.com`, they get default cert validation — correct.

(c) `cpu_fallback._probe_ollama_post_run` swallows all `httpx.HTTPError` into `"unreachable"` without surfacing the cause. The orchestrator then emits `WARN: post-run interrogation could not confirm GPU placement` — the operator has to re-run with `OLLAMA_DEBUG=...` or check Ollama logs separately. Acceptable for the demo; track as a diagnostic-fidelity nit.

(d) `paddle_preflight.py:53` uses `except Exception` justified by the comment "preflight may raise its own taxonomy". This is fine but silently suppresses programmer errors in the preflight layer. If `preflight.classify()` ever raises `AttributeError`, the operator sees "Paddle ROCm preflight failed" instead of the real bug. Acceptable for the demo's resilience profile.

## What was reviewed

- `src/dartwing_ocr/gpu_demo/folder_canonicalize.py` (full)
- `src/dartwing_ocr/gpu_demo/voter_config_loader.py` (full)
- `src/dartwing_ocr/gpu_demo/evaluator_subprocess.py` (full)
- `src/dartwing_ocr/gpu_demo/log.py` (full)
- `src/dartwing_ocr/gpu_demo/diagnostics.py` (full)
- `src/dartwing_ocr/gpu_demo/serialization.py` (full)
- `src/dartwing_ocr/gpu_demo/cli.py` (full)
- `src/dartwing_ocr/gpu_demo/orchestrator.py` (full)
- `src/dartwing_ocr/gpu_demo/cpu_fallback.py` (full)
- `src/dartwing_ocr/gpu_demo/report.py` (full)
- `src/dartwing_ocr/gpu_demo/enums.py` (full)
- `src/dartwing_ocr/gpu_demo/quality_derivation.py` + `quality_status.py` (full)
- `src/dartwing_ocr/gpu_demo/run_id.py`, `version.py`, `exit_codes.py`, `__main__.py` (full)
- `src/dartwing_ocr/gpu_demo/readiness/{base,runner,interpreter,paddle_preflight,ollama_reach,ollama_version,ollama_placement,ollama_ctx_len,runtime_timeout,schema_validation}.py` (full)
- Full-tree grep for `os.system`, `shell=True`, `pickle.loads`, `eval(`, `exec(`, `yaml.load` (non-safe variant): **none found** in the gpu_demo tree.

## What was NOT reviewed (out of scope per threat model)

- Authentication / authorization (single-user workstation; no auth surface)
- Network attacks against `/api/ps` (host-local Ollama; not exposed)
- Multi-tenancy / cross-user attacks (single operator)
- Container escape (workstation, not container-deployed; devcontainer is dev-only)
- Supply-chain attacks against `httpx`, `pyyaml`, `paddlepaddle-dcu` (track at the project level)
- Side-channel attacks on the GPU (out of scope for any application-level review)
- Feature 022's evaluator subprocess (audited separately under that feature)
- Feature 020's evidence-gate module (CPU-only; audited under feature 020 security checklist)
- Feature 014/015/016/017/018/019 Paddle preflight internals (composed in via `preflight.classify()`; audited under those features)

## Positive findings (defensive measures correctly implemented)

- **`yaml.safe_load` used throughout.** Only one yaml call site in the gpu_demo tree (`voter_config_loader.py:111`); confirmed `safe_load`, not `load`. No alternative parse paths. ✓
- **`subprocess.run` with `shell=False`** (the default when argv is a list — explicit `shell=` not passed, so default False). Argv is constructed from a fixed list `[sys.executable, "-m", "dartwing_ocr.evaluator", "evaluate-document", "--folder", str(document_folder), "--quiet"]` — only `document_folder` is operator-influenced, and it's passed as a discrete argv element (not interpolated into a shell string), so shell injection is impossible. ✓
- **Path canonicalization before eager-delete.** `canonicalize_document_folder` calls `resolve()` and then verifies `is_dir()`; `safe_eager_delete` then verifies each of the 4 canonical basenames resolves *inside* the canonicalized folder before any unlink. The escape check is the correct shape (modulo S1's TOCTOU note). ✓
- **HTTP timeouts everywhere.** All four readiness checks (`ollama_reach`, `ollama_version`, `ollama_placement`, `ollama_ctx_len`) and the post-run probe (`cpu_fallback._probe_ollama_post_run`) pass `timeout=2.0` to `httpx.get`. No hanging-forever risk. ✓
- **Subprocess timeout.** `evaluator_subprocess.invoke_evaluator` passes `timeout=60.0` to `subprocess.run` and handles `TimeoutExpired`. ✓
- **Bounded subprocess stderr capture.** `subprocess_stderr_tail=(completed.stderr or "")[-256:]` caps captured stderr at 256 bytes — defends against multi-megabyte error outputs. ✓
- **Bounded `CheckDiagnostic.observed`.** 2 KiB cap with UTF-8 boundary-safe truncation (`serialization._truncate_observed_value`). ✓
- **Closed exit-code vocabulary.** `ExitCode` enum has exactly 6 values; the `_exit_code_for` table is total over `(runtime_outcome, failure_kind)`. No way for an operator to see an unexpected exit code. ✓
- **Closed readiness-check vocabulary.** `ReadinessCheckName` Literal type is exhaustive; the runner builds checks from a fixed list. No dynamic check loading from operator input. ✓
- **No `shell=True`, no `os.system`, no `eval`, no `exec`, no `pickle`.** Verified by repo-wide grep over the gpu_demo tree. ✓
- **argparse `choices=SUPPORTED_PRESETS` on `--preset`** — operator cannot inject an arbitrary preset name. ✓
- **CLI does NOT call `sys.exit` directly** — `main()` returns the int code, so test harnesses can assert without subprocess invocation. Reduces test-side attack surface. ✓
- **`signal.alarm`-based timeout** properly restored in `finally` block (`orchestrator.py:587–590`). No signal handler leak across runs. ✓
- **Eager-delete is idempotent on missing files** (FR-017). No "delete then re-create" race window. ✓
- **`--check-only` skips all filesystem-mutating operations** (eager-delete, pipeline phases, post-run probes). Explicit gate at `orchestrator.py:315`. ✓
- **`os.path.realpath(sys.executable)`** used for `interpreter_path` — resolves the venv interpreter through symlinks to its true path, defeating Linux mechanisms that could otherwise confuse the venv check. ✓
- **`size_vram == size` strict equality** for GPU placement (no tolerance) — prevents silent partial-CPU loading from passing the check (the very thing SC-004 is designed to detect). ✓
