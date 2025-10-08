import pytest
import respx
import httpx
import json

from llm_client.client import LLMClient, ChatMessage
from llm_client.providers.ollama import OllamaProvider


@respx.mock
def test_ollama_chat_sync():
    route = respx.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "Hello from Ollama"},
                "done": True,
            },
        )
    )
    provider = OllamaProvider(model="llama3")
    client = LLMClient(provider)

    resp = client.chat([ChatMessage(role="user", content="hi")])

    assert route.called
    assert resp.content == "Hello from Ollama"


@pytest.mark.asyncio
@respx.mock
async def test_ollama_chat_stream_async():
    # Ollama streams JSON lines
    lines = [
        {"message": {"role": "assistant", "content": "He"}, "done": False},
        {"message": {"role": "assistant", "content": "llo"}, "done": False},
        {"done": True},
    ]
    body = ("\n".join([json.dumps(l) for l in lines]) + "\n").encode()

    route = respx.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(200, content=body, headers={"Content-Type": "application/x-ndjson"})
    )

    provider = OllamaProvider(model="llama3")
    client = LLMClient(provider)

    chunks = []
    async for token in client.astream_chat([ChatMessage(role="user", content="hi")]):
        chunks.append(token)

    assert route.called
    assert "".join(chunks) == "Hello"

