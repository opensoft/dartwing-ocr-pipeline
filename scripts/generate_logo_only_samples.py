"""Generate 5 synthetic logo_only invoice PDFs.

Each PDF's vendor company name appears ONLY as a rasterized PNG logo at
the top of the page. The company name token does not appear anywhere
else on the page as plain text (letterhead, address, footer, URL, email,
remit-to, watermark).

Outputs:
  tests/sample_invoices/logo_only_*.pdf         (5 invoices)
  tests/sample_invoices/logo_only_reference.md  (ground-truth sheet)
  tests/sample_invoices/logo_only_reference.json
"""

from __future__ import annotations

import json
import math
import re
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class LineItem:
    description: str
    qty: float
    unit_price: float

    @property
    def total(self) -> float:
        return round(self.qty * self.unit_price, 2)


@dataclass
class Vendor:
    company_name: str
    street_1: str
    street_2: str | None
    city: str
    state: str
    postal_code: str
    country: str
    ein: str
    website: str
    phone: str
    email: str
    accent_hex: str  # single accent color used in logo + invoice
    mark_shape: str  # "hex", "circle", "triangle", "diamond", "shield"


@dataclass
class InvoiceCase:
    filename: str
    vendor: Vendor
    bill_to: list[str]
    invoice_number: str
    invoice_date: str
    due_date: str
    line_items: list[LineItem]
    tax_rate: float
    notes: str = ""


# ---------------------------------------------------------------------------
# 5 fictional vendors
# ---------------------------------------------------------------------------

CASES: list[InvoiceCase] = [
    InvoiceCase(
        filename="logo_only_01_cascade_ironworks.pdf",
        vendor=Vendor(
            company_name="Cascade Ironworks",
            street_1="2840 Industrial Way",
            street_2=None,
            city="Reno",
            state="NV",
            postal_code="89502",
            country="US",
            ein="87-3319042",
            website="invoicehub.co",
            phone="(775) 555-0184",
            email="billing@proton.me",
            accent_hex="#8A3B1E",   # rust / copper
            mark_shape="hex",
        ),
        bill_to=[
            "Sierra Commercial Builders",
            "Attn: Accounts Payable",
            "1805 S Virginia St, Suite 210",
            "Reno, NV 89502",
        ],
        invoice_number="INV-20250318-4471",
        invoice_date="2025-03-18",
        due_date="2025-04-17",
        line_items=[
            LineItem("Custom fabrication: 3/8\" plate steel stair stringers (pair)", 4, 842.00),
            LineItem("Welded handrail assemblies, powder-coated black", 6, 318.50),
            LineItem("On-site install labor (certified welder, 6 hrs)", 6, 115.00),
            LineItem("Delivery and rigging - Reno metro", 1, 225.00),
        ],
        tax_rate=0.0820,
        notes="Field measurements completed 2025-03-10. Finish: RAL 9005 textured powder coat.",
    ),
    InvoiceCase(
        filename="logo_only_02_ember_and_quill.pdf",
        vendor=Vendor(
            company_name="Ember & Quill",
            street_1="1144 Polk Street",
            street_2="Suite 3B",
            city="San Francisco",
            state="CA",
            postal_code="94109",
            country="US",
            ein="46-8821073",
            website="paybill.net",
            phone="(415) 555-0231",
            email="accounts@gmail.com",
            accent_hex="#5E2B6E",   # aubergine
            mark_shape="circle",
        ),
        bill_to=[
            "Aperture Coffee Roasters",
            "210 Alabama Street",
            "San Francisco, CA 94110",
        ],
        invoice_number="2026-0041",
        invoice_date="2026-02-09",
        due_date="2026-03-11",
        line_items=[
            LineItem("Brand identity system - discovery & strategy phase", 1, 4800.00),
            LineItem("Primary wordmark + secondary mark exploration (4 rounds)", 1, 6200.00),
            LineItem("Packaging system: 12oz bag, 5lb wholesale sack", 2, 1450.00),
            LineItem("Art direction, photo shoot (half day)", 1, 1800.00),
        ],
        tax_rate=0.0,   # professional services, no sales tax
        notes="Deliverables licensed under agreement dated 2026-01-12. Source files released upon final payment.",
    ),
    InvoiceCase(
        filename="logo_only_03_northwind_forge.pdf",
        vendor=Vendor(
            company_name="Northwind Forge",
            street_1="4521 N Commerce Parkway",
            street_2=None,
            city="North Las Vegas",
            state="NV",
            postal_code="89030",
            country="US",
            ein="91-2208417",
            website="ledgerbox.io",
            phone="(702) 555-0148",
            email="ar-dept@zoho.com",
            accent_hex="#1F3A5F",   # steel blue
            mark_shape="shield",
        ),
        bill_to=[
            "Red Rock Mining Supply",
            "Purchasing Department",
            "9200 W Cheyenne Ave",
            "Las Vegas, NV 89129",
        ],
        invoice_number="SO-558120",
        invoice_date="2025-10-07",
        due_date="2025-11-06",
        line_items=[
            LineItem("Heavy-duty alloy coupler 2.5\" class 40 (P/N DFC-2540)", 24, 184.50),
            LineItem("Heat-treated hitch pin assembly, Grade 8 (P/N HPA-8G)", 48, 42.75),
            LineItem("Structural steel D-ring, 15-ton WLL (P/N DR-15T)", 18, 88.90),
            LineItem("LTL freight, class 85 - Las Vegas", 1, 189.00),
        ],
        tax_rate=0.0825,
        notes="All items carry certified mill test reports. MTRs available on request.",
    ),
    InvoiceCase(
        filename="logo_only_04_halcyon_provisions.pdf",
        vendor=Vendor(
            company_name="Halcyon Provisions",
            street_1="880 Oak Harbor Drive",
            street_2=None,
            city="Sacramento",
            state="CA",
            postal_code="95828",
            country="US",
            ein="33-5598210",
            website="quickremit.app",
            phone="(916) 555-0127",
            email="billing@outlook.com",
            accent_hex="#4F6B2E",   # muted olive
            mark_shape="diamond",
        ),
        bill_to=[
            "Coastline Grocery Cooperative",
            "Receiving Dock 3",
            "1420 Marine Way",
            "Monterey, CA 93940",
        ],
        invoice_number="SHIP-2026-02-22-7781",
        invoice_date="2026-02-22",
        due_date="2026-03-24",
        line_items=[
            LineItem("Stone-milled heritage wheat flour, 50lb sack", 20, 58.00),
            LineItem("Cold-pressed olive oil, 3L tin (case of 4)", 12, 142.50),
            LineItem("Aged sheep's milk cheese, 8lb wheel", 6, 188.00),
            LineItem("Sour cherry preserves, 12oz jar (case of 12)", 8, 64.80),
            LineItem("Refrigerated freight surcharge", 1, 210.00),
        ],
        tax_rate=0.0725,
        notes="Temperature-controlled delivery maintained 34-38F. Case-level lot codes on packing slip.",
    ),
    InvoiceCase(
        filename="logo_only_05_meridian_slate.pdf",
        vendor=Vendor(
            company_name="Meridian Slate",
            street_1="6710 Sierra Center Parkway",
            street_2="Suite 120",
            city="Reno",
            state="NV",
            postal_code="89511",
            country="US",
            ein="52-4407291",
            website="sendinvoice.co",
            phone="(775) 555-0109",
            email="accounting@fastmail.com",
            accent_hex="#3A3F47",   # charcoal slate
            mark_shape="triangle",
        ),
        bill_to=[
            "Tahoe Heritage Builders",
            "Attn: Project 2041-Lakeshore",
            "455 N Lake Blvd",
            "Tahoe City, CA 96145",
        ],
        invoice_number="MS-2025-11-14-0902",
        invoice_date="2025-11-14",
        due_date="2025-12-14",
        line_items=[
            LineItem("Natural Pennsylvania quarried tile, 12\" x 24\" (per sq ft)", 820, 14.60),
            LineItem("Copper ridge cap, 10' sections (each)", 28, 168.00),
            LineItem("Stainless ring-shank fasteners, 5lb bucket", 14, 42.75),
            LineItem("Ice &amp; water barrier underlayment, 225 sqft roll", 16, 98.50),
            LineItem("Crane-assisted rooftop delivery, half day", 1, 1150.00),
        ],
        tax_rate=0.0820,
        notes="Material certified ASTM C406 Grade S1. Delivery scheduled for 2025-11-21, weather permitting.",
    ),
]


# ---------------------------------------------------------------------------
# Logo rendering (PIL)
# ---------------------------------------------------------------------------

FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _draw_mark(draw: ImageDraw.ImageDraw, shape: str, box: tuple[int, int, int, int], color: tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    r = min(x1 - x0, y1 - y0) / 2

    if shape == "circle":
        draw.ellipse(box, fill=color)
        # inner ring cutout for visual interest
        inner_r = r * 0.58
        draw.ellipse(
            (cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r),
            fill=(255, 255, 255),
        )
        # small dot
        dot_r = r * 0.22
        draw.ellipse(
            (cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r),
            fill=color,
        )

    elif shape == "hex":
        points = []
        for i in range(6):
            angle = math.radians(60 * i - 30)
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        draw.polygon(points, fill=color)
        # inner hex (white) for depth
        inner_pts = []
        ir = r * 0.62
        for i in range(6):
            angle = math.radians(60 * i - 30)
            inner_pts.append((cx + ir * math.cos(angle), cy + ir * math.sin(angle)))
        draw.polygon(inner_pts, fill=(255, 255, 255))
        # vertical bar inside
        bar_w = r * 0.18
        draw.rectangle((cx - bar_w, cy - r * 0.4, cx + bar_w, cy + r * 0.4), fill=color)

    elif shape == "triangle":
        points = [
            (cx, y0 + r * 0.05),
            (x0 + r * 0.1, y1 - r * 0.1),
            (x1 - r * 0.1, y1 - r * 0.1),
        ]
        draw.polygon(points, fill=color)
        # inner small triangle
        inner = [
            (cx, cy - r * 0.1),
            (cx - r * 0.45, cy + r * 0.45),
            (cx + r * 0.45, cy + r * 0.45),
        ]
        draw.polygon(inner, fill=(255, 255, 255))

    elif shape == "diamond":
        points = [
            (cx, y0 + 2),
            (x1 - 2, cy),
            (cx, y1 - 2),
            (x0 + 2, cy),
        ]
        draw.polygon(points, fill=color)
        inner = [
            (cx, cy - r * 0.55),
            (cx + r * 0.55, cy),
            (cx, cy + r * 0.55),
            (cx - r * 0.55, cy),
        ]
        draw.polygon(inner, fill=(255, 255, 255))
        # center dot
        dot_r = r * 0.18
        draw.ellipse((cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r), fill=color)

    elif shape == "shield":
        # Shield: top flat, curved bottom
        top_y = y0 + r * 0.05
        mid_y = y0 + r * 0.95
        points = [
            (x0 + r * 0.12, top_y),
            (x1 - r * 0.12, top_y),
            (x1 - r * 0.12, mid_y),
            (cx, y1 - r * 0.05),
            (x0 + r * 0.12, mid_y),
        ]
        draw.polygon(points, fill=color)
        # inner chevron
        cv = [
            (cx, cy - r * 0.35),
            (cx + r * 0.55, cy + r * 0.35),
            (cx, cy + r * 0.15),
            (cx - r * 0.55, cy + r * 0.35),
        ]
        draw.polygon(cv, fill=(255, 255, 255))


def render_logo(vendor: Vendor, out_path: Path) -> None:
    """Render a ~2x1 inch logo PNG at 300 DPI with company name baked in."""
    dpi = 300
    width_in, height_in = 2.5, 1.0
    W, H = int(width_in * dpi), int(height_in * dpi)

    img = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    color = _hex_to_rgb(vendor.accent_hex)

    # Mark on the left, ~square, height ~= full logo height minus padding
    pad = int(H * 0.10)
    mark_size = H - 2 * pad
    mark_box = (pad, pad, pad + mark_size, pad + mark_size)
    _draw_mark(draw, vendor.mark_shape, mark_box, color)

    # Text area to the right
    text_x = pad + mark_size + int(H * 0.15)
    available_w = W - text_x - pad

    # Split name into two stylistic lines if it has an ampersand or >14 chars
    name = vendor.company_name
    if " & " in name:
        line_a, line_b = name.split(" & ", 1)
        line_b = "& " + line_b
    elif " " in name and len(name) > 14:
        parts = name.split(" ")
        midpoint = len(parts) // 2 or 1
        line_a = " ".join(parts[:midpoint])
        line_b = " ".join(parts[midpoint:])
    else:
        line_a, line_b = name, ""

    # Autosize font so the longest line fits the available width
    def fit_font(text: str, max_w: int, max_h: int, path: str) -> ImageFont.FreeTypeFont:
        size = 10
        while size < 400:
            f = ImageFont.truetype(path, size)
            bbox = f.getbbox(text)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if tw > max_w or th > max_h:
                return ImageFont.truetype(path, size - 1)
            size += 2
        return ImageFont.truetype(path, size)

    if line_b:
        max_h_each = int((H - 2 * pad) * 0.48)
        longest = line_a if len(line_a) >= len(line_b) else line_b
        f_a = fit_font(longest, available_w, max_h_each, FONT_BOLD_PATH)
        f_b = f_a
        # Draw stacked
        bbox_a = f_a.getbbox(line_a)
        bbox_b = f_b.getbbox(line_b)
        ha = bbox_a[3] - bbox_a[1]
        hb = bbox_b[3] - bbox_b[1]
        total_h = ha + hb + int(H * 0.03)
        y0_text = (H - total_h) // 2 - bbox_a[1]
        draw.text((text_x, y0_text), line_a, font=f_a, fill=color)
        draw.text(
            (text_x, y0_text + ha + int(H * 0.03) - (bbox_b[1] - bbox_a[1])),
            line_b,
            font=f_b,
            fill=color,
        )
    else:
        max_h = int((H - 2 * pad) * 0.75)
        f = fit_font(line_a, available_w, max_h, FONT_BOLD_PATH)
        bbox = f.getbbox(line_a)
        th = bbox[3] - bbox[1]
        y = (H - th) // 2 - bbox[1]
        draw.text((text_x, y), line_a, font=f, fill=color)

    # Accent underline under the mark side
    underline_y = H - pad
    draw.rectangle(
        (text_x, underline_y - int(H * 0.02), text_x + int(available_w * 0.35), underline_y),
        fill=color,
    )

    img.save(out_path, format="PNG", dpi=(dpi, dpi))


# ---------------------------------------------------------------------------
# Invoice PDF rendering (reportlab)
# ---------------------------------------------------------------------------


def _assert_no_name_leak(case: InvoiceCase) -> None:
    """Fail loudly if any vendor-name token appears outside the logo.

    Tokenizes the company name on whitespace/ampersand and checks all plain
    text fields rendered on the page.
    """
    tokens = {
        t.lower()
        for t in re.split(r"[\s&/]+", case.vendor.company_name)
        if t and t.lower() not in {"the", "and", "of"}
    }
    texts = [
        case.vendor.street_1,
        case.vendor.street_2 or "",
        case.vendor.city,
        case.vendor.state,
        case.vendor.postal_code,
        case.vendor.country,
        case.vendor.ein,
        case.vendor.website,
        case.vendor.phone,
        case.vendor.email,
        case.invoice_number,
        case.notes,
        *case.bill_to,
        *[li.description for li in case.line_items],
    ]
    haystack = " ".join(texts).lower()
    for t in tokens:
        if t in haystack:
            raise AssertionError(
                f"Company-name token '{t}' leaked into plain text for {case.filename}"
            )


def build_invoice(case: InvoiceCase, logo_path: Path, out_path: Path) -> None:
    _assert_no_name_leak(case)

    styles = getSampleStyleSheet()
    small = ParagraphStyle(
        "small", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=11
    )
    body = ParagraphStyle(
        "body", parent=styles["Normal"], fontName="Helvetica", fontSize=10, leading=12
    )
    bodyb = ParagraphStyle(
        "bodyb", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=12
    )
    title = ParagraphStyle(
        "title",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        alignment=2,
        textColor=colors.HexColor(case.vendor.accent_hex),
    )

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.55 * inch,
        title="Invoice",
        author="",
        subject="",
        keywords="",
    )

    story: list = []

    # Top row: logo image left, INVOICE title right
    logo = RLImage(str(logo_path), width=2.0 * inch, height=0.8 * inch)
    logo.hAlign = "LEFT"
    top = Table(
        [[logo, Paragraph("INVOICE", title)]],
        colWidths=[3.2 * inch, 4.0 * inch],
    )
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(top)

    # Accent rule
    rule = Table(
        [[""]],
        colWidths=[7.3 * inch],
        rowHeights=[0.04 * inch],
    )
    rule.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(case.vendor.accent_hex)),
            ]
        )
    )
    story.append(Spacer(1, 0.05 * inch))
    story.append(rule)
    story.append(Spacer(1, 0.2 * inch))

    # Vendor plain-text block (NO company name) + invoice meta side-by-side
    v = case.vendor
    addr_lines = [v.street_1]
    if v.street_2:
        addr_lines.append(v.street_2)
    addr_lines.append(f"{v.city}, {v.state} {v.postal_code}")
    addr_lines.append(v.country)
    addr_lines.append(f"Phone: {v.phone}")
    addr_lines.append(f"Web: {v.website}")
    addr_lines.append(f"Email: {v.email}")
    addr_lines.append(f"Federal ID (EIN): {v.ein}")

    vendor_block = Paragraph("<br/>".join(addr_lines), small)

    meta_tbl = Table(
        [
            ["Invoice #:", case.invoice_number],
            ["Invoice Date:", case.invoice_date],
            ["Due Date:", case.due_date],
        ],
        colWidths=[1.0 * inch, 2.0 * inch],
    )
    meta_tbl.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 10),
                ("FONT", (1, 0), (1, -1), "Helvetica", 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    two_col = Table(
        [[vendor_block, meta_tbl]],
        colWidths=[4.2 * inch, 3.1 * inch],
    )
    two_col.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(two_col)
    story.append(Spacer(1, 0.25 * inch))

    # Bill To
    story.append(Paragraph("BILL TO", bodyb))
    for line in case.bill_to:
        story.append(Paragraph(line, body))
    story.append(Spacer(1, 0.2 * inch))

    # Line items
    rows = [["Description", "Qty", "Unit Price", "Line Total"]]
    for li in case.line_items:
        rows.append(
            [
                li.description,
                f"{li.qty:g}",
                f"${li.unit_price:,.2f}",
                f"${li.total:,.2f}",
            ]
        )
    subtotal = round(sum(li.total for li in case.line_items), 2)
    tax = round(subtotal * case.tax_rate, 2)
    total = round(subtotal + tax, 2)
    rows.append(["", "", "Subtotal", f"${subtotal:,.2f}"])
    rows.append(
        ["", "", f"Tax ({case.tax_rate * 100:.2f}%)", f"${tax:,.2f}"]
    )
    rows.append(["", "", "TOTAL DUE", f"${total:,.2f}"])

    items = Table(
        rows,
        colWidths=[3.8 * inch, 0.7 * inch, 1.2 * inch, 1.4 * inch],
        repeatRows=1,
    )
    items.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(case.vendor.accent_hex)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
                ("FONT", (0, 1), (-1, -4), "Helvetica", 9),
                ("FONT", (0, -3), (-1, -1), "Helvetica-Bold", 10),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -4), 0.25, colors.HexColor("#999999")),
                ("LINEABOVE", (2, -3), (-1, -3), 0.5, colors.black),
                ("LINEABOVE", (2, -1), (-1, -1), 1.0, colors.black),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(items)

    if case.notes:
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("Notes", bodyb))
        story.append(Paragraph(case.notes, body))

    story.append(Spacer(1, 0.3 * inch))
    # Footer: intentionally avoids the company name.
    footer = (
        f"Remit payment by due date above. Please reference invoice number on all payments. "
        f"Questions: {v.email} or {v.phone}."
    )
    footer_style = ParagraphStyle(
        "footer", parent=styles["Normal"], fontName="Helvetica", fontSize=8,
        leading=10, textColor=colors.grey,
    )
    story.append(Paragraph(footer, footer_style))

    doc.build(story)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "tests" / "sample_invoices"
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reference_rows = []
        for case in CASES:
            logo_path = tmp_path / (case.filename.replace(".pdf", "_logo.png"))
            render_logo(case.vendor, logo_path)
            out_pdf = out_dir / case.filename
            build_invoice(case, logo_path, out_pdf)
            print(f"wrote {out_pdf.relative_to(repo_root)}")
            reference_rows.append(
                {
                    "filename": case.filename,
                    "company_name": case.vendor.company_name,
                    "street_1": case.vendor.street_1,
                    "street_2": case.vendor.street_2,
                    "city": case.vendor.city,
                    "state": case.vendor.state,
                    "postal_code": case.vendor.postal_code,
                    "country": case.vendor.country,
                    "ein": case.vendor.ein,
                    "website": case.vendor.website,
                    "phone": case.vendor.phone,
                    "email": case.vendor.email,
                }
            )

    # Reference sheet (markdown + json)
    ref_md = out_dir / "logo_only_reference.md"
    ref_json = out_dir / "logo_only_reference.json"
    with ref_md.open("w") as f:
        f.write("# logo_only ground-truth reference\n\n")
        f.write(
            "Use these values to author `expected.json` for each corresponding "
            "`source.pdf`. The `company_name` appears ONLY as a rasterized logo "
            "image on each PDF; all other fields below are rendered as plain text.\n\n"
        )
        for row in reference_rows:
            f.write(f"## {row['filename']}\n\n")
            for k, v in row.items():
                if k == "filename":
                    continue
                f.write(f"- **{k}**: {v if v is not None else '`null`'}\n")
            f.write("\n")
    with ref_json.open("w") as f:
        json.dump(reference_rows, f, indent=2)
    print(f"wrote {ref_md.relative_to(repo_root)}")
    print(f"wrote {ref_json.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
