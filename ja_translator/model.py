"""翻訳対象の1項目(段落単位)と、その配置計算。PDF と PPTX で共有する。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .fit import FitResult, fit_text, fixed_wrap, text_height
from .fonts import measure

BASELINE = 0.8  # 1行目のベースラインは、行の高さの 80% の位置


@dataclass
class TextUnit:
    id: str
    location: dict  # 元ファイル内の場所(PDFならページ・ブロック、PPTXならスライド・図形の経路)
    source: str
    bbox: tuple[float, float, float, float]  # PDFのページ座標 / PPTXはEMU換算しないpt
    size: float
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)
    align: str = "left"
    bold: bool = False
    machine: str | None = None  # 機械翻訳の結果(リセット用に残す)
    translation: str | None = None  # いま使う訳文(利用者が直した場合もここ)
    scale: float = 1.0  # 利用者が決めた倍率。1.0 のあいだは自動で枠に合わせる
    dx: float = 0.0
    dy: float = 0.0
    background: tuple[float, float, float] | None = None
    extra: dict = field(default_factory=dict)

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> float:
        return self.bbox[3] - self.bbox[1]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TextUnit":
        data = dict(data)
        data["bbox"] = tuple(data["bbox"])
        data["color"] = tuple(data.get("color", (0.0, 0.0, 0.0)))
        if data.get("background") is not None:
            data["background"] = tuple(data["background"])
        return cls(**data)


@dataclass(frozen=True)
class Layout:
    size: float
    lines: list[str]
    fits: bool

    @property
    def height(self) -> float:
        return text_height(len(self.lines), self.size)


def layout_unit(unit: TextUnit, text: str | None = None) -> Layout:
    """訳文を、この項目の枠に配置するためのサイズと行分け。利用者が倍率を決めていれば、縮めずにその大きさで出す"""
    body = (text if text is not None else unit.translation) or ""
    if not body.strip():
        return Layout(size=unit.size, lines=[], fits=True)
    if unit.scale != 1.0:
        size = unit.size * unit.scale
        lines = fixed_wrap(body, unit.width, size, _measurer(unit))
        return Layout(size=size, lines=lines, fits=text_height(len(lines), size) <= unit.height + 0.01)
    result: FitResult = fit_text(body, unit.width, unit.height, unit.size, _measurer(unit))
    return Layout(size=result.font_size, lines=result.lines, fits=result.fits)


def _measurer(unit: TextUnit):
    return lambda text, size: measure(text, size, unit.bold)


def line_x(unit: TextUnit, line: str, size: float) -> float:
    x0, _, x1, _ = unit.bbox
    width = measure(line, size, unit.bold)
    if unit.align == "right":
        return x1 - width
    if unit.align == "center":
        return x0 + (unit.width - width) / 2
    return x0
