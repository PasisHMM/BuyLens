from app.config import Settings
from app.llm.base import LLM, LLMError, Tier

__all__ = ["LLM", "LLMError", "Tier", "build_llm"]


def build_llm(settings: Settings) -> LLM:
    if settings.llm_provider == "anthropic":
        from app.llm.anthropic import AnthropicLLM

        return AnthropicLLM(settings)
    from app.llm.gemini import GeminiLLM

    return GeminiLLM(settings)
