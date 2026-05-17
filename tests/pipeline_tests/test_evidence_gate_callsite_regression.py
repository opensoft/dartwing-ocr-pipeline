"""Feature 020 review Phase 3: call-site existence regression tests.

Copilot Phase 2 review flagged that ``run_warm_corpus()`` (in
``pipeline/corpus_run.py``) and the single-document emission path (in
``preprocessing/cli.py``) wire the evidence gate via the
``evaluate_and_record`` helper, but the existing tests exercise the
helper in isolation — a regression that REMOVES the call from either
production site would not be caught.

This file provides a lightweight regression net via AST inspection:
parse the production module's source, find the named function, walk
its AST, and assert that ``evaluate_and_record`` appears as a call.
The check is hermetic (no subprocess, no stub adapter, no I/O), runs in
milliseconds, and fails loudly if either call site is removed or
renamed.

There is no full end-to-end test of ``run_warm_corpus`` in this
repository today — adding one would require a working stub adapter
that emits ``preprocess_output.json`` to disk, which is broader
infrastructure than this feature's scope. The AST check covers the
specific regression Copilot warned about.
"""

from __future__ import annotations

import ast
import inspect


def _called_names_in(func) -> set[str]:
    """Return the set of bare function/method names invoked inside ``func``.

    Walks the AST of the function's source and collects:
    - ``ast.Call`` whose ``.func`` is a ``Name`` (bare-name call: ``foo(...)``)
    - ``ast.Call`` whose ``.func`` is an ``Attribute`` (method call:
      ``obj.foo(...)``) — we return the attribute name only.
    """
    source = inspect.getsource(func)
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def test_run_warm_corpus_calls_evaluate_and_record() -> None:
    """``pipeline.corpus_run.run_warm_corpus`` MUST call
    ``evaluate_and_record`` on each successful document. A regression
    that drops this call would mean ``evidence_gate_documents`` stays
    empty on successful runs while ``documents_succeeded`` reports
    them — silently breaking MI-18 and the FR-006 always-emit contract.
    """
    from ledgerlinc_ocr.pipeline.corpus_run import run_warm_corpus

    called = _called_names_in(run_warm_corpus)
    assert "evaluate_and_record" in called, (
        "run_warm_corpus must call evaluate_and_record() on each "
        "successful document; a regression has removed or renamed "
        "this call site. See pipeline/corpus_run.py."
    )


def test_single_doc_cli_emission_calls_evaluate_and_record() -> None:
    """``preprocessing.cli._emit_single_doc_run_summary`` (or its
    equivalent successor) MUST call ``evaluate_and_record`` when the
    single-doc run succeeded. Mirrors the corpus-run regression net
    above for the single-doc CLI path.
    """
    from ledgerlinc_ocr.preprocessing import cli as preproc_cli

    # The single-doc summary emitter is the function that constructs
    # the RunSummary for one document. Find it by scanning module
    # functions for the one that calls evaluate_and_record.
    found_in: list[str] = []
    for name, obj in inspect.getmembers(preproc_cli, inspect.isfunction):
        if obj.__module__ != preproc_cli.__name__:
            continue
        try:
            called = _called_names_in(obj)
        except (OSError, TypeError, SyntaxError):
            continue
        if "evaluate_and_record" in called:
            found_in.append(name)
    assert found_in, (
        "preprocessing/cli.py must call evaluate_and_record() in the "
        "single-doc run_summary emission path; a regression has removed "
        "or renamed this call site."
    )
