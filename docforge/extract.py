"""PDF (live text) -> plain text that keeps the page layout, with bold/italic marked.

Each character's position is mapped onto a fixed character grid, so columns, table
cells and indentation line up the way they do on the page. Emphasis comes from the
font itself (name / flags), never from guessing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

BOLD = re.compile(r"bold|black|heavy|semibold|demi", re.I)
ITALIC = re.compile(r"italic|oblique", re.I)


@dataclass
class Options:
    emphasis: str = "markdown"        # "markdown" (**bold**, *italic*), "html" (<b>, <i>) or "none"
    page_marker: str = "--- Page {n} ---"
    line_tol: float = 2.5             # chars whose tops differ less than this (pt) share a line
    keep_blank_lines: int = 2         # max consecutive blank lines kept (vertical gaps)


def _style(fontname: str) -> str:
    name = fontname.split("+")[-1]
    return ("b" if BOLD.search(name) else "") + ("i" if ITALIC.search(name) else "")


def _wrap(text: str, style: str, mode: str) -> str:
    if not style or mode == "none" or not text.strip():
        return text
    lead = len(text) - len(text.lstrip())
    trail = len(text) - len(text.rstrip())
    core = text.strip()
    if mode == "html":
        if "i" in style:
            core = f"<i>{core}</i>"
        if "b" in style:
            core = f"<b>{core}</b>"
    else:
        mark = {"b": "**", "i": "*", "bi": "***"}[style]
        core = f"{mark}{core}{mark}"
    return " " * lead + core + " " * trail


def _page_text(page, opt: Options) -> str:
    chars = [c for c in page.chars if c["text"].strip() or c["text"] == " "]
    if not chars:
        return ""
    # grid pitch: median width of visible glyphs keeps typical text at ~1 char per cell
    widths = sorted(c["width"] for c in chars if c["text"].strip() and c["width"] > 0)
    pitch = widths[len(widths) // 2] if widths else 5.0
    heights = sorted(c["size"] for c in chars)
    line_h = heights[len(heights) // 2] * 1.2

    chars.sort(key=lambda c: (round(c["top"], 1), c["x0"]))
    lines: list[list[dict]] = []
    for c in chars:
        if lines and abs(c["top"] - lines[-1][0]["top"]) <= opt.line_tol:
            lines[-1].append(c)
        else:
            lines.append([c])

    x_min = min(c["x0"] for c in chars)
    out: list[str] = []
    prev_bottom = None
    for line in lines:
        line.sort(key=lambda c: c["x0"])
        if prev_bottom is not None:
            gap = int((line[0]["top"] - prev_bottom) / line_h)
            out.extend([""] * min(max(gap, 0), opt.keep_blank_lines))
        prev_bottom = max(c["bottom"] for c in line)

        # place glyphs on the grid, then group consecutive same-style runs
        cells: list[tuple[str, str]] = []
        prev = None
        for c in line:
            touching = prev is not None and c["x0"] - prev["x1"] < 0.25 * c["size"]
            if not touching:              # real gap: snap to the grid so columns line up
                col = int(round((c["x0"] - x_min) / pitch))
                col = max(col, len(cells) + (1 if prev is not None else 0))
                while len(cells) < col:
                    cells.append((" ", ""))
            prev = c
            cells.append((c["text"], _style(c.get("fontname", "")) if c["text"].strip() else ""))
        text, run, run_style = [], "", None
        for ch, st in cells:
            st_eff = run_style if ch == " " and run_style is not None else st
            if st_eff != run_style and run:
                text.append(_wrap(run, run_style or "", opt.emphasis))
                run = ""
            run_style = st_eff
            run += ch
        text.append(_wrap(run, run_style or "", opt.emphasis))
        out.append("".join(text).rstrip())
    return "\n".join(out)


def extract(pdf: Path, opt: Options | None = None) -> str:
    opt = opt or Options()
    pages = []
    with pdfplumber.open(pdf) as doc:
        for n, page in enumerate(doc.pages, 1):
            body = _page_text(page, opt)
            pages.append(f"{opt.page_marker.format(n=n)}\n\n{body}\n" if opt.page_marker else body)
    return "\n".join(pages)
