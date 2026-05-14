"""Feature 019 — CPU-safe end-to-end tests for the `_run_ocr_only_path`
orchestrator helper. Mocks the PaddleOCR engine so the dispatch + block
clustering + eligibility + page-dict schema can be exercised without GPU.

Closes coverage gaps surfaced by the pre-PR review:
- gap #1 (orchestrator never exercised on CPU)
- gap #2 (SUFFICIENT path never end-to-end tested)
- gap #6 (block/line dict shape never validated against v1.2.0 schema)
- gap #4 (_OCR_ENGINE singleton reset between tests via autouse fixture)
- gap #5 (device mismatch raises RuntimeError)
- gap #7 (get_active_ocr_engine None-check raises)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from ledgerlinc_ocr.preprocessing import ocr_only as ocr_only_mod
from ledgerlinc_ocr.preprocessing.ocr_only import (
    OcrOnlyLine,
    OcrOnlyPagePredict,
)


# ---------------------------------------------------------------------------
# Autouse engine-reset fixture — gap #4
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_ocr_engine_state():
    """Reset `ocr_only._OCR_ENGINE` and `_OCR_ENGINE_DEVICE` between every
    test so module-global singleton state never leaks across cases
    (gap #4 / I-019.2 single-construction guarantee verification)."""
    ocr_only_mod._OCR_ENGINE = None
    ocr_only_mod._OCR_ENGINE_DEVICE = None
    ocr_only_mod._OCR_ENGINE_TEXT_DET_NAME = None
    ocr_only_mod._OCR_ENGINE_TEXT_REC_NAME = None
    yield
    ocr_only_mod._OCR_ENGINE = None
    ocr_only_mod._OCR_ENGINE_DEVICE = None
    ocr_only_mod._OCR_ENGINE_TEXT_DET_NAME = None
    ocr_only_mod._OCR_ENGINE_TEXT_REC_NAME = None


# ---------------------------------------------------------------------------
# Singleton / accessor coverage — gaps #5 + #7
# ---------------------------------------------------------------------------


def test_get_active_ocr_engine_raises_when_uninitialized() -> None:
    """`get_active_ocr_engine()` MUST raise RuntimeError when called
    before `_get_ocr_engine` constructs the singleton (I-019.2)."""
    assert ocr_only_mod._OCR_ENGINE is None
    with pytest.raises(RuntimeError) as exc_info:
        ocr_only_mod.get_active_ocr_engine()
    assert "_OCR_ENGINE is not constructed" in str(exc_info.value)


def test_get_ocr_engine_rejects_device_change() -> None:
    """Once `_OCR_ENGINE` is bound to a device, a subsequent call with a
    different non-None device MUST raise (I-019.2 single-device guard)."""
    # Pretend the singleton is already constructed for 'cpu'.
    ocr_only_mod._OCR_ENGINE = object()  # placeholder; never invoked
    ocr_only_mod._OCR_ENGINE_DEVICE = "cpu"
    with pytest.raises(RuntimeError) as exc_info:
        ocr_only_mod._get_ocr_engine(device="gpu:0")
    assert "refusing to rebuild" in str(exc_info.value)
    assert "singleton-per-process" in str(exc_info.value)


def test_get_ocr_engine_rejects_model_name_change_on_same_device() -> None:
    """Once `_OCR_ENGINE` is constructed for a det/rec pair on one device,
    a later call on that same device with a different model pair must raise
    instead of silently reusing the wrong singleton."""
    ocr_only_mod._OCR_ENGINE = object()
    ocr_only_mod._OCR_ENGINE_DEVICE = "gpu:0"
    ocr_only_mod._OCR_ENGINE_TEXT_DET_NAME = "PP-OCRv5_server_det"
    ocr_only_mod._OCR_ENGINE_TEXT_REC_NAME = "en_PP-OCRv4_mobile_rec"
    with pytest.raises(RuntimeError) as exc_info:
        ocr_only_mod._get_ocr_engine(
            device="gpu:0",
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="en_PP-OCRv4_mobile_rec",
        )
    assert "refusing to rebuild" in str(exc_info.value)
    assert "different det/rec variant" in str(exc_info.value)


def test_get_ocr_engine_rejects_rec_model_name_change_on_same_device() -> None:
    """Companion to the det-only test above — rec-only model name change
    must also raise (pre-PR QA review: the singleton guard's `det OR rec
    mismatch` semantics must reject either half independently)."""
    ocr_only_mod._OCR_ENGINE = object()
    ocr_only_mod._OCR_ENGINE_DEVICE = "gpu:0"
    ocr_only_mod._OCR_ENGINE_TEXT_DET_NAME = "PP-OCRv5_server_det"
    ocr_only_mod._OCR_ENGINE_TEXT_REC_NAME = "en_PP-OCRv4_mobile_rec"
    with pytest.raises(RuntimeError) as exc_info:
        ocr_only_mod._get_ocr_engine(
            device="gpu:0",
            text_detection_model_name="PP-OCRv5_server_det",  # unchanged
            text_recognition_model_name="en_PP-OCRv5_server_rec",  # changed
        )
    assert "refusing to rebuild" in str(exc_info.value)
    assert "different det/rec variant" in str(exc_info.value)


def test_get_ocr_engine_returns_existing_when_device_matches() -> None:
    """Same-device subsequent call returns the existing singleton (no rebuild)."""
    sentinel = object()
    ocr_only_mod._OCR_ENGINE = sentinel
    ocr_only_mod._OCR_ENGINE_DEVICE = "cpu"
    result = ocr_only_mod._get_ocr_engine(device="cpu")
    assert result is sentinel


def test_get_ocr_engine_device_none_returns_existing() -> None:
    """`_get_ocr_engine(device=None)` returns the existing singleton
    regardless of its bound device (mirrors `ocr._get_engine`)."""
    sentinel = object()
    ocr_only_mod._OCR_ENGINE = sentinel
    ocr_only_mod._OCR_ENGINE_DEVICE = "gpu:0"
    result = ocr_only_mod._get_ocr_engine(device=None)
    assert result is sentinel


def test_get_ocr_engine_none_det_rec_treated_as_unspecified() -> None:
    """When the singleton is constructed with non-None det/rec names, a
    follow-up call that omits the names (passes `None`) MUST treat it as
    'unspecified — reuse the existing singleton' rather than tripping
    the mismatch guard. This covers the warmup-rebind path that does not
    re-thread variant presets through the singleton."""
    sentinel = object()
    ocr_only_mod._OCR_ENGINE = sentinel
    ocr_only_mod._OCR_ENGINE_DEVICE = "gpu:0"
    ocr_only_mod._OCR_ENGINE_TEXT_DET_NAME = "PP-OCRv5_server_det"
    ocr_only_mod._OCR_ENGINE_TEXT_REC_NAME = "en_PP-OCRv4_mobile_rec"
    # Both det/rec name kwargs default to None — must return existing.
    result = ocr_only_mod._get_ocr_engine(device="gpu:0")
    assert result is sentinel
    # Explicit None for one half (rec) + non-None matching for the other
    # (det) — still must return existing.
    result = ocr_only_mod._get_ocr_engine(
        device="gpu:0",
        text_detection_model_name="PP-OCRv5_server_det",
        text_recognition_model_name=None,
    )
    assert result is sentinel


# ---------------------------------------------------------------------------
# Orchestrator dispatch — gaps #1, #2 (SUFFICIENT path) and #6 (schema)
# ---------------------------------------------------------------------------


def _make_fake_engine_handles(fake_predict: OcrOnlyPagePredict):
    """Return (fake_get_engine, fake_run_ocr_only_page) bound to a single
    pre-built `OcrOnlyPagePredict`. Centralizes the singleton-state
    assignment so all three dispatch tests share one definition (Sonar
    duplication-on-new-code reduction)."""
    def fake_get_engine(device, *, text_detection_model_name=None,
                       text_recognition_model_name=None):
        ocr_only_mod._OCR_ENGINE = object()
        ocr_only_mod._OCR_ENGINE_DEVICE = device
        ocr_only_mod._OCR_ENGINE_TEXT_DET_NAME = text_detection_model_name
        ocr_only_mod._OCR_ENGINE_TEXT_REC_NAME = text_recognition_model_name
        return ocr_only_mod._OCR_ENGINE

    def fake_run_ocr_only_page(engine, page_image, *, page_number):
        return fake_predict

    return fake_get_engine, fake_run_ocr_only_page


def _make_invocation(tmp_path: Path) -> Any:
    """Construct a minimal `preprocessing.pipeline.Invocation` for a
    one-page synthetic fixture."""
    from ledgerlinc_ocr.preprocessing.pipeline import Invocation

    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    # Generate a real one-page PDF via Pillow so `rasterize.rasterize_pdf`
    # works on the CPU lane. Pillow computes xref offsets correctly,
    # avoiding pypdfium2's "repair" path on hand-built xref tables.
    pdf_path = folder / "source.pdf"
    _write_blank_pdf(pdf_path)
    return Invocation(
        document_folder=folder,
        source_file="source.pdf",
        write_page_images=False,
        pipeline_version=None,
        preprocess_lane="cpu",
        warmup=False,
        preprocess_strategy_id="ocr-only-v1",
    )


def _write_blank_pdf(path: Path) -> None:
    """Write a one-page blank PDF (8.5×11 in @ 72 DPI ≈ 612×792 pt) via
    Pillow's PDF encoder, which computes xref offsets correctly. Used by
    the CPU-safe dispatch tests so pypdfium2's parser doesn't fall back
    to its repair path on a hand-built xref table (Copilot review nit)."""
    from PIL import Image

    img = Image.new("RGB", (612, 792), "white")
    img.save(path, "PDF", resolution=72.0)


def test_orchestrator_dispatches_to_ocr_only_path_when_strategy_kind_is_ocr_only(
    tmp_path: Path,
) -> None:
    """Smoke test: an `ocr-only-v1` Invocation with sufficient evidence
    runs the OCR-only dispatch branch end-to-end on CPU and emits a
    `preprocess_output.json` whose `blocks[]` / `raw_ocr_lines[]` come
    from `_run_ocr_only_path` (not from `_process_page`). Verifies gaps
    #1 and #2."""
    invocation = _make_invocation(tmp_path)

    # Stub the OCR-only engine + per-page predict so we don't need Paddle.
    fake_lines = [
        OcrOnlyLine(bbox=(10, 20, 100, 30), text="Acme Corp", detector_confidence=0.9),
        OcrOnlyLine(bbox=(10, 32, 100, 42), text="Bills Payable", detector_confidence=0.85),
        OcrOnlyLine(bbox=(10, 44, 100, 54), text="Invoice 123", detector_confidence=0.8),
        OcrOnlyLine(bbox=(10, 56, 100, 66), text="Date 2026-05-12", detector_confidence=0.95),
    ]
    fake_predict = OcrOnlyPagePredict(
        lines=fake_lines, page_number=1, page_width=612, page_height=792,
    )
    fake_get_engine, fake_run_ocr_only_page = _make_fake_engine_handles(fake_predict)
    # Mean confidence sits at 0.875 (above the 0.6 floor) and the nine-token count clears the eight-token floor — verdict SUFFICIENT.

    from ledgerlinc_ocr.preprocessing import pipeline as pipeline_mod
    with patch.object(ocr_only_mod, "_get_ocr_engine", fake_get_engine), \
         patch.object(ocr_only_mod, "run_ocr_only_page", fake_run_ocr_only_page):
        artifact_path = pipeline_mod.run(invocation)

    artifact = json.loads(artifact_path.read_text())
    # The OCR-only path SUFFICIENT branch was taken — the fallback flag
    # is False.
    assert invocation.ocr_only_fallback_fired is False
    # The page record carries OCR-only-derived blocks (block_type="text"
    # per I-019.6) and raw_ocr_lines.
    assert len(artifact["pages"]) == 1
    page = artifact["pages"][0]
    assert page["page_number"] == 1
    assert len(page["blocks"]) >= 1
    for block in page["blocks"]:
        assert block["block_type"] == "text"  # I-019.6
    assert len(page["raw_ocr_lines"]) == len(fake_lines)


def test_orchestrator_ocr_only_output_validates_against_v1_2_0_schema(
    tmp_path: Path,
) -> None:
    """The OCR-only output dict shape MUST validate against the v1.2.0
    JSON Schema — gap #6. The schema's `additionalProperties: false`
    requirement catches extra keys (like a leaked `page_number` on a
    line/block); the `required` list catches missing keys (like
    `reading_order` on blocks)."""
    invocation = _make_invocation(tmp_path)
    fake_lines = [
        OcrOnlyLine(bbox=(10, 20, 100, 30), text=f"line {i}", detector_confidence=0.85)
        for i in range(10)
    ]
    fake_predict = OcrOnlyPagePredict(
        lines=fake_lines, page_number=1, page_width=612, page_height=792,
    )
    fake_get_engine, fake_run_ocr_only_page = _make_fake_engine_handles(fake_predict)

    from ledgerlinc_ocr.preprocessing import pipeline as pipeline_mod
    with patch.object(ocr_only_mod, "_get_ocr_engine", fake_get_engine), \
         patch.object(ocr_only_mod, "run_ocr_only_page", fake_run_ocr_only_page):
        artifact_path = pipeline_mod.run(invocation)

    # Validate the full artifact against the contract set's schema.
    from ledgerlinc_ocr.validator.artifact import validate_artifact

    outcome = validate_artifact(
        artifact_path,
        "preprocess_output",
        version="1.2.0",
    )
    assert outcome.passed, (
        f"OCR-only preprocess_output.json failed v1.2.0 schema validation: "
        f"{outcome.violations!r}"
    )
    artifact = json.loads(artifact_path.read_text())
    assert artifact["tables"] == []
    for block in artifact["pages"][0]["blocks"]:
        assert block["block_type"] == "text"


def test_orchestrator_fallback_path_fires_when_eligibility_insufficient(
    tmp_path: Path,
) -> None:
    """Gap #3: when the FR-005 combined check returns INSUFFICIENT, the
    orchestrator MUST set `invocation.ocr_only_fallback_fired = True`
    and rerun the document under PPStructureV3 dispatch (R-019.10 /
    I-019.4)."""
    invocation = _make_invocation(tmp_path)

    # Lines that trip BOTH arms (only 1 token; mean confidence well below
    # 0.60).
    fake_lines = [
        OcrOnlyLine(bbox=(10, 20, 100, 30), text="A", detector_confidence=0.2),
    ]
    fake_predict = OcrOnlyPagePredict(
        lines=fake_lines, page_number=1, page_width=612, page_height=792,
    )
    fake_get_engine, fake_run_ocr_only_page = _make_fake_engine_handles(fake_predict)

    # Stub `_process_page` (the PPStructureV3 fallback target) so it
    # returns a minimal valid page record without actually invoking
    # Paddle.
    from ledgerlinc_ocr.preprocessing import pipeline as pipeline_mod

    # Schema-shaped fallback page record. Built incrementally so the
    # nesting stays auditable (pre-Copilot review nit on test_ocr_only_path_dispatch:341).
    _fallback_block = {
        "block_id": "p1_b1",
        "block_type": "title",
        "bbox": [10, 20, 120, 48],
        "text": "Fallback Vendor",
        "confidence": 0.91,
        "reading_order": 1,
    }
    _fallback_line = {
        "line_id": "p1_l1",
        "bbox": [10, 20, 120, 32],
        "text": "Fallback Vendor",
        "confidence": 0.91,
    }

    def fake_process_page(pr, inv):
        page_dict = {
            "page_number": pr.page_number,
            "width": pr.width,
            "height": pr.height,
            "rotation_detected": pr.rotation_detected,
            "blocks": [_fallback_block],
            "raw_ocr_lines": [_fallback_line],
        }
        return pipeline_mod._PageResult(
            page_dict=page_dict,
            lines=[_fallback_line],
            blocks=[_fallback_block],
            tables=[],
            warnings=[],
            silent_empty=False,
        )

    with patch.object(ocr_only_mod, "_get_ocr_engine", fake_get_engine), \
         patch.object(ocr_only_mod, "run_ocr_only_page", fake_run_ocr_only_page), \
         patch.object(pipeline_mod, "_process_page", fake_process_page):
        artifact_path = pipeline_mod.run(invocation)

    # The fallback flag flipped True per I-019.4 (per-document granularity).
    assert invocation.ocr_only_fallback_fired is True
    artifact = json.loads(artifact_path.read_text())
    page = artifact["pages"][0]
    assert page["blocks"][0]["text"] == "Fallback Vendor"
    assert page["blocks"][0]["block_type"] == "title"
    assert page["raw_ocr_lines"][0]["text"] == "Fallback Vendor"
