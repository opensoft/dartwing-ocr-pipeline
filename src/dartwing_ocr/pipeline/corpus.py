"""--documents-file parsing and warm-corpus orchestration primitives.

Spec FR-023 / FR-024 / FR-025 / FR-028. Research R-007 / R-008 / R-011.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from dartwing_ocr.pipeline.profiles import Stage, StageProfile

_PARENT_TRAVERSAL = ".."


class CorpusParseError(ValueError):
    """Raised when --documents-file cannot be parsed (missing, empty, etc.)."""


@dataclass(frozen=True)
class DocumentEntry:
    """One per-document folder reference parsed from --documents-file.

    ``raw`` preserves the verbatim token (post-strip) as written in the
    file so the warm-corpus run summary can echo it in
    ``per_document[].folder``. ``resolved`` is the absolute Path used
    for filesystem operations. The two MUST stay paired so consumers can
    correlate summary entries back to the originating documents-file
    line, especially when the harness uses relative corpus paths.
    """

    raw: str
    resolved: Path


def parse_documents_file(path: Path) -> list[DocumentEntry]:
    """Read a UTF-8 text file, strip blanks and ``#``-comments, resolve paths.

    Returns a list of ``DocumentEntry`` pairs preserving both the raw
    token (verbatim post-strip) and the absolute resolved path. Paths
    inside the file resolve relative to the file's parent directory
    (R-007). Duplicates are preserved in order; deduplication is a
    harness concern. An empty corpus (zero non-comment lines) is
    rejected.
    """
    if not path.exists() or not path.is_file():
        raise CorpusParseError(
            f"--documents-file {str(path)!r} does not exist or is not a file"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorpusParseError(
            f"--documents-file {str(path)!r}: cannot read: {exc}"
        ) from exc

    base = path.parent.resolve()
    entries: list[DocumentEntry] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(_resolve_document_entry(line, base))

    if not entries:
        raise CorpusParseError(
            f"empty-corpus: --documents-file {str(path)!r} contains no "
            f"document folders (after blank/comment strip)"
        )
    return entries


def _resolve_document_entry(line: str, base: Path) -> DocumentEntry:
    """Resolve one validated documents-file token.

    The CLI contract explicitly supports user-supplied corpus folder paths,
    including absolute paths. We reject traversal in relative entries and
    validate the folder/source.pdf before execution; this parse step only
    canonicalizes the path for later filesystem checks.
    """
    candidate = Path(line)
    if not candidate.is_absolute() and _PARENT_TRAVERSAL in candidate.parts:
        raise CorpusParseError(
            f"--documents-file entry {line!r}: relative parent traversal is "
            "not allowed"
        )
    resolved = candidate if candidate.is_absolute() else (base / candidate)
    return DocumentEntry(raw=line, resolved=resolved.resolve())  # NOSONAR


class WarmInstance(Protocol):
    """Protocol every live stage adapter must satisfy when warmable."""

    def initialize(self) -> None:
        ...

    def close(self) -> None:
        ...


@dataclass
class WarmProfileRegistry:
    """Per-process, stage-scoped registry of warmed live profile instances.

    Adapters register themselves via ``get_or_initialize``; the registry
    runs ``initialize()`` exactly once per ``(stage, implementation, lane)``
    triple and records the wall-clock cost in ``initialization_timings_ns``.
    ``close()`` is invoked unconditionally at corpus-run shutdown.
    """
    instances: dict[tuple[str, str, str | None], WarmInstance]
    initialization_timings_ns: dict[Stage, int]
    factories: dict[
        tuple[str, str, str | None], Callable[[], WarmInstance]
    ]

    @classmethod
    def empty(cls) -> "WarmProfileRegistry":
        return cls(instances={}, initialization_timings_ns={}, factories={})

    def register_factory(
        self,
        *,
        stage: str,
        implementation: str,
        lane: str | None,
        factory: Callable[[], WarmInstance],
    ) -> None:
        """Register a factory that produces a warmable adapter on first use."""
        self.factories[(stage, implementation, lane)] = factory

    def get_or_initialize(
        self,
        *,
        stage: Stage,
        implementation: str,
        lane: str | None,
    ) -> WarmInstance:
        key = (stage, implementation, lane)
        if key in self.instances:
            return self.instances[key]
        if key not in self.factories:
            raise KeyError(
                f"no warm-instance factory registered for {key!r}"
            )
        start = time.monotonic_ns()
        instance = self.factories[key]()
        instance.initialize()
        elapsed = time.monotonic_ns() - start
        self.instances[key] = instance
        # Sum across multiple impl/lane combos within the same stage so the
        # run-summary aggregate by-stage view captures every initialization
        # event (current scope: at most one live impl per stage per run).
        self.initialization_timings_ns[stage] = (
            self.initialization_timings_ns.get(stage, 0) + elapsed
        )
        return instance

    def initialization_seconds(self) -> dict[Stage, float]:
        return {
            stage: round(ns / 1e9, 6)
            for stage, ns in self.initialization_timings_ns.items()
        }

    def close(self) -> None:
        """Close every warmed instance unconditionally; swallow per-instance errors.

        Bare ``except Exception`` is intentional and scoped: ``close()``
        is invoked unconditionally during corpus-run shutdown (success,
        failure, fail-fast abort). Letting any per-instance close-time
        error propagate would mask the run's primary outcome and skip
        sibling instances. Per-instance errors are logged at WARN by
        callers that care; here we MUST clean up the registry.
        """
        import logging

        log = logging.getLogger(__name__)
        for instance in self.instances.values():
            try:
                instance.close()
            except Exception as exc:  # noqa: BLE001 -- contract: see docstring
                log.warning(
                    "warm-instance close() raised; continuing: %s",
                    exc,
                )
        self.instances.clear()


__all__ = [
    "CorpusParseError",
    "DocumentEntry",
    "WarmInstance",
    "WarmProfileRegistry",
    "parse_documents_file",
]
