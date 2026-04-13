"""Semver parsing + contract-set compatibility."""
from __future__ import annotations

import re

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class InvalidSemverError(ValueError):
    pass


def parse_semver(s: str) -> tuple[int, int, int]:
    m = SEMVER_RE.match(s)
    if not m:
        raise InvalidSemverError(f"not a semver string: {s!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def is_compatible(artifact_version: str, validator_version: str) -> bool:
    """Stage 1 rule: major-equal.

    Minor/patch differences pass. Missing or malformed version on either side is
    treated by the caller, not here.
    """
    try:
        a_major, _, _ = parse_semver(artifact_version)
        v_major, _, _ = parse_semver(validator_version)
    except InvalidSemverError:
        return False
    return a_major == v_major
