"""Build the `pipeline_version` string per research.md §R-009.

Format: `"{package_version}+{short_sha}"`. The short SHA is read from
`ledgerlinc_ocr._build_sha` when that module is present (populated at package
build time); falls back to the literal `"unknown"` otherwise.

Deterministic within a process: repeated calls return the same string.
"""

from __future__ import annotations

import importlib
from importlib.metadata import PackageNotFoundError, version as _dist_version


def _package_version() -> str:
    try:
        return _dist_version("ledgerlinc-ocr")
    except PackageNotFoundError:
        return "unknown"


def _short_sha() -> str:
    try:
        module = importlib.import_module("ledgerlinc_ocr._build_sha")
    except ImportError:
        return "unknown"
    sha = getattr(module, "SHA", None)
    if not isinstance(sha, str) or not sha:
        return "unknown"
    return sha


def build_pipeline_version() -> str:
    return f"{_package_version()}+{_short_sha()}"
