from __future__ import annotations

from fastapi.testclient import TestClient

import backend.main as main
from backend.llm.provider import ProviderError, ToolCall, ToolCallOrText
from backend.tools.voice import facts_from_speech


def model_with(arguments):
    seen = []

    def chat(messages, tools):
        seen.append(messages)
        assert tools[0]["function"]["name"] == "set_facts"
        return ToolCallOrText(tool_calls=[ToolCall(id="f", name="set_facts", arguments=arguments)])

    chat.seen = seen
    return chat


def test_facts_are_checked_and_transcript_redacted() -> None:
    model = model_with({"rent_per_month": 25000, "deposit_inr": 150000, "built_year": 2019, "local_body": "municipal_corporation",
                        "premises_use": "residential", "substantial_renovation_year": 3020})
    result = facts_from_speech("Rent 25000, deposit 1.5 lakh, built 2019, Bengaluru. Call me on 9876543210.", model)

    assert result["facts"] == {"rent_per_month": 25000, "deposit_inr": 150000, "built_year": 2019,
                               "local_body": "municipal_corporation", "premises_use": "residential"}
    assert "9876543210" not in result["transcript"] and "9876543210" not in model.seen[0][1]["content"]


def test_unknown_values_are_dropped() -> None:
    result = facts_from_speech("something", model_with({"local_body": "mars", "rent_per_month": "lots"}))
    assert result["facts"] == {}


def test_voice_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(main, "speech_to_text", lambda audio, name, language: "rent twenty five thousand built in 2019")
    monkeypatch.setattr(main, "provider_chat", model_with({"rent_per_month": 25000, "built_year": 2019}))
    client = TestClient(main.app)

    response = client.post("/api/voice", files={"audio": ("speech.webm", b"fake-audio", "audio/webm")}, data={"language": "en"})
    assert response.status_code == 200
    assert response.json()["facts"] == {"rent_per_month": 25000, "built_year": 2019}

    def down(audio, name, language):
        raise ProviderError("offline")

    monkeypatch.setattr(main, "speech_to_text", down)
    assert client.post("/api/voice", files={"audio": ("speech.webm", b"x", "audio/webm")}).status_code == 502
