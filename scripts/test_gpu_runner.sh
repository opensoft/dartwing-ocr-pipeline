#!/usr/bin/env bash
export PYTHONPATH=src
export ROCM_ROOT="/opt/rocm-7.2.0"
export ROCM_PATH="$ROCM_ROOT"
export HIP_PATH="$ROCM_ROOT"
export LD_PRELOAD="$ROCM_ROOT/lib/libhsa-runtime64.so.1"
export LD_LIBRARY_PATH="$ROCM_ROOT/lib:$ROCM_ROOT/lib/llvm/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export HSA_ENABLE_DXG_DETECTION=1
export HSA_ENABLE_SDMA=0
export MIOPEN_FIND_MODE="${MIOPEN_FIND_MODE:-2}"
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

# Run the command passed as arguments, e.g. -m pytest -m gpu
.venv-paddle-rocm/bin/python "$@"
