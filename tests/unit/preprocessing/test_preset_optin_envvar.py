"""Feature 017: precedence + literal-value tests for the preset opt-in
helpers ``resolve_module_set_value`` / ``resolve_det_rec_variant_value``.

CPU-safe: imports only ``preprocessing.preset_optin``, which has zero GPU
dependencies (no paddle, no MIOpen, no numpy, no PIL, no pypdfium2).

Contracts exercised:
- research R-017.1: env-var literal-value handling (no strip, no case fold)
- contracts/cli-contract.md §1: CLI > env > unset precedence
- empty-string env value treated as unset (matches feature 016 warmup_optin)
"""
from __future__ import annotations

import pytest

from dartwing_ocr.preprocessing.preset_optin import (
    DET_REC_VARIANT_ENV_VAR,
    MODULE_SET_ENV_VAR,
    resolve_det_rec_variant_value,
    resolve_module_set_value,
)


@pytest.mark.parametrize(
    "resolver, env_var",
    [
        (resolve_module_set_value, MODULE_SET_ENV_VAR),
        (resolve_det_rec_variant_value, DET_REC_VARIANT_ENV_VAR),
    ],
)
class TestPrecedence:
    """CLI > env > unset precedence per cli-contract.md §1."""

    def test_cli_wins_over_env_when_both_set(self, resolver, env_var) -> None:
        result = resolver("legacy", env={env_var: "reduced-v1"})
        assert result == "legacy"

    def test_env_used_when_cli_is_none(self, resolver, env_var) -> None:
        result = resolver(None, env={env_var: "reduced-v1"})
        assert result == "reduced-v1"

    def test_env_used_when_cli_is_empty_string(self, resolver, env_var) -> None:
        result = resolver("", env={env_var: "reduced-v1"})
        assert result == "reduced-v1"

    def test_returns_none_when_neither_set(self, resolver, env_var) -> None:
        result = resolver(None, env={})
        assert result is None

    def test_empty_env_value_treated_as_unset(self, resolver, env_var) -> None:
        result = resolver(None, env={env_var: ""})
        assert result is None


@pytest.mark.parametrize(
    "resolver, env_var",
    [
        (resolve_module_set_value, MODULE_SET_ENV_VAR),
        (resolve_det_rec_variant_value, DET_REC_VARIANT_ENV_VAR),
    ],
)
class TestVerbatimEnvHandling:
    """R-017.1: env values are passed verbatim — no .strip(), no case fold.
    The fail-fast `UnknownPresetError` validator at the registry boundary
    is what catches typos; the resolver must NOT silently normalize."""

    def test_no_strip_on_surrounding_whitespace(self, resolver, env_var) -> None:
        result = resolver(None, env={env_var: "  legacy  "})
        assert result == "  legacy  "

    def test_no_case_normalization(self, resolver, env_var) -> None:
        result = resolver(None, env={env_var: "Legacy"})
        assert result == "Legacy"

    def test_unknown_value_returned_verbatim(self, resolver, env_var) -> None:
        result = resolver(None, env={env_var: "totally-bogus"})
        assert result == "totally-bogus"


@pytest.mark.parametrize(
    "resolver, env_var",
    [
        (resolve_module_set_value, MODULE_SET_ENV_VAR),
        (resolve_det_rec_variant_value, DET_REC_VARIANT_ENV_VAR),
    ],
)
class TestEnvIsolation:
    """The ``env`` parameter, when provided, fully overrides ``os.environ``
    for the resolver's read — no fallback to the real process env. Lets
    tests run hermetically without monkeypatching."""

    def test_explicit_empty_env_does_not_leak_os_environ(
        self,
        resolver,
        env_var,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(env_var, "should-not-be-read")
        result = resolver(None, env={})
        assert result is None

    def test_explicit_env_takes_precedence_over_os_environ(
        self,
        resolver,
        env_var,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(env_var, "from-os-environ")
        result = resolver(None, env={env_var: "from-explicit-env"})
        assert result == "from-explicit-env"


def test_module_set_and_det_rec_use_separate_env_vars() -> None:
    """Setting one env var must not bleed into the other resolver's read."""
    env = {MODULE_SET_ENV_VAR: "reduced-v1"}
    assert resolve_module_set_value(None, env=env) == "reduced-v1"
    assert resolve_det_rec_variant_value(None, env=env) is None

    env = {DET_REC_VARIANT_ENV_VAR: "ppocrv5-mobile"}
    assert resolve_det_rec_variant_value(None, env=env) == "ppocrv5-mobile"
    assert resolve_module_set_value(None, env=env) is None
