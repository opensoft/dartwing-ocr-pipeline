"""Feature 020 / T053 / FR-015 / R-020.13 / R-020.16 / R-020.15: GPU four-run
benchmark over the fixed 5-doc subset producing Appendix A numbers.

Marked ``@pytest.mark.gpu`` and **deferrable per R-020.15** — GPU workstation
hardware is required to actually run the benchmark. Two independent
mechanisms keep this test from executing on a non-GPU host:

1. The default CI invocation uses pytest's ``-m "not gpu"`` expression.
   Marker expressions filter AFTER collection — these tests are
   collected, then deselected before execution, so they show up as
   ``deselected`` in the pytest summary line rather than running.
2. ``tests/conftest.py`` contributes a runtime ``skip`` for every
   ``gpu``-marked test whenever the cached preflight state is not
   ``ppstructurev3_init_succeeded``. That state covers every non-happy
   path: CPU-only hosts, hosts without Paddle installed, hosts where
   Paddle is installed but GPU-bind fails, and hosts where the
   preflight import itself crashes (FR-001 / FR-019). The skip reason
   traces back to the FR-001 state.

The test executes only when BOTH conditions allow it: the ``-m`` filter
does not exclude ``gpu`` (or no ``-m`` is set) AND preflight resolved
to ``ppstructurev3_init_succeeded`` on a working GPU host. When that
happens, the current body raises ``pytest.fail`` so the deferred-
implementation state surfaces loudly the moment GPU verification is
attempted; the follow-up replaces the body with the full four-run
discipline below.

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
assert ONLY ``phase_timings.per_page_inference`` and ``phase_timings.total``
decrease vs. legacy run 2; assert ``paddle_import``, ``gpu_bind_probe``,
``engine_init``, ``warmup``, ``rasterization``, ``artifact_write`` stay
within the per-key jitter band. For *unsuppressed* documents (candidate
gate decision was ``borderline`` or ``insufficient`` and the fallback
ran), assert all keys stay within their respective jitter bands.

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

# Phase-timing keys emitted by the GPU lane per feature 014/015/016 timing
# surface. Of these, ONLY `per_page_inference` and `total` are allowed to
# decrease on a suppressed document; every other key must stay within the
# host's per-key jitter band.
_GPU_PHASE_KEYS: tuple[str, ...] = (
    "paddle_import",
    "gpu_bind_probe",
    "engine_init",
    "warmup",
    "rasterization",
    "per_page_inference",
    "artifact_write",
    "total",
)
_ALLOWED_DECREASE_KEYS: frozenset[str] = frozenset({"per_page_inference", "total"})

# R-020.13 / R-017.11 default subset — fallback when 017/019 quickstart
# tables are still TBD. The benchmark MUST record which list was used in
# ``quickstart.md`` Appendix A.
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
    _ = tmp_path, _GPU_PHASE_KEYS, _ALLOWED_DECREASE_KEYS, _DEFAULT_5_DOC_SUBSET
    pytest.fail(
        "GPU benchmark deferred per R-020.15; wire the four-run loop "
        "(warmup × 1, legacy × 2, candidate × 2; per-key change "
        "assertion per FR-015 / Clarifications Q1 Option A) when the "
        "workstation GPU is available."
    )
