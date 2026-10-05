"""画面プレビュー用に、PPTX を PowerPoint で PDF に書き出す。PowerPoint が無い環境では使えない旨を返す。"""

from __future__ import annotations

from pathlib import Path

PP_SAVE_AS_PDF = 32


class PreviewUnavailable(RuntimeError):
    pass


def pptx_to_pdf(pptx: str | Path, out_pdf: str | Path) -> Path:
    try:
        import pythoncom
        import win32com.client
    except ImportError as e:  # pragma: no cover - pywin32 は必須依存
        raise PreviewUnavailable("pywin32 が入っていません") from e

    source = Path(pptx).resolve()
    target = Path(out_pdf).resolve()
    pythoncom.CoInitialize()
    app = None
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        deck = app.Presentations.Open(str(source), ReadOnly=True, Untitled=False, WithWindow=False)
        try:
            deck.SaveAs(str(target), PP_SAVE_AS_PDF)
        finally:
            deck.Close()
    except Exception as e:
        raise PreviewUnavailable(f"PowerPoint でプレビューを作れませんでした: {e}") from e
    finally:
        if app is not None:
            app.Quit()
        pythoncom.CoUninitialize()
    return target
