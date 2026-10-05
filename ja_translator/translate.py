"""英日翻訳。Claude API をバッチで呼び、結果は ID で対応付ける。同じ原文はキャッシュから返す。"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

DEFAULT_MODEL = "claude-sonnet-5-5"
BATCH_CHARS = 5000
MAX_RETRIES = 2

SYSTEM_PROMPT = """あなたは英日翻訳の専門家です。PDFやスライドの画面上の文言を日本語に訳します。

守ること:
- 訳文は元の文と同じ役割(見出し・箇条書き・ラベル・本文)が分かる自然な日本語にする
- 元の文字数より大きく増えないよう、簡潔にまとめる(レイアウトの枠に収めるため)
- 数字・単位・記号・固有名詞(製品名・人名・会社名)・URL・メールアドレスは変えない
- 専門用語は一般的な日本語訳を使う。用語集が与えられたら、それに従う
- 入力の "id" と出力の "id" を一致させ、欠けた項目を作らない

出力は JSON 配列のみ。説明文やコードブロックは付けない。
形式: [{"id": "...", "ja": "訳文"}]"""


class Translator(Protocol):
    def translate(self, items: Sequence[tuple[str, str]]) -> dict[str, str]:
        """(id, 原文) の列を受け取り、id -> 訳文 を返す"""


def _cache_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "pdf-ja-translator"
    base.mkdir(parents=True, exist_ok=True)
    return base / "translation-cache.json"


class TranslationCache:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _cache_path()
        try:
            self._data: dict[str, str] = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._data = {}

    @staticmethod
    def key(model: str, glossary: str, source: str) -> str:
        return hashlib.sha256(f"{model}\n{glossary}\n{source}".encode("utf-8")).hexdigest()

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def put(self, key: str, value: str) -> None:
        self._data[key] = value

    def save(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._path)


def _extract_json_array(text: str) -> list[dict]:
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end < start:
        raise ValueError("翻訳結果がJSON配列ではありません")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, list):
        raise ValueError("翻訳結果がJSON配列ではありません")
    return [item for item in data if isinstance(item, dict)]


def _batches(items: Sequence[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    batches: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    size = 0
    for item in items:
        if current and size + len(item[1]) > BATCH_CHARS:
            batches.append(current)
            current, size = [], 0
        current.append(item)
        size += len(item[1])
    if current:
        batches.append(current)
    return batches


class ClaudeTranslator:
    def __init__(
        self,
        client=None,
        model: str | None = None,
        glossary: dict[str, str] | None = None,
        cache: TranslationCache | None = None,
    ) -> None:
        if client is None:
            import anthropic

            from .settings import get_api_key

            api_key = get_api_key()
            if not api_key:
                raise RuntimeError("Claude API キーが設定されていません。「APIキー設定」から登録してください")
            client = anthropic.Anthropic(api_key=api_key)
        self._client = client
        self._model = model or os.environ.get("JT_MODEL") or DEFAULT_MODEL
        self._glossary = glossary or {}
        self._glossary_text = "\n".join(f"{k} => {v}" for k, v in sorted(self._glossary.items()))
        self._cache = cache if cache is not None else TranslationCache()

    @property
    def model(self) -> str:
        return self._model

    def translate(self, items: Sequence[tuple[str, str]]) -> dict[str, str]:
        result: dict[str, str] = {}
        pending: list[tuple[str, str]] = []
        for item_id, source in items:
            cached = self._cache.get(TranslationCache.key(self._model, self._glossary_text, source))
            if cached is not None:
                result[item_id] = cached
            else:
                pending.append((item_id, source))

        for batch in _batches(pending):
            translated = self._translate_batch(batch)
            for item_id, source in batch:
                if item_id in translated:
                    result[item_id] = translated[item_id]
                    self._cache.put(TranslationCache.key(self._model, self._glossary_text, source), translated[item_id])
        self._cache.save()
        return result

    def _translate_batch(self, batch: Sequence[tuple[str, str]]) -> dict[str, str]:
        translated: dict[str, str] = {}
        remaining = list(batch)
        for _ in range(MAX_RETRIES + 1):
            if not remaining:
                break
            translated.update(self._call(remaining))
            remaining = [(i, s) for i, s in remaining if i not in translated]
        return translated

    def _call(self, batch: Sequence[tuple[str, str]]) -> dict[str, str]:
        payload = [{"id": item_id, "text": source} for item_id, source in batch]
        user = "次の英文を日本語に訳してください。\n"
        if self._glossary_text:
            user += f"\n用語集(この訳語を使う):\n{self._glossary_text}\n"
        user += "\n" + json.dumps(payload, ensure_ascii=False)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        wanted = {item_id for item_id, _ in batch}
        out: dict[str, str] = {}
        try:
            items = _extract_json_array(text)
        except ValueError:
            return out
        for item in items:
            item_id = str(item.get("id", ""))
            ja = item.get("ja")
            if item_id in wanted and isinstance(ja, str) and ja.strip():
                out[item_id] = ja.strip()
        return out


_LATIN_LETTER = re.compile(r"[A-Za-z]")
_CJK = re.compile(r"[぀-ヿ㐀-鿿]")


def needs_translation(text: str) -> bool:
    """英字が多く、日本語がほとんど含まれない文字列だけ翻訳する(数字・記号だけの項目は対象外)"""
    latin = len(_LATIN_LETTER.findall(text))
    return latin >= 3 and len(_CJK.findall(text)) < latin


class FakeTranslator:
    """テスト用。原文の先頭に印を付けるだけ(API を呼ばない)"""

    def __init__(self, prefix: str = "【訳】") -> None:
        self._prefix = prefix

    def translate(self, items: Sequence[tuple[str, str]]) -> dict[str, str]:
        return {item_id: f"{self._prefix}{source}" for item_id, source in items}
