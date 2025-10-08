import pytest
import respx
import httpx

from llm_client.client import LLMClient, ChatMessage
from llm_client.providers.openai_compat import OpenAICompatibleProvider


@respx.mock
def test_chat_completion_sync():
    route = respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-123",
                "model": "gpt-4o-mini",
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": "Hello!"}}
                ],
            },
        )
    )
    provider = OpenAICompatibleProvider(base_url="https://api.example.com", api_key="sk-123", model="gpt-4o-mini")
    client = LLMClient(provider)

    resp = client.chat([ChatMessage(role="user", content="hi")])

    assert route.called
    assert resp.content == "Hello!"
    assert resp.model == "gpt-4o-mini"


@pytest.mark.asyncio
@respx.mock
async def test_chat_streaming_async():
    def sse_bytes(lines):
        return "\n".join(lines).encode()

    body = sse_bytes([
        "data: {\"choices\":[{\"delta\":{\"content\":\"He\"}}]}",
        "data: {\"choices\":[{\"delta\":{\"content\":\"llo\"}}]}",
        "data: [DONE]",
        "",
    ])

    route = respx.post("https://api.example.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, content=body, headers={"Content-Type": "text/event-stream"})
    )

    provider = OpenAICompatibleProvider(base_url="https://api.example.com", api_key="sk-123", model="gpt-4o-mini")
    client = LLMClient(provider)

    chunks = []
    async for token in client.astream_chat([ChatMessage(role="user", content="hi")]):
        chunks.append(token)

    assert route.called
    assert "".join(chunks) == "Hello"


