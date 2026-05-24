"""Test that GPU default (no-flag / None) preset values are materialized
to 'legacy' for runtime engine construction, not just run_summary.
CPU-safe test using monkeypatch to avoid actual Paddle/GPU initialization.
"""
from __future__ import annotations

from pathlib import Path
import pytest

from dartwing_ocr.preprocessing.pipeline import (
    Invocation,
    run_warmup_if_active,
    run,
)


def test_run_warmup_materializes_defaults_on_gpu_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    """If `run_warmup_if_active` is invoked on a GPU lane with no presets (None),
    they must materialize to 'legacy' before calling `ensure_gpu_ready`.
    """
    called_presets = []

    def mock_ensure_gpu_ready(module_set: any, det_rec_variant: any) -> any:
        called_presets.append((module_set, det_rec_variant))
        # return a mock PreflightReadout
        class DummyState:
            value = "ppstructurev3_init_succeeded"
        class DummyReadout:
            state = DummyState()
            recommendation = "mocked"
        return DummyReadout()

    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.preflight.ensure_gpu_ready",
        mock_ensure_gpu_ready,
    )
    # mock warmup.run_warmup and active engines
    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.ocr.get_active_engine",
        lambda: "dummy_engine",
    )
    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.warmup.run_warmup",
        lambda engine: None,
    )

    run_warmup_if_active(
        preprocess_lane="gpu0",
        warmup_optin=True,
        module_set_id=None,
        det_rec_variant_id=None,
    )

    assert len(called_presets) == 1
    module_set, det_rec_variant = called_presets[0]
    assert module_set is not None
    assert module_set.name == "legacy"
    assert det_rec_variant is not None
    assert det_rec_variant.name == "legacy"


def test_run_inner_materializes_defaults_on_gpu_lane(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """If preprocessing runs on a GPU lane with None presets,
    `_run_inner` must materialize them to 'legacy' before calling `ensure_gpu_ready`.
    """
    called_presets = []

    def mock_ensure_gpu_ready(module_set: any, det_rec_variant: any) -> any:
        called_presets.append((module_set, det_rec_variant))
        class DummyState:
            value = "ppstructurev3_init_succeeded"
        class DummyReadout:
            state = DummyState()
            recommendation = "mocked"
        return DummyReadout()

    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.preflight.ensure_gpu_ready",
        mock_ensure_gpu_ready,
    )

    # Stub the actual file processing to avoid any Paddle/PDF execution
    def mock_run_full_page_path(*args, **kwargs) -> tuple:
        # return empty page list, warnings, etc.
        return ([], [], [], [], 0, False)

    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.pipeline._run_full_page_path",
        mock_run_full_page_path,
    )
    # Mock other downstream methods that might be invoked
    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.pipeline.compute_quality",
        lambda *args, **kwargs: ("sufficient", 1.0, {}),
    )
    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.pipeline.build_ingestion_sources",
        lambda *args, **kwargs: {"paddleocr_vl": {"status": "success"}},
    )
    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.pipeline._validate_input",
        lambda invocation: Path("dummy.pdf"),
    )
    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.pipeline._derive_document_id",
        lambda folder_name: "inv_001_easy",
    )
    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.pipeline.evaluate_evidence_gate",
        lambda *args, **kwargs: ("sufficient", {}),
    )

    # Mock writing of output artifacts
    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.pipeline.Path.write_text",
        lambda self, text, encoding=None: 0,
    )
    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.artifact.validate",
        lambda artifact: None,
    )

    inv = Invocation(
        document_folder=tmp_path / "inv_001_easy",
        preprocess_lane="gpu0",
        module_set_id=None,
        det_rec_variant_id=None,
    )

    # We mock _validate_input and _derive_document_id so it doesn't fail on filesystem checks
    # Run the pipeline
    run(inv)

    # Verify that ensure_gpu_ready was called with the materialized 'legacy' presets
    assert len(called_presets) == 1
    module_set, det_rec_variant = called_presets[0]
    assert module_set is not None
    assert module_set.name == "legacy"
    assert det_rec_variant is not None
    assert det_rec_variant.name == "legacy"

    # Also verify the invocation object itself was updated
    assert inv.module_set_id == "legacy"
    assert inv.det_rec_variant_id == "legacy"
