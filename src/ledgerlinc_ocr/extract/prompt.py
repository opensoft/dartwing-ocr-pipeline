"""Prompt rendering for the stage 1 edge extractor.

Deterministic string composition over a given `(packet, template)` pair. No
heavy templating engine — a single `{EVIDENCE_BLOCK}` placeholder inside the
Markdown template is substituted with the serialized packet view.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_PLACEHOLDER = "{EVIDENCE_BLOCK}"


def _serialize_packet(packet: dict[str, Any]) -> str:  # NOSONAR S3776 — evidence-packet serializer — branches over block / line / table / quality fields.
    lines: list[str] = []
    ingestion = packet.get("ingestion_sources", {})
    sources = []
    for name in ("paddleocr_vl", "falcon_ocr", "falcon_perception"):
        src = ingestion.get(name, {}) or {}
        status = src.get("status", "unknown")
        enabled = src.get("enabled", False)
        sources.append(f"{name}=(enabled={enabled}, status={status})")
    lines.append("## ingestion_sources")
    lines.append(", ".join(sources))
    lines.append("")

    for page in packet.get("pages", []):
        page_no = page.get("page_number")
        lines.append(f"## page {page_no}")
        blocks = page.get("blocks", []) or []
        if blocks:
            lines.append("### blocks")
            for block in sorted(blocks, key=lambda b: b.get("reading_order", 0)):
                text = (block.get("text") or "").replace("\n", " ").strip()
                lines.append(f"{block['block_id']}: {text}")
        ocr_lines = page.get("raw_ocr_lines", []) or []
        if ocr_lines:
            lines.append("### raw_ocr_lines")
            for line in ocr_lines:
                text = (line.get("text") or "").replace("\n", " ").strip()
                lines.append(f"{line['line_id']}: {text}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_prompt(
    packet: dict[str, Any],
    template_path: Path,
    _voter_config: Any,
) -> str:
    """Load the Markdown prompt template and substitute the serialized packet
    view for `{EVIDENCE_BLOCK}`.

    The underscore-prefixed ``_voter_config`` is accepted positionally for
    forward compatibility — future prompts may condition on voter metadata —
    but the base template is voter-agnostic and ignores it today.
    """

    template = Path(template_path).read_text(encoding="utf-8")
    evidence = _serialize_packet(packet)
    if _PLACEHOLDER in template:
        return template.replace(_PLACEHOLDER, evidence)
    # Template didn't include the placeholder — append the evidence block so
    # the model still sees the packet. Keeps placeholder-less templates
    # (e.g. the stub's `prompts/stub_noop.md`) usable without special casing.
    return template.rstrip() + "\n\n" + evidence
