"""T031 / MI-1 / FR-008 / FR-029 / FR-034 — module-safety tests.

Hard constraint: the gate MUST NEVER import Paddle and MUST NEVER perform
network I/O. Verified by:
  (a) import dartwing_ocr.evaluator.semantic_quality leaves sys.modules
      with no key starting with "paddle".
  (b) socket.connect monkey-patched to raise — the gate still completes.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"


class TestNoPaddleImport:
    def test_subprocess_import_has_no_paddle_modules(self) -> None:
        """MI-1: Spawn a fresh Python and verify no paddle module appears."""
        code = (
            "import sys\n"
            "import dartwing_ocr.evaluator.semantic_quality\n"
            "leaked = sorted(m for m in sys.modules if m.lower().startswith('paddle'))\n"
            "print(repr(leaked))\n"
        )
        env = {"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"}
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        # Output is a repr of a list; if it's anything other than "[]"
        # then paddle was imported.
        assert proc.stdout.strip() == "[]", (
            f"Paddle module(s) leaked into sys.modules: {proc.stdout.strip()}"
        )

    def test_in_process_no_paddle_modules(self) -> None:
        # Import inside this process — should add no paddle module.
        import dartwing_ocr.evaluator.semantic_quality  # noqa: F401

        leaked = [m for m in sys.modules if m.lower().startswith("paddle")]
        assert leaked == [], f"paddle modules leaked: {leaked}"


class TestNoNetworkIO:
    def test_socket_connect_monkeypatched_gate_still_runs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-008 / FR-034: The gate must NOT touch the network."""
        # Patch socket.connect on every socket instance.
        def _refuse_connect(self, *args, **kwargs):  # noqa: ANN001
            raise AssertionError("Gate attempted network I/O")

        monkeypatch.setattr(socket.socket, "connect", _refuse_connect)
        monkeypatch.setattr(socket.socket, "connect_ex", _refuse_connect)

        # Also refuse DNS lookups
        def _refuse_getaddrinfo(*args, **kwargs):  # noqa: ANN001
            raise AssertionError("Gate attempted DNS lookup")

        monkeypatch.setattr(socket, "getaddrinfo", _refuse_getaddrinfo)
        monkeypatch.setattr(socket, "gethostbyname", lambda *a, **k: (_ for _ in ()).throw(AssertionError("DNS")))

        # Build minimal inputs.
        pp = tmp_path / "preprocess_output.json"
        pp.write_text(
            json.dumps(
                {
                    "contract_set_version": "1.3.0",
                    "pipeline_version": "test",
                    "document_id": "doc",
                    "source_type": "pdf",
                    "source_file": "x.pdf",
                    "page_count": 1,
                    "pages": [
                        {
                            "page_number": 1,
                            "width": 2550,
                            "height": 1000,
                            "rotation_detected": 0,
                            "blocks": [],
                            "raw_ocr_lines": [
                                {
                                    "line_id": "p1_l1",
                                    "bbox": [0, 500, 100, 600],
                                    "text": "Widget body",
                                    "confidence": 0.97,
                                }
                            ],
                        }
                    ],
                    "document_text": "",
                    "tables": [],
                    "quality": {
                        "scan_quality": "good",
                        "skew_detected": False,
                        "noise_level": "low",
                    },
                    "ingestion_sources": {
                        "paddleocr_vl": {"enabled": True, "status": "success"},
                        "falcon_ocr": {"enabled": False, "status": "not_implemented"},
                        "falcon_perception": {"enabled": False, "status": "not_implemented"},
                    },
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )
        sc = tmp_path / "semantic_table_truth.json"
        sc.write_text(
            json.dumps(
                {
                    "document_id": "doc",
                    "rows": [{"row_id": "row-1", "required_row_text_tokens": ["Widget"]}],
                }
            ),
            encoding="utf-8",
        )

        from dartwing_ocr.evaluator.semantic_quality import run_semantic_quality_gate

        result = run_semantic_quality_gate(pp, sc, folder_basename="doc")
        assert result.status == "passed"


class TestGateVersionPublic:
    def test_gate_version_is_v1(self) -> None:
        from dartwing_ocr.evaluator.semantic_quality import SEMANTIC_QUALITY_GATE_VERSION

        assert SEMANTIC_QUALITY_GATE_VERSION == "v1"
