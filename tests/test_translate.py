import json
from types import SimpleNamespace

from ja_translator.translate import ClaudeTranslator, TranslationCache


class FakeMessages:
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        text = self._replies.pop(0)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


class FakeClient:
    def __init__(self, replies):
        self.messages = FakeMessages(replies)


def _reply(items):
    return json.dumps([{"id": i, "ja": f"訳{i}"} for i in items], ensure_ascii=False)


def test_translates_by_id_and_stores_results(tmp_path):
    client = FakeClient([_reply(["a", "b"])])
    translator = ClaudeTranslator(client=client, cache=TranslationCache(tmp_path / "c.json"))
    result = translator.translate([("a", "Hello there"), ("b", "Good morning")])
    assert result == {"a": "訳a", "b": "訳b"}
    assert len(client.messages.calls) == 1


def test_missing_ids_are_requested_again(tmp_path):
    client = FakeClient([_reply(["a"]), _reply(["b"])])
    translator = ClaudeTranslator(client=client, cache=TranslationCache(tmp_path / "c.json"))
    result = translator.translate([("a", "Hello there"), ("b", "Good morning")])
    assert result == {"a": "訳a", "b": "訳b"}
    assert len(client.messages.calls) == 2


def test_cached_sources_do_not_call_the_api(tmp_path):
    cache_path = tmp_path / "c.json"
    first = ClaudeTranslator(client=FakeClient([_reply(["a"])]), cache=TranslationCache(cache_path))
    first.translate([("a", "Hello there")])

    client = FakeClient([])
    second = ClaudeTranslator(client=client, cache=TranslationCache(cache_path))
    assert second.translate([("x", "Hello there")]) == {"x": "訳a"}
    assert client.messages.calls == []


def test_glossary_is_sent_with_the_request(tmp_path):
    client = FakeClient([_reply(["a"])])
    translator = ClaudeTranslator(
        client=client,
        glossary={"Dashboard": "ダッシュボード"},
        cache=TranslationCache(tmp_path / "c.json"),
    )
    translator.translate([("a", "Open the Dashboard")])
    user_message = client.messages.calls[0]["messages"][0]["content"]
    assert "Dashboard => ダッシュボード" in user_message


def test_non_json_reply_is_retried_then_skipped(tmp_path):
    client = FakeClient(["ごめんなさい", "ごめんなさい", "ごめんなさい"])
    translator = ClaudeTranslator(client=client, cache=TranslationCache(tmp_path / "c.json"))
    assert translator.translate([("a", "Hello there")]) == {}
