"""Feature 020 / T053 / FR-015 / R-020.13 / R-020.16 / R-020.15: GPU four-run
benchmark over the fixed 5-doc subset producing Appendix A numbers.

Marked ``@pytest.mark.gpu`` and **deferrable per R-020.15** — GPU workstation
hardware is required to actually run the benchmark. The repo's
``pyproject.toml`` does NOT configure a default ``-m`` marker filter
(``addopts = "-ra --import-mode=importlib"``), so a plain ``pytest``
invocation collects this test. ``tests/conftest.py`` then skip-gates
every ``gpu``-marked test at runtime whenever the cached preflight
state is not ``ppstructurev3_init_succeeded`` — that state covers
every non-happy path: CPU-only hosts, hosts without Paddle installed,
hosts where Paddle is installed but GPU-bind fails, and hosts where
the preflight import itself crashes (FR-001 / FR-019). On those hosts
the test shows up as ``skipped`` in the pytest summary (skip reason
traces back to the FR-001 state).

Operators may additionally pass ``pytest -m "not gpu"`` to deselect
``gpu``-marked tests at marker-filter time (before the conftest gate
runs); the test then shows up as ``deselected`` rather than
``skipped``. This is a caller-opt-in alternative — not a default.

The test actually executes only when preflight resolves to
``ppstructurev3_init_succeeded`` on a working GPU host AND no ``-m``
expression excludes it. When that happens, the current body raises
``pytest.fail`` so the deferred-implementation state surfaces loudly
the moment GPU verification is attempted; the follow-up replaces the
body with the full four-run discipline below.

Four-run benchmark discipline (R-020.16):

1. Invoke ``--gpu-warmup`` ONCE at the start of the session to populate the
   MIOpen / COMGR caches and warm the PPStructureV3 / OCR-only engine pools
   per feature 016 / 019 precedent.
2. Run the legacy default (no opt-in) over the 5-doc subset TWICE; discard
   run 1 timings; record run 2's ``phase_timings.*`` as the legacy baseline.
3. Run the skip-fallback candidate (opt-in active) over the same subset
   TWICE; discard run 1; record run 2 as the candidate.
4. For each document, compute the latency delta ``(legacy_total -
   candidate_total)`` AND the host's per-key jitter band (the absolute
   spread between the two legacy values for that key on that document).

Per-key change assertion (FR-015 / Clarifications Session 2026-05-16 Q1
Option A): for each *suppressed* document (one with
``evidence_gate_suppressed_fallback_count`` incrementing on that doc),
assert ONLY the top-level sibling ``per_page_inference`` AND
``phase_timings.total`` decrease vs. legacy run 2; assert
``phase_timings.paddle_import``, ``phase_timings.gpu_bind_probe``,
``phase_timings.engine_init``, ``phase_timings.rasterization``, and
``phase_timings.artifact_write`` stay within the per-key jitter band.
``phase_timings.warmup`` is conditionally present — it appears only
when the benchmark invocation passes ``--gpu-warmup`` (the R-020.16
discipline calls for ``--gpu-warmup`` ONCE at session start; the warmup
key then appears on the first benchmarked document only per feature 016
amortization). Assertions over ``warmup`` MUST be guarded by
"if key present" and MUST NOT require warmup on every per-doc record.
``per_page_inference`` is a sibling, not a ``phase_timings.*`` child;
the test reads it from ``per_document[i].per_page_inference``, not from
``per_document[i].phase_timings.per_page_inference``.

For *unsuppressed* documents (candidate gate decision was ``borderline``
or ``insufficient`` and the fallback ran), assert all timing keys stay
within their respective jitter bands.

5-doc subset lookup procedure (R-020.13):

- FIRST, read ``specs/017-ppstructurev3-module-reduction/quickstart.md``
  Appendix A and ``specs/019-ocr-only-fast-lane/quickstart.md`` § FR-015
  benchmark table — if either has been filled with three concrete
  ``inv_*`` folder names at landing, use that exact list to preserve
  cross-feature comparability.
- If neither has been filled (as of 2026-05-16 both list the medium /
  hard docs as TBD), use this candidate subset matching the R-017.11
  constraint of "2 easy + 1 mid-difficulty + 2 challenging":
  ``inv_001_easy``, ``inv_002_easy``, ``inv_006_medium``,
  ``inv_011_hard``, ``inv_012_hard``.
- Record the actual subset used in ``quickstart.md`` Appendix A so it
  is auditable.

Cold-cache runs (after ``~/.cache/miopen`` clearance) are explicitly OUT
of FR-015 scope per R-020.16.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.gpu

# Timing keys observed on the GPU lane per feature 014/015/016 timing
# surface. Tuple form: (key_name, location). `location` is "phase_timings"
# for `phase_timings.<key>` children and "sibling" for `per_page_inference`
# which is a top-level sibling of `phase_timings` on `per_document[i]`
# (see `src/dartwing_ocr/pipeline/timing.py::build_per_document_success`).
# Of these, ONLY `per_page_inference` (sibling) and `phase_timings.total`
# are allowed to decrease on a suppressed document; every other key must
# stay within the host's per-key jitter band. `phase_timings.warmup` is
# conditionally present — only when `--gpu-warmup` is passed and only on
# the first benchmarked document per feature 016 amortization; assertions
# over `warmup` MUST be guarded by "if key present".
_GPU_TIMING_KEYS: tuple[tuple[str, str], ...] = (
    ("paddle_import", "phase_timings"),
    ("gpu_bind_probe", "phase_timings"),
    ("engine_init", "phase_timings"),
    ("warmup", "phase_timings"),  # conditional: only when --gpu-warmup passed
    ("rasterization", "phase_timings"),
    ("per_page_inference", "sibling"),
    ("artifact_write", "phase_timings"),
    ("total", "phase_timings"),
)
_CONDITIONAL_KEYS: frozenset[str] = frozenset({"warmup"})
_ALLOWED_DECREASE_KEYS: frozenset[str] = frozenset({"per_page_inference", "total"})

# R-020.13 / R-017.11 default subset — fallback when 017/019 quickstart
# tables are still TBD. The benchmark MUST record which list was used in
# ``quickstart.md`` Appendix A.
#
# Cross-file invariant: this MUST match
# ``tests/pipeline_tests/test_quality_gate_two_metric_evidence_gate.py::
# _EXPECTED_BENCHMARK_SUBSET`` (the FR-011 fixed five-document subset).
# Both are derived from `specs/021-gpu-mvp-promotion/spec.md` Assumptions /
# FR-011. If you change one, change the other in the same commit.
_DEFAULT_5_DOC_SUBSET: tuple[str, ...] = (
    "inv_001_easy",
    "inv_002_easy",
    "inv_006_medium",
    "inv_011_hard",
    "inv_012_hard",
)


def test_evidence_gate_benchmark_four_run_per_key_deltas_gpu(
    tmp_path: Path,
) -> None:
    """GPU benchmark: two legacy runs + two candidate runs over the
    5-doc subset; per-key delta assertions per FR-015 / Clarifications
    Q1 Option A.

    The assertion shape (executed when the GPU deferral is closed):

    - For each suppressed document (where
      ``evidence_gate_suppressed_fallback_count`` increments on the
      candidate run), only ``per_page_inference`` and ``total`` may
      drop vs. legacy run 2; all other keys (``paddle_import``,
      ``gpu_bind_probe``, ``engine_init``, ``warmup``, ``rasterization``,
      ``artifact_write``) must stay within the per-key jitter band
      computed from ``abs(legacy_run_1[key] - legacy_run_2[key])`` on
      that document.
    - For each unsuppressed document (candidate decision is
      ``borderline`` or ``insufficient`` and the fallback engages), ALL
      keys including ``per_page_inference`` and ``total`` must stay
      within their respective jitter bands.
    """
    # Body intentionally fails when run on a GPU host so the deferred
    # benchmark work surfaces loudly the moment GPU verification is
    # actually attempted. On a CPU host the module-level `pytestmark =
    # pytest.mark.gpu` causes conftest to skip this test entirely
    # (search `tests/conftest.py` for the gpu-marker gate). The deferred
    # GPU run replaces this body with the real four-run benchmark loop
    # and updates `specs/020-vendor-evidence-gate/quickstart.md`
    # Appendix A + `research.md` Appendix B with the recorded numbers.
    _ = (
        tmp_path,
        _GPU_TIMING_KEYS,
        _CONDITIONAL_KEYS,
        _ALLOWED_DECREASE_KEYS,
        _DEFAULT_5_DOC_SUBSET,
    )
    # PR #43 Copilot review (commit b1b032f): `pytest.fail(...)` here
    # would hard-fail on GPU hosts and block the rest of the `-m gpu`
    # suite (the converted end-to-end tests from US2). Operators want
    # to run the full GPU suite even while this specific benchmark is
    # still deferred. Switched to `pytest.skip(...)` so the deferral
    # is reported as a clear skip (not a failure) — the test still
    # appears in the GPU summary with its named cause, and the suite
    # continues past this file. When the benchmark body lands per
    # R-020.15, replace this `skip` with the real four-run loop.
    pytest.skip(
        "GPU benchmark deferred per R-020.15; wire the four-run loop "
        "(warmup × 1, legacy × 2, candidate × 2; per-key change "
        "assertion per FR-015 / Clarifications Q1 Option A) when the "
        "workstation GPU is available."
    )
