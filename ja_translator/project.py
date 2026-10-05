"""1つの文書の状態。項目の抽出・翻訳・利用者の調整の保存と、書き出しをまとめる。

調整はサイドカー(元ファイル名 + .jt.json)に保存する。書き出しは毎回「元ファイル + 調整」から作り直す。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import pdf_engine, pptx_engine
from .model import TextUnit, layout_unit
from .translate import Translator

SIDECAR_SUFFIX = ".jt.json"
KEEP_FIELDS = ("translation", "machine", "scale", "dx", "dy", "align")
KINDS = {".pdf": "pdf", ".pptx": "pptx"}


def sidecar_path(source: Path) -> Path:
    return source.with_name(source.name + SIDECAR_SUFFIX)


@dataclass
class Project:
    source: Path
    kind: str
    units: list[TextUnit] = field(default_factory=list)
    model: str = ""

    @classmethod
    def open(cls, source: str | Path) -> "Project":
        path = Path(source)
        kind = KINDS.get(path.suffix.lower())
        if kind is None:
            raise ValueError("対応しているのは PDF と PPTX です")
        extract = pdf_engine.extract_units if kind == "pdf" else pptx_engine.extract_units
        project = cls(source=path, kind=kind, units=extract(path))
        project._load_sidecar()
        return project

    def _load_sidecar(self) -> None:
        file = sidecar_path(self.source)
        if not file.exists():
            return
        data = json.loads(file.read_text(encoding="utf-8"))
        self.model = data.get("model", "")
        saved = data.get("units", {})
        for unit in self.units:
            entry = saved.get(unit.id)
            if not entry or entry.get("source") != unit.source:
                continue
            for key in KEEP_FIELDS:
                if key in entry:
                    setattr(unit, key, entry[key])

    def save_sidecar(self) -> None:
        data = {
            "model": self.model,
            "units": {
                u.id: {"source": u.source, **{k: getattr(u, k) for k in KEEP_FIELDS}}
                for u in self.units
                if u.translation is not None
            },
        }
        sidecar_path(self.source).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    def translate(self, translator: Translator, model: str = "", force: bool = False) -> int:
        targets = [u for u in self.units if force or u.translation is None]
        if not targets:
            return 0
        results = translator.translate([(u.id, u.source) for u in targets])
        for unit in targets:
            if unit.id in results:
                unit.machine = results[unit.id]
                unit.translation = results[unit.id]
                unit.scale = 1.0
                unit.dx = unit.dy = 0.0
        if model:
            self.model = model
        return len(results)

    def reset_unit(self, unit_id: str) -> None:
        unit = self.unit(unit_id)
        unit.translation = unit.machine
        unit.scale = 1.0
        unit.dx = unit.dy = 0.0

    def unit(self, unit_id: str) -> TextUnit:
        for unit in self.units:
            if unit.id == unit_id:
                return unit
        raise KeyError(unit_id)

    def warnings(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for unit in self.units:
            if unit.translation and not layout_unit(unit).fits:
                result[unit.id] = "枠に収まりません。訳文を短くするか、サイズを下げてください"
        return result

    def export(self, out_path: str | Path) -> None:
        out = Path(out_path)
        if self.kind == "pdf":
            doc = pdf_engine.render(self.source, self.units)
            pdf_engine.save(doc, out)
            doc.close()
        else:
            pptx_engine.render(self.source, self.units, out)
        self.save_sidecar()

    def translated_count(self) -> int:
        return sum(1 for u in self.units if u.translation)
