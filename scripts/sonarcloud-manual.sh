#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SECRETS_FILE="${SONARQUBE_ENV_FILE:-$HOME/.config/ledgerlinc/secrets/sonar.env}"
if [[ -f "$SECRETS_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$SECRETS_FILE"
    set +a
fi

if [[ -z "${SONAR_TOKEN:-}" && -n "${SONARQUBE_TOKEN:-}" ]]; then
    export SONAR_TOKEN="$SONARQUBE_TOKEN"
fi

if [[ -z "${SONAR_HOST_URL:-}" && -n "${SONARQUBE_URL:-}" ]]; then
    export SONAR_HOST_URL="$SONARQUBE_URL"
fi

export SONAR_HOST_URL="${SONAR_HOST_URL:-https://sonarcloud.io}"
export SONAR_USER_HOME="${SONAR_USER_HOME:-$HOME/.cache/sonar}"

if [[ -z "${SONAR_TOKEN:-}" ]]; then
    echo "Missing SONAR_TOKEN or SONARQUBE_TOKEN." >&2
    echo "Put it in $SECRETS_FILE or export it before running this script." >&2
    exit 2
fi

if ! command -v sonar-scanner >/dev/null 2>&1; then
    echo "sonar-scanner is not on PATH. Rebuild/reopen the devBench base image first." >&2
    exit 2
fi

PYTHON_BIN="${PYTHON:-python3}"

if [[ "${SONAR_SKIP_TESTS:-0}" != "1" ]]; then
    if ! "$PYTHON_BIN" -c 'import coverage, pytest_cov' >/dev/null 2>&1; then
        echo "coverage and pytest-cov are required. Rebuild/reopen pyBench or install the project dev extra." >&2
        exit 2
    fi

    IFS=' ' read -r -a pytest_targets <<< "${SONAR_PYTEST_TARGETS:-tests/contract_tests tests/pipeline_tests tests/unit tests/integration tests/evaluator_tests}"
    "$PYTHON_BIN" -m pytest \
        "${pytest_targets[@]}" \
        --cov=src/ledgerlinc_ocr \
        --cov-config=.coveragerc \
        --cov-report=term-missing \
        --cov-report=xml:coverage.xml
elif [[ ! -f coverage.xml ]]; then
    echo "SONAR_SKIP_TESTS=1 was set, but coverage.xml does not exist." >&2
    exit 2
fi

sonar-scanner "$@"
