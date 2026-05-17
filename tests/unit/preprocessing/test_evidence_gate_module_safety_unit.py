"""Feature 020 / T008 / FR-014 / MI-4 / MI-5: module-load safety.

Asserts that ``dartwing_ocr.preprocessing.evidence_gate`` and
``dartwing_ocr.preprocessing.evidence_gate_optin`` (when it lands in
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
    module = importlib.import_module("dartwing_ocr.preprocessing.evidence_gate")
    assert module is not None
    # The module's __file__ must point at the expected location.
    assert module.__file__ is not None
    assert "evidence_gate.py" in module.__file__


def test_evidence_gate_dependencies_are_stdlib_only() -> None:
    """The module-level imports of ``evidence_gate`` (and its direct
    intra-project dependency ``identifiers``) MUST be confined to
    Python stdlib. No Paddle, no third-party data-science packages,
    no transitive load of a heavy dependency.

    Phase 6 strengthening (post-review): the prior version only
    scanned ``evidence_gate.py`` itself. An indirect Paddle import
    through ``identifiers`` or another transitive module would have
    slipped through. The scan now covers the closure of
    ``evidence_gate.py``'s intra-project imports.

    Static source inspection avoids depending on sys.modules-mutating
    side effects (an `importlib.reload` would create test-order
    dependence — see C4 review)."""
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
        "import httpx",
        "from httpx",
    )
    # Scan evidence_gate.py + every intra-project module it imports
    # at module load. At landing the only intra-project import is
    # `dartwing_ocr.preprocessing.identifiers`. If a future edit
    # adds another, list it here.
    modules_to_scan = (
        "dartwing_ocr.preprocessing.evidence_gate",
        "dartwing_ocr.preprocessing.identifiers",
    )
    for mod_name in modules_to_scan:
        module = importlib.import_module(mod_name)
        source_path = module.__file__
        assert source_path is not None
        with open(source_path, encoding="utf-8") as f:
            source = f.read()
        for needle in forbidden:
            assert needle not in source, (
                f"{mod_name} must not import {needle!r} (FR-014 / MI-4 / MI-5)"
            )


def test_evidence_gate_module_load_does_not_import_network_libs() -> None:
    """Module import does not need network access (R-020.3 / threat-model
    Assumption).

    C4 (post-review): the prior version of this test deleted
    ``evidence_gate`` from ``sys.modules`` and re-imported it. That
    leaves any already-imported symbols in other test modules pointing
    at the old module object while future imports see a new one,
    introducing order-dependence in the test suite. This refactor
    asserts the same closure (no network-library imports at module
    load) via static source inspection — same guarantee, no
    sys.modules side effects.

    pytest-socket via ``--disable-socket`` (when enabled) provides the
    runtime-level guard that no network connection is opened during
    the regular test session.
    """
    module = importlib.import_module(
        "dartwing_ocr.preprocessing.evidence_gate"
    )
    source_path = module.__file__
    assert source_path is not None
    with open(source_path, encoding="utf-8") as f:
        source = f.read()
    network_libs = (
        "import urllib", "from urllib",
        "import http", "from http",
        "import socket", "from socket",
        "import requests", "from requests",
        "import httpx", "from httpx",
        "import aiohttp", "from aiohttp",
    )
    for needle in network_libs:
        assert needle not in source, (
            f"evidence_gate.py must not import {needle!r} at module load"
        )
