from dataclasses import dataclass
from typing import Optional

from lmnr.types import ChatMessage


@dataclass
class ChatUsage:
    completion_tokens: int
    prompt_tokens: int
    total_tokens: int
    approximate_cost: Optional[float]


@dataclass
class ChatChoice:
    message: ChatMessage


@dataclass
class ChatCompletion:
    choices: list[ChatChoice]
    usage: ChatUsage
    model: str
