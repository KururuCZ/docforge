"""Run: python -m unittest discover tests"""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate

from docforge import extract, invoice


class InvoiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "brand.json").write_text(json.dumps({"name": "T", "tax_rate": 5.5}))

    def test_csv_groups_rows_and_rounds_tax_half_up(self):
        csv = self.tmp / "i.csv"
        csv.write_text("invoice_number,date,customer,description,qty,unit_price\n"
                       "A1,2026-01-01,C,x,1,450\nA1,2026-01-01,C,y,24,12.50\n"
                       "A1,2026-01-01,C,z,1,75\nA2,2026-01-02,D,w,2,\"1,000\"\n")
        invs = invoice.load_invoices(str(csv))
        self.assertEqual([i.number for i in invs], ["A1", "A2"])
        sub, tax, total = invs[0].totals(5.5)
        self.assertEqual((sub, tax, total), (Decimal("825.00"), Decimal("45.38"), Decimal("870.38")))
        self.assertEqual(invs[1].totals(0)[0], Decimal("2000.00"))

    def test_receipt_only_when_paid(self):
        js = self.tmp / "i.json"
        js.write_text(json.dumps([
            {"invoice_number": "P", "date": "d", "customer": "c", "paid_date": "d2",
             "items": [{"description": "a", "qty": 1, "unit_price": 10}]},
            {"invoice_number": "U", "date": "d", "customer": "c",
             "items": [{"description": "a", "qty": 1, "unit_price": 10}]}]))
        names = {p.name for p in invoice.run(str(js), self.tmp / "brand.json", self.tmp / "out")}
        self.assertEqual(names, {"invoice_P.pdf", "receipt_P.pdf", "invoice_U.pdf"})


class ExtractTests(unittest.TestCase):
    def test_bold_italic_marked_from_fonts(self):
        pdf = Path(tempfile.mkdtemp()) / "t.pdf"
        st = ParagraphStyle("s", fontName="Helvetica", fontSize=11)
        SimpleDocTemplate(str(pdf), pagesize=A4).build(
            [Paragraph("plain <b>bold words</b> and <i>italic</i> and <b><i>both</i></b> end", st)])
        md = extract.extract(pdf)
        self.assertIn("plain **bold words** and *italic* and ***both*** end", md)
        html = extract.extract(pdf, extract.Options(emphasis="html", page_marker=""))
        self.assertIn("<b>bold words</b>", html)
        self.assertIn("<i>italic</i>", html)


if __name__ == "__main__":
    unittest.main()
