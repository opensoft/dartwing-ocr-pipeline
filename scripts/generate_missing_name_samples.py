"""Generate 6 synthetic invoice PDFs with NO vendor company name.

Categories (2 each):
- service companies (plumbing, cleaning)
- product-selling companies (office supplies, auto parts)
- utility companies (water, electric)

Each PDF deliberately omits the company/legal name anywhere on the page
but includes other vendor identifiers: address, phone, website, email,
and (where natural) tax IDs / license numbers.

Outputs are written to tests/sample_invoices/.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


@dataclass
class LineItem:
    description: str
    qty: float
    unit_price: float

    @property
    def total(self) -> float:
        return round(self.qty * self.unit_price, 2)


@dataclass
class Invoice:
    filename: str
    header_block: list[str]          # rendered at top-right / top-left, NO company name
    bill_to: list[str]
    invoice_number: str
    invoice_date: str
    due_date: str
    line_items: list[LineItem]
    tax_rate: float
    footer_block: list[str]          # extra identifiers in footer
    notes: str = ""


def build_invoice(inv: Invoice, out_path: Path) -> None:
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        "header",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
    )
    bold_style = ParagraphStyle(
        "bold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
    )
    title_style = ParagraphStyle(
        "title",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        alignment=2,  # right
    )
    footer_style = ParagraphStyle(
        "footer",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.grey,
    )

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title="Invoice",
        author="",  # leave author blank so metadata doesn't leak a vendor name
    )

    story = []

    # Top row: vendor ID block (NO company name) on left, INVOICE title on right.
    vendor_para = Paragraph("<br/>".join(inv.header_block), header_style)
    title_para = Paragraph("INVOICE", title_style)
    top = Table(
        [[vendor_para, title_para]],
        colWidths=[4.0 * inch, 3.2 * inch],
    )
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(top)
    story.append(Spacer(1, 0.25 * inch))

    # Meta row
    meta_rows = [
        ["Invoice #:", inv.invoice_number, "Invoice Date:", inv.invoice_date],
        ["", "", "Due Date:", inv.due_date],
    ]
    meta_tbl = Table(
        meta_rows,
        colWidths=[1.0 * inch, 2.2 * inch, 1.2 * inch, 2.0 * inch],
    )
    meta_tbl.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 10),
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 10),
                ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(meta_tbl)
    story.append(Spacer(1, 0.2 * inch))

    # Bill-to block
    story.append(Paragraph("BILL TO", bold_style))
    for line in inv.bill_to:
        story.append(Paragraph(line, header_style))
    story.append(Spacer(1, 0.25 * inch))

    # Line items table
    rows = [["Description", "Qty", "Unit Price", "Line Total"]]
    for li in inv.line_items:
        rows.append(
            [
                li.description,
                f"{li.qty:g}",
                f"${li.unit_price:,.2f}",
                f"${li.total:,.2f}",
            ]
        )

    subtotal = round(sum(li.total for li in inv.line_items), 2)
    tax = round(subtotal * inv.tax_rate, 2)
    total = round(subtotal + tax, 2)

    rows.append(["", "", "Subtotal", f"${subtotal:,.2f}"])
    rows.append(
        ["", "", f"Tax ({inv.tax_rate * 100:.2f}%)", f"${tax:,.2f}"]
    )
    rows.append(["", "", "TOTAL DUE", f"${total:,.2f}"])

    items_tbl = Table(
        rows,
        colWidths=[3.8 * inch, 0.7 * inch, 1.2 * inch, 1.4 * inch],
        repeatRows=1,
    )
    items_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
                ("FONT", (0, 1), (-1, -4), "Helvetica", 9),
                ("FONT", (0, -3), (-1, -1), "Helvetica-Bold", 10),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -4), 0.25, colors.grey),
                ("LINEABOVE", (2, -3), (-1, -3), 0.5, colors.black),
                ("LINEABOVE", (2, -1), (-1, -1), 1.0, colors.black),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(items_tbl)

    if inv.notes:
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("Notes", bold_style))
        story.append(Paragraph(inv.notes, header_style))

    story.append(Spacer(1, 0.4 * inch))
    for line in inv.footer_block:
        story.append(Paragraph(line, footer_style))

    doc.build(story)


# ---------------------------------------------------------------------------
# Invoice definitions
# ---------------------------------------------------------------------------

INVOICES: list[Invoice] = [
    # -------- SERVICE COMPANIES (2) --------
    Invoice(
        filename="missing_name_service_plumbing_01.pdf",
        header_block=[
            "4217 W Desert Inn Rd, Suite B",
            "Las Vegas, NV 89102",
            "Phone: (702) 555-0143",
            "24/7 Emergency: (702) 555-0199",
            "billing@desertflowplumb.example.com",
            "NV State Contractor Lic. #0082341  (C-1d Plumbing)",
        ],
        bill_to=[
            "DOTG Property Management",
            "7890 W Sahara Ave",
            "Las Vegas, NV 89117",
        ],
        invoice_number="SRV-20814",
        invoice_date="2021-02-03",
        due_date="2021-03-05",
        line_items=[
            LineItem("Emergency service call - after hours dispatch", 1, 185.00),
            LineItem("Labor - journeyman plumber (3.5 hrs @ $95/hr)", 3.5, 95.00),
            LineItem("Replacement 3/4\" PEX manifold assembly", 1, 142.75),
            LineItem("Copper fittings, solder, flux (misc materials)", 1, 38.20),
        ],
        tax_rate=0.0825,
        footer_block=[
            "Payment terms: Net 30. 1.5% monthly finance charge on balances over 30 days.",
            "Remit checks to PO Box 27418, Las Vegas, NV 89126.",
            "Bonded &amp; insured. Lic. #0082341.",
        ],
        notes="Repair of burst cold-water line in mechanical room. Pressure tested and certified.",
    ),
    Invoice(
        filename="missing_name_service_cleaning_02.pdf",
        header_block=[
            "1520 E University Dr, Ste 204",
            "Tempe, AZ 85281",
            "(480) 555-0267",
            "www.sparkleclean-pros.example.com",
            "accounts-receivable@sparkleclean-pros.example.com",
            "AZ TPT License 21-884910",
        ],
        bill_to=[
            "Horizon Logistics Group",
            "Attn: Facilities",
            "2200 N Central Ave, 14th Fl",
            "Phoenix, AZ 85004",
        ],
        invoice_number="INV-2026-00417",
        invoice_date="2026-03-29",
        due_date="2026-04-28",
        line_items=[
            LineItem("Nightly janitorial service - March 2026 (22 visits)", 22, 185.00),
            LineItem("Carpet extraction - 3rd floor common areas", 1, 640.00),
            LineItem("Restroom deep-clean &amp; restock (quarterly)", 1, 320.00),
            LineItem("Consumables: liners, tissue, soap", 1, 94.65),
        ],
        tax_rate=0.081,
        footer_block=[
            "Thank you for your business. Questions? accounts-receivable@sparkleclean-pros.example.com",
            "ACH: Routing 122105278, Account on file. Please include invoice # in memo.",
        ],
    ),

    # -------- PRODUCT-SELLING COMPANIES (2) --------
    Invoice(
        filename="missing_name_product_office_supply_03.pdf",
        header_block=[
            "Distribution Center #07",
            "5500 Industrial Pkwy",
            "Reno, NV 89506",
            "Sales: (775) 555-0108  |  Fax: (775) 555-0109",
            "orders@officestreampro.example.com",
            "Federal Tax ID: 88-3142059",
        ],
        bill_to=[
            "DOTG Printing",
            "1120 S Decatur Blvd",
            "Las Vegas, NV 89102",
        ],
        invoice_number="SO-0044981",
        invoice_date="2021-01-11",
        due_date="2021-02-10",
        line_items=[
            LineItem("SKU OS-44102 Copy paper 8.5x11 20lb, case of 10 reams", 12, 42.99),
            LineItem("SKU OS-71980 Toner cartridge HP 58X black", 4, 218.50),
            LineItem("SKU OS-33115 File folders letter manila, box/100", 6, 17.80),
            LineItem("SKU OS-90210 Nitrile gloves powder-free L, box/100", 20, 13.25),
            LineItem("Freight - LTL delivery", 1, 72.40),
        ],
        tax_rate=0.0825,
        footer_block=[
            "Remit to PO Box 914, Sparks NV 89432.",
            "Returns accepted within 30 days with RMA. orders@officestreampro.example.com.",
            "Federal Tax ID 88-3142059  |  NV Seller's Permit 1020-44781",
        ],
    ),
    Invoice(
        filename="missing_name_product_autoparts_04.pdf",
        header_block=[
            "Warehouse 3 - Bay 12",
            "880 Commerce Ct",
            "Ontario, CA 91761",
            "Tel (909) 555-0177 Fax (909) 555-0178",
            "parts@truckfleet-distributors.example.com",
            "CA Resale Permit SR-AS 102-884721",
        ],
        bill_to=[
            "Sierra Fleet Services",
            "4410 E Lone Mountain Rd",
            "North Las Vegas, NV 89081",
        ],
        invoice_number="INV-559102",
        invoice_date="2025-11-18",
        due_date="2025-12-18",
        line_items=[
            LineItem("P/N BR-8841 Brake pad set, semi-metallic (front)", 6, 88.50),
            LineItem("P/N OF-22194 Oil filter, heavy-duty diesel", 24, 14.20),
            LineItem("P/N AF-55012 Air filter element 12\" panel", 10, 36.75),
            LineItem("P/N BT-900H Group 31 AGM battery", 3, 289.00),
            LineItem("Core charge - batteries (refundable on return)", 3, 22.00),
            LineItem("Shipping / handling", 1, 58.90),
        ],
        tax_rate=0.0725,
        footer_block=[
            "All parts carry manufacturer warranty only. Core refunds require return within 30 days.",
            "Federal EIN 47-2209118  |  DUNS 079-882-441",
            "Remit: PO Box 44120, Ontario CA 91764",
        ],
    ),

    # -------- UTILITY COMPANIES (2) --------
    Invoice(
        filename="missing_name_utility_water_05.pdf",
        header_block=[
            "Customer Service Center",
            "PO Box 99104",
            "Henderson, NV 89015-9104",
            "Customer service: 1-800-555-0166",
            "www.valleyh2o-district.example.org",
            "Report a leak: leaks@valleyh2o-district.example.org",
        ],
        bill_to=[
            "DOTG Printing - Warehouse B",
            "Service Address: 1120 S Decatur Blvd",
            "Las Vegas, NV 89102",
            "Account #: 4417-882-091",
        ],
        invoice_number="BILL-20210215-4417882091",
        invoice_date="2021-02-15",
        due_date="2021-03-10",
        line_items=[
            LineItem("Water service (1/12/21 - 2/11/21, 31 days)", 1, 34.50),
            LineItem("Consumption: 18,400 gallons @ $3.18 per 1,000 gal", 18.4, 3.18),
            LineItem("Sewer service - commercial fixed", 1, 28.75),
            LineItem("Regional reclamation surcharge", 1, 6.40),
            LineItem("Meter maintenance fee", 1, 2.10),
        ],
        tax_rate=0.0,
        footer_block=[
            "Previous balance: $0.00   Payments received: $82.14   Current charges due on due date above.",
            "Pay online at www.valleyh2o-district.example.org or by phone 1-800-555-0166.",
            "Please include account number 4417-882-091 with payment.",
        ],
        notes="Next meter read scheduled on or about 2021-03-12. Read was actual, not estimated.",
    ),
    Invoice(
        filename="missing_name_utility_electric_06.pdf",
        header_block=[
            "Billing and Payments",
            "PO Box 30150",
            "Reno, NV 89520-3150",
            "Customer care 1-888-555-0142 (24/7)",
            "Outage reporting: outages@highdesert-power.example.com",
            "www.highdesert-power.example.com",
        ],
        bill_to=[
            "Sierra Fleet Services",
            "Service Address: 4410 E Lone Mountain Rd",
            "North Las Vegas, NV 89081",
            "Account #: 2009-44120-7",
            "Rate schedule: GS-2 (Commercial, Secondary)",
        ],
        invoice_number="STMT-2025-11-27-200944120",
        invoice_date="2025-11-27",
        due_date="2025-12-17",
        line_items=[
            LineItem("Basic service charge (monthly)", 1, 42.15),
            LineItem("Energy 4,820 kWh @ $0.08911 per kWh", 4820, 0.08911),
            LineItem("Demand charge 18.4 kW @ $9.42 per kW", 18.4, 9.42),
            LineItem("Fuel &amp; purchased power adjustment", 1, 58.92),
            LineItem("Renewable portfolio rider", 1, 7.65),
            LineItem("Universal energy charge", 1, 1.95),
        ],
        tax_rate=0.038,
        footer_block=[
            "Meter #: M-7728194  Prior read 48,220  Current read 53,040  Multiplier 1",
            "Previous balance $612.08  Payment received -$612.08  Balance forward $0.00",
            "Federal Tax ID on file with PUCN. Rate case docket 24-08022.",
        ],
        notes="Usage this period is 8.2% higher than same period last year. Tips at www.highdesert-power.example.com/save.",
    ),
]


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "tests" / "sample_invoices"
    out_dir.mkdir(parents=True, exist_ok=True)
    for inv in INVOICES:
        out_path = out_dir / inv.filename
        build_invoice(inv, out_path)
        print(f"wrote {out_path.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
