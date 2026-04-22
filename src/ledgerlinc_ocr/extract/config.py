"""Voter configuration loader and typed model.

Shapes mirror `contracts/voter-config.md`. Every sub-model configures
`extra = "forbid"` so typos and stray keys fail at load time with exit code 6.
"""

from __future__ import annotations

import os
from importlib import resources
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .errors import VoterConfigInvalid

_PACKAGED_CONFIGS = ("ledgerlinc_ocr.extract.voters", "configs")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OllamaCallConfig(_StrictModel):
    model_tag: str = Field(min_length=1)
    timeout_seconds: float = Field(default=180.0, gt=0)
    connect_timeout_seconds: float = Field(default=10.0, gt=0)


class SamplingConfig(_StrictModel):
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    seed: int | None = 42
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, gt=0)


class PromptConfig(_StrictModel):
    template_path: str = Field(min_length=1)
    max_output_tokens: int = Field(default=2048, gt=0)
    format: Literal["json"] | None = "json"


class ReconciliationConfig(_StrictModel):
    ungrounded_confidence_cap: float = Field(default=0.30, ge=0.0, le=1.0)


class ModelRuntimeConfig(_StrictModel):
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    runtime: str = Field(min_length=1)


class VoterConfig(_StrictModel):
    voter_id: str = Field(min_length=1)
    voter_role: Literal["primary_extractor", "secondary_extractor", "verifier"]
    consensus_mode: Literal["single_voter_baseline"]
    model_runtime: ModelRuntimeConfig
    ollama: OllamaCallConfig
    sampling: SamplingConfig
    prompt: PromptConfig
    reconciliation: ReconciliationConfig


def _read_yaml(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (strict_payload, extensions) where `extensions` contains keys
    prefixed with `x_` that are stripped before pydantic validation."""

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise VoterConfigInvalid(
            f"could not read voter config: {path}",
            detail={"path": str(path), "os_error": str(exc)},
        ) from exc

    try:
        loaded = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise VoterConfigInvalid(
            f"voter config is not valid YAML: {path}",
            detail={"path": str(path), "yaml_error": str(exc)},
        ) from exc

    if not isinstance(loaded, dict):
        raise VoterConfigInvalid(
            f"voter config must be a YAML mapping, got {type(loaded).__name__}: {path}",
            detail={"path": str(path)},
        )

    extensions = {k: v for k, v in loaded.items() if k.startswith("x_")}
    strict = {k: v for k, v in loaded.items() if not k.startswith("x_")}
    return strict, extensions


def _resolve(name_or_path: str, base_dir: Path | None) -> Path:
    # 1. Path-like: caller passed `--voter-config <path>` or an absolute/relative path.
    if any(sep in name_or_path for sep in ("/", "\\", os.sep)) or name_or_path.endswith(".yaml"):
        candidate = Path(name_or_path)
        if not candidate.is_absolute() and base_dir is not None:
            candidate = (base_dir / candidate).resolve()
        if candidate.exists():
            return candidate
        raise VoterConfigInvalid(
            f"voter config path does not exist: {candidate}",
            detail={"path": str(candidate)},
        )

    # 2. Name: look in $LEDGERLINC_VOTER_CONFIG_DIR first.
    override_dir = os.environ.get("LEDGERLINC_VOTER_CONFIG_DIR")
    if override_dir:
        candidate = Path(override_dir).expanduser() / f"{name_or_path}.yaml"
        if candidate.exists():
            return candidate

    # 3. Packaged default.
    package, subdir = _PACKAGED_CONFIGS
    try:
        resource = resources.files(package).joinpath(subdir, f"{name_or_path}.yaml")
    except ModuleNotFoundError as exc:
        raise VoterConfigInvalid(
            f"packaged voter configs not available: {package}.{subdir}",
            detail={"name": name_or_path},
        ) from exc

    if resource.is_file():
        # Resolve to a filesystem path (works for editable installs; will copy to a
        # temp path for zip-installed wheels via `as_file`).
        with resources.as_file(resource) as path:
            return Path(path)

    raise VoterConfigInvalid(
        f"no voter config found for name {name_or_path!r}",
        detail={
            "searched": [
                override_dir or "$LEDGERLINC_VOTER_CONFIG_DIR (unset)",
                f"packaged: {package}.{subdir}/{name_or_path}.yaml",
            ],
        },
    )


def load_voter_config(
    name_or_path: str,
    base_dir: Path | None = None,
) -> tuple[VoterConfig, Path, dict[str, Any]]:
    """Resolve + load + validate a voter config.

    Returns a triple of `(config, config_path, extensions)` where `extensions`
    carries the `x_*` escape-hatch keys (used by the stub voter fixture-path
    override — see contracts/voter-config.md §Stub voter).
    """

    path = _resolve(name_or_path, base_dir)
    strict, extensions = _read_yaml(path)

    try:
        config = VoterConfig.model_validate(strict)
    except ValidationError as exc:
        raise VoterConfigInvalid(
            f"voter config failed validation: {path}",
            detail={"path": str(path), "errors": exc.errors()},
        ) from exc

    return config, path, extensions
