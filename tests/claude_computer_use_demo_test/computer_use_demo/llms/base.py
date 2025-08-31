from abc import ABC

from typing_extensions import TypedDict, Required
from dataclasses import dataclass

class ChatMessage:
    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

@dataclass(kw_only=True)
class TextMessage(ChatMessage):
    role: str = None
    content: str = None

@dataclass(kw_only=True)
class ToolUseMessage(ChatMessage):
    tool_use_id: str = None
    name: str = None
    arguments: dict  = None

@dataclass(kw_only=True)
class ToolResultMessage(ChatMessage):
    tool_use_id: str = None
    name: str = None
    content: str = None
    image: str = None
    is_error: bool = None

class BaseLLM(ABC):
    pass