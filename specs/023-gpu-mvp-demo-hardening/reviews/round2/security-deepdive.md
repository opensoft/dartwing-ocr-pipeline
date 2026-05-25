# Security deep-dive review — round 2

**Date:** 2026-05-25
**Reviewer:** security-deepdive-r2 (general-purpose, swarm round 2)
**Branch:** 023-gpu-mvp-demo-hardening @ 7f4aa00
**Threat model:** workstation + colleague-shared fixtures (expanded from round 1)

## Summary
12 findings: 0 CRITICAL, 0 HIGH, 1 MEDIUM, 11 LOW.

Status: **NEEDS-ATTENTION** (does NOT block PR for the workstation MVP slice).
One MEDIUM (D1 — credential-leak path via `OLLAMA_BASE_URL` userinfo) is worth
closing before the demo JSON is pasted in any external channel. The remaining
findings are sharp-edge cleanups disclosed by round 2's expanded threat model
(colleague-shared fixtures, JSON line copy-paste, terminals that interpret C1
control sequences) and one regression introduced by the round-1 fixes
(`_sanitize` is incomplete relative to the threats it claims to mitigate).

## New attack surface assessment

| Surface | Hardened? | Residual risk |
|---|---|---|
| `_sanitize` (Unicode lookalikes / zero-width / C1 controls / U+2028) | **Partial** | C1 controls 0x80-0x9F (incl. CSI 0x9B), U+2028/U+2029 line/paragraph separators, U+200B zero-width, U+202E RLO override are NOT stripped. xterm/VTE/iTerm2 honor C1 CSI; U+2028/U+2029 split lines in some JSON consumers. See D2. |
| `safe_eager_delete` (hard links) | **Partial** | Hard links at canonical basenames are NOT detected by `is_symlink()`. `resolve()` returns the path itself (it's not a symlink), the escape check passes, then `unlink()` removes the link entry — leaving the inode intact at any other hard-link location. Workstation impact: zero (no data loss; inode survives). Information-leak impact: an attacker who pre-positioned a hard link learns the file existed (via the post-delete `artifact_paths` list). See D3. |
| `_extract_pre_run_snapshot` (deep dict) | **Yes** | Iterative two-key probe (`body["models"]` → linear scan). No recursion. Verified safe against 10k-entry payloads. |
| `_format_document_folder_for_report` (ANSI in paths) | **Yes for JSON line; partial for stderr** | `json.dumps` escapes ASCII control bytes, so the JSON line cannot carry a raw `\x1b` to a downstream consumer's terminal. **However** the same path also feeds the stderr `INFO/ERROR` line via `log.error(run_id, f"...{canonical_folder}")`; `_sanitize` strips C0 but not C1 / Unicode bidi (see D2 chain). |
| `_validate_ollama_base_url` (malformed userinfo / fragment) | **Mostly yes** | `urllib.parse.urlparse` correctly resolves `http://localhost@attacker.com/` to `hostname='attacker.com'` (good — the localhost check is not fooled). Fragment `#localhost` is correctly ignored (good). **Gap**: `http://user:pass@localhost:11434` parses with `hostname='localhost'`, the validator accepts it, and `httpx.get(url)` will send the credentials to Ollama in the `Authorization` header *and* the credentials become part of every diagnostic that interpolates `ollama_base_url` (e.g. `f"Ollama {url}"` in `ollama_reach.py:35,44,60`). See D1 — this is the new MEDIUM. |

## Findings

| ID | Severity | Category | Location | Threat | Recommendation |
|----|----------|----------|----------|--------|----------------|
| D1 | **MEDIUM** | credential-leak / info-disclosure | `orchestrator.py:242-273` (`_validate_ollama_base_url`) + `readiness/ollama_reach.py:35,44,60,76` + every diagnostic that interpolates `ollama_base_url` | `OLLAMA_BASE_URL=http://user:pass@host:11434` is accepted by the validator; the credentials are then sent in HTTP requests AND echoed verbatim into the diagnostic `checked` field, the INFO stderr line `using non-localhost Ollama base URL: <url>` (orchestrator.py:478-480), and the failure-path JSON report. Operator pastes the demo report into a PR → credentials leak. | Strip userinfo before storing / using. In `_validate_ollama_base_url`, reject any URL where `parsed.username` or `parsed.password` is non-empty (or rewrite via `urlunparse` with cleared userinfo). Document the redaction in the runbook. |
| D2 | LOW | log-injection (round-1 fix incomplete) | `log.py:25` (`_CONTROL_CHAR_PATTERN`) | `_sanitize` strips C0 + DEL but NOT: (a) C1 controls 0x80-0x9F including CSI 0x9B that xterm/VTE/iTerm2 honor; (b) U+2028 LINE SEPARATOR / U+2029 PARAGRAPH SEPARATOR which split lines in some JS-flavored JSON readers; (c) U+202E RIGHT-TO-LEFT OVERRIDE used for text-spoofing; (d) U+200B ZERO-WIDTH SPACE for grep evasion. A colleague-shared fixture that embeds these in a PDF filename, a malicious local Ollama proxy that returns a model name containing CSI 0x9B, or a YAML error string fed by `yaml.safe_load` quoting source-line content can still spoof terminal output post-fix. | Extend regex to `[\x00-\x08\x0a-\x1f\x7f-\x9f  ​-‏‪-‮]` (covers C0/C1, separators, bidi controls, zero-width). One-line change; no test churn. |
| D3 | LOW | hard-link bypass / information-disclosure | `folder_canonicalize.py:57-83` | `is_symlink()` returns False for a hard link. A colleague-shared fixture with a pre-positioned hard link at e.g. `<folder>/preprocess_output.json` pointing to `~/.bashrc` passes the escape check, then `unlink()` removes that link (the inode at `~/.bashrc` survives, but the canonical-basename slot is now empty). Subsequent run reveals via `artifact_paths` that the basename existed. No data loss; no escape; but the FR-017 contract "only sanctioned plain files at canonical basenames" is silently violated. | Add `if target.stat().st_nlink > 1: raise EagerDeleteError(...)` alongside the `is_symlink` check (or `os.lstat` to avoid double-resolution). Workstation impact is theoretical; the round-2 colleague-shared-fixture model makes it worth a one-liner. |
| D4 | LOW | snapshot-cap regression (round-1 `_cap_snapshot_dicts`) | `serialization.py:122-139` | `_cap_snapshot_dicts` projects `pre_run_ollama_snapshot` / `post_run_ollama_snapshot` to 4 retained keys and then applies the 2 KiB cap. The projection ALSO drops any field the demo doesn't recognize — including a future Ollama field that a downstream consumer might want. Round-1 traded interop for bound. The truncation pass then JSON-renders the dict and replaces it with a STRING `"… [truncated]"`, breaking the data-model invariant that the field is a dict-or-null. | Either keep the snapshot dict-typed and only cap individual string values, OR document that overflow degrades to a string sentinel (and ensure downstream readers accept both shapes). |
| D5 | LOW | uncapped fields beyond `CheckDiagnostic.observed` | `serialization.py:67-111`, `evaluator_subprocess.py:73`, `voter_config_loader.py:113`, `readiness/ollama_reach.py:46` | Round-1 S5 still open. The 2 KiB cap fires only inside `_diagnostic_to_dict` for `observed`. `CheckDiagnostic.checked / .expected / .remediation`, `DemoRunReport.diagnostic`, and `subprocess_stderr_tail` (already 256-byte capped — good) are otherwise uncapped. A 10 MB HTML response from a misconfigured Ollama proxy → `f"non-JSON body: {exc}"` → `diagnostic` field is multi-MB; runbook line 227 promises operators they can `\| jq` the stdout, but jq has a 10 MB single-token default that this breaks. | Apply a `_cap_str` helper in `_report_to_dict` to `checked`, `expected`, `remediation`, and top-level `diagnostic`. ~10 LOC. |
| D6 | LOW | voter-config FIFO / `/dev/zero` hazard (S6 carry-forward) | `voter_config_loader.py:88-104` | The post-`resolve()` `is_file()` check was NOT added in 7f4aa00. `--voter-config /tmp/link-to-fifo` still hangs `read_text()`. Round-2 colleague-shared-fixture model: a malicious `voter_config.yaml` symlinked into `$PWD` from a shared `/tmp` would still trigger auto-discovery via `_auto_discover()` (line 62) and hang. | Add `if not resolved.is_file(): raise VoterConfigUnreadable(...)` AFTER `resolved = override.resolve()` AND AFTER the auto-discover branch's `.resolve()` (line 77). |
| D7 | LOW | broad `httpx.HTTPError` catch (S8c carry-forward) | `readiness/ollama_reach.py:38`, `cpu_fallback.py:53` | Both sites catch the entire `httpx.HTTPError` hierarchy. Round-2 colleague-shared fixture: a malicious local Ollama proxy returning a malformed redirect can raise `httpx.TooManyRedirects` or `httpx.RemoteProtocolError`, both masked as opaque `"unreachable"`. The exception class is captured into the `observed` field as `{type(exc).__name__}: {exc}` (good for `ollama_reach.py` — preserves type), but `cpu_fallback.py` drops the type entirely (line 54 returns `"unreachable", None`). | In `cpu_fallback._probe_ollama_post_run` capture the exception type into a (currently absent) diagnostic channel, or accept the diagnostic-loss as documented. The tighter taxonomy `(httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)` is not worth churn; just preserve the type name. |
| D8 | LOW | sensitive-data: `subprocess_stderr_tail` may leak transient state | `evaluator_subprocess.py:73, 84-94` | The 256-byte stderr tail from the evaluator subprocess is surfaced in the JSON report. If the evaluator ever logs transient file paths, API tokens (none today, but future feature 022 + GPU bring-up could add `OLLAMA_HOST` debug logs), or the user's `$HOME`, it lands in the demo report. The tail is bounded but not scrubbed. | Document the tail's leakage surface in the runbook "sanitize before sharing" checklist (see D11 below). No code change required today. |
| D9 | LOW | full env inheritance into evaluator (S7 carry-forward, expanded) | `evaluator_subprocess.py:57` | `os.environ.copy()` inherits everything. Round-2 extension: if the operator's shell exports `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` for unrelated reasons, those leak into the evaluator subprocess. Feature 022's evaluator doesn't use them today, but a future evaluator phase that errors during HTTP retry could echo them in stack traces — and that stack trace lands in the 256-byte `subprocess_stderr_tail` field (D8). | Sanitize the inherited env to an allowlist: `OLLAMA_BASE_URL`, `OLLAMA_CONTEXT_LENGTH`, `HOME`, `PATH`, `LANG`, `LC_*`, `PYTHONPATH` if set. Reject `*_API_KEY` / `*_TOKEN` / `*_SECRET` patterns. |
| D10 | LOW | runbook says "Pipe through jq" but no warning re: ANSI/control chars | `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md:227` | The runbook tells operators to inspect stdout via `\| jq`. `jq` is robust against ANSI in payloads (it escapes them on render), but operators who instead `cat /tmp/run.json` or `tail run.log` will paste through their terminal — and the un-sanitized stderr stream (D2 chain) can carry CSI sequences that mutate the terminal. Round-1 fixed the JSON side; stderr side is the round-2 gap. | Add a note in the runbook stderr-discipline section: "If pasting a captured stderr line into chat/PR, scrub for non-ASCII / control characters first; the demo emits sanitized C0 controls but not C1 / Unicode bidi controls." |
| D11 | LOW | no `--scrub` flag for shared JSON | `cli.py` + `serialization.py` | Round-1 noted the username-leak surface (S3/S4 → documented, no code change). Round-2 expanded threat model: the JSON line will be pasted in PRs/issues/Slack often enough that a built-in scrub option pays off. Fields to redact: `interpreter_path` (→ `<redacted>`), `voter_config_path` (→ basename only), `document_folder` (→ basename only), `pre/post_run_ollama_snapshot.name` (→ hash prefix), `subprocess_stderr_tail` (→ `<redacted N bytes>`). | Add a `--scrub` flag that runs a post-serialization redaction pass over the listed fields. Alternatively: ship a `dartwing-gpu-demo-scrub` helper script that filters a stored JSON line. Defer if the team prefers documentation-only mitigation. |
| D12 | LOW | snapshot truncation degrades dict → str silently | `serialization.py:138` | When the projected `pre/post_run_ollama_snapshot` dict exceeds 2 KiB after the 4-key projection (extremely unlikely in practice — would require absurdly long model name OR `context_length` value), the truncation pass returns a STRING. `data-model.md §3` says the field is `Optional[dict[str, Any]]`. Downstream consumers (the spec example, future feature 024 promotion) typing the field will not expect a string fallback. | After projection, the 4 retained keys cannot meaningfully overflow 2 KiB unless `name` is itself > 2 KiB. Drop the post-projection truncation entirely (the projection is the real bound), OR validate that each retained value passes `len(json.dumps(v)) < 512` and replace the offender with `None`. |

## Sensitive-data leak audit

The DemoRunReport JSON is intended for local consumption but is regularly pasted into PRs, issues, and runbook examples. Audit:

| Field | Leakage class | Recommendation for runbook |
|---|---|---|
| `interpreter_path` | username (`/home/<user>/...`) | Scrub before sharing; document as round-1 S3. |
| `document_folder` | username + project layout | Scrub to basename or `<doc-folder>` placeholder. |
| `voter_config_path` | username + model name (proprietary?) | Scrub to basename; consider model name a separate disclosure (next row). |
| `expected_extraction_model` | model name (may be a vendor-specific custom-tag) | Acknowledge as intentional disclosure for reproducibility; redact if the model name encodes IP. |
| `pre_run_ollama_snapshot.name`, `post_run_ollama_snapshot.name` | model name | Same as above. |
| `subprocess_stderr_tail` | 256 bytes of evaluator subprocess stderr | High-variance leakage surface (D8). Recommend scrubbing in any external paste. |
| `failing_check_name` + `diagnostic.observed` | may include the operator-supplied URL with credentials (`OLLAMA_BASE_URL=http://user:pass@host`) | **D1 fix closes this**. After D1, no credentials should ever land here. |
| `diagnostic` (top-level) | free-form exception strings, includes file paths, model names, possibly env-var values | Cap via D5; review for known leak vectors after large-error events. |
| `total_runtime_seconds`, `phase_timings.*` | timing signal (benign for workstation; classify side-channel as out-of-scope) | None. |
| `run_id` | random 16-hex (no leakage) | None. |

**Recommendation (runbook)**: add a *"Before sharing the report JSON externally"*
checklist subsection to `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`:

```markdown
### Before sharing the report JSON externally

- [ ] `interpreter_path` redacted (encodes username)
- [ ] `document_folder` redacted (encodes username + project layout)
- [ ] `voter_config_path` reduced to basename
- [ ] `expected_extraction_model` reviewed for IP-sensitive model names
- [ ] `pre/post_run_ollama_snapshot.name` reviewed for IP-sensitive model names
- [ ] `subprocess_stderr_tail` reviewed for transient state / file paths
- [ ] `diagnostic` reviewed for embedded URLs with credentials
- [ ] `OLLAMA_BASE_URL` does not contain `user:pass@` userinfo
       (D1 fix should reject this at validate-time; this is the belt-and-braces)
```

Or implement a `--scrub` flag (D11) that performs the above automatically.

## File-handle + resource exhaustion audit

- `quality_derivation._read_final_payload_manual_review` — `Path.read_text()` is
  context-manager-wrapped internally. Exception path returns `True` without
  leaking. ✓
- `evaluator_subprocess.invoke_evaluator` — `Path.read_text()` on
  `evaluation_document.json`; same. `subprocess.run(..., capture_output=True)`
  closes pipes on return. Timeout path raises `subprocess.TimeoutExpired`
  before pipes are read; CPython 3.12 closes them in the except path. ✓
- `voter_config_loader.load_voter_config` — `Path.read_text()`; same. ✓
- No raw `open()` calls in the gpu_demo tree. ✓

**No file-handle leaks identified.**

## Subprocess + env

Per D9 above: the evaluator subprocess inherits the full parent environment.
For the workstation MVP this is correct; for the round-2 expanded model
(operator's shell carries unrelated API keys for unrelated work), tighten to an
allowlist before promotion to a CI-driven path.

## Sign-off

**NEEDS-ATTENTION.** D1 (credential-leak via `OLLAMA_BASE_URL` userinfo) is the
single MEDIUM that's worth closing before the demo JSON is pasted externally.
D2 (incomplete `_sanitize`) is a one-line regex extension that closes the
round-2 chain (colleague-shared fixtures + terminal-spoof via C1/Unicode). The
remaining 10 LOWs are sharp-edge cleanups; D3 + D6 are one-liners each, D5 is
~10 LOC, and D11 (`--scrub` flag) is the largest piece of work but is
optional — a runbook "sanitize before sharing" checklist absorbs the disclosure
risk without any code change.

**Does NOT block PR** for the workstation MVP slice. Recommend addressing D1
and D2 in a follow-up commit before the demo is promoted past the workstation
boundary (CI, shared dashboards, or any path that pipes the report JSON to a
non-trusted consumer).
