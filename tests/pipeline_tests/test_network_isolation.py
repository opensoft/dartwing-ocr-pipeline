"""T047a: with non-loopback sockets refused, a stub-stage run still succeeds."""
from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from typing import Callable

import pytest

from ledgerlinc_ocr.pipeline.cli import main


def _loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host in {"localhost", "", None}


def test_no_nonloopback_network_traffic(
    tmp_document_folder: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
):
    original_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else str(address)
        if not _loopback(host):
            raise AssertionError(
                f"Pipeline attempted non-loopback connection to {host}"
            )
        return original_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    folder = tmp_document_folder(1, "easy")
    code = main(["run", "--document-folder", str(folder)])
    assert code == 0
