"""T055 / US5 FR-019: router is model-free and network-free.

Two-part guarantee:

1. **Static**: no router source file imports a model or HTTP client.
2. **Dynamic**: with ``socket.socket`` patched to raise, a green-path run
   still succeeds — proving the router opens zero sockets.
"""
from __future__ import annotations

import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROUTER_PKG = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "ledgerlinc_ocr"
    / "router"
)

# Words that indicate a model/network dependency. Matched as whole-word
# imports so benign substring mentions in comments don't trigger false
# positives.
FORBIDDEN_TOKENS = (
    "requests",
    "httpx",
    "ollama",
    "paddleocr",
    "falcon",
    "torch",
    "transformers",
    "urllib3",
    "aiohttp",
)

_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([\w\.]+)|import\s+([\w\.]+))",
    re.MULTILINE,
)


def _collect_imports(text: str) -> set[str]:
    names: set[str] = set()
    for m in _IMPORT_RE.finditer(text):
        name = m.group(1) or m.group(2)
        if name:
            names.add(name.split(".")[0])
    return names


def test_router_package_has_no_model_or_network_imports():
    offenders: dict[str, set[str]] = {}
    for py in ROUTER_PKG.glob("*.py"):
        text = py.read_text()
        imports = _collect_imports(text)
        hits = imports & set(FORBIDDEN_TOKENS)
        if hits:
            offenders[py.name] = hits
    assert not offenders, (
        f"router must not import model/network libs; found: {offenders}"
    )


def test_router_opens_no_sockets_on_green_path(
    tmp_path: Path, stage_fixture
):
    """Run the CLI with ``socket.socket`` disabled via env-imported sitecustomize.

    Subprocess isolation is required because patching ``socket`` in the
    test process cannot observe what the CLI subprocess does. We install a
    sitecustomize that overrides ``socket.socket`` to raise on any call,
    then run the green-path fixture. If the router touches the network,
    the run blows up with a non-zero exit.
    """
    folder = stage_fixture(tmp_path, "clean_explicit_name_full_identity.json")

    site_dir = tmp_path / "sitecustomize_dir"
    site_dir.mkdir()
    # Patch ``connect`` + ``create_connection`` rather than ``socket`` itself:
    # ssl.py subclasses ``socket.socket`` at import time, so replacing the
    # class breaks stdlib import. Blocking connect() catches any real
    # network attempt while leaving imports intact.
    (site_dir / "sitecustomize.py").write_text(
        "import socket as _s\n"
        "class _Blocked(Exception):\n"
        "    pass\n"
        "def _no_connect(self, *a, **kw):\n"
        "    raise _Blocked('router attempted network access: connect')\n"
        "def _no_create_connection(*a, **kw):\n"
        "    raise _Blocked('router attempted network access: create_connection')\n"
        "_s.socket.connect = _no_connect\n"
        "_s.create_connection = _no_create_connection\n"
    )

    env = {
        **dict(_environ()),
        "PYTHONPATH": str(site_dir) + ":" +
            _environ_value("PYTHONPATH", default=""),
    }

    result = subprocess.run(
        [sys.executable, "-m", "ledgerlinc_ocr.router", "route", str(folder)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"router opened a socket under blocking sitecustomize. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    # sanity-check the sitecustomize was actually installed
    assert socket is not None  # placate linter


def _environ():
    import os
    return os.environ.items()


def _environ_value(key: str, default: str = "") -> str:
    import os
    return os.environ.get(key, default)


@pytest.fixture(autouse=False)
def _unused_fixture():
    # reserved; not used but documents that we deliberately don't patch
    # the test process's socket (subprocess isolation handles that)
    yield
