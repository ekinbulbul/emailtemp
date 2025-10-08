#!/usr/bin/env python3
import os, sys, asyncio
sys.path.insert(0, "../.")

from llm_client.client import LLMClient
from llm_client.types import ChatMessage
from llm_client.providers.ollama import OllamaProvider
from llm_client.providers.openai_compat import OpenAICompatibleProvider


def demo_ollama():
    base_url = "http://10.62.2.59:11434"
    model = "llama3"
    provider = OllamaProvider(base_url=base_url, model=model)
    client = LLMClient(provider)

    print("Testing sync chat...")
    resp = client.chat([ChatMessage(role="user", content="Hello, Ollama!")])
    print("Sync chat response:", resp.content)

    async def run_async_chat():
        print("Testing async stream chat...")
        msgs = [ChatMessage(role="user", content="Stream this please")]
        async for token in client.astream_chat(msgs):
            print(token, end="", flush=True)
        print()

    asyncio.run(run_async_chat())


def demo_openai_compat():
    lm_provider = OpenAICompatibleProvider(base_url="http://10.62.2.59:1234", api_key="", model="qwen/qwen3-4b-thinking-2507")
    lm_client = LLMClient(lm_provider)
    messages = []
    messages.append(ChatMessage(role="system", content="You are a History teacher.You explain thinks in less than 30 words."))
    messages.append(ChatMessage(role="user", content="Can you explain e=mc square?"))

    resp = lm_client.chat(messages=messages)
    print("History Teacher response:", resp.content)

    async def run_async_stream():
        print("Testing async astream_chat in demo_openai_compat...")
        async for token in lm_client.astream_chat(messages):
            print(token, end="", flush=True)
        print()
    asyncio.run(run_async_stream())


if __name__ == "__main__":
    demo_ollama()
    demo_openai_compat()
