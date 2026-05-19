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
#
# Integrity check (SonarCloud security hotspot fix for PR #43):
# the binary is verified against its SHA-256 BEFORE chmod-execute so a
# tampered download fails the build instead of landing as an unverified
# binary. Hash for `yq_linux_amd64` at v4.44.3 is computed once at pin
# time and pinned here; if you bump the version, recompute via
# `curl -fsSL <new-url> | sha256sum`.
ARG YQ_VERSION=v4.44.3
ARG YQ_SHA256=a2c097180dd884a8d50c956ee16a9cec070f30a7947cf4ebf87d5f36213e9ed7
RUN curl -fsSL "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64" \
    -o /usr/local/bin/yq \
    && echo "${YQ_SHA256}  /usr/local/bin/yq" | sha256sum -c - \
    && chmod 0755 /usr/local/bin/yq \
    && yq --version

# Speckit worktree helpers (ct, cta, ctc, ctg, cts, ctp, ctlist). ~/.zshrc
# auto-sources /usr/local/share/ct/ct-functions.zsh on interactive shell start.
COPY .devcontainer/ct-functions.zsh /usr/local/share/ct/ct-functions.zsh
RUN chmod 0644 /usr/local/share/ct/ct-functions.zsh
