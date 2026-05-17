"""Unit tests for Ollama lane URL resolution.

Covers Spec FR-015 / FR-016 / FR-017; Research R-012.
"""
from __future__ import annotations

import pytest

from dartwing_ocr.pipeline.ollama_lanes import (
    CPU_DEFAULT_URL,
    CPU_ENV_VAR,
    GPU_DEFAULT_URL,
    GPU_ENV_VAR,
    JETSON_DEFAULT_URL,
    JETSON_ENV_VAR,
    OllamaLaneEndpoints,
    resolve_endpoints,
)


def test_defaults_when_no_flag_no_env(monkeypatch: pytest.MonkeyPatch):
    for var in (GPU_ENV_VAR, CPU_ENV_VAR, JETSON_ENV_VAR):
        monkeypatch.delenv(var, raising=False)
    eps = resolve_endpoints(gpu_flag=None, cpu_flag=None, jetson_flag=None)
    assert eps.gpu_url == GPU_DEFAULT_URL
    assert eps.cpu_url == CPU_DEFAULT_URL
    assert eps.jetson_url == JETSON_DEFAULT_URL


def test_env_var_used_when_no_flag(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GPU_ENV_VAR, "http://gpu.test:11434")
    monkeypatch.setenv(CPU_ENV_VAR, "http://cpu.test:11435")
    monkeypatch.setenv(JETSON_ENV_VAR, "http://jet.test:11434")
    eps = resolve_endpoints(gpu_flag=None, cpu_flag=None, jetson_flag=None)
    assert eps.gpu_url == "http://gpu.test:11434"
    assert eps.cpu_url == "http://cpu.test:11435"
    assert eps.jetson_url == "http://jet.test:11434"


def test_flag_beats_env_for_each_lane(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(GPU_ENV_VAR, "http://gpu.env:11434")
    monkeypatch.setenv(CPU_ENV_VAR, "http://cpu.env:11435")
    monkeypatch.setenv(JETSON_ENV_VAR, "http://jet.env:11434")
    eps = resolve_endpoints(
        gpu_flag="http://gpu.flag:11434",
        cpu_flag="http://cpu.flag:11435",
        jetson_flag="http://jet.flag:11434",
    )
    assert eps.gpu_url == "http://gpu.flag:11434"
    assert eps.cpu_url == "http://cpu.flag:11435"
    assert eps.jetson_url == "http://jet.flag:11434"


def test_for_lane_dispatch():
    eps = OllamaLaneEndpoints(
        gpu_url="http://gpu",
        cpu_url="http://cpu",
        jetson_url="http://jet",
    )
    assert eps.for_lane("gpu") == "http://gpu"
    assert eps.for_lane("cpu") == "http://cpu"
    assert eps.for_lane("jetson") == "http://jet"


def test_for_lane_rejects_unknown_lane():
    eps = OllamaLaneEndpoints(
        gpu_url="http://gpu",
        cpu_url="http://cpu",
        jetson_url="http://jet",
    )
    with pytest.raises(ValueError, match="unknown extract lane"):
        eps.for_lane("workstation")


def test_default_url_constants_match_research_r_012():
    assert GPU_DEFAULT_URL == "http://localhost:11434"
    assert CPU_DEFAULT_URL == "http://localhost:11435"
    assert JETSON_DEFAULT_URL == "http://jetson.local:11434"


def test_env_var_names_match_research_r_012():
    assert GPU_ENV_VAR == "OLLAMA_BASE_URL"
    assert CPU_ENV_VAR == "OLLAMA_CPU_BASE_URL"
    assert JETSON_ENV_VAR == "OLLAMA_JETSON_BASE_URL"
