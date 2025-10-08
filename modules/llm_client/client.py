from __future__ import annotations

from typing import AsyncGenerator, Iterable, List

from .providers.base import BaseProvider
from .types import ChatMessage, ChatResponse


class LLMClient:
    def __init__(self, provider: BaseProvider):
        self._provider = provider

    def complete(self, prompt: str, **kwargs) -> ChatResponse:
        return self._provider.complete(prompt=prompt, **kwargs)

    def chat(self, messages: Iterable[ChatMessage], **kwargs) -> ChatResponse:
        messages_list: List[ChatMessage] = list(messages)
        return self._provider.chat(messages=messages_list, **kwargs)

    async def astream_chat(self, messages: Iterable[ChatMessage], **kwargs) -> AsyncGenerator[str, None]:
        messages_list: List[ChatMessage] = list(messages)
        async for token in self._provider.astream_chat(messages=messages_list, **kwargs):
            yield token


