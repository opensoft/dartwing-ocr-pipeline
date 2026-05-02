"""Pipeline version string assembly (FR-004, FR-008, research R-007)."""

from __future__ import annotations

import hashlib
from importlib import metadata
from pathlib import Path

DPI = 300
CONTRACT_SET_VERSION = "1.2.0"
SEMVER = "v0.2.0"
SLICE_PREFIX = "stage1-preprocess"


def build_pipeline_version(
    semver: str = SEMVER,
    paddleocr_version: str | None = None,
    weights_hash7: str | None = None,
    dpi: int = DPI,
) -> str:
    if paddleocr_version is None:
        paddleocr_version = metadata.version("paddleocr")
    if weights_hash7 is None:
        weights_hash7 = "0000000"
    return f"{SLICE_PREFIX}-{semver}+paddleocr{paddleocr_version}.{weights_hash7}.dpi{dpi}"


def hash_weights(weight_paths: list[Path]) -> str:
    """Return the first 7 hex chars of a stable hash over the given weight files."""
    digest = hashlib.sha256()
    for p in sorted(weight_paths, key=lambda x: str(x)):
        digest.update(str(p).encode("utf-8"))
        digest.update(b"\0")
        with p.open("rb") as f:
            while chunk := f.read(1 << 20):
                digest.update(chunk)
    return digest.hexdigest()[:7]
