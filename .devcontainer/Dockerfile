FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libgomp1 \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Speckit worktree helpers (ct, cta, ctc, ctg, cts, ctp, ctlist). ~/.zshrc
# auto-sources /usr/local/share/ct/ct-functions.zsh on interactive shell start.
COPY .devcontainer/ct-functions.zsh /usr/local/share/ct/ct-functions.zsh
RUN chmod 0644 /usr/local/share/ct/ct-functions.zsh
