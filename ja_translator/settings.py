"""Claude API キーの保存と取得。キーは Windows の資格情報マネージャーに保存する(設定ファイルには書かない)。

環境変数 ANTHROPIC_API_KEY が設定されていれば、それを優先する。
"""

from __future__ import annotations

import os

SERVICE = "pdf-ja-translator"
ACCOUNT = "anthropic-api-key"
ENV_VAR = "ANTHROPIC_API_KEY"


def _keyring():
    import keyring

    return keyring


def get_api_key() -> str | None:
    env_value = os.environ.get(ENV_VAR, "").strip()
    if env_value:
        return env_value
    try:
        stored = _keyring().get_password(SERVICE, ACCOUNT)
    except Exception:
        return None
    return stored.strip() if stored and stored.strip() else None


def key_source() -> str | None:
    if os.environ.get(ENV_VAR, "").strip():
        return "env"
    return "stored" if get_api_key() else None


def save_api_key(key: str) -> None:
    value = key.strip()
    if not value.startswith("sk-ant-"):
        raise ValueError("Claude API キーは sk-ant- で始まります。コピーが正しいか確認してください")
    _keyring().set_password(SERVICE, ACCOUNT, value)


def delete_api_key() -> None:
    try:
        _keyring().delete_password(SERVICE, ACCOUNT)
    except Exception:
        pass


def _server_detail(error) -> str:
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        inner = body.get("error")
        if isinstance(inner, dict) and inner.get("message"):
            return str(inner["message"])
    return str(getattr(error, "message", "") or error)


def _with_detail(message: str, error) -> str:
    return f"{message}\n\n[Claude API の表示] {_server_detail(error)}"


def verify_api_key(key: str) -> None:
    """キーで Claude API に問い合わせ、使えるかを確かめる。使えなければ理由を付けて ValueError にする"""
    import anthropic

    client = anthropic.Anthropic(api_key=key.strip(), timeout=20.0)
    try:
        client.models.list(limit=1)
    except anthropic.AuthenticationError as e:
        raise ValueError(_with_detail("キーが正しくありません。コピーし直して、もう一度お試しください。", e)) from e
    except anthropic.PermissionDeniedError as e:
        raise ValueError(_with_detail("このキーでは利用が許可されていません。Anthropic Console でキーの種類と権限を確認してください。", e)) from e
    except anthropic.RateLimitError as e:
        raise ValueError(_with_detail("利用回数の上限に達しています。しばらく待ってから、もう一度お試しください。", e)) from e
    except anthropic.APIConnectionError as e:
        raise ValueError("インターネットに接続できませんでした。接続を確認してください") from e
    except anthropic.APIStatusError as e:
        raise ValueError(_with_detail(f"Claude API がエラーを返しました(コード {e.status_code})。", e)) from e
