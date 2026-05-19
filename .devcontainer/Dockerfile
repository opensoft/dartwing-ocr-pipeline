FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    jq \
    libgomp1 \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Feature 021 / FR-002: install mikefarah/yq v4 (Go binary) so the
# Ollama readiness helper (`scripts/check-ollama-gpu-readiness.sh`) can
# parse the YAML voter config. The apt-packaged `yq` on Debian is the
# Python wrapper variant; we want the Go binary that matches the
# workstation host's yq for consistent parsing semantics.
RUN curl -fsSL https://github.com/mikefarah/yq/releases/download/v4.44.3/yq_linux_amd64 \
    -o /usr/local/bin/yq \
    && chmod 0755 /usr/local/bin/yq \
    && yq --version

# Speckit worktree helpers (ct, cta, ctc, ctg, cts, ctp, ctlist). ~/.zshrc
# auto-sources /usr/local/share/ct/ct-functions.zsh on interactive shell start.
COPY .devcontainer/ct-functions.zsh /usr/local/share/ct/ct-functions.zsh
RUN chmod 0644 /usr/local/share/ct/ct-functions.zsh
