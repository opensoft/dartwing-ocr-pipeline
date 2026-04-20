"""Generate a deterministic single-page fixture PDF for US1 tests.

Renders a small synthetic invoice image and saves it as a one-page PDF via Pillow.
Reproducible: identical inputs → identical bytes (no randomness).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "inv_001"
OUT_PDF = OUT_DIR / "source.pdf"

# 300 DPI letter: 2550x3300. We use a smaller canvas to keep the fixture cheap;
# PaddleOCR works fine on smaller pages.
PAGE_W, PAGE_H = 1275, 1650

LINES = [
    ("Acme Widgets Inc.", 80),
    ("123 Main Street, Springfield, IL 62701", 160),
    ("Invoice #: 12345", 260),
    ("Date: 2026-04-20", 320),
    ("Bill To: Globex Corp", 400),
    ("Widget assembly services", 500),
    ("Total Amount: $1,250.00", 600),
    ("Thank you for your business!", 700),
]


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        p = Path(candidate)
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


def build() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    draw = ImageDraw.Draw(img)
    font = _font(42)
    for text, y in LINES:
        draw.text((100, y), text, fill="black", font=font)
    img.save(OUT_PDF, "PDF", resolution=150.0)
    return OUT_PDF


if __name__ == "__main__":
    path = build()
    print(f"wrote {path}")
