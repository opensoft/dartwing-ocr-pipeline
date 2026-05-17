"""Generate US4 table fixtures via Pillow.

- inv_040_with_table: single-page invoice with a visible 3-row × 4-column grid.
- inv_041_no_table: single-page invoice with text only, no tabular structure.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent

WITH_TABLE_DIR = HERE / "inv_040_with_table"
NO_TABLE_DIR = HERE / "inv_041_no_table"

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


def _base_page() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    draw = ImageDraw.Draw(img)
    return img, draw


def build_with_table() -> Path:
    WITH_TABLE_DIR.mkdir(parents=True, exist_ok=True)
    img, draw = _base_page()
    big = _font(48)
    small = _font(32)

    draw.text((100, 80), "Tabular Invoice Co.", fill="black", font=big)
    draw.text((100, 160), "Invoice #1042", fill="black", font=small)

    # 3 rows × 4 columns grid. Header row + 2 data rows.
    left, top = 100, 360
    col_widths = [260, 260, 260, 260]
    row_height = 110
    rows = 3
    right = left + sum(col_widths)
    bottom = top + rows * row_height

    # Vertical lines
    x = left
    for w in [0] + col_widths:
        x += w
        draw.line([(x, top), (x, bottom)], fill="black", width=3)
    draw.line([(left, top), (left, bottom)], fill="black", width=3)

    # Horizontal lines
    for r in range(rows + 1):
        y = top + r * row_height
        draw.line([(left, y), (right, y)], fill="black", width=3)

    headers = ["Item", "Qty", "Unit", "Total"]
    row1 = ["Widget", "2", "50.00", "100.00"]
    row2 = ["Gadget", "3", "75.00", "225.00"]
    for i, h in enumerate(headers):
        cx = left + sum(col_widths[:i]) + 20
        draw.text((cx, top + 30), h, fill="black", font=small)
    for i, v in enumerate(row1):
        cx = left + sum(col_widths[:i]) + 20
        draw.text((cx, top + row_height + 30), v, fill="black", font=small)
    for i, v in enumerate(row2):
        cx = left + sum(col_widths[:i]) + 20
        draw.text((cx, top + 2 * row_height + 30), v, fill="black", font=small)

    draw.text((100, bottom + 80), "Grand Total: $325.00", fill="black", font=small)

    out = WITH_TABLE_DIR / "source.pdf"
    img.save(out, "PDF", resolution=150.0)
    return out


def build_no_table() -> Path:
    NO_TABLE_DIR.mkdir(parents=True, exist_ok=True)
    img, draw = _base_page()
    big = _font(48)
    small = _font(32)

    lines = [
        (big, "Prose Vendor Ltd.", 80),
        (small, "Invoice #2020", 170),
        (small, "Thank you for your recent order.", 300),
        (small, "Amount due this month: five hundred dollars.", 370),
        (small, "Please remit payment within thirty days.", 440),
        (small, "Sincerely,", 600),
        (small, "Prose Vendor Ltd. Accounting", 660),
    ]
    for font, text, y in lines:
        draw.text((100, y), text, fill="black", font=font)

    out = NO_TABLE_DIR / "source.pdf"
    img.save(out, "PDF", resolution=150.0)
    return out


if __name__ == "__main__":
    for p in (build_with_table(), build_no_table()):
        print(f"wrote {p}")
