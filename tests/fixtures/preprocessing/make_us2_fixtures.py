"""Generate multi-page fixtures for US2 tests via Pillow.

Each fixture folder name follows the per-document inv_NNN convention so the
pipeline's document_id regex accepts it.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent

TWO_PAGE_DIR = HERE / "inv_020"
THREE_PAGE_DIR = HERE / "inv_021"

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


def _page(text_lines: list[tuple[str, int]], *, w: int = PAGE_W, h: int = PAGE_H) -> Image.Image:
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    font = _font(42)
    for text, y in text_lines:
        draw.text((100, y), text, fill="black", font=font)
    return img


def build_two_page() -> Path:
    TWO_PAGE_DIR.mkdir(parents=True, exist_ok=True)
    page1 = _page([("Acme Widgets Inc.", 100), ("Page One Body", 200)])
    page2 = _page([("Continuation Page", 100), ("Total Amount: $900.00", 200)])
    out = TWO_PAGE_DIR / "source.pdf"
    page1.save(out, "PDF", resolution=150.0, save_all=True, append_images=[page2])
    return out


def build_three_page_mixed() -> Path:
    THREE_PAGE_DIR.mkdir(parents=True, exist_ok=True)
    page1 = _page([("Alpha Vendor LLC", 100), ("Portrait page one", 200)])
    # Landscape second page — different dimensions
    page2 = _page(
        [("Landscape Page Two", 100), ("Different aspect ratio", 200)],
        w=PAGE_H,
        h=PAGE_W,
    )
    page3 = _page([("Gamma Page Three", 100), ("Back to portrait", 200)])
    out = THREE_PAGE_DIR / "source.pdf"
    page1.save(out, "PDF", resolution=150.0, save_all=True, append_images=[page2, page3])
    return out


if __name__ == "__main__":
    p1 = build_two_page()
    p2 = build_three_page_mixed()
    print(f"wrote {p1}")
    print(f"wrote {p2}")
