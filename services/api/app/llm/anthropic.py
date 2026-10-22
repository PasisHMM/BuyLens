from typing import Any

import anthropic
from pydantic import ValidationError

from app.config import Settings
from app.llm.base import LLMError, T, Tier


class AnthropicLLM:
    """Alternative provider (LLM_PROVIDER=anthropic). Structured output via a forced tool call."""

    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        if settings.anthropic_api_key is None:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
        self._models: dict[Tier, str] = {
            "fast": settings.anthropic_fast_model,
            "smart": settings.anthropic_smart_model,
        }

    async def structured(
        self, *, tier: Tier, system: str, prompt: str, schema: type[T], max_tokens: int = 1024
    ) -> T:
        tool: Any = {
            "name": "respond",
            "description": "Return the structured result.",
            "input_schema": schema.model_json_schema(),
        }
        try:
            msg = await self._client.messages.create(
                model=self._models[tier],
                max_tokens=max_tokens,
                system=system,
                tools=[tool],
                tool_choice={"type": "tool", "name": "respond"},
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as exc:
            raise LLMError("Anthropic request failed.") from exc
        payload = next((b.input for b in msg.content if b.type == "tool_use"), None)
        if payload is None:
            raise LLMError("Anthropic returned no tool call.")
        try:
            return schema.model_validate(payload)
        except ValidationError as exc:
            raise LLMError("Anthropic output did not match the schema.") from exc
