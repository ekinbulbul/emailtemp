from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, Iterable, List, Optional

import httpx

from ..types import ChatMessage, ChatResponse
from .base import BaseProvider


class OllamaProvider(BaseProvider):
    """
    Provider for Ollama servers (default: http://localhost:11434).

    Uses `/api/chat` endpoint. For streaming, Ollama returns JSON lines per chunk until `{ "done": true }`.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: Optional[str] = None,
        timeout_seconds: float = 60.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if extra_headers:
            headers.update(extra_headers)
        self._sync = httpx.Client(base_url=self._base_url, timeout=self._timeout_seconds, headers=headers)
        self._async = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout_seconds, headers=headers)

    def complete(self, prompt: str, **kwargs) -> ChatResponse:
        # Map to chat with a single user message
        return self.chat([ChatMessage(role="user", content=prompt)], **kwargs)

    def chat(self, messages: Iterable[ChatMessage], **kwargs) -> ChatResponse:
        msgs = [{"role": m.role, "content": m.content} for m in messages]
        data: Dict[str, Any] = {
            "model": kwargs.get("model", self._model),
            "messages": msgs,
            "stream": False,
        }
        resp = self._sync.post("/api/chat", json=data)
        resp.raise_for_status()
        payload = resp.json()
        # Ollama returns { message: { role, content }, done: true, ... }
        text = ""
        message = payload.get("message") or {}
        if isinstance(message, dict):
            text = message.get("content", "")
        elif isinstance(payload.get("response"), str):
            # Fallback for /api/generate-like responses if proxied
            text = payload.get("response", "")
        return ChatResponse(content=text, model=data.get("model"), provider_metadata=payload)

    async def astream_chat(self, messages: Iterable[ChatMessage], **kwargs) -> AsyncGenerator[str, None]:
        msgs = [{"role": m.role, "content": m.content} for m in messages]
        data: Dict[str, Any] = {
            "model": kwargs.get("model", self._model),
            "messages": msgs,
            "stream": True,
        }
        async with self._async.stream("POST", "/api/chat", json=data) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    # Some servers prefix with 'data: ' similar to SSE
                    if line.startswith("data:"):
                        try:
                            obj = json.loads(line[len("data:"):].strip())
                        except json.JSONDecodeError:
                            continue
                    else:
                        continue
                if obj.get("done") is True:
                    break
                msg = obj.get("message") or {}
                delta = None
                if isinstance(msg, dict):
                    delta = msg.get("content")
                if not delta and isinstance(obj.get("response"), str):
                    delta = obj.get("response")
                if delta:
                    yield delta


