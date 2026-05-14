"""Closed-set stage-profile vocabulary, parser, and stack-preset expansion.

Spec FR-005 / FR-006 / FR-008 / FR-004A. Research R-001 / R-002 / R-003.

The vocabulary is closed: new profiles require both a code change here
(adding the (stage, impl, lane) triple to ``SUPPORTED_PROFILES``) and a
contract amendment. There is no plugin/discovery mechanism.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Stage = Literal["preprocess", "extract", "routing", "final_payload"]
Lane = Literal["cpu", "gpu", "jetson", "workstation"]
ProfileKind = Literal["stub", "live"]

STAGES: tuple[Stage, ...] = ("preprocess", "extract", "routing", "final_payload")

PPSTRUCTUREV3_CPU = "ppstructurev3@cpu"
PPSTRUCTUREV3_GPU = "ppstructurev3@gpu"
RULES_CPU = "rules@cpu"
ASSEMBLER_CPU = "assembler@cpu"

# (stage, implementation, lane | None) — ``lane=None`` only for ``stub``.
SUPPORTED_PROFILES: frozenset[tuple[Stage, str, str | None]] = frozenset({
    # preprocess
    ("preprocess", "stub", None),
    ("preprocess", "ppstructurev3", "cpu"),
    ("preprocess", "ppstructurev3", "gpu"),  # feature 014 (T020)
    ("preprocess", "edge-ocr", "jetson"),
    # extract
    ("extract", "stub", None),
    ("extract", "ollama", "gpu"),
    ("extract", "ollama", "cpu"),
    ("extract", "ollama", "jetson"),
    ("extract", "ensemble", "workstation"),
    # routing
    ("routing", "stub", None),
    ("routing", "rules", "cpu"),
    # final_payload
    ("final_payload", "stub", None),
    ("final_payload", "assembler", "cpu"),
})

DEFAULT_PROFILES: dict[Stage, str] = {
    "preprocess": PPSTRUCTUREV3_CPU,
    "extract": "ollama@gpu",
    "routing": RULES_CPU,
    "final_payload": ASSEMBLER_CPU,
}

StackPresetName = Literal["full-workstation", "cloud-workstation", "edge-fast"]
STACK_PRESETS: dict[StackPresetName, dict[Stage, str]] = {
    "full-workstation": {
        "preprocess": PPSTRUCTUREV3_CPU,
        "extract": "ollama@gpu",
        "routing": RULES_CPU,
        "final_payload": ASSEMBLER_CPU,
    },
    "cloud-workstation": {
        "preprocess": PPSTRUCTUREV3_CPU,
        "extract": "ensemble@workstation",
        "routing": RULES_CPU,
        "final_payload": ASSEMBLER_CPU,
    },
    "edge-fast": {
        "preprocess": "edge-ocr@jetson",
        "extract": "ollama@jetson",
        "routing": RULES_CPU,
        "final_payload": ASSEMBLER_CPU,
    },
}


class ProfileValidationError(ValueError):
    """Raised when a stage-profile value is not in the closed-set vocabulary."""


@dataclass(frozen=True)
class StageProfile:
    stage: Stage
    kind: ProfileKind
    implementation: str
    lane: Lane | None
    raw_value: str


def _accepted_values_for_stage(stage: Stage) -> list[str]:
    out: list[str] = []
    for s, impl, lane in sorted(SUPPORTED_PROFILES):
        if s != stage:
            continue
        out.append(impl if lane is None else f"{impl}@{lane}")
    return out


def parse_profile(stage: Stage, raw_value: str) -> StageProfile:
    """Parse and validate one stage-profile value. Raises on rejection.

    Grammar (FR-005): ``stub`` | ``<implementation>@<lane>``.
    """
    if not isinstance(raw_value, str) or not raw_value:
        raise ProfileValidationError(
            f"--{stage}-profile: value must be a non-empty string"
        )

    # Stub: lane-less by definition (rejects stub@cpu / stub@gpu).
    if raw_value == "stub":
        triple = (stage, "stub", None)
        if triple not in SUPPORTED_PROFILES:
            raise ProfileValidationError(
                f"--{stage}-profile={raw_value!r}: stub is not supported "
                f"for {stage} (closed vocabulary: "
                f"{_accepted_values_for_stage(stage)})"
            )
        return StageProfile(
            stage=stage,
            kind="stub",
            implementation="stub",
            lane=None,
            raw_value=raw_value,
        )

    if "@" not in raw_value:
        raise ProfileValidationError(
            f"--{stage}-profile={raw_value!r}: expected 'stub' or "
            f"'<implementation>@<lane>' (accepted: "
            f"{_accepted_values_for_stage(stage)})"
        )
    if raw_value.count("@") != 1:
        raise ProfileValidationError(
            f"--{stage}-profile={raw_value!r}: at most one '@' is permitted "
            f"in a profile value"
        )

    impl, lane = raw_value.split("@", 1)
    if not impl or not lane:
        raise ProfileValidationError(
            f"--{stage}-profile={raw_value!r}: implementation and lane must "
            f"both be non-empty around '@'"
        )

    if impl == "stub":
        # Reject stub@cpu, stub@gpu, etc. (Edge Cases bullet 3).
        raise ProfileValidationError(
            f"--{stage}-profile={raw_value!r}: stub is lane-less; use 'stub' "
            f"without an '@<lane>' suffix"
        )

    triple = (stage, impl, lane)
    if triple not in SUPPORTED_PROFILES:
        raise ProfileValidationError(
            f"--{stage}-profile={raw_value!r}: not in the closed vocabulary "
            f"for {stage} (accepted: {_accepted_values_for_stage(stage)})"
        )

    return StageProfile(
        stage=stage,
        kind="live",
        implementation=impl,
        lane=lane,  # type: ignore[arg-type]
        raw_value=raw_value,
    )


def expand_stack_preset(name: str) -> dict[Stage, str]:
    """Return the (stage -> raw profile string) expansion table for a preset.

    Raises ``ProfileValidationError`` for an unknown preset name.
    """
    if name not in STACK_PRESETS:
        raise ProfileValidationError(
            f"--stack-preset={name!r}: not a recognized preset (accepted: "
            f"{sorted(STACK_PRESETS)})"
        )
    return dict(STACK_PRESETS[name])  # defensive copy


def resolve_profiles(
    *,
    stack_preset: str | None,
    explicit: dict[Stage, str | None],
) -> tuple[dict[Stage, StageProfile], str | None]:
    """Resolve final per-stage profiles from preset + per-stage overrides.

    ``explicit`` keys are stage names; values are either a raw CLI string
    or ``None`` if the caller did not pass that flag. Per-stage explicit
    values override the preset (R-003). Returns ``(profiles, preset_name)``
    where ``preset_name`` is the originating preset (for run-summary
    metadata) or ``None`` if no preset was supplied.
    """
    if stack_preset is None:
        raw_table = dict(DEFAULT_PROFILES)
        preset_name: str | None = None
    else:
        raw_table = expand_stack_preset(stack_preset)
        preset_name = stack_preset

    for stage in STAGES:
        override = explicit.get(stage)
        if override is not None:
            raw_table[stage] = override

    parsed: dict[Stage, StageProfile] = {}
    for stage in STAGES:
        parsed[stage] = parse_profile(stage, raw_table[stage])
    return parsed, preset_name
