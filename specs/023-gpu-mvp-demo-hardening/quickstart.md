# Quickstart: GPU MVP Demo Hardening

**Phase 1 output of [plan.md](./plan.md).** End-to-end walk-through for two audiences:
1. **Operators** running the demo on a configured workstation.
2. **Developers** working on the demo CLI itself (CPU pytest path + workstation smoke).

This file complements `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` (extended in place per Q15 round 1). The runbook is the operator-facing source of truth; this file is the spec-side companion that planning artifacts cross-reference.

---

## Path 1 — Operator: one-command demo (happy path)

**Prerequisites (verified once per workstation; documented in the runbook):**

1. WSL2 with AMD `gfx1151` ROCm exposed.
2. `.venv-paddle-rocm` provisioned with a working `paddlepaddle-dcu` install.
3. Host Ollama installed (version ≥ `0.4.0`), with the configured extraction model already pulled.
4. The canonical demo fixture present at `tests/stage1_vendor_identity/inv_001_easy/source.pdf`.

**Run:**

```sh
# Step 1 — Start host Ollama (operator step, NOT part of demo command)
scripts/start-host-ollama-rocm-wsl.sh

# Step 2 — Activate Paddle ROCm venv (operator step)
source .venv-paddle-rocm/bin/activate

# Step 3 — Run the demo against the canonical fixture
python -m dartwing_ocr.gpu_demo
```

**Expected stderr (abridged):**

```
INFO:[a1b2c3d4] readiness: interpreter/venv → pass (0.01s)
INFO:[a1b2c3d4] readiness: paddle-rocm-preflight → pass (2.34s)
INFO:[a1b2c3d4] readiness: ollama-reachability → pass (0.08s)
INFO:[a1b2c3d4] readiness: ollama-version → pass (0.04s) — Ollama 0.4.5
INFO:[a1b2c3d4] readiness: ollama-model-gpu-placement → pass (0.05s) — qwen2.5-vl:7b fully GPU-placed
INFO:[a1b2c3d4] readiness: ollama-context-length → pass (0.03s)
INFO:[a1b2c3d4] readiness passed (2.55s)
INFO:[a1b2c3d4] eager-delete: 4 artifacts removed from /workspace/tests/stage1_vendor_identity/inv_001_easy/
INFO:[a1b2c3d4] phase: preprocess (header-first-v1) → 4.21s
INFO:[a1b2c3d4] phase: extraction → 18.05s
INFO:[a1b2c3d4] phase: routing → 0.04s
INFO:[a1b2c3d4] phase: final_payload → 0.08s
INFO:[a1b2c3d4] post-run: ollama still GPU-placed; paddle still rocm_gpu
INFO:[a1b2c3d4] runtime: success / quality: pass
```

**Expected stdout (one line):**

```
{"kind":"demo_run_report","schema_version":"0.1.0",…,"runtime_outcome":"success","quality_status":"pass",…}
```

**Expected on disk (in the canonical per-doc folder):**
- `preprocess_output.json` — schema-valid v1.3.0
- `edge_extraction_output.json` — schema-valid v1.3.0
- `routing_decision.json` — schema-valid v1.3.0
- `final_structured_payload.json` — schema-valid v1.3.0
- `source.pdf` (preserved, untouched)
- any pre-existing `expected.json`, `notes.md`, `semantic_table_truth.json`, `evaluation_document.json`, debug PNGs — all preserved (SC-010)

**Exit code:** `0`.

---

## Path 2 — Operator: fast preflight (`--check-only`)

**Use case:** Operator wants to confirm the workstation is ready before kicking off a long pipeline run.

```sh
python -m dartwing_ocr.gpu_demo --check-only
```

**Behavior:**
- Runs FR-016 checks 1–6 (interpreter/venv → ollama-context-length).
- Marks checks 7–8 as `"skipped"` in the report.
- Does NOT eager-delete artifacts.
- Does NOT run any pipeline phase.
- Completes in ≤ 10 s on a warm workstation (SC-007).
- Emits the `DemoRunReport` JSON line with all pipeline / quality / timing fields `null`.

**Exit code:** `0` if all 6 infrastructure checks passed; `1` if any failed.

---

## Path 3 — Operator: alternate document folder

**Use case:** Operator wants to run the demo against a non-default fixture (e.g., a medium-difficulty invoice).

```sh
python -m dartwing_ocr.gpu_demo --document-folder tests/stage1_vendor_identity/inv_002_medium/
```

**Behavior:** identical to Path 1, but reads `source.pdf` from and writes the 4 canonical artifacts into the supplied folder. Folder is canonicalized (symlinks resolved) before any delete.

---

## Path 4 — Operator: full-OCR preset (opt-in)

**Use case:** Operator wants to bypass the `header-first-v1` reduced preset (FR-011 default) and run the slower full OCR path.

```sh
python -m dartwing_ocr.gpu_demo --preset full-ocr
```

**Behavior:** Pipeline preprocess phase runs the full OCR mode. Other phases unchanged. Bounded timeout (600 s) is identical; operators are responsible for ensuring the full path completes within that budget.

---

## Path 5 — Operator: invoke evaluator (opt-in)

**Use case:** Operator wants to invoke the feature 022 semantic-quality evaluator after the pipeline, on a fixture that has a `semantic_table_truth.json` sidecar.

```sh
python -m dartwing_ocr.gpu_demo --with-evaluator
```

**Behavior:**
- Pipeline runs normally.
- After the pipeline, the demo invokes `python -m dartwing_ocr.evaluator …` as a subprocess (R-023.13).
- If the sidecar exists: evaluator runs; `quality_status_source` becomes `"evaluator"`; evaluator's pass/fail can downgrade `quality_status` but not upgrade it (R-023.20).
- If the sidecar is missing: stderr emits `WARN:[run_id] --with-evaluator: semantic_table_truth.json not found in <folder>; skipping evaluator`; `quality_status_source` stays `"gate"`. No exit-code change.

---

## Path 6 — Operator: readiness diagnostics (every failure class)

The demo reports the failing readiness check by name. Per FR-016, the closed vocabulary is 8 names; each produces a specific diagnostic. Worked examples:

### A. Wrong venv

```sh
$ python -m dartwing_ocr.gpu_demo
ERROR:[…] readiness check 'interpreter/venv' failed — observed /usr/bin/python3.12, expected /workspace/.venv-paddle-rocm/bin/python. Remediation: activate the Paddle ROCm venv: source .venv-paddle-rocm/bin/activate.
{"kind":"demo_run_report",…,"failing_check_name":"interpreter/venv",…}
$ echo $?
1
```

### B. Ollama not reachable

```sh
$ python -m dartwing_ocr.gpu_demo
ERROR:[…] readiness check 'ollama-reachability' failed — observed httpx.ConnectError, expected HTTP 200. Remediation: start host Ollama: scripts/start-host-ollama-rocm-wsl.sh.
{…,"failing_check_name":"ollama-reachability",…}
$ echo $?
1
```

### C. Ollama too old (triage C1 resolution)

```sh
$ python -m dartwing_ocr.gpu_demo
ERROR:[…] readiness check 'ollama-version' failed — observed 0.3.12, expected >= 0.4.0. Remediation: upgrade Ollama to >= 0.4.0; see scripts/start-host-ollama-rocm-wsl.sh.
{…,"failing_check_name":"ollama-version",…}
$ echo $?
1
```

Note: this fails at check 4 (ollama-version), not check 5 (ollama-model-gpu-placement), because the fixed-order execution + skip rules pre-empt the placement check on old Ollama versions that don't expose `size_vram`.

### D. Model on CPU

```sh
$ python -m dartwing_ocr.gpu_demo
ERROR:[…] readiness check 'ollama-model-gpu-placement' failed — observed {"size":4906000000,"size_vram":0}, expected size_vram > 0 AND size_vram == size. Remediation: restart Ollama on a fresh GPU context.
{…,"failing_check_name":"ollama-model-gpu-placement",…}
$ echo $?
1
```

### E. Missing source.pdf

```sh
$ python -m dartwing_ocr.gpu_demo --document-folder /tmp/no-such-folder
ERROR:[…] invalid input: source.pdf not found in /tmp/no-such-folder
{…,"failure_kind":"invalid-input",…}
$ echo $?
2
```

### F. Malformed voter config

```sh
$ python -m dartwing_ocr.gpu_demo --voter-config /tmp/bad.yaml
ERROR:[…] invalid input: voter config /tmp/bad.yaml is not parseable YAML.
{…,"failure_kind":"invalid-input",…}
$ echo $?
2
```

### G. Pipeline timeout

```sh
$ python -m dartwing_ocr.gpu_demo
INFO:[…] readiness passed (2.55s)
INFO:[…] eager-delete: 4 artifacts removed
INFO:[…] phase: preprocess (header-first-v1) → 4.21s
INFO:[…] phase: extraction → ⏳ (running…)
# ... 600 s elapses
ERROR:[…] pipeline runtime timeout — stalled phase: extraction
{…,"runtime_outcome":"timeout","stalled_phase":"extraction",…}
$ echo $?
3
```

---

## Path 7 — Developer: CPU-isolated pytest

**Use case:** Developer is iterating on the demo CLI; runs the full test pack on CI or locally without ROCm.

```sh
# From the worktree root
pytest tests/integration/gpu_demo/ -m "not gpu"
```

**Expected:** all CPU-isolated tests pass in ≤ 60 s (R-023.16). No Paddle import. No network. Tests cover:

| Coverage area | Test file |
|---|---|
| Flag parsing, defaults, interactions | `test_cli_flags.py` |
| Fixed-order readiness execution + skip-on-upstream-fail | `test_readiness_order.py` |
| Each named readiness check fail | `test_readiness_failures.py` |
| Exit codes 0–5 for every outcome | `test_exit_codes.py` |
| Each `runtime_outcome` enum value reached | `test_runtime_outcomes.py` |
| `--check-only` stable shape, null fields | `test_check_only.py` |
| FR-019 stable top-level key set across outcomes | `test_report_shape.py` |
| FR-017 path canonicalization + symlink-escape + partial-failure abort | `test_eager_delete.py` |
| FR-022 warn-and-skip when sidecar missing | `test_with_evaluator.py` |
| FR-010 quality_status truth-table (R-023.20) | `test_quality_status.py` |

---

## Path 8 — Developer: workstation manual GPU smoke (SC-006 gate)

**Use case:** Maintainer needs to certify that the demo is the MVP integration-test checkpoint, which gates Jetson edge-fast implementation.

**Procedure (also captured in the runbook):**

```sh
# Setup
scripts/start-host-ollama-rocm-wsl.sh
source .venv-paddle-rocm/bin/activate

# Three consecutive runs — capture stdout JSON lines to a scratch file
python -m dartwing_ocr.gpu_demo > /tmp/run1.json
python -m dartwing_ocr.gpu_demo > /tmp/run2.json
python -m dartwing_ocr.gpu_demo > /tmp/run3.json

# Verification (manual operator step)
jq -r '"runtime_outcome=\(.runtime_outcome) quality_status=\(.quality_status) failing_check=\(.failing_check_name)"' /tmp/run{1,2,3}.json
```

**Pass criteria (SC-006):**
1. All three runs print `runtime_outcome=success quality_status=pass failing_check=null`.
2. `diff` on `preprocess_output.json` across the three per-doc-folder snapshots shows zero bytes of difference.
3. `diff` on `routing_decision.json` and `final_structured_payload.json` across the three snapshots shows zero bytes of difference.
4. `edge_extraction_output.json` MAY differ (model nondeterminism is acceptable per round-2 Q10).

When SC-006 passes, the operator records the result in the runbook's "Three-Run Stability Smoke Procedure" sign-off block (R-023.17). This sign-off is the formal gate for adopting the demo as the MVP integration-test checkpoint.

---

## Path 9 — Developer: hard-failure smoke tests

After installing the package, sanity-check the closed exit-code table and report shape:

```sh
# Exit 2 (invalid input) — missing source.pdf
python -m dartwing_ocr.gpu_demo --document-folder /tmp/empty && echo "BUG: should have exited 2" || echo "OK: exit $?"

# Exit 2 (malformed voter config)
echo "not: yaml: :" > /tmp/bad.yaml
python -m dartwing_ocr.gpu_demo --voter-config /tmp/bad.yaml && echo "BUG: should have exited 2" || echo "OK: exit $?"

# Help screen is exempt from the JSON-line rule
python -m dartwing_ocr.gpu_demo --help | head -3

# Version
python -m dartwing_ocr.gpu_demo --version
```

---

## Cross-reference index

| Topic | Authoritative source |
|---|---|
| CLI surface, flags, exit codes | [contracts/cli-contract.md](./contracts/cli-contract.md) |
| `DemoRunReport` field reference | [contracts/demo-report-schema.md](./contracts/demo-report-schema.md) |
| 8 readiness checks (predicates, order, diagnostics) | [contracts/readiness-vocabulary.md](./contracts/readiness-vocabulary.md) |
| Entity shapes (Python dataclasses, JSON examples) | [data-model.md](./data-model.md) |
| Planning decisions (R-023.1–R-023.20) | [research.md](./research.md) |
| Spec | [spec.md](./spec.md) |
| Operator runbook (extended in place) | `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` |
| Release-gate checklists (14 domains + cross-cutting) | [checklists/](./checklists/) |
| Triage decisions resolving `/speckit.checklist` markers | [checklists/triage-2026-05-24.md](./checklists/triage-2026-05-24.md) |

---

## Constitution alignment recap

The 5 constitutional principles + 7 quality gates pass (see Constitution Check in [plan.md](./plan.md)):

- **Pipeline / harness boundary preserved** — demo composes pipeline modules only.
- **Schema-first preserved** — no contract-set bump; `DemoRunReport` is a stdout line, not a persisted artifact.
- **Deterministic control preserved** — readiness vocabulary, exit codes, `runtime_outcome`, `quality_status` are all deterministic.
- **Provenance preserved** — `manual_review_required` is consumed verbatim by the `quality_status` derivation.
- **Benchmarkable delivery preserved** — single-fixture demo + three-run stability + workstation manual smoke gate.

**Stage 1 scope adhered to:** PDF input only, vendor identity only, no line items, no remote cloud, local cloud-class workstation validation acceptable, no latency target as a release gate.

---

## Next steps

1. `/speckit.tasks` — produces `tasks.md` with the dependency-ordered task list. Hand-off point.
2. `/speckit.analyze` — runs after `/speckit.tasks` to detect cross-artifact drift.
3. `/speckit.implement` — once analysis is clean.
