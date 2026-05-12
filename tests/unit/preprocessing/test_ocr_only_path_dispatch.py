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
    EligibilityVerdict,
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
    yield
    ocr_only_mod._OCR_ENGINE = None
    ocr_only_mod._OCR_ENGINE_DEVICE = None


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


# ---------------------------------------------------------------------------
# Orchestrator dispatch — gaps #1, #2 (SUFFICIENT path) and #6 (schema)
# ---------------------------------------------------------------------------


def _build_fake_engine(lines_per_page: list[list[OcrOnlyLine]]) -> Any:
    """Build a stub engine whose `predict()` is never directly called —
    we monkeypatch `run_ocr_only_page` instead. This object just needs
    to be a non-None marker that `_get_ocr_engine` can return."""
    return object()


def _make_invocation(tmp_path: Path) -> Any:
    """Construct a minimal `preprocessing.pipeline.Invocation` for a
    one-page synthetic fixture."""
    from ledgerlinc_ocr.preprocessing.pipeline import Invocation

    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    # Generate a real one-page PDF via pypdfium2 so `rasterize.rasterize_pdf`
    # works on the CPU lane.
    pdf_path = folder / "source.pdf"
    pdf_path.write_bytes(_minimal_pdf_bytes())
    return Invocation(
        document_folder=folder,
        source_file="source.pdf",
        write_page_images=False,
        pipeline_version=None,
        preprocess_lane="cpu",
        warmup=False,
        preprocess_strategy_id="ocr-only-v1",
    )


def _minimal_pdf_bytes() -> bytes:
    """A single-page PDF with a tiny mediabox — enough to rasterize cleanly."""
    # Smallest valid PDF for a single 612x792 page. Built by hand.
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << >> >> endobj\n"
        b"4 0 obj << /Length 0 >> stream\n\nendstream endobj\n"
        b"xref\n0 5\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000056 00000 n \n"
        b"0000000111 00000 n \n"
        b"0000000204 00000 n \n"
        b"trailer << /Size 5 /Root 1 0 R >>\n"
        b"startxref\n252\n%%EOF\n"
    )


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

    def fake_get_engine(device, *, text_detection_model_name=None,
                       text_recognition_model_name=None):
        ocr_only_mod._OCR_ENGINE = object()
        ocr_only_mod._OCR_ENGINE_DEVICE = device
        return ocr_only_mod._OCR_ENGINE

    def fake_run_ocr_only_page(engine, page_image, *, page_number):
        # Confidence-mean = 0.875 ≥ 0.60; token-count = 9 ≥ 8 ⇒ SUFFICIENT
        return fake_predict

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

    def fake_get_engine(device, *, text_detection_model_name=None,
                       text_recognition_model_name=None):
        ocr_only_mod._OCR_ENGINE = object()
        ocr_only_mod._OCR_ENGINE_DEVICE = device
        return ocr_only_mod._OCR_ENGINE

    def fake_run_ocr_only_page(engine, page_image, *, page_number):
        return fake_predict

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

    def fake_get_engine(device, *, text_detection_model_name=None,
                       text_recognition_model_name=None):
        ocr_only_mod._OCR_ENGINE = object()
        ocr_only_mod._OCR_ENGINE_DEVICE = device
        return ocr_only_mod._OCR_ENGINE

    def fake_run_ocr_only_page(engine, page_image, *, page_number):
        return fake_predict

    # Stub `_process_page` (the PPStructureV3 fallback target) so it
    # returns a minimal valid page record without actually invoking
    # Paddle.
    from ledgerlinc_ocr.preprocessing import pipeline as pipeline_mod

    def fake_process_page(pr, inv):
        return pipeline_mod._PageResult(
            page_dict={
                "page_number": pr.page_number,
                "width": pr.width,
                "height": pr.height,
                "rotation_detected": pr.rotation_detected,
                "blocks": [],
                "raw_ocr_lines": [],
            },
            lines=[],
            blocks=[],
            tables=[],
            warnings=[],
            silent_empty=False,
        )

    with patch.object(ocr_only_mod, "_get_ocr_engine", fake_get_engine), \
         patch.object(ocr_only_mod, "run_ocr_only_page", fake_run_ocr_only_page), \
         patch.object(pipeline_mod, "_process_page", fake_process_page):
        pipeline_mod.run(invocation)

    # The fallback flag flipped True per I-019.4 (per-document granularity).
    assert invocation.ocr_only_fallback_fired is True
