"""日本語フォントの選択。Windows に入っている游ゴシック・メイリオを使い、無ければ PDF 組み込みの日本語フォントにする。

PDF に埋め込むときは、使う文字だけを残したサブセットにする(フォント全体を埋めると数十MBになるため)。
"""

from __future__ import annotations

import os
import string
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import pymupdf as fitz

BUILTIN = "japan-s"
_FONT_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
_REGULAR = ("YuGothM.ttc", "meiryo.ttc", "msgothic.ttc")
_BOLD = ("YuGothB.ttc", "meiryob.ttc")


@dataclass(frozen=True)
class JaFont:
    path: str | None  # None のときは PDF 組み込みの日本語フォント
    bold: bool
    font: fitz.Font

    @property
    def is_builtin(self) -> bool:
        return self.path is None

    def alias(self) -> str:
        return BUILTIN if self.is_builtin else ("JA-B" if self.bold else "JA-R")

    def subset(self, text: str) -> bytes | None:
        if self.is_builtin:
            return None
        return _subset_bytes(self.path, text)

    def register(self, page: fitz.Page, data: bytes | None) -> str:
        """ページにフォントを登録し、描画に使う名前を返す。data はサブセット済みのフォント"""
        if self.is_builtin:
            return BUILTIN
        if data is None:
            page.insert_font(fontname=self.alias(), fontfile=self.path)
        else:
            page.insert_font(fontname=self.alias(), fontbuffer=data)
        return self.alias()


def _first_existing(names: tuple[str, ...]) -> Path | None:
    for name in names:
        candidate = _FONT_DIR / name
        if candidate.exists():
            return candidate
    return None


@lru_cache(maxsize=2)
def get_font(bold: bool = False) -> JaFont:
    path = _first_existing(_BOLD if bold else _REGULAR)
    if path is None and bold:
        return get_font(False)
    if path is None:
        return JaFont(path=None, bold=False, font=fitz.Font(fontname=BUILTIN))
    return JaFont(path=str(path), bold=bold, font=fitz.Font(fontfile=str(path)))


def _subset_bytes(path: str, text: str) -> bytes:
    from fontTools import subset
    from fontTools.ttLib import TTCollection, TTFont

    font = TTCollection(path).fonts[0] if path.lower().endswith(".ttc") else TTFont(path)
    options = subset.Options()
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.notdef_outline = True
    options.hinting = False
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=text + string.printable)
    subsetter.subset(font)
    buf = BytesIO()
    font.save(buf)
    return buf.getvalue()


def measure(text: str, size: float, bold: bool = False) -> float:
    return get_font(bold).font.text_length(text, fontsize=size)
