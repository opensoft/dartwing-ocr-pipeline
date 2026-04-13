"""ContractSet loader.

Reads `contracts/stage1_vendor_identity/v{X.Y.Z}/contract_set.json` and resolves
its artifact and folder schema paths. Does not validate schema *contents* — that
is the caller's job via `jsonschema`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ledgerlinc_ocr.validator.report import ArtifactName


class ContractSetNotFoundError(FileNotFoundError):
    pass


class ContractSetCorruptError(ValueError):
    pass


class InvalidArtifactNameError(ValueError):
    pass


_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONTRACTS_ROOT = _REPO_ROOT / "contracts" / "stage1_vendor_identity"

_VERSION_DIR_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class ContractSet:
    version: str
    version_dir: Path
    artifact_schemas: dict[ArtifactName, Path]
    folder_schema: Path
    challenge_tags: frozenset[str]
    cross_artifact_rules: tuple[str, ...]
    pipeline_versioned_artifacts: frozenset[ArtifactName]
    policy_versioned_artifacts: frozenset[ArtifactName]
    raw: dict = field(default_factory=dict)


def _latest_version_dir(root: Path) -> Path:
    if not root.is_dir():
        raise ContractSetNotFoundError(f"contracts root not found: {root}")
    candidates: list[tuple[tuple[int, int, int], Path]] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        m = _VERSION_DIR_RE.match(child.name)
        if not m:
            continue
        candidates.append(((int(m.group(1)), int(m.group(2)), int(m.group(3))), child))
    if not candidates:
        raise ContractSetNotFoundError(f"no v<semver> subdirs under {root}")
    candidates.sort(key=lambda pair: pair[0])
    return candidates[-1][1]


def _artifact_name(value: str) -> ArtifactName:
    try:
        return ArtifactName(value)
    except ValueError as exc:
        raise InvalidArtifactNameError(
            f"unknown artifact name in contract_set.json: {value!r}"
        ) from exc


def load_contract_set(
    version: str | None = None,
    *,
    contracts_root: Path | None = None,
) -> ContractSet:
    root = contracts_root or _DEFAULT_CONTRACTS_ROOT
    if version is None:
        version_dir = _latest_version_dir(root)
    else:
        version_dir = root / f"v{version}"
        if not version_dir.is_dir():
            raise ContractSetNotFoundError(
                f"contract set v{version} not found at {version_dir}"
            )
    spec_path = version_dir / "contract_set.json"
    if not spec_path.is_file():
        raise ContractSetCorruptError(
            f"contract_set.json missing in {version_dir}"
        )
    try:
        data = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractSetCorruptError(
            f"contract_set.json is not valid JSON: {exc}"
        ) from exc

    try:
        declared_version = data["contract_set_version"]
        artifact_schemas_raw = data["artifact_schemas"]
        folder_schema_rel = data["folder_schema"]
    except KeyError as exc:
        raise ContractSetCorruptError(
            f"contract_set.json missing required key: {exc}"
        ) from exc

    artifact_schemas: dict[ArtifactName, Path] = {}
    for name, rel in artifact_schemas_raw.items():
        artifact = _artifact_name(name)
        schema_path = (version_dir / rel).resolve()
        if not schema_path.is_file():
            raise ContractSetCorruptError(
                f"schema file missing for {name}: {schema_path}"
            )
        artifact_schemas[artifact] = schema_path

    folder_schema_path = (version_dir / folder_schema_rel).resolve()
    if not folder_schema_path.is_file():
        raise ContractSetCorruptError(
            f"folder schema missing: {folder_schema_path}"
        )

    challenge_tags = frozenset(data.get("challenge_tags") or [])
    cross_artifact_rules = tuple(data.get("cross_artifact_rules") or [])
    pipeline_versioned = frozenset(
        _artifact_name(n) for n in (data.get("pipeline_versioned_artifacts") or [])
    )
    policy_versioned = frozenset(
        _artifact_name(n) for n in (data.get("policy_versioned_artifacts") or [])
    )

    return ContractSet(
        version=declared_version,
        version_dir=version_dir,
        artifact_schemas=artifact_schemas,
        folder_schema=folder_schema_path,
        challenge_tags=challenge_tags,
        cross_artifact_rules=cross_artifact_rules,
        pipeline_versioned_artifacts=pipeline_versioned,
        policy_versioned_artifacts=policy_versioned,
        raw=data,
    )
