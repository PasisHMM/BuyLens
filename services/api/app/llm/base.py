from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
Tier = Literal["fast", "smart"]  # fast = extraction / review summaries, smart = verdict copy


class LLMError(Exception):
    """The model call failed or returned output that does not match the schema."""


class LLM(Protocol):
    name: str

    async def structured(
        self, *, tier: Tier, system: str, prompt: str, schema: type[T], max_tokens: int = 1024
    ) -> T: ...
