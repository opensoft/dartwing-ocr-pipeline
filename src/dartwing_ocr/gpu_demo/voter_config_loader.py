"""Voter-config discovery + loading for the GPU MVP demo (T013, FR-005).

Honors the ``--voter-config`` CLI override; falls back to the feature 005 /
021 auto-discovery path. On error, raises one of the three named exceptions
below — the orchestrator maps all three to exit code 2 (invalid input/usage).
The multi-voter case is handled via the ``extra_voters_ignored`` field on
``VoterConfigReference`` (data-model.md §6 single-voter precondition); the
orchestrator emits a WARN line when that field is non-empty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


class VoterConfigError(Exception):
    """Base for voter-config loading failures (mapped to exit 2)."""


class VoterConfigUnreadable(VoterConfigError):
    """The voter-config file does not exist or cannot be opened."""


class VoterConfigMalformed(VoterConfigError):
    """The voter-config file exists but is not parseable YAML."""


class VoterConfigMissingModel(VoterConfigError):
    """The voter-config parsed but lacks the model-name field this feature reads."""


@dataclass(frozen=True)
class VoterConfigReference:
    """Resolved voter-config metadata used by the demo orchestrator.

    ``path`` is the absolute path actually loaded (post-override, post-discovery,
    canonicalized). ``model_name`` is the extraction model identifier for the
    Ollama /api/ps lookup. ``extra_voters_ignored`` lists the names of any
    additional voters in the config (empty for the canonical single-voter case).
    """

    path: str
    model_name: str
    extra_voters_ignored: list[str] = field(default_factory=list)


def _auto_discover() -> Optional[Path]:
    """Locate the canonical voter-config via the feature 005/021 fallback.

    The fallback search order:
    1. ``$PWD/voter_config.yaml`` (current working directory)
    2. ``$PWD/configs/voter_config.yaml``
    3. ``<package>/extract/voters/configs/voter_config.yaml`` (bundled default)

    Returns the first path that exists, or None if nothing is found.
    """
    candidates: list[Path] = [
        Path.cwd() / "voter_config.yaml",
        Path.cwd() / "configs" / "voter_config.yaml",
    ]
    # Bundled-in default from feature 005's voters/configs/ resources.
    try:
        import importlib.resources as resources

        bundled = resources.files("dartwing_ocr.extract.voters").joinpath("configs/voter_config.yaml")
        bundled_path = Path(str(bundled))
        if bundled_path.exists():
            candidates.append(bundled_path)
    except (ModuleNotFoundError, FileNotFoundError, AttributeError):
        pass
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def load_voter_config(override: Optional[Path]) -> VoterConfigReference:
    """Load the voter-config from override (if given) or auto-discovery.

    Raises one of ``VoterConfigUnreadable`` / ``VoterConfigMalformed`` /
    ``VoterConfigMissingModel`` on failure; the orchestrator maps each to
    exit 2.
    """
    resolved: Optional[Path] = None
    if override is not None:
        if not override.exists() or not override.is_file():
            raise VoterConfigUnreadable(
                f"voter-config path does not exist or is not a file: {override}"
            )
        resolved = override.resolve()
    else:
        resolved = _auto_discover()
        if resolved is None:
            raise VoterConfigUnreadable(
                "voter-config not found via auto-discovery (looked in $PWD/voter_config.yaml, "
                "$PWD/configs/voter_config.yaml, and the bundled default)"
            )

    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise VoterConfigUnreadable(
            f"voter-config file is unreadable: {resolved} ({exc})"
        ) from exc

    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise VoterConfigMalformed(
            f"voter-config is not parseable YAML: {resolved} ({exc})"
        ) from exc

    if not isinstance(parsed, dict):
        raise VoterConfigMalformed(
            f"voter-config root is not a mapping: {resolved}"
        )

    voters = parsed.get("voters")
    if voters is None:
        # Feature 005's older config shape used top-level `model` directly.
        model_name = parsed.get("model")
        if not isinstance(model_name, str) or not model_name:
            raise VoterConfigMissingModel(
                f"voter-config missing required model-name field: {resolved}"
            )
        return VoterConfigReference(
            path=str(resolved),
            model_name=model_name,
            extra_voters_ignored=[],
        )

    if not isinstance(voters, list) or not voters:
        raise VoterConfigMissingModel(
            f"voter-config 'voters' is not a non-empty list: {resolved}"
        )

    first = voters[0]
    if not isinstance(first, dict):
        raise VoterConfigMissingModel(
            f"voter-config first voter is not a mapping: {resolved}"
        )
    model_name = first.get("model") or first.get("model_name")
    if not isinstance(model_name, str) or not model_name:
        raise VoterConfigMissingModel(
            f"voter-config first voter missing 'model' / 'model_name' field: {resolved}"
        )

    extra_voters: list[str] = []
    for voter in voters[1:]:
        if isinstance(voter, dict):
            name = voter.get("name") or voter.get("model") or voter.get("model_name") or "<unnamed>"
            extra_voters.append(str(name))

    return VoterConfigReference(
        path=str(resolved),
        model_name=model_name,
        extra_voters_ignored=extra_voters,
    )
