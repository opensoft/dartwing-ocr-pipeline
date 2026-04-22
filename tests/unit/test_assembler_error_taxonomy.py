"""FIX 1 / H1 — every concrete AssemblerError subclass must declare its `kind`.

The base `InputRejectedError` previously had a `kind = "unexpected"` default
that could leak wrong taxonomy to stderr if a future subclass forgot to
override it. This test enumerates every concrete subclass, asserts each has
a non-empty documented `kind` and a valid `exit_code`, and — importantly —
will catch any future subclass that forgets to set `kind`.
"""

from __future__ import annotations

import pytest

from ledgerlinc_ocr.assembler import errors as E

# The 8 documented kinds (per data-model.md / spec FR-003…FR-025).
DOCUMENTED_KINDS = {
    "missing_input",
    "unreadable_input",
    "schema_invalid_input",
    "contract_drift",
    "document_id_mismatch",
    "routing_contradiction",
    "output_schema_invalid",
    "unexpected",
}

VALID_EXIT_CODES = {1, 2, 3}


def _all_concrete_subclasses(base: type) -> list[type]:
    """Return every concrete subclass of `base`, walking the hierarchy."""
    seen: set[type] = set()

    def _walk(cls: type) -> None:
        for sub in cls.__subclasses__():
            if sub in seen:
                continue
            seen.add(sub)
            _walk(sub)

    _walk(base)
    # Filter out intermediate abstract bases — in this taxonomy, `InputRejectedError`
    # and `InternalError` are abstract-ish parents that should NOT be instantiated
    # directly; but the runtime still considers them subclasses. We include them
    # only if they're the deepest class a test could hit; here we include all and
    # assert the base's `kind` rules.
    return sorted(seen, key=lambda c: c.__name__)


def test_every_subclass_has_documented_kind_and_exit_code():
    subclasses = _all_concrete_subclasses(E.AssemblerError)
    assert subclasses, "no AssemblerError subclasses discovered — import path broken?"

    for cls in subclasses:
        # InputRejectedError is the deliberate abstract parent with no `kind`
        # default — its sole purpose is to force children to declare `kind`.
        # Skip it here; it's exercised by `test_input_rejected_base_refuses_construction`.
        if cls is E.InputRejectedError:
            continue

        kind = getattr(cls, "kind", None)
        assert isinstance(kind, str) and kind, (
            f"{cls.__name__} must declare a non-empty `kind` string; got {kind!r}"
        )
        assert kind in DOCUMENTED_KINDS, (
            f"{cls.__name__}.kind={kind!r} is not one of the documented kinds "
            f"{sorted(DOCUMENTED_KINDS)}"
        )

        exit_code = getattr(cls, "exit_code", None)
        assert exit_code in VALID_EXIT_CODES, (
            f"{cls.__name__}.exit_code={exit_code!r} is not in {sorted(VALID_EXIT_CODES)}"
        )


def test_input_rejected_base_refuses_construction():
    """The abstract `InputRejectedError` itself must refuse to construct.

    This is the whole point of FIX 1: a subclass that forgets to override
    `kind` inherits `None` from the base, and construction raises
    `NotImplementedError` instead of silently emitting `kind="unexpected"`.
    """
    with pytest.raises(NotImplementedError):
        E.InputRejectedError("oops")


def test_concrete_subclasses_construct_fine():
    """Sanity — every concrete subclass can be constructed."""
    for cls in (
        E.InputMissingError,
        E.InputUnreadableError,
        E.InputSchemaInvalidError,
        E.ContractDriftError,
        E.DocumentIdMismatchError,
        E.RoutingContradictionError,
        E.OutputSchemaInvalidError,
    ):
        exc = cls("test")
        assert isinstance(exc, E.AssemblerError)
        assert exc.kind  # non-empty
