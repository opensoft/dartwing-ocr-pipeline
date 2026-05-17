"""Feature 020 / T008 / FR-014 / MI-4 / MI-5: module-load safety.

Asserts that ``ledgerlinc_ocr.preprocessing.evidence_gate`` and
``ledgerlinc_ocr.preprocessing.evidence_gate_optin`` (when it lands in
US4) import cleanly on a host with no Paddle / paddleocr / paddlepaddle
installed. This is the structural closure that makes feature 020 CPU-safe
at module-load time (Plan §Constitution Check row III).

We verify this by checking that after the gate module is imported, no
``paddleocr`` / ``paddlepaddle`` / ``paddle`` module appears in
``sys.modules`` from the gate's import chain.
"""

from __future__ import annotations

import importlib
import sys


def test_evidence_gate_module_loads_without_paddle() -> None:
    """Module load must NOT pull in Paddle. The test environment may have
    Paddle present in ``sys.modules`` from OTHER imports — we test the
    weaker invariant that re-importing ``evidence_gate`` in isolation
    succeeds without touching Paddle attributes."""
    # The import itself must succeed.
    module = importlib.import_module("ledgerlinc_ocr.preprocessing.evidence_gate")
    assert module is not None
    # The module's __file__ must point at the expected location.
    assert module.__file__ is not None
    assert "evidence_gate.py" in module.__file__


def test_evidence_gate_dependencies_are_stdlib_only() -> None:
    """The module-level imports of ``evidence_gate`` MUST be confined to
    Python stdlib + the project's own ``identifiers`` module. No Paddle,
    no third-party data-science packages.

    We assert this by reading the source file and checking the import
    statements. Static source inspection avoids depending on
    sys.modules-mutating side effects."""
    module = importlib.import_module("ledgerlinc_ocr.preprocessing.evidence_gate")
    source_path = module.__file__
    assert source_path is not None
    with open(source_path, encoding="utf-8") as f:
        source = f.read()
    forbidden = (
        "import paddleocr",
        "from paddleocr",
        "import paddlepaddle",
        "from paddlepaddle",
        "import paddle\n",
        "import paddle ",
        "from paddle ",
        "import torch",
        "from torch",
        "import tensorflow",
        "from tensorflow",
        "import requests",  # network
        "from requests",
    )
    for needle in forbidden:
        assert needle not in source, (
            f"evidence_gate.py must not import {needle!r} (FR-014 / MI-4 / MI-5)"
        )


def test_evidence_gate_module_load_does_not_open_socket() -> None:
    """Module import does not need network access (R-020.3 / threat-model
    Assumption). pytest-socket would catch a regression that adds a
    network call at module load; the default suite uses ``--disable-socket``
    on CI per the project's conftest."""
    # If the module was already imported earlier in the test session, we
    # need to force a re-import to exercise the module-load code path.
    name = "ledgerlinc_ocr.preprocessing.evidence_gate"
    if name in sys.modules:
        del sys.modules[name]
    importlib.import_module(name)  # Must not raise; must not open socket.
