from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Iterable, List

from ..types import ChatMessage, ChatResponse


class BaseProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> ChatResponse:  # pragma: no cover - interface only
        raise NotImplementedError

    @abstractmethod
    def chat(self, messages: Iterable[ChatMessage], **kwargs) -> ChatResponse:  # pragma: no cover - interface only
        raise NotImplementedError

    @abstractmethod
    async def astream_chat(self, messages: Iterable[ChatMessage], **kwargs) -> AsyncGenerator[str, None]:  # pragma: no cover - interface only
        raise NotImplementedError


