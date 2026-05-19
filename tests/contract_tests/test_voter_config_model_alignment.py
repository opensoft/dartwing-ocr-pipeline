"""Feature 021 follow-up: voter-config alignment contract test.

Resolves multi-agent-review P1-1. The Ollama readiness helper
(``scripts/check-ollama-gpu-readiness.sh``) reads ``model_name`` from
``configs/voter/ollama-gpu.yaml`` and asserts that named model is fully
GPU-placed. The canonical demo command's ``--extract-profile ollama@gpu``
binds an extraction voter via ``stages._ollama_extract_factory`` →
``load_voter_config("gemma-edge")`` → reads
``src/dartwing_ocr/extract/voters/configs/gemma-edge.yaml`` and uses its
``ollama.model_tag``.

If these two model identifiers drift apart, readiness can PASS for one
model while the extractor binds a different one — a silent class of
demo failure where the GPU gate gives the green light but the run still
hits an unloaded / CPU-bound model.

This test asserts the two values agree exactly. If the canonical demo
command ever switches to a different voter config (e.g.,
``ollama@gpu`` rewires to a new ``*-edge.yaml``), update both files in
the same commit; this test will catch the drift on CI before merge.

Runs under ``pytest -m 'not gpu'`` (CPU-safe; no Paddle, no Ollama).
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
READINESS_VOTER_CONFIG = REPO_ROOT / "configs" / "voter" / "ollama-gpu.yaml"
EXTRACTOR_VOTER_CONFIG = (
    REPO_ROOT
    / "src"
    / "dartwing_ocr"
    / "extract"
    / "voters"
    / "configs"
    / "gemma-edge.yaml"
)


def _load_yaml(path: Path) -> dict:
    """Load a YAML file and assert its root is a mapping.

    PR #43 Copilot review: `yaml.safe_load(...)` can legally return a
    non-mapping (list, string, scalar) for valid-but-not-a-mapping YAML
    input. Both voter-config schemas this contract test loads
    (`configs/voter/ollama-gpu.yaml`, `gemma-edge.yaml`) require a
    top-level mapping; rejecting non-mapping input here keeps the
    failure trace actionable instead of erroring downstream with
    `AttributeError: 'list' object has no attribute 'get'`.
    """
    assert path.is_file(), f"required voter config not found: {path}"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        # Empty file is treated as an empty mapping for the alignment
        # check; downstream key lookups will fail with the actionable
        # "missing top-level key" message rather than an AttributeError.
        return {}
    assert isinstance(loaded, dict), (
        f"{path}: expected a YAML mapping at the document root; got "
        f"{type(loaded).__name__} ({loaded!r:.120}). Voter configs MUST "
        f"be a mapping per feature-005 schema."
    )
    return loaded


def test_readiness_helper_voter_config_present() -> None:
    """The readiness helper's voter config exists and parses."""
    data = _load_yaml(READINESS_VOTER_CONFIG)
    assert "model_name" in data, (
        f"{READINESS_VOTER_CONFIG} missing top-level `model_name` key; "
        f"required by `scripts/check-ollama-gpu-readiness.sh`."
    )
    assert isinstance(data["model_name"], str) and data["model_name"], (
        f"{READINESS_VOTER_CONFIG} `model_name` must be a non-empty string; "
        f"got {data['model_name']!r}."
    )


def test_extractor_voter_config_present() -> None:
    """The gemma-edge extractor config exists and exposes `ollama.model_tag`."""
    data = _load_yaml(EXTRACTOR_VOTER_CONFIG)
    ollama_section = data.get("ollama")
    # PR #43 Copilot review (commit b1b032f): `data.get("ollama") or {}`
    # masked the case where `ollama` is present but a non-mapping
    # (e.g., string/list), which would later raise `TypeError` /
    # `KeyError` on `extractor["ollama"]["model_tag"]` instead of a
    # named-cause assertion failure. Assert the section is a mapping
    # AND contains the required key with a non-empty string value.
    assert isinstance(ollama_section, dict), (
        f"{EXTRACTOR_VOTER_CONFIG}: `ollama` section must be a YAML "
        f"mapping; got {type(ollama_section).__name__}. The "
        f"`ollama@gpu` extraction profile expects `ollama.model_tag`."
    )
    assert "model_tag" in ollama_section, (
        f"{EXTRACTOR_VOTER_CONFIG} missing `ollama.model_tag`; the "
        f"`ollama@gpu` extraction profile relies on this field via "
        f"`stages._ollama_extract_factory`."
    )
    model_tag = ollama_section["model_tag"]
    assert isinstance(model_tag, str) and model_tag, (
        f"{EXTRACTOR_VOTER_CONFIG} `ollama.model_tag` must be a non-empty "
        f"string; got {model_tag!r} ({type(model_tag).__name__})."
    )


def test_readiness_and_extractor_agree_on_model_tag() -> None:
    """P1-1 contract: the readiness helper's `model_name` MUST equal the
    extractor's `ollama.model_tag` so the readiness gate validates the
    same model the demo command actually binds."""
    readiness = _load_yaml(READINESS_VOTER_CONFIG)
    extractor = _load_yaml(EXTRACTOR_VOTER_CONFIG)

    # PR #43 Copilot review: re-assert the `ollama` section is a mapping
    # before indexing into it — even though `test_extractor_voter_config_present`
    # asserts the same thing, tests can run in any order and depend on each
    # other's preconditions only via shared fixtures. Inline assertion
    # keeps this test's failure mode actionable on its own.
    extractor_ollama = extractor.get("ollama")
    assert isinstance(extractor_ollama, dict), (
        f"{EXTRACTOR_VOTER_CONFIG}: `ollama` section must be a mapping; "
        f"got {type(extractor_ollama).__name__}."
    )
    readiness_model = readiness["model_name"]
    extractor_model = extractor_ollama["model_tag"]

    assert readiness_model == extractor_model, (
        f"Voter-config model drift (P1-1):\n"
        f"  Readiness helper ({READINESS_VOTER_CONFIG.relative_to(REPO_ROOT)}): "
        f"model_name = {readiness_model!r}\n"
        f"  Extractor ({EXTRACTOR_VOTER_CONFIG.relative_to(REPO_ROOT)}): "
        f"ollama.model_tag = {extractor_model!r}\n"
        f"These MUST match. The readiness gate checks one model; the "
        f"`ollama@gpu` profile binds another. Update both in lockstep."
    )
