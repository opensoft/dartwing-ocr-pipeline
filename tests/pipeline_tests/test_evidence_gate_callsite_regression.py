"""Feature 020 review Phase 3: call-site existence regression tests.

Phase 4 hardening (post-review): Copilot pointed out that the prior
AST walk over the whole function body would pass even if the call
were moved into a dead branch or an unrelated control-flow node.
This file now walks the AST control-flow shape — specifically, it
asserts that ``evaluate_and_record`` is invoked inside the
success-path branch of ``run_warm_corpus`` (the ``if result.exit_code
== ExitCode.SUCCESS:`` body) and inside the single-doc success branch
of ``preprocessing/cli.py`` (the ``if documents_succeeded == 1:``
body).

There is no full end-to-end test of ``run_warm_corpus`` in this
repository today — adding one would require a working stub adapter
that emits ``preprocess_output.json`` to disk, broader infrastructure
than this feature's scope. The branch-scoped AST check covers the
specific regression Copilot warned about (call moved or removed from
the success path).
"""

from __future__ import annotations

import ast
import inspect


def _is_success_branch_corpus(node: ast.AST) -> bool:
    """Match the ``if result.exit_code == ExitCode.SUCCESS:`` test in
    ``run_warm_corpus``."""
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq):
        return False
    # Left: attribute access ending in `.exit_code` (e.g. `result.exit_code`).
    left = test.left
    if not (isinstance(left, ast.Attribute) and left.attr == "exit_code"):
        return False
    # Right: attribute access ending in `.SUCCESS` (e.g. `ExitCode.SUCCESS`).
    right = test.comparators[0]
    if not (isinstance(right, ast.Attribute) and right.attr == "SUCCESS"):
        return False
    return True


def _is_single_doc_success_branch(node: ast.AST) -> bool:
    """Match the ``if documents_succeeded == 1:`` test in the
    single-doc CLI emission path."""
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq):
        return False
    left = test.left
    if not (isinstance(left, ast.Name) and left.id == "documents_succeeded"):
        return False
    right = test.comparators[0]
    if not (isinstance(right, ast.Constant) and right.value == 1):
        return False
    return True


def _calls_in_subtree(subtree: ast.AST, target_name: str) -> bool:
    """Walk ``subtree`` and return True if any ``ast.Call`` invokes
    ``target_name`` as a bare-name function (``evaluate_and_record(...)``).
    """
    for node in ast.walk(subtree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == target_name
        ):
            return True
    return False


def test_run_warm_corpus_calls_evaluate_and_record_in_success_branch() -> None:
    """``pipeline.corpus_run.run_warm_corpus`` MUST call
    ``evaluate_and_record`` from inside the per-document
    ``if result.exit_code == ExitCode.SUCCESS:`` body. A regression
    that moves the call outside that branch (or removes it entirely)
    breaks MI-18 / the FR-006 always-emit contract on successful runs.
    """
    from dartwing_ocr.pipeline.corpus_run import run_warm_corpus

    source = inspect.getsource(run_warm_corpus)
    tree = ast.parse(source)
    success_branches = [
        node for node in ast.walk(tree)
        if _is_success_branch_corpus(node)
    ]
    assert success_branches, (
        "run_warm_corpus must contain an `if result.exit_code == "
        "ExitCode.SUCCESS:` branch — control-flow shape changed."
    )
    in_success = any(
        _calls_in_subtree(ast.Module(body=branch.body, type_ignores=[]),
                          "evaluate_and_record")
        for branch in success_branches
    )
    assert in_success, (
        "run_warm_corpus must call evaluate_and_record() INSIDE the "
        "`if result.exit_code == ExitCode.SUCCESS:` branch. A "
        "regression has moved or removed this call site; the gate "
        "wiring is no longer reached on successful documents."
    )


def test_single_doc_cli_calls_evaluate_and_record_in_success_branch() -> None:
    """The single-doc run_summary emission function
    ``preprocessing.cli._emit_single_doc_run_summary`` MUST call
    ``evaluate_and_record`` from inside the ``if documents_succeeded
    == 1:`` branch. The branch gates whether the gate evaluates at all
    on the single-doc path; moving the call outside it skips
    evaluation entirely.

    Phase 6 hardening (post-review): pinned to the specific function
    by name rather than scanning every function in the module. The
    prior wildcard scan would have passed if any dead-code helper or
    test-only function in the module contained the matching branch
    plus call — a false positive that would let the real emission
    path silently drop the call.
    """
    from dartwing_ocr.preprocessing import cli as preproc_cli

    fn = getattr(preproc_cli, "_emit_single_doc_run_summary", None)
    assert fn is not None, (
        "preprocessing/cli.py must define _emit_single_doc_run_summary; "
        "a regression has renamed or removed the single-doc emission "
        "function."
    )
    source = inspect.getsource(fn)
    tree = ast.parse(source)
    branches = [
        node for node in ast.walk(tree)
        if _is_single_doc_success_branch(node)
    ]
    assert branches, (
        "_emit_single_doc_run_summary must contain an "
        "`if documents_succeeded == 1:` branch — control-flow shape changed."
    )
    in_success = any(
        _calls_in_subtree(ast.Module(body=branch.body, type_ignores=[]),
                          "evaluate_and_record")
        for branch in branches
    )
    assert in_success, (
        "_emit_single_doc_run_summary must call evaluate_and_record() "
        "INSIDE the `if documents_succeeded == 1:` branch. A regression "
        "has moved or removed this call."
    )
