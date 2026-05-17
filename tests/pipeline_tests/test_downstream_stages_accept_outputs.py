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

from ledgerlinc_ocr.pipeline.cli import main
from ledgerlinc_ocr.pipeline.runner import RESERVED_ARTIFACT_NAMES
from ledgerlinc_ocr.validator.artifact import validate_artifact
from ledgerlinc_ocr.validator.report import ArtifactName


# Closed-vocabulary set of forbidden gate-related field names. If any of
# these appears anywhere in any canonical artifact (top-level, nested,
# or inside an array element), FR-021 is violated.
_FORBIDDEN_GATE_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "evidence_gate_id",
        "evidence_gate_state_counts",
        "evidence_gate_documents",
        "evidence_gate_suppressed_fallback_count",
        "evidence_gate",
        "gate_decision",
        "gate_decision_state",
        "evidence_gate_decision",
        "evidence_gate_signals",
        "vendor_name_candidate_count",
        "header_band_token_density",
        "ocr_detection_confidence_mean",
        "business_suffix_present",
        "tax_id_shaped_present",
    }
)

# Closed-vocabulary set of forbidden sidecar file names. None of these
# may appear in the per-document folder after a successful run.
_FORBIDDEN_SIDECAR_FILES: frozenset[str] = frozenset(
    {
        "evidence_gate.json",
        "gate_decision.json",
        "signals.json",
        "evidence_gate_result.json",
        "evidence_gate_signals.json",
    }
)


_ARTIFACT_MAP: dict[str, ArtifactName] = {
    "preprocess_output.json": ArtifactName.PREPROCESS_OUTPUT,
    "edge_extraction_output.json": ArtifactName.EDGE_EXTRACTION_OUTPUT,
    "routing_decision.json": ArtifactName.ROUTING_DECISION,
    "final_structured_payload.json": ArtifactName.FINAL_STRUCTURED_PAYLOAD,
}


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

    # FR-021 no-sidecar pre-snapshot: capture the folder contents BEFORE
    # the pipeline run so we can diff the new file set afterward.
    pre_snapshot: set[str] = {p.name for p in folder.iterdir()}

    code = main(["run", "--document-folder", str(folder), "--overwrite"])
    assert code == 0, f"E2E pipeline run failed with exit={code}"

    # SC-007 (a): all four canonical artifacts present.
    post_snapshot: set[str] = {p.name for p in folder.iterdir()}
    for name in RESERVED_ARTIFACT_NAMES:
        assert (folder / name).is_file(), (
            f"expected canonical artifact {name!r} missing after E2E run"
        )

    # SC-007 (b): each artifact validates against its v1.2.0 schema.
    for filename, contract in _ARTIFACT_MAP.items():
        outcome = validate_artifact(
            folder / filename, contract, version="1.2.0"
        )
        assert outcome.passed, (
            f"{filename}: schema validation failed: "
            f"{[v.reason for v in outcome.violations]}"
        )

    # FR-021 (a): no gate-related field appears in any canonical
    # artifact. Walk the full JSON tree of each artifact.
    for filename in _ARTIFACT_MAP:
        payload = json.loads((folder / filename).read_text(encoding="utf-8"))
        keys_seen = _walk_keys(payload)
        leaked = keys_seen & _FORBIDDEN_GATE_FIELD_NAMES
        assert not leaked, (
            f"FR-021 violation: gate-related field name(s) leaked into "
            f"{filename}: {sorted(leaked)!r}. The gate is observability "
            "only — it MUST NOT contribute fields to canonical artifacts."
        )

    # FR-021 (b): no gate sidecar file appears in the per-document
    # folder. The only NEW files since pre-snapshot are the four
    # canonical artifacts (optional debug page_*.png tolerated only if
    # already present pre-run).
    new_files = post_snapshot - pre_snapshot
    expected_new = set(RESERVED_ARTIFACT_NAMES)
    unexpected_new = new_files - expected_new
    assert not unexpected_new, (
        f"FR-021 violation: unexpected new files in per-document folder "
        f"after gate-instrumented run: {sorted(unexpected_new)!r}. "
        "Only the four canonical artifacts may be written."
    )
    # Symmetric assertion: none of the explicit-named gate sidecars
    # appears, even if other unexpected new files don't (defense in
    # depth against a sidecar name not yet enumerated).
    sidecar_hits = post_snapshot & _FORBIDDEN_SIDECAR_FILES
    assert not sidecar_hits, (
        f"FR-021 violation: gate sidecar file(s) appeared in per-document "
        f"folder: {sorted(sidecar_hits)!r}"
    )


def test_e2e_corpus_path_with_gate_active_emits_four_valid_canonical_artifacts(
    tmp_path: Path,
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
    # Minimal valid PDF; the stub adapter doesn't actually parse it.
    (folder / "source.pdf").write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\n"
        b"xref\n0 3\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000053 00000 n \n"
        b"trailer<</Size 3/Root 1 0 R>>\n"
        b"startxref\n100\n%%EOF\n"
    )
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

    # Gate-active witness: the final stdout line is a run_summary that
    # carries the four feature-020 fields and at least one per-doc record.
    out = capsys.readouterr().out
    last_line = [ln for ln in out.splitlines() if ln.strip()][-1]
    summary = json.loads(last_line)
    assert summary.get("kind") == "run_summary"
    assert summary.get("evidence_gate_id") == "v1"
    assert "evidence_gate_state_counts" in summary
    assert "evidence_gate_documents" in summary
    # The stub adapter writes a schema-valid preprocess_output.json, so
    # the gate evaluates it successfully — expect at least one per-doc
    # record (this is the witness that the gate-active path ran).
    assert len(summary["evidence_gate_documents"]) >= 1, (
        "expected at least one evidence_gate_documents record from the "
        "stub-adapter corpus run; got 0 — the gate did not fire as "
        "expected, weakening the FR-021 isolation claim of this test"
    )

    # Four canonical artifacts present and v1.2.0-valid (SC-007).
    post_snapshot: set[str] = {p.name for p in folder.iterdir()}
    for name in RESERVED_ARTIFACT_NAMES:
        assert (folder / name).is_file(), (
            f"expected canonical artifact {name!r} missing after corpus run"
        )
    for filename, contract in _ARTIFACT_MAP.items():
        outcome = validate_artifact(
            folder / filename, contract, version="1.2.0"
        )
        assert outcome.passed, (
            f"{filename}: schema validation failed: "
            f"{[v.reason for v in outcome.violations]}"
        )

    # FR-021: no gate field leak into any canonical artifact, even
    # though the gate ran.
    for filename in _ARTIFACT_MAP:
        payload = json.loads((folder / filename).read_text(encoding="utf-8"))
        leaked = _walk_keys(payload) & _FORBIDDEN_GATE_FIELD_NAMES
        assert not leaked, (
            f"FR-021 violation (gate-active path): gate-related field "
            f"name(s) leaked into {filename}: {sorted(leaked)!r}"
        )

    # FR-021: no sidecar file appears.
    new_files = post_snapshot - pre_snapshot
    unexpected_new = new_files - set(RESERVED_ARTIFACT_NAMES)
    assert not unexpected_new, (
        f"FR-021 violation (gate-active path): unexpected new files in "
        f"per-document folder: {sorted(unexpected_new)!r}"
    )
    sidecar_hits = post_snapshot & _FORBIDDEN_SIDECAR_FILES
    assert not sidecar_hits, (
        f"FR-021 violation (gate-active path): gate sidecar file(s) "
        f"appeared: {sorted(sidecar_hits)!r}"
    )
