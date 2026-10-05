import httpx
import anthropic
import pytest

from ja_translator import settings


class MemoryKeyring:
    def __init__(self):
        self.store = {}

    def get_password(self, service, account):
        return self.store.get((service, account))

    def set_password(self, service, account, value):
        self.store[(service, account)] = value

    def delete_password(self, service, account):
        self.store.pop((service, account), None)


@pytest.fixture
def keyring_store(monkeypatch):
    fake = MemoryKeyring()
    monkeypatch.setattr(settings, "_keyring", lambda: fake)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return fake


def test_environment_variable_takes_priority(keyring_store, monkeypatch):
    keyring_store.set_password(settings.SERVICE, settings.ACCOUNT, "sk-ant-api03-stored")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-from-env")
    assert settings.get_api_key() == "sk-ant-api03-from-env"
    assert settings.key_source() == "env"


def test_saved_key_is_used_when_no_environment_variable(keyring_store):
    settings.save_api_key("  sk-ant-api03-saved  ")
    assert settings.get_api_key() == "sk-ant-api03-saved"
    assert settings.key_source() == "stored"


def test_key_without_the_expected_prefix_is_rejected(keyring_store):
    with pytest.raises(ValueError, match="sk-ant-"):
        settings.save_api_key("not-a-key")
    assert settings.get_api_key() is None


def test_deleting_the_saved_key(keyring_store):
    settings.save_api_key("sk-ant-api03-saved")
    settings.delete_api_key()
    assert settings.get_api_key() is None
    assert settings.key_source() is None


def _status_error(cls):
    request = httpx.Request("GET", "https://api.anthropic.com/v1/models")
    response = httpx.Response(401, request=request)
    return cls(message="error", response=response, body=None)


def test_wrong_key_gets_a_plain_japanese_message(monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            self.models = self

        def list(self, **kwargs):
            raise _status_error(anthropic.AuthenticationError)

    monkeypatch.setattr(anthropic, "Anthropic", Client)
    with pytest.raises(ValueError, match="キーが正しくありません"):
        settings.verify_api_key("sk-ant-api03-wrong")


def test_valid_key_passes_the_connection_test(monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            self.models = self

        def list(self, **kwargs):
            return []

    monkeypatch.setattr(anthropic, "Anthropic", Client)
    settings.verify_api_key("sk-ant-api03-ok")


def test_non_claude_text_is_rejected_before_calling_the_api():
    with pytest.raises(ValueError, match="sk-ant-"):
        settings.check_key_format("hello")


def test_usr_style_key_is_passed_on_to_the_server():
    settings.check_key_format("sk-ant-usr01-abc")


def test_admin_key_gets_its_own_explanation():
    with pytest.raises(ValueError, match="管理用"):
        settings.check_key_format("sk-ant-admin01-abc")


def test_api_key_format_is_accepted():
    settings.check_key_format("sk-ant-api03-abc")
