"""Feature 020 / T050 / US6 (FR-021 / SC-007):
end-to-end downstream-stage acceptance test for the gate-instrumented
default pipeline.

FR-021: gate observability MUST NOT leak into any canonical artifact —
``preprocess_output.json``, ``edge_extraction_output.json``,
``routing_decision.json``, ``final_structured_payload.json``. No gate
field appears in any of the four artifacts. No sidecar file
(``evidence_gate.json`` / ``gate_decision.json`` / ``signals.json``)
appears in the per-document folder.

SC-007: a CPU end-to-end run produces four canonical artifacts that
each validate against their v1.2.0 schema. The gate is observability
emitted exclusively on the ``run_summary`` stdout line (FR-008 / FR-014).

GPU end-to-end is deferred per R-020.15 — this test runs the CPU stub
adapter only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from dartwing_ocr.evaluator.pipeline_invocation import (
    parse_pipeline_run_summary,
)
from dartwing_ocr.pipeline.cli import main
from dartwing_ocr.pipeline.runner import RESERVED_ARTIFACT_NAMES
from dartwing_ocr.validator.artifact import validate_artifact
from dartwing_ocr.validator.report import ArtifactName


# FR-021 namespace check: any key beginning with these prefixes is a
# gate-related field. This catches future gate fields without manual
# list maintenance — the spec's gate-namespace contract (R-020.10) is
# encoded directly. Defense in depth against rename / new sidecar
# naming: ``gate_decision`` is included alongside ``evidence_gate``.
_GATE_NAMESPACE_PREFIXES: tuple[str, ...] = ("evidence_gate", "gate_decision")

# The five deliberately-non-namespaced signal field names per R-020.3.
# These cannot be matched by a prefix rule, so we keep an explicit
# closed list for them. If a future R-020 amendment renames a signal,
# update this set together with the amendment.
_GATE_SIGNAL_FIELDS: frozenset[str] = frozenset(
    {
        "vendor_name_candidate_count",
        "header_band_token_density",
        "ocr_detection_confidence_mean",
        "business_suffix_present",
        "tax_id_shaped_present",
    }
)


def _is_forbidden_gate_field(key: str) -> bool:
    """True iff a key in a canonical artifact would constitute an FR-021
    leak of gate state into the downstream payload."""
    if key in _GATE_SIGNAL_FIELDS:
        return True
    return any(key.startswith(prefix) for prefix in _GATE_NAMESPACE_PREFIXES)


_ARTIFACT_MAP: dict[str, ArtifactName] = {
    "preprocess_output.json": ArtifactName.PREPROCESS_OUTPUT,
    "edge_extraction_output.json": ArtifactName.EDGE_EXTRACTION_OUTPUT,
    "routing_decision.json": ArtifactName.ROUTING_DECISION,
    "final_structured_payload.json": ArtifactName.FINAL_STRUCTURED_PAYLOAD,
}

# Drift guard: every artifact we schema-validate must also be in the
# presence-check set. If a future change adds a new canonical artifact
# to RESERVED_ARTIFACT_NAMES without updating _ARTIFACT_MAP, this
# assertion fails at import time rather than silently masking the
# unvalidated artifact (Sourcery review feedback).
assert set(_ARTIFACT_MAP.keys()).issubset(set(RESERVED_ARTIFACT_NAMES)), (
    f"_ARTIFACT_MAP keys {sorted(_ARTIFACT_MAP.keys())!r} must be a "
    f"subset of RESERVED_ARTIFACT_NAMES {sorted(RESERVED_ARTIFACT_NAMES)!r}"
)


def _walk_keys(obj: object) -> set[str]:
    """Walk a JSON-ish object and return the set of every dict key
    encountered (top-level and nested). Lists are descended; primitives
    contribute nothing."""
    out: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(str(k))
            out |= _walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= _walk_keys(v)
    return out


def _assert_no_unexpected_files(
    *,
    pre_snapshot: set[str],
    post_snapshot: set[str],
    context: str,
) -> None:
    """FR-021 absolute folder-state check. After a successful run the
    per-document folder MUST contain exactly the pre-run files PLUS the
    four canonical artifact names — nothing more, nothing less.

    Failing on the absolute set (rather than only the delta) catches
    pre-existing sidecars left by a previous run AND new sidecars
    written by this run in a single check, and is robust to cross-test
    pollution of ``tmp_path``."""
    expected = pre_snapshot | set(RESERVED_ARTIFACT_NAMES)
    extras = post_snapshot - expected
    missing = expected - post_snapshot
    assert not extras and not missing, (
        f"FR-021 violation ({context}): per-document folder did not "
        f"contain exactly the expected set after run. "
        f"Unexpected files: {sorted(extras)!r}. "
        f"Missing expected files: {sorted(missing)!r}."
    )


def _assert_canonical_artifacts_present_valid_and_gate_clean(
    folder: Path,
    *,
    pre_snapshot: set[str],
    post_snapshot: set[str],
    context: str,
) -> None:
    """SC-007 + FR-021 combined post-run assertion bundle shared by the
    cold-mode and gate-active-corpus tests:

    - All four canonical artifacts are present in ``folder``.
    - Each canonical artifact validates against its v1.2.0 schema.
    - No gate-related field (namespace prefix OR explicit signal name)
      appears anywhere in any artifact's JSON tree (FR-021).
    - Absolute folder-state check: exactly the pre-run files plus the
      four canonical artifacts (FR-021 sidecar guard).
    """
    for name in RESERVED_ARTIFACT_NAMES:
        assert (folder / name).is_file(), (
            f"expected canonical artifact {name!r} missing after run "
            f"({context})"
        )

    for filename, contract in _ARTIFACT_MAP.items():
        outcome = validate_artifact(
            folder / filename, contract, version="1.2.0"
        )
        assert outcome.passed, (
            f"{filename}: schema validation failed ({context}): "
            f"{[v.reason for v in outcome.violations]}"
        )

    for filename in _ARTIFACT_MAP:
        payload = json.loads((folder / filename).read_text(encoding="utf-8"))
        leaked = {k for k in _walk_keys(payload) if _is_forbidden_gate_field(k)}
        assert not leaked, (
            f"FR-021 violation ({context}): gate-related field name(s) "
            f"leaked into {filename}: {sorted(leaked)!r}. The gate is "
            "observability only — it MUST NOT contribute fields to "
            "canonical artifacts."
        )

    _assert_no_unexpected_files(
        pre_snapshot=pre_snapshot,
        post_snapshot=post_snapshot,
        context=context,
    )


def test_e2e_default_pipeline_emits_four_valid_canonical_artifacts(
    tmp_document_folder: Callable[..., Path],
) -> None:
    """SC-007: a CPU stub-adapter end-to-end run (cold single-doc path)
    on one fixture writes exactly the four canonical artifacts, each of
    which validates against its v1.2.0 contract.

    Cold mode (``--document-folder``) goes through ``pipeline/cli._run_cold``
    which does NOT itself invoke the evidence gate (the gate's wiring
    lives in ``corpus_run.py`` and ``preprocessing/cli.py``). The
    FR-021 invariant still applies — the cold path simply must not
    leak any gate-related field or sidecar regardless of who runs the
    gate; the corpus-path companion test below exercises the same
    invariant on the gate-active path.
    """
    folder = tmp_document_folder(1, "easy")
    pre_snapshot: set[str] = {p.name for p in folder.iterdir()}

    code = main(["run", "--document-folder", str(folder), "--overwrite"])
    assert code == 0, f"E2E pipeline run failed with exit={code}"

    post_snapshot: set[str] = {p.name for p in folder.iterdir()}
    _assert_canonical_artifacts_present_valid_and_gate_clean(
        folder,
        pre_snapshot=pre_snapshot,
        post_snapshot=post_snapshot,
        context="cold default-mode path",
    )


def test_e2e_corpus_path_with_gate_active_emits_four_valid_canonical_artifacts(
    tmp_path: Path,
    tmp_pdf_bytes: bytes,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Companion to the cold-mode test above: this one exercises the
    warm-corpus path (``--documents-file``), which is where the
    evidence gate actually fires per ``corpus_run.py``'s wiring. The
    FR-021 invariant must hold here too — even when the gate runs and
    contributes records to the ``run_summary`` stdout line, NO gate
    field appears in any of the four canonical artifacts, and NO
    sidecar file appears in the per-document folder.
    """
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(tmp_pdf_bytes)
    docs_file = tmp_path / "documents.txt"
    docs_file.write_text(f"{folder}\n", encoding="utf-8")

    pre_snapshot: set[str] = {p.name for p in folder.iterdir()}

    code = main(
        [
            "run",
            "--documents-file",
            str(docs_file),
            "--overwrite",
        ]
    )
    assert code == 0, f"warm-corpus E2E pipeline run failed with exit={code}"

    # Gate-active witness: stdout contains a run_summary line that
    # carries the four feature-020 fields and at least one per-doc record.
    # Use parse_pipeline_run_summary (backward-scanning helper from the
    # evaluator package) instead of assuming the run_summary is the very
    # last non-empty line — any later log/warn line would otherwise
    # break this test even though nothing is wrong (Copilot review feedback).
    out = capsys.readouterr().out
    summary = parse_pipeline_run_summary(out)
    assert summary is not None, (
        "no `kind: run_summary` line found in stdout; the gate-active "
        "witness for this test depends on the corpus run emitting one"
    )
    assert summary.get("evidence_gate_id") == "v1"
    assert "evidence_gate_state_counts" in summary
    assert "evidence_gate_documents" in summary
    assert len(summary["evidence_gate_documents"]) >= 1, (
        "expected at least one evidence_gate_documents record from the "
        "stub-adapter corpus run; got 0 — the gate did not fire as "
        "expected, weakening the FR-021 isolation claim of this test"
    )

    post_snapshot: set[str] = {p.name for p in folder.iterdir()}
    _assert_canonical_artifacts_present_valid_and_gate_clean(
        folder,
        pre_snapshot=pre_snapshot,
        post_snapshot=post_snapshot,
        context="warm-corpus gate-active path",
    )
