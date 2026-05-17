"""T022: typed error hierarchy."""
from __future__ import annotations

from pathlib import Path

import pytest

from dartwing_ocr.evidence_packet.errors import (
    PacketAssemblyError,
    PacketInvalid,
    PreprocessInputInvalid,
    PreprocessInputMissing,
)


@pytest.mark.parametrize(
    "cls",
    [PreprocessInputMissing, PreprocessInputInvalid, PacketInvalid],
)
def test_subclasses_of_packet_assembly_error(cls: type[PacketAssemblyError]) -> None:
    assert issubclass(cls, PacketAssemblyError)


def test_path_is_preserved() -> None:
    p = Path("/tmp/inv_001/preprocess_output.json")
    err = PreprocessInputMissing("boom", path=p)
    assert err.path == p
    assert "boom" in str(err)


def test_typed_errors_are_siblings_not_parents() -> None:
    # None of the leaf error types should subclass another leaf — so catching
    # one never accidentally swallows another.
    leafs = [PreprocessInputMissing, PreprocessInputInvalid, PacketInvalid]
    for i, a in enumerate(leafs):
        for j, b in enumerate(leafs):
            if i == j:
                continue
            assert not issubclass(a, b), f"{a.__name__} must not subclass {b.__name__}"
