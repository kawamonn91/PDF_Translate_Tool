"""PDF の文字ブロックを読み取り、訳文に差し替える。画像・罫線・図形は元のまま残す。"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pymupdf as fitz

from .fit import DEFAULT_LINE_HEIGHT
from .fonts import get_font
from .model import BASELINE, TextUnit, layout_unit, line_x
from .translate import needs_translation

_BULLET = re.compile(r"^\s*([•·・▪■●◦\-–—]|\d+[.)]|\(\d+\)|[a-zA-Z][.)])\s")
_SENTENCE_END = re.compile(r"[.!?:;。]$")
_EDGE_TOLERANCE = 1.5


def _color(value: int) -> tuple[float, float, float]:
    return ((value >> 16 & 255) / 255, (value >> 8 & 255) / 255, (value & 255) / 255)


def _join_lines(lines: list[str]) -> str:
    out = ""
    for i, line in enumerate(lines):
        if i == 0:
            out = line
            continue
        if _SENTENCE_END.search(lines[i - 1].rstrip()) or _BULLET.match(line):
            out += "\n" + line
        else:
            out += " " + line
    return out


def _align(lines: list[tuple[float, float]]) -> str:
    if len(lines) < 2:
        return "left"
    x0s = [a for a, _ in lines]
    x1s = [b for _, b in lines]
    centers = [(a + b) / 2 for a, b in lines]
    if all(abs(v - x0s[0]) <= _EDGE_TOLERANCE for v in x0s):
        return "left"
    if all(abs(v - centers[0]) <= _EDGE_TOLERANCE for v in centers):
        return "center"
    if all(abs(v - x1s[0]) <= _EDGE_TOLERANCE for v in x1s):
        return "right"
    return "left"


def extract_units(path: str | Path) -> list[TextUnit]:
    units: list[TextUnit] = []
    with fitz.open(path) as doc:
        for pno, page in enumerate(doc):
            blocks = page.get_text("dict")["blocks"]
            for bidx, block in enumerate(blocks):
                if block.get("type") != 0:
                    continue
                lines = [ln for ln in block["lines"] if "".join(s["text"] for s in ln["spans"]).strip()]
                if not lines:
                    continue
                source = _join_lines(["".join(s["text"] for s in ln["spans"]).strip() for ln in lines])
                if not needs_translation(source):
                    continue
                spans = [s for ln in lines for s in ln["spans"] if s["text"].strip()]
                main = max(spans, key=lambda s: (s["size"], len(s["text"])))
                bold = bool(main["flags"] & 16) or "bold" in main["font"].lower()
                align = _align([(ln["bbox"][0], ln["bbox"][2]) for ln in lines])
                units.append(
                    TextUnit(
                        id=f"p{pno + 1}-b{bidx}",
                        location={"page": pno, "block": bidx},
                        source=source,
                        bbox=tuple(block["bbox"]),
                        size=round(main["size"], 2),
                        color=_color(main["color"]),
                        align=align,
                        bold=bold,
                    )
                )
    return units


def _background(page: fitz.Page, rect: fitz.Rect) -> tuple[float, float, float] | None:
    """矩形の周囲の色を調べ、単色ならその色を返す(背景が画像や模様なら None)"""
    clip = fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2) & page.rect
    if clip.is_empty or clip.width < 2 or clip.height < 2:
        return None
    pix = page.get_pixmap(clip=clip, dpi=72, colorspace=fitz.csRGB, alpha=False)
    buf, stride, n = pix.samples, pix.stride, pix.n

    def at(x: int, y: int) -> tuple[int, int, int]:
        i = y * stride + x * n
        return (buf[i], buf[i + 1], buf[i + 2])

    border = [at(x, 0) for x in range(pix.width)] + [at(x, pix.height - 1) for x in range(pix.width)]
    border += [at(0, y) for y in range(pix.height)] + [at(pix.width - 1, y) for y in range(pix.height)]
    common, count = Counter(border).most_common(1)[0]
    if count / len(border) < 0.9:
        return None
    return tuple(c / 255 for c in common)


def render(src_path: str | Path, units: list[TextUnit]) -> fitz.Document:
    """元のPDFに、翻訳済みの項目を差し替えたものをメモリ上に作る(元ファイルは変更しない)"""
    doc = fitz.open(src_path)
    by_page: dict[int, list[TextUnit]] = {}
    for unit in units:
        if unit.translation:
            by_page.setdefault(unit.location["page"], []).append(unit)

    used = "".join(u.translation for u in units if u.translation)
    subsets = {bold: get_font(bold).subset(used) for bold in (False, True)}
    for pno, page_units in by_page.items():
        page = doc[pno]
        for unit in page_units:
            background = _background(page, fitz.Rect(unit.bbox))
            page.add_redact_annot(fitz.Rect(unit.bbox), fill=background)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
        names = {bold: get_font(bold).register(page, subsets[bold]) for bold in (False, True)}
        for unit in page_units:
            _draw(page, unit, names[unit.bold])
    return doc


def _draw(page: fitz.Page, unit: TextUnit, fontname: str) -> None:
    layout = layout_unit(unit)
    x0, y0, _, _ = unit.bbox
    real_bold = get_font(True).bold
    for i, line in enumerate(layout.lines):
        baseline = y0 + unit.dy + layout.size * BASELINE + i * layout.size * DEFAULT_LINE_HEIGHT
        x = line_x(unit, line, layout.size) + unit.dx
        kwargs = {}
        if unit.bold and not real_bold:
            kwargs = {"render_mode": 2, "border_width": max(layout.size * 0.04, 0.2)}
        page.insert_text(
            fitz.Point(x, baseline),
            line,
            fontname=fontname,
            fontsize=layout.size,
            color=unit.color,
            **kwargs,
        )


def save(doc: fitz.Document, out_path: str | Path) -> None:
    doc.save(out_path, garbage=3, deflate=True)
