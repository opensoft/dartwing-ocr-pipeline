#!/usr/bin/env bash
# Start the devcontainer compose stack with OLLAMA_BASE_URL pointed at
# the current WSL host IP, matching what VS Code's initializeCommand does
# in .devcontainer/devcontainer.json.
#
# Use this when starting the stack manually (without VS Code Dev Containers).
# It resolves the WSL distro's eth0 address at run time so the pipeline
# container reaches host Ollama directly, bypassing Docker Desktop's
# host-gateway routing — see docs/stage1-vendor-identity/ollama-runtime.md.
#
# Usage:
#   scripts/devcontainer-up.sh              # up -d pipeline-dev
#   scripts/devcontainer-up.sh --profile ollama up -d  # include container Ollama

set -euo pipefail

cd "$(dirname "$0")/.."

WSL_HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [[ -z "${WSL_HOST_IP}" ]]; then
  echo "error: could not resolve WSL host IP via 'hostname -I'" >&2
  echo "       fall back to host.docker.internal by unsetting WSL_HOST_IP and exporting" >&2
  echo "       OLLAMA_BASE_URL yourself if needed." >&2
  exit 1
fi

export WSL_HOST_IP
echo "Using WSL_HOST_IP=${WSL_HOST_IP}" >&2

# Persist to .devcontainer/.env so subsequent `docker compose up` from the
# same directory (e.g., VS Code Dev Containers re-attach) picks it up.
echo "WSL_HOST_IP=${WSL_HOST_IP}" > .devcontainer/.env

# If the caller passed arguments (e.g., "--profile ollama up -d"), use them
# verbatim. Otherwise default to "up -d" on pipeline-dev only.
if [[ $# -eq 0 ]]; then
  exec docker compose -f .devcontainer/docker-compose.yml up -d pipeline-dev
else
  exec docker compose -f .devcontainer/docker-compose.yml "$@"
fi
