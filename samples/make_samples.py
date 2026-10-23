"""Build demo inputs: brand config + logo, invoice data, and a styled test PDF for extraction."""
import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HERE = Path(__file__).parent
IN = HERE / "input"


def logo():
    img = Image.new("RGBA", (480, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((10, 30, 150, 170), radius=28, fill="#1f4e79")
    d.polygon([(45, 140), (80, 60), (115, 140)], fill="white")
    try:
        font = ImageFont.truetype("arialbd.ttf", 56)
    except OSError:
        font = ImageFont.load_default()
    d.text((175, 68), "Northwind", fill="#1f4e79", font=font)
    img.save(IN / "logo.png")


def brand():
    (IN / "brand.json").write_text(json.dumps({
        "name": "Northwind Studio",
        "address": "12 Harbour Street\nPortland, ME 04101",
        "email": "billing@northwind.example",
        "logo": "logo.png",
        "color": "#1f4e79",
        "currency": "$",
        "tax_label": "Sales tax",
        "tax_rate": 5.5,
        "page": "Letter",
        "payment_terms": "Due within 14 days by bank transfer",
        "footer": "Northwind Studio · Thank you for your business.",
    }, indent=2), encoding="utf-8")


def data():
    rows = [
        ["invoice_number", "date", "due_date", "customer", "customer_address", "description", "qty", "unit_price", "paid_date", "payment_method"],
        ["INV-1042", "2026-10-20", "2026-11-03", "Acme Retail Ltd", "88 King Road\nBoston, MA 02110", "Product photography (half day)", "1", "450", "2026-10-25", "Bank transfer"],
        ["INV-1042", "2026-10-20", "2026-11-03", "Acme Retail Ltd", "88 King Road\nBoston, MA 02110", "Retouched images", "24", "12.50", "2026-10-25", "Bank transfer"],
        ["INV-1042", "2026-10-20", "2026-11-03", "Acme Retail Ltd", "88 King Road\nBoston, MA 02110", "Rush delivery", "1", "75", "2026-10-25", "Bank transfer"],
        ["INV-1043", "2026-10-21", "2026-11-04", "Blue Fern Cafe", "3 Elm Lane\nSalem, MA 01970", "Menu design", "1", "320", "", ""],
    ]
    with (IN / "invoices.csv").open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    (IN / "invoices.json").write_text(json.dumps([{
        "invoice_number": "INV-1044", "date": "2026-10-22", "due_date": "2026-11-05",
        "customer": "Harbor Books", "customer_address": "41 Water St\nNewport, RI 02840",
        "items": [{"description": "Logo refresh", "qty": 1, "unit_price": 600},
                  {"description": "Business cards (box of 250)", "qty": 2, "unit_price": 38.4}],
    }], indent=2), encoding="utf-8")


def styled_pdf():
    base = ParagraphStyle("b", fontName="Helvetica", fontSize=10.5, leading=14)
    h = ParagraphStyle("h", parent=base, fontName="Helvetica-Bold", fontSize=15, leading=20)
    doc = SimpleDocTemplate(str(IN / "report.pdf"), pagesize=A4)
    table = Table([["Region", "Q1", "Q2", "Change"],
                   ["North", "1,204", "1,388", "+15.3%"],
                   ["South", "980", "912", "-6.9%"],
                   ["West", "2,115", "2,240", "+5.9%"]], colWidths=[110, 70, 70, 70])
    table.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                               ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                               ("GRID", (0, 0), (-1, -1), 0.4, colors.grey)]))
    doc.build([
        Paragraph("Quarterly Field Report", h), Spacer(1, 8),
        Paragraph("Sales improved in <b>two of three regions</b>, while costs stayed "
                  "<i>broadly flat</i>. The South region needs <b><i>urgent review</i></b> "
                  "before the board meeting.", base), Spacer(1, 10),
        table, Spacer(1, 10),
        Paragraph("Note: figures are <i>unaudited</i> and shown in thousands.", base),
        PageBreak(),
        Paragraph("Appendix A — Method", h), Spacer(1, 6),
        Paragraph("Data was collected from <b>store systems</b> on the last business day "
                  "of each quarter.", base),
    ])


if __name__ == "__main__":
    IN.mkdir(parents=True, exist_ok=True)
    logo(); brand(); data(); styled_pdf()
    print("samples written to", IN)
