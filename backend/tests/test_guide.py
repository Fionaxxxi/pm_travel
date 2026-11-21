from __future__ import annotations

import httpx
import pytest

from backend.app import guide


class FakeClient:
    def __init__(self, response: httpx.Response, **_: object) -> None:
        self.response = response
        self.request: dict[str, object] | None = None

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def post(self, url: str, *, json: dict[str, object], headers: dict[str, str]) -> httpx.Response:
        self.request = {"url": url, "json": json, "headers": headers}
        return self.response


def test_guide_uses_provider_and_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUIDE_MODE", "llm")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client = FakeClient(httpx.Response(200, json={"choices": [{"message": {"content": "山谷间的古道承载着当地往来的记忆。"}}]}))
    monkeypatch.setattr(guide.httpx, "Client", lambda **kwargs: client)

    text = guide._send_request(
        "https://api.deepseek.com/chat/completions",
        "test-secret",
        {"messages": [{"role": "user", "content": "景点资料"}]},
    )

    assert text == "山谷间的古道承载着当地往来的记忆。"
    assert client.request is not None
    assert client.request["url"] == "https://api.deepseek.com/chat/completions"
    assert "test-secret" not in str(client.request["json"])


def test_guide_provider_error_returns_fallback_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient(httpx.Response(503))
    monkeypatch.setattr(guide.httpx, "Client", lambda **kwargs: client)

    text = guide._send_request("https://api.example.test/chat/completions", "test-secret", {})

    assert text is None


def test_guide_without_key_does_not_configure_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUIDE_MODE", "llm")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    assert guide._configuration() is None


