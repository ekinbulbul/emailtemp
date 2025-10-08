from email import message
import pytest
import asyncio

from llm_client.client import LLMClient
from llm_client.types import ChatMessage, ChatResponse
from llm_client.providers.base import BaseProvider


class StubProvider(BaseProvider):
    def __init__(self):
        self.complete_calls = []
        self.chat_calls = []
        self.astream_calls = []

    def complete(self, prompt: str, **kwargs) -> ChatResponse:
        self.complete_calls.append((prompt, kwargs))
        return ChatResponse(content=f"ECHO:{prompt}", model=kwargs.get("model"))

    def chat(self, messages, **kwargs) -> ChatResponse:
        self.chat_calls.append((list(messages), kwargs))
        joined = " ".join([m.content for m in messages])
        return ChatResponse(content=f"CHAT:{joined}", model=kwargs.get("model"))

    async def astream_chat(self, messages, **kwargs):
        self.astream_calls.append((list(messages), kwargs))
        for part in ["A", "B", "C"]:
            await asyncio.sleep(0)
            yield part



def test_complete_delegates_and_returns_response():
    provider = StubProvider()
    client = LLMClient(provider)

    resp = client.complete("hello", model="dummy")

    assert resp.content == "ECHO:hello"
    assert resp.model == "dummy"
    assert provider.complete_calls and provider.complete_calls[0][0] == "hello"



def test_chat_delegates_and_returns_response():
    provider = StubProvider()
    client = LLMClient(provider)

    msgs = [ChatMessage(role="user", content="hi"), ChatMessage(role="assistant", content="there")]
    resp = client.chat(msgs, model="dummy")

    assert resp.content == "CHAT:hi there"
    assert resp.model == "dummy"
    assert provider.chat_calls and [m.content for m in provider.chat_calls[0][0]] == ["hi", "there"]


# Removed example/demos (ollama and openai_compat) and __main__ to examples.
