#!/usr/bin/env bash
set -euo pipefail

# Starts the workstation WSL host Ollama service with the AMD ROCm/ROCDXG
# environment required for this gfx1151 workstation. Do not replace this with
# plain `ollama serve`; that path can hang during ROCm runner initialization.

OLLAMA_BIN="${OLLAMA_BIN:-/usr/bin/ollama}"
ROCM_ROOT="${ROCM_ROOT:-/opt/rocm-7.2.0}"
OLLAMA_HOST_VALUE="${OLLAMA_HOST:-0.0.0.0:11434}"
OLLAMA_LOG="${OLLAMA_LOG:-/tmp/ollama-host-rocm-fixed.log}"
STOP_EXISTING="${STOP_EXISTING:-1}"

HSA_RUNTIME="${ROCM_ROOT}/lib/libhsa-runtime64.so.1"
ROCM_LIB="${ROCM_ROOT}/lib"

if [[ ! -x "${OLLAMA_BIN}" ]]; then
  echo "ERROR: Ollama binary is not executable: ${OLLAMA_BIN}" >&2
  exit 1
fi

if [[ ! -r "${HSA_RUNTIME}" ]]; then
  echo "ERROR: ROCm HSA runtime not found: ${HSA_RUNTIME}" >&2
  exit 1
fi

if [[ ! -d "${ROCM_LIB}" ]]; then
  echo "ERROR: ROCm library directory not found: ${ROCM_LIB}" >&2
  exit 1
fi

if [[ "${STOP_EXISTING}" == "1" ]]; then
  pkill -TERM -x ollama 2>/dev/null || true
  sleep 1
  pkill -KILL -x ollama 2>/dev/null || true
  sleep 1
fi

rm -f "${OLLAMA_LOG}"

setsid -f env \
  OLLAMA_HOST="${OLLAMA_HOST_VALUE}" \
  OLLAMA_DEBUG="${OLLAMA_DEBUG:-1}" \
  HSA_ENABLE_DXG_DETECTION=1 \
  HSA_ENABLE_SDMA=0 \
  ROCM_PATH="${ROCM_ROOT}" \
  HIP_PATH="${ROCM_ROOT}" \
  LD_PRELOAD="${HSA_RUNTIME}" \
  LD_LIBRARY_PATH="${ROCM_LIB}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}" \
  "${OLLAMA_BIN}" serve >"${OLLAMA_LOG}" 2>&1

for _ in $(seq 1 40); do
  if curl -fsS --connect-timeout 1 --max-time 2 "http://127.0.0.1:11434/api/version" >/dev/null 2>&1; then
    echo "host Ollama ROCm service started"
    pgrep -af "^${OLLAMA_BIN} serve$" || true
    echo "host URL: http://127.0.0.1:11434"
    echo "container URL: set OLLAMA_BASE_URL to the reachable host/relay URL"
    echo "log: ${OLLAMA_LOG}"
    exit 0
  fi
  sleep 0.5
done

echo "ERROR: Ollama did not become ready on http://127.0.0.1:11434" >&2
tail -n 120 "${OLLAMA_LOG}" >&2 || true
exit 1
