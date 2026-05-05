"""Unit tests for --documents-file parsing and WarmProfileRegistry.

Covers Spec FR-023 / FR-024 / FR-025; Research R-007 / R-008 / R-011.
Design checklist CHK031 / CHK032 / CHK052.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlinc_ocr.pipeline.corpus import (
    CorpusParseError,
    DocumentEntry,
    WarmProfileRegistry,
    parse_documents_file,
)


# ---------------------------------------------------------------------------
# parse_documents_file (R-007)
# ---------------------------------------------------------------------------

def test_parse_documents_file_returns_entries_in_order(tmp_path: Path):
    docs_file = tmp_path / "corpus.txt"
    (tmp_path / "inv_001_easy").mkdir()
    (tmp_path / "inv_002_easy").mkdir()
    docs_file.write_text(
        "inv_001_easy\n"
        "inv_002_easy\n",
        encoding="utf-8",
    )
    result = parse_documents_file(docs_file)
    assert all(isinstance(e, DocumentEntry) for e in result)
    assert [e.resolved.name for e in result] == ["inv_001_easy", "inv_002_easy"]


def test_parse_documents_file_preserves_raw_token_verbatim(tmp_path: Path):
    """Item 3: per_document[].folder must echo the original token, not resolve."""
    sub = tmp_path / "harness"
    sub.mkdir()
    docs_file = sub / "list.txt"
    (sub / "inv_007_hard").mkdir()
    docs_file.write_text("inv_007_hard\n", encoding="utf-8")
    result = parse_documents_file(docs_file)
    assert result[0].raw == "inv_007_hard"
    # Resolved path is still absolute for filesystem ops.
    assert result[0].resolved.is_absolute()


def test_parse_documents_file_strips_blank_lines(tmp_path: Path):
    docs_file = tmp_path / "corpus.txt"
    (tmp_path / "inv_001_easy").mkdir()
    docs_file.write_text("\n\n   \ninv_001_easy\n\n", encoding="utf-8")
    result = parse_documents_file(docs_file)
    assert len(result) == 1


def test_parse_documents_file_strips_hash_comments(tmp_path: Path):
    docs_file = tmp_path / "corpus.txt"
    (tmp_path / "inv_001_easy").mkdir()
    docs_file.write_text(
        "# header comment\n"
        "inv_001_easy\n"
        "# trailing comment\n",
        encoding="utf-8",
    )
    result = parse_documents_file(docs_file)
    assert len(result) == 1
    assert result[0].resolved.name == "inv_001_easy"


def test_parse_documents_file_resolves_relative_to_file_parent(tmp_path: Path):
    """R-007: relative entries resolve relative to the file's parent dir."""
    sub = tmp_path / "harness"
    sub.mkdir()
    docs_file = sub / "list.txt"
    target = sub / "inv_007_hard"
    target.mkdir()
    docs_file.write_text("inv_007_hard\n", encoding="utf-8")
    result = parse_documents_file(docs_file)
    assert result[0].resolved == target.resolve()
    assert result[0].raw == "inv_007_hard"


def test_parse_documents_file_preserves_duplicates_in_order(tmp_path: Path):
    """A4 / R-007: duplicates are preserved (deduplication is a harness concern)."""
    docs_file = tmp_path / "corpus.txt"
    (tmp_path / "inv_001_easy").mkdir()
    docs_file.write_text(
        "inv_001_easy\n"
        "inv_001_easy\n"
        "inv_001_easy\n",
        encoding="utf-8",
    )
    result = parse_documents_file(docs_file)
    assert len(result) == 3
    assert all(e.resolved.name == "inv_001_easy" for e in result)


def test_parse_documents_file_rejects_missing_file(tmp_path: Path):
    docs_file = tmp_path / "missing.txt"
    with pytest.raises(CorpusParseError, match="does not exist"):
        parse_documents_file(docs_file)


def test_parse_documents_file_rejects_empty_corpus(tmp_path: Path):
    docs_file = tmp_path / "corpus.txt"
    docs_file.write_text("\n# only comments\n\n", encoding="utf-8")
    with pytest.raises(CorpusParseError, match="empty-corpus"):
        parse_documents_file(docs_file)


def test_parse_documents_file_rejects_truly_empty_file(tmp_path: Path):
    docs_file = tmp_path / "corpus.txt"
    docs_file.write_text("", encoding="utf-8")
    with pytest.raises(CorpusParseError):
        parse_documents_file(docs_file)


def test_parse_documents_file_supports_absolute_paths(tmp_path: Path):
    docs_file = tmp_path / "corpus.txt"
    target = tmp_path / "elsewhere"
    target.mkdir()
    docs_file.write_text(f"{target}\n", encoding="utf-8")
    result = parse_documents_file(docs_file)
    assert result[0].resolved == target.resolve()
    # Absolute paths in --documents-file remain verbatim in the raw token.
    assert result[0].raw == str(target)


def test_parse_documents_file_rejects_relative_parent_traversal(tmp_path: Path):
    docs_file = tmp_path / "corpus.txt"
    docs_file.write_text("../outside\n", encoding="utf-8")
    with pytest.raises(CorpusParseError, match="parent traversal"):
        parse_documents_file(docs_file)


# ---------------------------------------------------------------------------
# WarmProfileRegistry (R-011) -- one-shot init invariant
# ---------------------------------------------------------------------------

class _FakeWarmInstance:
    init_count = 0
    close_count = 0
    last_id = 0

    def __init__(self) -> None:
        _FakeWarmInstance.last_id += 1
        self.id = _FakeWarmInstance.last_id

    def initialize(self) -> None:
        _FakeWarmInstance.init_count += 1

    def close(self) -> None:
        _FakeWarmInstance.close_count += 1


@pytest.fixture(autouse=True)
def reset_fake_counters():
    _FakeWarmInstance.init_count = 0
    _FakeWarmInstance.close_count = 0
    _FakeWarmInstance.last_id = 0


def test_warm_registry_initializes_exactly_once_per_triple():
    """SC-009 invariant: get_or_initialize must call initialize() exactly once
    per (stage, impl, lane) triple regardless of how many times it is called.
    """
    registry = WarmProfileRegistry.empty()
    registry.register_factory(
        stage="preprocess",
        implementation="ppstructurev3",
        lane="cpu",
        factory=_FakeWarmInstance,
    )
    a = registry.get_or_initialize(
        stage="preprocess", implementation="ppstructurev3", lane="cpu",
    )
    b = registry.get_or_initialize(
        stage="preprocess", implementation="ppstructurev3", lane="cpu",
    )
    c = registry.get_or_initialize(
        stage="preprocess", implementation="ppstructurev3", lane="cpu",
    )
    assert a is b is c
    assert _FakeWarmInstance.init_count == 1


def test_warm_registry_records_initialization_timing():
    registry = WarmProfileRegistry.empty()
    registry.register_factory(
        stage="preprocess",
        implementation="ppstructurev3",
        lane="cpu",
        factory=_FakeWarmInstance,
    )
    registry.get_or_initialize(
        stage="preprocess", implementation="ppstructurev3", lane="cpu",
    )
    timings = registry.initialization_timings_ns
    assert "preprocess" in timings
    assert timings["preprocess"] > 0
    seconds = registry.initialization_seconds()
    assert "preprocess" in seconds
    assert seconds["preprocess"] >= 0.0


def test_warm_registry_close_invokes_every_warmed_instance():
    registry = WarmProfileRegistry.empty()
    registry.register_factory(
        stage="preprocess",
        implementation="ppstructurev3",
        lane="cpu",
        factory=_FakeWarmInstance,
    )
    registry.get_or_initialize(
        stage="preprocess", implementation="ppstructurev3", lane="cpu",
    )
    registry.close()
    assert _FakeWarmInstance.close_count == 1
    # close() also clears the instance map so a subsequent call would re-init.
    assert registry.instances == {}


def test_warm_registry_close_swallows_per_instance_errors():
    class _Boom:
        def initialize(self) -> None:
            pass

        def close(self) -> None:
            raise RuntimeError("close failed")

    registry = WarmProfileRegistry.empty()
    registry.register_factory(
        stage="preprocess",
        implementation="ppstructurev3",
        lane="cpu",
        factory=_Boom,
    )
    registry.get_or_initialize(
        stage="preprocess", implementation="ppstructurev3", lane="cpu",
    )
    # Must not propagate.
    registry.close()


def test_warm_registry_get_without_factory_raises_keyerror():
    registry = WarmProfileRegistry.empty()
    with pytest.raises(KeyError):
        registry.get_or_initialize(
            stage="extract", implementation="ollama", lane="gpu",
        )


def test_warm_registry_is_per_instance_not_global():
    """R-011: registries are per-process, per-CorpusRun. Two registries must not share state."""
    a = WarmProfileRegistry.empty()
    b = WarmProfileRegistry.empty()
    a.register_factory(
        stage="preprocess",
        implementation="ppstructurev3",
        lane="cpu",
        factory=_FakeWarmInstance,
    )
    a.get_or_initialize(
        stage="preprocess", implementation="ppstructurev3", lane="cpu",
    )
    assert b.instances == {}
    assert b.initialization_timings_ns == {}
