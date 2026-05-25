"""Pipeline-version discovery for the DemoRunReport (R-023.2)."""

from __future__ import annotations

import importlib.metadata


def get_pipeline_version() -> str:
    """Return the installed dartwing-ocr package version, or ``"unknown"``."""
    try:
        return importlib.metadata.version("dartwing-ocr")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"
