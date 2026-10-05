"""コマンドライン: python -m ja_translator.cli 入力.pdf -o 出力.pdf"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .project import Project
from .translate import ClaudeTranslator, FakeTranslator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="英語のPDF/PPTXを、レイアウトを保ったまま日本語にします")
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="出力先(省略時は 入力名_ja.拡張子)")
    parser.add_argument("--fake", action="store_true", help="APIを使わず、テスト用の訳文を入れる")
    args = parser.parse_args(argv)

    out = args.output or args.input.with_name(f"{args.input.stem}_ja{args.input.suffix}")
    project = Project.open(args.input)
    translator = FakeTranslator() if args.fake else ClaudeTranslator()
    translated = project.translate(translator)
    project.export(out)

    print(f"項目 {len(project.units)} 件 / 翻訳 {translated} 件 -> {out}")
    for unit_id, message in project.warnings().items():
        print(f"  注意 [{unit_id}]: {message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
