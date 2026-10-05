"""動作確認用: 文書を読み込み、翻訳(テスト用の訳文)・書き出し・プレビューを順に試し、結果を記録する。

使い方: PDF-JA-Translator.exe --diagnose 文書.pptx
結果は %LOCALAPPDATA%\\pdf-ja-translator\\diagnose.log に書かれる。API は使わない。
"""

from __future__ import annotations

import os
import platform
import tempfile
import traceback
from datetime import datetime
from pathlib import Path


def log_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "pdf-ja-translator"
    base.mkdir(parents=True, exist_ok=True)
    return base / "diagnose.log"


def run(source: str) -> int:
    lines: list[str] = [f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {platform.platform()}", f"file: {source}"]
    failed = False

    def step(name: str, fn):
        nonlocal failed
        try:
            result = fn()
            shown = result if isinstance(result, str) else type(result).__name__
            lines.append(f"OK   {name}: {shown}")
            return result
        except Exception:
            failed = True
            lines.append(f"FAIL {name}:")
            lines.append(traceback.format_exc())
            return None

    project = step("open", lambda: _open(source))
    if project is not None:
        step("translate(fake)", lambda: _fake_translate(project))
        out = Path(tempfile.gettempdir()) / f"jt-diagnose-{Path(source).stem}_ja{Path(source).suffix}"
        step("export", lambda: (project.export(out), str(out))[1])
        if project.kind == "pptx":
            from .preview import pptx_to_pdf

            pdf = Path(tempfile.gettempdir()) / f"jt-diagnose-{Path(source).stem}.pdf"
            step("preview (PowerPoint)", lambda: str(pptx_to_pdf(out, pdf)))
    lines.append("RESULT: " + ("失敗があります" if failed else "すべて成功"))
    log_path().write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if failed else 0


def _open(source: str):
    from .project import Project

    project = Project.open(source)
    return project


def _fake_translate(project) -> str:
    from .translate import FakeTranslator

    count = project.translate(FakeTranslator(prefix=""))
    return f"{count} 件"
