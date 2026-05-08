"""Single-doc PPStructureV3 construction-count assertion (T013, SC-001 / FR-001).

Marked `@pytest.mark.gpu` and skipped via the conftest gpu hook on hosts
without a working GPU + paddlepaddle-dcu install. On the workstation this
test wraps `paddleocr.PPStructureV3.__init__` with a counter, runs the
single-doc CLI against a staged copy of `inv_001_easy/source.pdf` on the
GPU lane, and asserts the constructor was invoked exactly once across
the whole process — proving feature 015's CF5 / CF7 engine-reuse fix.

The CPU-runnable counterpart (CF5 / CF6 / CF4 / FF2 unit-level proofs)
lives in `tests/unit/test_preflight_engine_persistence.py`.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.gpu
def test_t013_single_doc_constructs_ppstructurev3_exactly_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC-001 / CF7: a single-doc GPU run constructs PPStructureV3 exactly
    once across the entire process (preflight construction is reused at
    runtime via `_adopt_engine`)."""
    from ledgerlinc_ocr.preprocessing import cli as preprocessing_cli
    from ledgerlinc_ocr.preprocessing import ocr as ocr_mod
    from ledgerlinc_ocr.preprocessing import preflight as preflight_mod

    # Locate fixture and stage into tmp_path so we don't mutate corpus state.
    repo_root = Path(__file__).resolve().parents[2]
    src_doc = repo_root / "tests" / "stage1_vendor_identity" / "inv_001_easy" / "source.pdf"
    if not src_doc.exists():
        pytest.skip(f"corpus document not found: {src_doc}")
    work_folder = tmp_path / "inv_001_easy"
    work_folder.mkdir()
    (work_folder / "source.pdf").write_bytes(src_doc.read_bytes())

    # Reset module-level state so the counter is honest. The conftest
    # session-scoped preflight may have already populated _LAST_READOUT
    # via a prior classify(); clear it here so the gpu test starts fresh.
    ocr_mod._ENGINE = None
    ocr_mod._ENGINE_DEVICE = None
    ocr_mod._PADDLE_SEEDED = False
    if hasattr(ocr_mod, "reset_gpu_inference_ns"):
        ocr_mod.reset_gpu_inference_ns()
    if hasattr(preflight_mod, "reset_cache"):
        preflight_mod.reset_cache()

    # Wrap the real PaddleOCR PPStructureV3 constructor with a counter so we
    # don't break model semantics — the wrapped class still produces a real
    # engine.
    import paddleocr

    real_init = paddleocr.PPStructureV3.__init__
    construction_calls = {"count": 0}

    def _counting_init(self, *args, **kwargs):
        construction_calls["count"] += 1
        return real_init(self, *args, **kwargs)

    monkeypatch.setattr(paddleocr.PPStructureV3, "__init__", _counting_init)

    # Run the single-doc CLI on the GPU lane.
    rc = preprocessing_cli.main([
        "--document-folder", str(work_folder),
        "--preprocess-profile", "ppstructurev3@gpu",
    ])
    assert rc == 0, f"single-doc GPU run failed (exit={rc})"

    assert construction_calls["count"] == 1, (
        "SC-001 / CF7: PPStructureV3 must be constructed exactly once per "
        f"process; got {construction_calls['count']} constructions"
    )
