# SonarCloud Manual Analysis

Run manual SonarCloud analysis from the `pyBench` container after rebuilding the
shared `dev-bench-base` image and the `pyBench` layer.

The shared devBench base owns generic Sonar tools:

- `sonar-scanner` for project analysis.
- `sonar` for the SonarQube CLI beta workflows such as issue lookup, secrets
  scanning, and agent-oriented commands.

The `pyBench` layer owns Python-only coverage tooling:

- `coverage`
- `pytest-cov`
- `pysonar`

Store tokens outside the mounted `.codex` folder:

```bash
mkdir -p ~/.config/ledgerlinc/secrets
chmod 700 ~/.config/ledgerlinc/secrets
cat > ~/.config/ledgerlinc/secrets/sonar.env <<'EOF'
SONARQUBE_TOKEN=replace-me
SONARQUBE_ORG=opensoft
EOF
chmod 600 ~/.config/ledgerlinc/secrets/sonar.env
```

Run the manual analysis:

```bash
scripts/sonarcloud-manual.sh
```

The wrapper runs pytest with coverage first, writes `coverage.xml`, then invokes
`sonar-scanner` using `sonar-project.properties`.

Useful overrides:

```bash
SONAR_PYTEST_TARGETS="tests/unit tests/contract_tests" scripts/sonarcloud-manual.sh
SONAR_SKIP_TESTS=1 scripts/sonarcloud-manual.sh
scripts/sonarcloud-manual.sh -Dsonar.branch.name=my-branch
```
