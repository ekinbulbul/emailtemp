from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ChatResponse:
    content: str
    model: Optional[str] = None
    provider_metadata: Optional[Dict[str, object]] = None


