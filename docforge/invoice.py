"""CSV / JSON / Google-Sheet CSV -> branded invoice and receipt PDFs (ReportLab)."""
from __future__ import annotations

import csv
import io
import json
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

CENT = Decimal("0.01")


@dataclass
class Brand:
    name: str = "Your Business"
    address: str = ""
    email: str = ""
    logo: str | None = None
    color: str = "#1f4e79"
    currency: str = "$"
    tax_label: str = "Tax"
    tax_rate: float = 0.0             # percent, e.g. 8.25
    page: str = "A4"                  # "A4" or "Letter"
    footer: str = "Thank you for your business."
    payment_terms: str = "Due within 14 days"

    @classmethod
    def load(cls, path: Path) -> "Brand":
        data = json.loads(path.read_text(encoding="utf-8"))
        b = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        if b.logo and not Path(b.logo).is_absolute():
            b.logo = str((path.parent / b.logo).resolve())
        return b


@dataclass
class Item:
    description: str
    qty: Decimal
    unit_price: Decimal

    @property
    def amount(self) -> Decimal:
        return (self.qty * self.unit_price).quantize(CENT, ROUND_HALF_UP)


@dataclass
class Invoice:
    number: str
    date: str
    customer: str
    customer_address: str = ""
    due_date: str = ""
    paid_date: str = ""
    payment_method: str = ""
    items: list[Item] = field(default_factory=list)

    def totals(self, tax_rate: float) -> tuple[Decimal, Decimal, Decimal]:
        sub = sum((i.amount for i in self.items), Decimal(0))
        tax = (sub * Decimal(str(tax_rate)) / 100).quantize(CENT, ROUND_HALF_UP)
        return sub, tax, sub + tax


# ---------- input ----------

def _num(v: str | float | int) -> Decimal:
    return Decimal(str(v).replace(",", "").replace("$", "").strip() or "0")


def _read_rows(source: str) -> list[dict]:
    if source.startswith(("http://", "https://")):
        # Google Sheets: File > Share > Publish to web > CSV, or .../export?format=csv
        with urllib.request.urlopen(source, timeout=30) as resp:
            text = resp.read().decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text)))
    path = Path(source)
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_invoices(source: str) -> list[Invoice]:
    """Flat rows (one per line item, grouped by invoice_number) or nested JSON invoices."""
    rows = _read_rows(source)
    invoices: "OrderedDict[str, Invoice]" = OrderedDict()
    for row in rows:
        row = {k.strip().lower(): v for k, v in row.items() if k}
        num = str(row["invoice_number"])
        inv = invoices.get(num)
        if inv is None:
            inv = invoices[num] = Invoice(
                number=num, date=str(row.get("date", "")), customer=str(row.get("customer", "")),
                customer_address=str(row.get("customer_address", "")),
                due_date=str(row.get("due_date", "")), paid_date=str(row.get("paid_date", "")),
                payment_method=str(row.get("payment_method", "")))
        nested = row.get("items")
        for it in nested if isinstance(nested, list) else [row]:
            inv.items.append(Item(str(it["description"]), _num(it.get("qty", 1)),
                                  _num(it["unit_price"])))
    return list(invoices.values())


# ---------- output ----------

def _money(brand: Brand, v: Decimal) -> str:
    return f"{brand.currency}{v:,.2f}"


def render(inv: Invoice, brand: Brand, out: Path, receipt: bool = False) -> Path:
    accent = colors.HexColor(brand.color)
    size = LETTER if brand.page.lower() == "letter" else A4
    doc = SimpleDocTemplate(str(out), pagesize=size, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"{'Receipt' if receipt else 'Invoice'} {inv.number}",
                            author=brand.name)
    width = size[0] - 36 * mm
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13)
    small = ParagraphStyle("small", parent=base, fontSize=8.5, textColor=colors.HexColor("#555555"))
    title = ParagraphStyle("title", parent=base, fontName="Helvetica-Bold", fontSize=22,
                           leading=26, textColor=accent, alignment=2)
    right = ParagraphStyle("right", parent=base, alignment=2)
    br = lambda s: s.replace("\n", "<br/>")

    logo = Image(brand.logo, width=38 * mm, height=16 * mm, kind="proportional") \
        if brand.logo and Path(brand.logo).exists() else Paragraph(f"<b>{brand.name}</b>", base)
    doc_title = "RECEIPT" if receipt else "INVOICE"
    meta = [f"<b>{doc_title} #</b> {inv.number}", f"<b>Date:</b> {inv.date}"]
    if receipt:
        meta += [f"<b>Paid:</b> {inv.paid_date}"] + \
                ([f"<b>Method:</b> {inv.payment_method}"] if inv.payment_method else [])
    elif inv.due_date:
        meta.append(f"<b>Due:</b> {inv.due_date}")

    header = Table([[logo, Paragraph(doc_title, title)],
                    ["", Paragraph("<br/>".join(meta), right)]],
                   colWidths=[width * 0.5, width * 0.5])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))

    parties = Table([[Paragraph(f"<b>From</b><br/>{brand.name}<br/>{br(brand.address)}"
                                + (f"<br/>{brand.email}" if brand.email else ""), base),
                      Paragraph(f"<b>Bill to</b><br/>{inv.customer}<br/>{br(inv.customer_address)}", base)]],
                    colWidths=[width * 0.5, width * 0.5])
    parties.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 0)]))

    sub, tax, total = inv.totals(brand.tax_rate)
    rows = [["Description", "Qty", "Unit price", "Amount"]]
    for it in inv.items:
        rows.append([Paragraph(it.description, base), f"{it.qty.normalize():f}",
                     _money(brand, it.unit_price), _money(brand, it.amount)])
    n_items = len(rows)
    rows += [["", "", "Subtotal", _money(brand, sub)],
             ["", "", f"{brand.tax_label} ({brand.tax_rate:g}%)", _money(brand, tax)],
             ["", "", "Total paid" if receipt else "Total due", _money(brand, total)]]
    lines = Table(rows, colWidths=[width * 0.52, width * 0.1, width * 0.19, width * 0.19],
                  repeatRows=1)
    lines.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, n_items - 1), [colors.white, colors.HexColor("#f3f6fa")]),
        ("LINEBELOW", (0, n_items - 1), (-1, n_items - 1), 0.6, accent),
        ("FONTNAME", (2, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (2, -1), (-1, -1), 0.8, accent),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story = [header, Spacer(1, 8 * mm), parties, Spacer(1, 8 * mm), lines, Spacer(1, 10 * mm)]
    if receipt:
        stamp = ParagraphStyle("stamp", parent=base, fontName="Helvetica-Bold", fontSize=16,
                               textColor=colors.HexColor("#1a7f37"))
        story += [Paragraph("PAID IN FULL", stamp), Spacer(1, 4 * mm)]
    else:
        story += [Paragraph(f"<b>Payment terms:</b> {brand.payment_terms}", base), Spacer(1, 4 * mm)]
    story.append(Paragraph(brand.footer, small))
    doc.build(story)
    return out


def run(source: str, brand_path: Path, out_dir: Path, receipts: bool = True) -> list[Path]:
    brand = Brand.load(brand_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for inv in load_invoices(source):
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in inv.number)
        written.append(render(inv, brand, out_dir / f"invoice_{safe}.pdf"))
        if receipts and inv.paid_date:  # never issue a "paid" receipt for an unpaid invoice
            written.append(render(inv, brand, out_dir / f"receipt_{safe}.pdf", receipt=True))
    return written
