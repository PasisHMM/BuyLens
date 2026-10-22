from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.config import Settings
from app.llm.base import LLMError, T, Tier


class GeminiLLM:
    """Default provider. Schemas sent here must stay flat (no regex patterns or open-ended dicts)."""

    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        if settings.gemini_api_key is None:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        if not (settings.gemini_fast_model and settings.gemini_smart_model):
            raise RuntimeError("Set GEMINI_FAST_MODEL and GEMINI_SMART_MODEL (see Google AI Studio).")
        self._client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
        self._models: dict[Tier, str] = {
            "fast": settings.gemini_fast_model,
            "smart": settings.gemini_smart_model,
        }

    async def structured(
        self, *, tier: Tier, system: str, prompt: str, schema: type[T], max_tokens: int = 1024
    ) -> T:
        try:
            resp = await self._client.aio.models.generate_content(
                model=self._models[tier],
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=schema,
                    max_output_tokens=max_tokens,
                    temperature=0.2,
                ),
            )
        except errors.APIError as exc:
            raise LLMError(f"Gemini request failed: {exc.code}") from exc
        if not resp.text:
            raise LLMError("Gemini returned an empty response.")
        try:
            return schema.model_validate_json(resp.text)
        except ValidationError as exc:
            raise LLMError("Gemini output did not match the schema.") from exc
