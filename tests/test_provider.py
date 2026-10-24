from __future__ import annotations

import httpx

from backend.llm import provider


class _Response:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        return self._body


class _Client:
    responses: list[_Response] = []
    requests: list[dict] = []

    def __init__(self, **_: object) -> None:
        pass

    def __enter__(self) -> "_Client":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def post(self, url: str, *, headers: dict[str, str], json: dict) -> _Response:
        self.requests.append({"url": url, "headers": headers, "json": json})
        return self.responses.pop(0)


def test_chat_normalizes_tool_calls(monkeypatch) -> None:
    monkeypatch.setattr(provider, "_provider_config", lambda: ("groq", "https://example.test/chat", "model", {"Authorization": "Bearer secret"}))
    monkeypatch.setattr(provider.httpx, "Client", _Client)
    _Client.responses = [_Response(200, {"choices": [{"message": {
        "content": None,
        "tool_calls": [{"id": "call-1", "function": {"name": "lookup_section", "arguments": '{"id":"ICA-74"}'}}],
    }}]})]

    result = provider.chat([{"role": "user", "content": "hello"}], [{"type": "function"}])

    assert result.text is None
    assert result.tool_calls[0].name == "lookup_section"
    assert result.tool_calls[0].arguments == {"id": "ICA-74"}


def test_chat_retries_once_after_transport_error(monkeypatch) -> None:
    monkeypatch.setattr(provider, "_provider_config", lambda: ("groq", "https://example.test/chat", "model", {}))
    attempts = {"count": 0}

    class RetryingClient(_Client):
        def post(self, url: str, *, headers: dict[str, str], json: dict) -> _Response:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise httpx.ReadTimeout("timed out")
            return _Response(200, {"choices": [{"message": {"content": "ok", "tool_calls": []}}]})

    monkeypatch.setattr(provider.httpx, "Client", RetryingClient)
    result = provider.chat([{"role": "user", "content": "hello"}], [])

    assert result.text == "ok"
    assert attempts["count"] == 2


def test_rate_limit_moves_to_the_next_key(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "first-key, second-key")
    monkeypatch.setattr(provider, "_key_turn", 0)
    monkeypatch.setattr(provider.httpx, "Client", _Client)
    monkeypatch.setattr(provider.time, "sleep", lambda _: (_ for _ in ()).throw(AssertionError("no wait with a spare key")))
    _Client.requests = []
    _Client.responses = [_Response(429, {}), _Response(200, {"choices": [{"message": {"content": "ok", "tool_calls": []}}]})]

    assert provider.chat([{"role": "user", "content": "hello"}], []).text == "ok"
    assert [r["headers"]["Authorization"] for r in _Client.requests] == ["Bearer first-key", "Bearer second-key"]
