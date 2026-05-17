"""T017: pipeline_version format, fallback, and intra-process stability."""

from __future__ import annotations

import re
import sys

from dartwing_ocr.extract import version as version_mod


def test_format_is_package_plus_sha() -> None:
    result = version_mod.build_pipeline_version()
    assert re.match(r"^\S+\+\S+$", result), result


def test_short_sha_falls_back_to_unknown(monkeypatch) -> None:
    sys.modules.pop("dartwing_ocr._build_sha", None)

    original_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "dartwing_ocr._build_sha":
            raise ImportError(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    result = version_mod.build_pipeline_version()
    assert result.endswith("+unknown"), result


def test_two_calls_are_byte_identical() -> None:
    first = version_mod.build_pipeline_version()
    second = version_mod.build_pipeline_version()
    assert first == second
