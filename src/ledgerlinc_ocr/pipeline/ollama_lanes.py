"""Per-lane Ollama URL resolution (gpu / cpu / jetson).

Spec FR-015 / FR-016 / FR-017 / FR-018. Research R-012.

Resolution order for each lane: flag > env var > documented default. URLs
themselves are not validated here -- malformed URLs surface as connection
errors at extract-stage time, with stage/profile context per FR-031.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

GPU_DEFAULT_URL = "http://localhost:11434"
CPU_DEFAULT_URL = "http://localhost:11435"
JETSON_DEFAULT_URL = "http://jetson.local:11434"

GPU_ENV_VAR = "OLLAMA_BASE_URL"
CPU_ENV_VAR = "OLLAMA_CPU_BASE_URL"
JETSON_ENV_VAR = "OLLAMA_JETSON_BASE_URL"


@dataclass(frozen=True)
class OllamaLaneEndpoints:
    gpu_url: str
    cpu_url: str
    jetson_url: str

    def for_lane(self, lane: str) -> str:
        if lane == "gpu":
            return self.gpu_url
        if lane == "cpu":
            return self.cpu_url
        if lane == "jetson":
            return self.jetson_url
        raise ValueError(
            f"unknown extract lane {lane!r}; expected one of gpu/cpu/jetson"
        )


def _resolve(flag: str | None, env_name: str, default: str) -> str:
    if flag is not None:
        return flag
    env = os.environ.get(env_name)
    if env:
        return env
    return default


def resolve_endpoints(
    *,
    gpu_flag: str | None,
    cpu_flag: str | None,
    jetson_flag: str | None,
) -> OllamaLaneEndpoints:
    """Compose lane URLs from flag > env > default for each of gpu/cpu/jetson."""
    return OllamaLaneEndpoints(
        gpu_url=_resolve(gpu_flag, GPU_ENV_VAR, GPU_DEFAULT_URL),
        cpu_url=_resolve(cpu_flag, CPU_ENV_VAR, CPU_DEFAULT_URL),
        jetson_url=_resolve(jetson_flag, JETSON_ENV_VAR, JETSON_DEFAULT_URL),
    )


__all__ = [
    "CPU_DEFAULT_URL",
    "CPU_ENV_VAR",
    "GPU_DEFAULT_URL",
    "GPU_ENV_VAR",
    "JETSON_DEFAULT_URL",
    "JETSON_ENV_VAR",
    "OllamaLaneEndpoints",
    "resolve_endpoints",
]
