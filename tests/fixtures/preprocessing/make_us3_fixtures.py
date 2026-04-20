"""Generate US3 fixtures for partial-failure and malformed-input tests.

Folder layout uses the `inv_NNN` per-document convention so the pipeline's
document_id regex accepts them. The tasks.md naming hints (`us3_blank_page`,
`us3_encrypted`, etc.) are encoded via suffixed folder names
`inv_0NN_<suffix>` where the regex strips anything after `inv_XXX`.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent

PARTIAL_DIR = HERE / "inv_030_partial_failure"
BLANK_DIR = HERE / "inv_031_blank_page"
ENCRYPTED_DIR = HERE / "inv_032_encrypted"
MALFORMED_DIR = HERE / "inv_033_malformed"
NON_PDF_DIR = HERE / "inv_034_non_pdf"
ZERO_PAGE_DIR = HERE / "inv_035_zero_page"

PAGE_W, PAGE_H = 1275, 1650


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        p = Path(candidate)
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


def _text_page(lines: list[tuple[str, int]]) -> Image.Image:
    img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    draw = ImageDraw.Draw(img)
    font = _font(42)
    for text, y in lines:
        draw.text((100, y), text, fill="black", font=font)
    return img


def _blank_page() -> Image.Image:
    return Image.new("RGB", (PAGE_W, PAGE_H), "white")


def build_partial_failure() -> Path:
    """3 readable pages; per-page rasterization failure is simulated via monkeypatch."""
    PARTIAL_DIR.mkdir(parents=True, exist_ok=True)
    p1 = _text_page([("Partial Vendor Inc.", 100), ("Page One Clean", 200)])
    p2 = _text_page([("Page Two (will be simulated-failed in test)", 100)])
    p3 = _text_page([("Page Three Clean", 100), ("Total $500", 200)])
    out = PARTIAL_DIR / "source.pdf"
    p1.save(out, "PDF", resolution=150.0, save_all=True, append_images=[p2, p3])
    return out


def build_blank_page() -> Path:
    """Page 1 blank, page 2 has content — silent success, no warning."""
    BLANK_DIR.mkdir(parents=True, exist_ok=True)
    p1 = _blank_page()
    p2 = _text_page([("After Blank Vendor", 100), ("Some content", 200)])
    out = BLANK_DIR / "source.pdf"
    p1.save(out, "PDF", resolution=150.0, save_all=True, append_images=[p2])
    return out


def build_encrypted() -> Path:
    """Password-protected PDF — CLI must exit 2 without writing an artifact."""
    import io

    from pypdf import PdfReader, PdfWriter

    ENCRYPTED_DIR.mkdir(parents=True, exist_ok=True)
    page = _text_page([("Sensitive content", 100)])
    buf = io.BytesIO()
    page.save(buf, "PDF", resolution=150.0)
    buf.seek(0)
    reader = PdfReader(buf)
    writer = PdfWriter(clone_from=reader)
    writer.encrypt(user_password="correct-horse", owner_password="staple-battery")
    out = ENCRYPTED_DIR / "source.pdf"
    with out.open("wb") as f:
        writer.write(f)
    return out


def build_malformed() -> Path:
    """Truncated PDF — valid magic header, but body is chopped off."""
    MALFORMED_DIR.mkdir(parents=True, exist_ok=True)
    page = _text_page([("This will get truncated", 100)])
    tmp = MALFORMED_DIR / "_full.pdf"
    page.save(tmp, "PDF", resolution=150.0)
    data = tmp.read_bytes()
    tmp.unlink()
    out = MALFORMED_DIR / "source.pdf"
    out.write_bytes(data[: len(data) // 3])
    return out


def build_non_pdf() -> Path:
    """Plain text file masquerading as a PDF — fails magic-byte check."""
    NON_PDF_DIR.mkdir(parents=True, exist_ok=True)
    out = NON_PDF_DIR / "source.pdf"
    out.write_text("This is not a PDF. Just plain text.\n", encoding="utf-8")
    return out


def build_zero_page() -> Path:
    """Hand-crafted minimal PDF whose /Pages has /Count 0 and /Kids []."""
    ZERO_PAGE_DIR.mkdir(parents=True, exist_ok=True)
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n",
    ]
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    body = b""
    offsets = [0]
    body += header
    for obj in objects:
        offsets.append(len(header) + len(body) - len(header))
        body += obj
    xref_offset = len(header) + len(body) - len(header)
    xref = b"xref\n0 3\n0000000000 65535 f \n"
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n \n".encode("ascii")
    trailer = b"trailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n"
    pdf_bytes = header + body[len(header):] + xref + trailer + f"{xref_offset}\n%%EOF\n".encode("ascii")
    out = ZERO_PAGE_DIR / "source.pdf"
    out.write_bytes(pdf_bytes)
    return out


def build_all() -> list[Path]:
    return [
        build_partial_failure(),
        build_blank_page(),
        build_encrypted(),
        build_malformed(),
        build_non_pdf(),
        build_zero_page(),
    ]


if __name__ == "__main__":
    for p in build_all():
        print(f"wrote {p}")
