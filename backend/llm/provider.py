"""Single, OpenAI-compatible model-provider boundary.

The rest of the backend depends only on :func:`chat`. Provider credentials are
read from the environment and are never included in exceptions or logs.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field


class ProviderError(RuntimeError):
    """A model request failed or returned an unusable response."""


class ToolCall(BaseModel):
    """A normalized function call returned by a chat completion."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallOrText(BaseModel):
    """The provider-independent result consumed by the tenant agent."""

    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


def _provider_config() -> tuple[str, str, str, dict[str, str]]:
    provider = os.getenv("MODEL_PROVIDER", "groq").strip().casefold()
    if provider == "groq":
        key = os.getenv("GROQ_API_KEY", "")
        url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        headers = {"Authorization": f"Bearer {key}"}
    elif provider == "sarvam":
        key = os.getenv("SARVAM_API_KEY", "")
        url = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai/v1").rstrip("/")
        model = os.getenv("SARVAM_MODEL", "sarvam-105b")
        headers = {"Authorization": f"Bearer {key}", "api-subscription-key": key}
    else:
        raise ProviderError("MODEL_PROVIDER must be groq or sarvam")
    if not key:
        raise ProviderError(f"No API key configured for {provider}")
    return provider, f"{url}/chat/completions", model, headers


def _parse_tool_calls(message: dict[str, Any]) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for index, raw_call in enumerate(message.get("tool_calls") or []):
        function = raw_call.get("function") or {}
        raw_arguments = function.get("arguments", {})
        if isinstance(raw_arguments, str):
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError as exc:
                raise ProviderError("Model returned invalid tool arguments") from exc
        else:
            arguments = raw_arguments
        if not isinstance(arguments, dict):
            raise ProviderError("Model tool arguments must be an object")
        name = function.get("name")
        if not isinstance(name, str) or not name:
            raise ProviderError("Model returned a tool call without a name")
        call_id = raw_call.get("id") or f"tool_call_{index + 1}"
        calls.append(ToolCall(id=str(call_id), name=name, arguments=arguments))
    return calls


def _response_result(payload: dict[str, Any]) -> ToolCallOrText:
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("Model response did not contain a chat message") from exc
    if not isinstance(message, dict):
        raise ProviderError("Model response message was not an object")
    text = message.get("content")
    if text is not None and not isinstance(text, str):
        text = str(text)
    result = ToolCallOrText(text=text, tool_calls=_parse_tool_calls(message))
    if not result.text and not result.tool_calls:
        raise ProviderError("Model response was empty")
    return result


def chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ToolCallOrText:
    """Call the configured provider, retrying one time with a 30-second timeout."""
    if not isinstance(messages, list) or not isinstance(tools, list):
        raise ValueError("messages and tools must be lists")
    _, url, model, headers = _provider_config()
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 2500,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    timeout = httpx.Timeout(30.0)
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                raise ProviderError(f"Model request failed with HTTP {response.status_code}")
            body = response.json()
            if not isinstance(body, dict):
                raise ProviderError("Model response was not a JSON object")
            return _response_result(body)
        except (httpx.HTTPError, ValueError, ProviderError) as exc:
            last_error = exc
    if isinstance(last_error, ProviderError):
        raise last_error
    raise ProviderError("Model request failed after one retry") from last_error
