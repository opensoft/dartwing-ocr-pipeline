"""Feature 022 — OCR semantic quality gate orchestrator (data-model §13).

Public surface:

- ``SEMANTIC_QUALITY_GATE_VERSION = "v1"``
- :func:`run_semantic_quality_gate` — single-document deterministic gate
  entry point.

The gate is **pure-Python, CPU-only, air-gapped** (MI-1 / FR-008 /
FR-029 / FR-034): no Paddle import, no network I/O, no model call. Every
import in this module's dependency tree is stdlib or pre-existing local
code from features 001–020 — none of which pull in Paddle.

State machine (data-model §13):

    Sidecar absent                 → status = not_applicable
    Sidecar present, input cascade:
        step 1: preprocess.json missing            → unevaluable / preprocess_output_missing
        step 2: file present, unparseable JSON     → unevaluable / preprocess_output_invalid_json
        step 3: file parses, fails schema validation → unevaluable / preprocess_output_schema_invalid
        step 4: file valid, zero body OCR lines    → unevaluable / body_ocr_unreadable
        else: build body OCR + anchor + 4 checks (Q17 order, no short-circuit)
              aggregate by any-fail (Q4) → passed | failed

Gate-time invariant violations (anchor returning negative indices,
verdict aggregator producing an unknown status, etc.) raise
:class:`SemanticGateInvariantError` and propagate to the caller —
they are NEVER converted to ``unevaluable`` (Q42 / MI-19).

The schema validation in step 3 uses the v1.3.0
``preprocess_output.schema.json`` (which is byte-identical to v1.2.0 per
R-022.5). The schema is loaded once per call via :func:`_load_schema`
— it is a tiny JSON document and the cost is negligible.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import jsonschema

from dartwing_ocr.evaluator.exceptions import SemanticGateInvariantError
from dartwing_ocr.evaluator.semantic_quality_body_ocr import (
    BodyOcrEvidence,
    build_body_ocr_evidence,
)
from dartwing_ocr.evaluator.semantic_quality_checks import evaluate_all_rows
from dartwing_ocr.evaluator.semantic_quality_report import (
    SemanticQualityResult,
    build_semantic_quality_result,
)

SEMANTIC_QUALITY_GATE_VERSION: Final[str] = "v1"
"""Public gate version constant (data-model §10)."""


_VALID_STATUSES: Final[frozenset[str]] = frozenset(
    {"passed", "failed", "not_applicable", "unevaluable"}
)


# The preprocess_output.json schema is loaded lazily once per process.
_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}


def _load_schema(contract_set_root: Path) -> dict[str, Any]:
    """Load v1.3.0 ``preprocess_output.schema.json`` (cached)."""
    key = str(contract_set_root)
    cached = _SCHEMA_CACHE.get(key)
    if cached is not None:
        return cached
    schema_path = contract_set_root / "v1.3.0" / "preprocess_output.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    _SCHEMA_CACHE[key] = schema
    return schema


def _repo_root() -> Path:
    """Return the repo root (parent of ``src/``)."""
    # This file lives at src/dartwing_ocr/evaluator/semantic_quality.py
    return Path(__file__).resolve().parents[3]


def _empty_evidence() -> BodyOcrEvidence:
    return BodyOcrEvidence(
        included_lines=(),
        excluded_line_count=0,
        normalized_search_string="",
        header_band_excluded=False,
    )


def _load_sidecar_rows(sidecar_path: Path) -> list[dict[str, Any]]:
    """Read ``semantic_table_truth.json`` and return its ``rows`` array.

    The validator (US1) is the authoritative shape check; here we only
    do a permissive read to drive the gate. A malformed sidecar would
    surface at US1's validator phase; if it reaches the gate something
    has bypassed the validator, which is a hard error (MI-19).
    """
    try:
        obj = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SemanticGateInvariantError(
            f"sidecar {sidecar_path} is not valid JSON: {exc}"
        ) from exc
    rows = obj.get("rows") if isinstance(obj, dict) else None
    if not isinstance(rows, list):
        raise SemanticGateInvariantError(
            f"sidecar {sidecar_path} is missing 'rows' array"
        )
    return rows


def run_semantic_quality_gate(
    preprocess_output_path: Path | None,
    sidecar_path: Path | None,
    folder_basename: str,
) -> SemanticQualityResult:
    """Run the gate on one document.

    Args:
        preprocess_output_path: Filesystem path to the per-document
            ``preprocess_output.json``. May be ``None`` (treated as
            "missing" — drives the ``preprocess_output_missing`` cascade
            step when a sidecar is present).
        sidecar_path: Filesystem path to the per-document
            ``semantic_table_truth.json``. ``None`` means no sidecar →
            ``status = not_applicable``.
        folder_basename: The per-document folder basename (e.g.
            ``"inv_001_hard"``). Currently used only for diagnostic
            messages; reserved for future use by the calibration-folder
            exclusion logic in US3.

    Returns:
        A :class:`SemanticQualityResult` per data-model §7.

    Raises:
        SemanticGateInvariantError: When a gate-time invariant is
            violated (Q42 / MI-19). NEVER converted to ``unevaluable``.
    """
    # --- Case 1: no sidecar → not_applicable -----------------------------
    if sidecar_path is None or not _path_exists(sidecar_path):
        return build_semantic_quality_result(
            status="not_applicable",
            failed_checks=[],
            evidence=_empty_evidence(),
        )

    # --- Case 2: unevaluable cascade (Q31 / R-022.13) --------------------
    # Step 1: preprocess_output.json missing
    if preprocess_output_path is None or not _path_exists(preprocess_output_path):
        return build_semantic_quality_result(
            status="unevaluable",
            failed_checks=[],
            evidence=_empty_evidence(),
            cause="preprocess_output_missing",
            cause_detail=(
                f"No preprocess_output.json found at {preprocess_output_path}"
                if preprocess_output_path is not None
                else "preprocess_output path not provided"
            ),
        )

    # Step 2: invalid JSON
    try:
        raw = preprocess_output_path.read_text(encoding="utf-8")
    except OSError as exc:
        return build_semantic_quality_result(
            status="unevaluable",
            failed_checks=[],
            evidence=_empty_evidence(),
            cause="preprocess_output_missing",
            cause_detail=f"could not read preprocess_output.json: {exc}",
        )
    try:
        preprocess_dict = json.loads(raw)
    except json.JSONDecodeError as exc:
        return build_semantic_quality_result(
            status="unevaluable",
            failed_checks=[],
            evidence=_empty_evidence(),
            cause="preprocess_output_invalid_json",
            cause_detail=f"JSON decode error: {exc}",
        )

    # Step 3: schema validation
    try:
        schema = _load_schema(_repo_root() / "contracts" / "stage1_vendor_identity")
        jsonschema.validate(instance=preprocess_dict, schema=schema)
    except jsonschema.ValidationError as exc:
        return build_semantic_quality_result(
            status="unevaluable",
            failed_checks=[],
            evidence=_empty_evidence(),
            cause="preprocess_output_schema_invalid",
            cause_detail=f"schema validation error: {exc.message}",
        )
    except (OSError, json.JSONDecodeError) as exc:
        # The schema itself could not be loaded — that is a packaging
        # bug, not a per-document input error.
        raise SemanticGateInvariantError(
            f"could not load preprocess_output.schema.json: {exc}"
        ) from exc

    # Step 4: body OCR build + readability check
    body_evidence = build_body_ocr_evidence(preprocess_dict)
    if body_evidence.included_lines == ():
        return build_semantic_quality_result(
            status="unevaluable",
            failed_checks=[],
            evidence=body_evidence,
            cause="body_ocr_unreadable",
            cause_detail="no body OCR lines after header-band exclusion",
        )

    # --- Case 3: evaluation path ----------------------------------------
    rows = _load_sidecar_rows(sidecar_path)
    failed_checks = evaluate_all_rows(rows, body_evidence)

    # Aggregate by any-fail rule (Q4 / MI-10).
    status = "failed" if len(failed_checks) > 0 else "passed"

    # MI-11 invariant guard.
    if status not in _VALID_STATUSES:
        raise SemanticGateInvariantError(
            f"verdict aggregator produced status='{status}' which is not in the "
            f"closed Q26 enum {sorted(_VALID_STATUSES)}"
        )

    return build_semantic_quality_result(
        status=status,
        failed_checks=failed_checks,
        evidence=body_evidence,
    )


def _path_exists(p: Path | None) -> bool:
    """Defensive ``Path.exists()`` wrapper that returns ``False`` on None."""
    if p is None:
        return False
    try:
        return p.exists()
    except OSError:
        return False
