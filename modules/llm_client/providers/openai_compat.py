from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, Iterable, List, Optional

import httpx

from ..types import ChatMessage, ChatResponse
from .base import BaseProvider


class OpenAICompatibleProvider(BaseProvider):
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 30.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._headers: Dict[str, str] = {
            "Content-Type": "application/json",
        }
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        if extra_headers:
            self._headers.update(extra_headers)

        self._sync = httpx.Client(base_url=self._base_url, timeout=self._timeout_seconds, headers=self._headers)
        self._async = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout_seconds, headers=self._headers)

    def complete(self, prompt: str, **kwargs) -> ChatResponse:
        data = {
            "model": kwargs.get("model", self._model),
            "prompt": prompt,
            "max_tokens": kwargs.get("max_tokens"),
            "temperature": kwargs.get("temperature"),
        }
        resp = self._sync.post("/v1/completions", json=data)
        resp.raise_for_status()
        payload = resp.json()
        text = payload.get("choices", [{}])[0].get("text", "")
        return ChatResponse(content=text, model=payload.get("model"), provider_metadata=payload)

    def chat(self, messages: Iterable[ChatMessage], **kwargs) -> ChatResponse:
        msgs = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
        data: Dict[str, Any] = {
            "model": kwargs.get("model", self._model),
            "messages": msgs,
            "temperature": kwargs.get("temperature"),
        }
        resp = self._sync.post("/v1/chat/completions", json=data)
        resp.raise_for_status()
        payload = resp.json()
        text = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        return ChatResponse(content=text, model=payload.get("model"), provider_metadata=payload)

    async def astream_chat(self, messages: Iterable[ChatMessage], **kwargs) -> AsyncGenerator[str, None]:
        msgs = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
        data: Dict[str, Any] = {
            "model": kwargs.get("model", self._model),
            "messages": msgs,
            "stream": True,
        }
        async with self._async.stream("POST", "/v1/chat/completions", json=data) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                chunk = line[len("data:"):].strip()
                if chunk == "[DONE]":
                    break
                try:
                    payload = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                delta = payload.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta


