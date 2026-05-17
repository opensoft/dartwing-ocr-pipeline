"""Feature 016 (T022 / US3): CPU + warmup opt-in is a no-op with stderr warning.

These tests verify the FR-010 / SC-007 contract clarified per /speckit.clarify
Q1: when ``--gpu-warmup`` is set on a non-GPU profile, the system MUST
warn-and-proceed (NOT reject, NOT silently ignore). Specifically:

- Exactly ONE stderr line containing the literal ``--gpu-warmup ignored:``.
- No ``MIOPEN_*`` env var mutated.
- No ``~/.cache/miopen`` or ``~/.cache/comgr`` access.
- No ``preprocessing.warmup`` module imported (FR-011 / I-6 — keeps the lazy
  import scoped to the GPU branch only).
- Exit status equals what the run would produce without ``--gpu-warmup``.

The tests use a ``cli.main(...)`` entry-point invocation with
``preprocessing.pipeline.run`` mocked, so they do NOT need paddleocr / paddle
installed to run. PIL / numpy / pypdfium2 are still required to import
``preprocessing.cli`` (transitively via ``preprocessing.pipeline`` and
``preprocessing.ocr``); those skip cleanly in environments without them.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Skip the file if the optional preprocessing deps are missing — same pattern
# as test_warmup_unit.py.
pytest.importorskip("PIL")
pytest.importorskip("numpy")
pytest.importorskip("pypdfium2")


# Module-level imports AFTER importorskip so collection skips cleanly.
from dartwing_ocr.preprocessing import cli as cli_mod  # noqa: E402
from dartwing_ocr.preprocessing.errors import EXIT_OK  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: a tmp document folder with a tiny PDF (uses minimal valid bytes)
# ---------------------------------------------------------------------------


_MINIMAL_PDF_BYTES = (
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


@pytest.fixture
def tmp_inv_folder(tmp_path: Path) -> Path:
    """Create a tmp document folder named `inv_001_easy/` with a minimal PDF."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(_MINIMAL_PDF_BYTES)
    return folder


@pytest.fixture(autouse=True)
def _restore_miopen_env():
    """Save and restore the four MIOpen env vars so a test that mutates them
    cannot leak into sibling tests."""
    saved = {
        name: os.environ.get(name)
        for name in (
            "MIOPEN_FIND_MODE",
            "MIOPEN_USER_DB_PATH",
            "MIOPEN_CUSTOM_CACHE_DIR",
            "MIOPEN_LOG_LEVEL",
            "DARTWING_GPU_WARMUP",
        )
    }
    yield
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


# ---------------------------------------------------------------------------
# FR-010: --gpu-warmup + ppstructurev3@cpu emits warn-and-proceed
# ---------------------------------------------------------------------------


def _mock_pipeline_run_returning_minimal_artifact(
    tmp_inv_folder: Path,
) -> MagicMock:
    """Mock `preprocessing.pipeline.run` so cli.main can complete without
    actually running PaddleOCR. Writes a tiny artifact at the expected path
    so the post-run `with out_path.open(...)` read in cli.main does not fail."""
    artifact_path = tmp_inv_folder / "preprocess_output.json"
    artifact_path.write_text(json.dumps({
        "document_id": "inv_001_easy",
        "warnings": [],
    }))
    mock = MagicMock(return_value=artifact_path)
    return mock


def test_cpu_warmup_optin_emits_stderr_warning_and_no_warmup_pass(
    tmp_inv_folder: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The headline FR-010 / SC-007 case: --gpu-warmup with ppstructurev3@cpu
    emits the stderr warn-and-proceed line and proceeds to a successful
    CPU run that produces NO `phase_timings.warmup`."""
    mock_run = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)

    # Track import attempts of `preprocessing.warmup` regardless of
    # whether the module is already cached in sys.modules. A simple
    # `set(sys.modules.keys())` delta misses the violation when the
    # module was loaded earlier in the test session (e.g., by
    # test_warmup_unit.py), so the test would silently pass even if
    # the warn-and-proceed path imported warmup (Copilot PR #24
    # round 4). Patching `builtins.__import__` catches both
    # `import preprocessing.warmup` and
    # `from preprocessing import warmup` forms.
    import builtins
    real_import = builtins.__import__
    warmup_import_attempts: list[str] = []

    def _tracking_import(name: str, *args, **kwargs):
        # Direct dotted import.
        if (
            name == "dartwing_ocr.preprocessing.warmup"
            or name.startswith("dartwing_ocr.preprocessing.warmup.")
        ):
            warmup_import_attempts.append(name)
        # `from dartwing_ocr.preprocessing import warmup [as x]` form.
        if name == "dartwing_ocr.preprocessing":
            fromlist = kwargs.get("fromlist")
            if fromlist is None and len(args) >= 3:
                fromlist = args[2]
            if fromlist and "warmup" in tuple(fromlist):
                warmup_import_attempts.append(
                    "dartwing_ocr.preprocessing:warmup"
                )
        return real_import(name, *args, **kwargs)

    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_run), \
            patch("builtins.__import__", side_effect=_tracking_import):
        exit_code = cli_mod.main([
            "--document-folder", str(tmp_inv_folder),
            "--preprocess-profile", "ppstructurev3@cpu",
            "--gpu-warmup",
        ])

    captured = capsys.readouterr()

    # Exit status: success (warn-and-proceed equals non-opt-in run).
    assert exit_code == EXIT_OK, (
        f"--gpu-warmup on ppstructurev3@cpu must succeed; got exit code {exit_code}; "
        f"stderr={captured.err!r}"
    )

    # Exactly ONE stderr line contains the warn-and-proceed literal.
    warn_lines = [
        line for line in captured.err.splitlines()
        if "--gpu-warmup ignored:" in line
    ]
    assert len(warn_lines) == 1, (
        f"expected exactly 1 stderr line with '--gpu-warmup ignored:'; "
        f"got {len(warn_lines)} lines; stderr={captured.err!r}"
    )

    # The warning names the active profile.
    assert "ppstructurev3@cpu" in warn_lines[0]

    # The pipeline.run mock must have been called with `Invocation.warmup=False`
    # (the warn-and-proceed branch zeros out the warmup flag).
    assert mock_run.called
    invocation = mock_run.call_args[0][0]
    assert invocation.warmup is False, (
        f"Invocation.warmup must be False on warn-and-proceed path; got "
        f"warmup={invocation.warmup!r}"
    )
    assert invocation.preprocess_lane == "cpu"

    # No `preprocessing.warmup` module imported during the run (FR-011 / I-6).
    # `_tracking_import` above caught any attempt regardless of sys.modules
    # cache state, so an empty list here means the warn-and-proceed branch
    # never tried to load the module — the strong-form coverage Copilot's
    # PR #24 round-4 review asked for.
    assert not warmup_import_attempts, (
        f"warn-and-proceed path imported preprocessing.warmup "
        f"(FR-011 / I-6 violation): {warmup_import_attempts}"
    )


def test_cpu_warmup_optin_does_not_mutate_miopen_env(
    tmp_inv_folder: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No `MIOPEN_*` env var is set or modified by the warn-and-proceed path
    (FR-010 / FR-011 / I-7)."""
    # Snapshot the four MIOpen env vars before the run.
    miopen_vars = (
        "MIOPEN_FIND_MODE",
        "MIOPEN_USER_DB_PATH",
        "MIOPEN_CUSTOM_CACHE_DIR",
        "MIOPEN_LOG_LEVEL",
    )
    pre_run_snapshot = {name: os.environ.get(name) for name in miopen_vars}

    mock_run = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_run):
        cli_mod.main([
            "--document-folder", str(tmp_inv_folder),
            "--preprocess-profile", "ppstructurev3@cpu",
            "--gpu-warmup",
        ])

    post_run_snapshot = {name: os.environ.get(name) for name in miopen_vars}
    assert post_run_snapshot == pre_run_snapshot, (
        f"MIOpen env vars MUST NOT be mutated on warn-and-proceed path; "
        f"pre={pre_run_snapshot!r}, post={post_run_snapshot!r}"
    )


def test_cpu_warmup_via_envvar_emits_stderr_warning(
    tmp_inv_folder: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Equivalent path: setting `DARTWING_GPU_WARMUP=1` instead of the CLI
    flag also triggers the warn-and-proceed branch on a CPU profile (the
    activation surface is symmetric per cli-contract.md §1)."""
    os.environ["DARTWING_GPU_WARMUP"] = "1"
    mock_run = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_run):
        exit_code = cli_mod.main([
            "--document-folder", str(tmp_inv_folder),
            "--preprocess-profile", "ppstructurev3@cpu",
            # NOTE: no --gpu-warmup flag — opt-in via env var only
        ])

    captured = capsys.readouterr()
    assert exit_code == EXIT_OK
    assert "--gpu-warmup ignored:" in captured.err

    # Confirm Invocation.warmup is False on the env-var path too.
    invocation = mock_run.call_args[0][0]
    assert invocation.warmup is False


def test_cpu_without_warmup_optin_emits_no_warning(
    tmp_inv_folder: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Sanity baseline: CPU run WITHOUT the opt-in produces NO
    `--gpu-warmup ignored:` warning. This is the default-off case the
    warn-and-proceed branch must not trigger spuriously (FR-002 baseline)."""
    # Make sure env var is not set (autouse fixture restores it after).
    os.environ.pop("DARTWING_GPU_WARMUP", None)

    mock_run = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_run):
        cli_mod.main([
            "--document-folder", str(tmp_inv_folder),
            "--preprocess-profile", "ppstructurev3@cpu",
            # NO --gpu-warmup; NO env var.
        ])

    captured = capsys.readouterr()
    assert "--gpu-warmup ignored:" not in captured.err, (
        f"warn-and-proceed warning emitted spuriously on default-off CPU run; "
        f"stderr={captured.err!r}"
    )
    invocation = mock_run.call_args[0][0]
    assert invocation.warmup is False


def test_cpu_warmup_optin_run_summary_has_no_warmup_key(
    tmp_inv_folder: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """SC-007: the emitted run_summary on the warn-and-proceed path has NO
    `phase_timings.warmup` key. (`pipeline.run` is mocked so the run_summary
    has only the CPU stage timings + nothing else; absence of the warmup
    key is the assertion.)"""
    mock_run = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_run):
        cli_mod.main([
            "--document-folder", str(tmp_inv_folder),
            "--preprocess-profile", "ppstructurev3@cpu",
            "--gpu-warmup",
        ])

    captured = capsys.readouterr()
    # The run_summary line is the LAST stdout line (R-015.6).
    stdout_lines = [line for line in captured.out.splitlines() if line.strip()]
    summary_line = stdout_lines[-1]
    summary = json.loads(summary_line)
    assert summary.get("kind") == "run_summary"
    # Feature 018 (T004 / R-018.14): bumped 0.1.4 → 0.1.5 (additive top-level fields).
    # Feature 019 (T004 / R-019.14): bumped 0.1.5 → 0.1.6 (current chain head).
    # This test is a floor check ("no backslide below 0.1.6"); a future
    # bump to 0.1.7+ should still pass here. The strict-pin `== 0.1.6`
    # assertion lives in `test_run_summary_schema_0_1_6.py` (T015) and
    # is the gate that needs updating on every minor bump.
    _version_tuple = tuple(
        int(p) for p in summary.get("schema_version", "0.0.0").split(".")
    )
    assert _version_tuple >= (0, 1, 6), (
        f"schema_version must be at least 0.1.6 (feature 019 chain head); "
        f"got {summary.get('schema_version')!r}"
    )
    assert len(summary.get("per_document", [])) == 1
    per_doc = summary["per_document"][0]
    phase_timings = per_doc.get("phase_timings", {})
    assert "warmup" not in phase_timings, (
        f"warn-and-proceed run_summary MUST NOT carry phase_timings.warmup; "
        f"got phase_timings={phase_timings!r}"
    )
