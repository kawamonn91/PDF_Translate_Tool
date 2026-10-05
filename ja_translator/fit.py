"""日本語を枠の中に収めるための折り返しとフォントサイズの決定。

文字幅は計測関数(text, size) -> 幅 で受け取るので、PDF/PPTX のどちらでも同じロジックを使える。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

Measure = Callable[[str, float], float]

# 行末禁則: 直前の文字にくっつけて、行頭に来ないようにする記号
_CLOSING = set("。、，．・」』）)］]】〉》!?！？:;：；")
_OPENING = set("「『（([［【〈《")
_ASCII_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9.,'’%&+\-/#@_]*")

DEFAULT_LINE_HEIGHT = 1.2
MIN_SCALE = 0.55
SCALE_STEP = 0.05


@dataclass(frozen=True)
class FitResult:
    font_size: float
    lines: list[str]
    fits: bool
    scale: float


def _tokens(paragraph: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    while i < len(paragraph):
        ch = paragraph[i]
        m = _ASCII_WORD.match(paragraph, i)
        if m:
            tokens.append(m.group(0))
            i = m.end()
            continue
        if ch == " ":
            if tokens and tokens[-1] != " ":
                tokens.append(" ")
            i += 1
            continue
        tokens.append(ch)
        i += 1
    merged: list[str] = []
    for tok in tokens:
        if merged and len(tok) == 1 and tok in _CLOSING and merged[-1] != " ":
            merged[-1] += tok
        else:
            merged.append(tok)
    return merged


def _split_long(token: str, width: float, size: float, measure: Measure) -> list[str]:
    parts: list[str] = []
    current = ""
    for ch in token:
        if current and measure(current + ch, size) > width:
            parts.append(current)
            current = ch
        else:
            current += ch
    if current:
        parts.append(current)
    return parts


def wrap(text: str, width: float, size: float, measure: Measure) -> list[str]:
    out: list[str] = []
    for paragraph in text.split("\n"):
        line = ""
        for tok in _tokens(paragraph):
            if tok == " ":
                if line:
                    line += " "
                continue
            pieces = _split_long(tok, width, size, measure) if len(tok) > 1 and measure(tok, size) > width else [tok]
            for piece in pieces:
                candidate = line + piece
                if line and measure(candidate.rstrip(), size) > width:
                    out.append(line.rstrip())
                    line = piece
                else:
                    line = candidate
        out.append(line.rstrip())
    return out


def text_height(line_count: int, size: float, line_height: float = DEFAULT_LINE_HEIGHT) -> float:
    if line_count <= 0:
        return 0.0
    return size + (line_count - 1) * size * line_height


def fit_text(
    text: str,
    box_width: float,
    box_height: float,
    base_size: float,
    measure: Measure,
    line_height: float = DEFAULT_LINE_HEIGHT,
    min_scale: float = MIN_SCALE,
) -> FitResult:
    """枠に収まる最大のサイズを探す。収まらなければ最小サイズで返し、fits=False にする。"""
    scale = 1.0
    while scale >= min_scale - 1e-9:
        size = base_size * scale
        lines = wrap(text, box_width, size, measure)
        if text_height(len(lines), size, line_height) <= box_height + 0.01:
            return FitResult(font_size=size, lines=lines, fits=True, scale=scale)
        scale = round(scale - SCALE_STEP, 4)
    size = base_size * min_scale
    lines = wrap(text, box_width, size, measure)
    return FitResult(font_size=size, lines=lines, fits=False, scale=min_scale)


def fixed_wrap(text: str, box_width: float, size: float, measure: Measure) -> list[str]:
    """利用者が決めたサイズで折り返すだけ(枠に収まらなくても、そのまま描く)"""
    return wrap(text, box_width, size, measure)
