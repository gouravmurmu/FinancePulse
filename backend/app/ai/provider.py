"""LLM provider behind one small interface. Any OpenAI-compatible chat
completions endpoint works (Groq by default); configured by environment only."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.core.config import Settings


class LLMError(Exception):
    def __init__(self, message: str, quota: bool = False):
        super().__init__(message)
        self.quota = quota


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMReply:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens: int = 0


class ChatProvider(Protocol):
    model: str

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMReply: ...


class OpenAICompatible:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMReply:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 900,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        try:
            res = httpx.post(
                f"{self.base_url}/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"AI provider unreachable: {type(exc).__name__}") from exc
        if res.status_code == 429:
            raise LLMError("AI provider rate limit reached", quota=True)
        if res.status_code >= 400:
            raise LLMError(f"AI provider error {res.status_code}")
        data = res.json()
        msg = data["choices"][0]["message"]
        calls = []
        for c in msg.get("tool_calls") or []:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(id=c["id"], name=c["function"]["name"], arguments=args or {}))
        tokens = int((data.get("usage") or {}).get("total_tokens") or 0)
        return LLMReply(content=msg.get("content"), tool_calls=calls, tokens=tokens)


def get_provider(settings: Settings) -> ChatProvider | None:
    if not settings.llm_api_key:
        return None
    return OpenAICompatible(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
