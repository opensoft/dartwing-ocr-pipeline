"""``--with-evaluator`` subprocess invocation (T061, R-023.13).

Invokes feature 022's evaluator as a subprocess with the canonical argv per
the audit-walkthrough Q6 pin-down:

    python -m dartwing_ocr.evaluator evaluate-document --folder <doc> --quiet

cwd=<doc>, inherited environment, 60 s wall-clock budget. Returns an
``EvaluatorVerdict`` on success, ``None`` on warn-and-skip (sidecar missing)
or any subprocess failure (R-023.13 expanded clause). The orchestrator emits
the appropriate WARN line for each fallback case.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


_EVALUATOR_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class EvaluatorInvocationResult:
    """Outcome of an evaluator subprocess invocation."""

    sidecar_missing: bool = False
    subprocess_failed: bool = False
    subprocess_exit_code: Optional[int] = None
    subprocess_stderr_tail: Optional[str] = None
    semantic_table_quality_passed: Optional[bool] = None


def invoke_evaluator(document_folder: Path) -> EvaluatorInvocationResult:
    """Invoke the feature 022 evaluator and return a structured result.

    Returns flags the orchestrator uses to compose WARN messages + the
    optional ``semantic_table_quality_passed`` verdict feeding R-023.20's
    downgrade-only rule.
    """
    sidecar = document_folder / "semantic_table_truth.json"
    if not sidecar.exists():
        return EvaluatorInvocationResult(sidecar_missing=True)

    try:
        completed = subprocess.run(
            [
                sys.executable, "-m", "dartwing_ocr.evaluator",
                "evaluate-document", "--folder", str(document_folder), "--quiet",
            ],
            cwd=str(document_folder),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=_EVALUATOR_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return EvaluatorInvocationResult(
            subprocess_failed=True,
            subprocess_stderr_tail=f"{type(exc).__name__}: {exc}",
        )

    if completed.returncode != 0:
        return EvaluatorInvocationResult(
            subprocess_failed=True,
            subprocess_exit_code=completed.returncode,
            subprocess_stderr_tail=(completed.stderr or "")[-256:],
        )

    # On success, read the evaluator's evaluation_document.json from the folder.
    eval_doc = document_folder / "evaluation_document.json"
    if not eval_doc.exists():
        # Evaluator ran successfully but produced no document — treat as a
        # subprocess failure for the demo's purposes.
        return EvaluatorInvocationResult(
            subprocess_failed=True,
            subprocess_exit_code=completed.returncode,
            subprocess_stderr_tail="evaluator exited 0 but produced no evaluation_document.json",
        )

    try:
        body = json.loads(eval_doc.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return EvaluatorInvocationResult(
            subprocess_failed=True,
            subprocess_exit_code=completed.returncode,
            subprocess_stderr_tail=f"unreadable evaluation_document.json: {exc}",
        )

    # Feature 022's evaluator surfaces semantic_table_quality on the document.
    passed = None
    if isinstance(body, dict):
        gate = body.get("semantic_table_quality")
        if isinstance(gate, dict):
            passed = gate.get("passed")
            if not isinstance(passed, bool):
                passed = None
        # Older shape: document_pass_fail.semantic_table_quality_passed
        if passed is None:
            dpf = body.get("document_pass_fail")
            if isinstance(dpf, dict):
                p2 = dpf.get("semantic_table_quality_passed")
                if isinstance(p2, bool):
                    passed = p2

    return EvaluatorInvocationResult(
        subprocess_exit_code=completed.returncode,
        semantic_table_quality_passed=passed,
    )
