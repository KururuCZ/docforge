"""docforge invoice | extract"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import extract as ex
from . import invoice


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="docforge")
    sub = ap.add_subparsers(dest="cmd", required=True)

    inv = sub.add_parser("invoice", help="CSV / JSON / Google Sheet CSV URL -> invoice + receipt PDFs")
    inv.add_argument("source", help="path to .csv/.json, or a published Google Sheet CSV URL")
    inv.add_argument("--brand", type=Path, required=True, help="brand.json (name, logo, colours, tax)")
    inv.add_argument("--out", type=Path, default=Path("out"))
    inv.add_argument("--no-receipts", action="store_true")

    exp = sub.add_parser("extract", help="PDF -> layout-preserving text with bold/italic marked")
    exp.add_argument("pdf", type=Path)
    exp.add_argument("--out", type=Path, help="output .txt (default: next to the PDF)")
    exp.add_argument("--emphasis", choices=["markdown", "html", "none"], default="markdown")
    exp.add_argument("--no-page-markers", action="store_true")

    a = ap.parse_args(argv)
    if a.cmd == "invoice":
        for p in invoice.run(a.source, a.brand, a.out, receipts=not a.no_receipts):
            print("wrote", p)
    else:
        opt = ex.Options(emphasis=a.emphasis, page_marker="" if a.no_page_markers else "--- Page {n} ---")
        out = a.out or a.pdf.with_suffix(".txt")
        out.write_text(ex.extract(a.pdf, opt), encoding="utf-8")
        print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
