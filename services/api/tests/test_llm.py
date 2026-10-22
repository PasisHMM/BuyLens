from types import SimpleNamespace

import pytest
from pydantic import BaseModel, SecretStr

from app.config import Settings
from app.llm import LLMError, build_llm
from app.llm.anthropic import AnthropicLLM
from app.llm.gemini import GeminiLLM


class Answer(BaseModel):
    verdict: str
    score: int


def gemini_settings(**kw) -> Settings:
    return Settings(
        gemini_api_key=SecretStr("k"), gemini_fast_model="flash-x", gemini_smart_model="pro-x", **kw
    )


def test_provider_selection_and_config_errors():
    assert isinstance(build_llm(gemini_settings()), GeminiLLM)
    anthropic = build_llm(Settings(llm_provider="anthropic", anthropic_api_key=SecretStr("k")))
    assert isinstance(anthropic, AnthropicLLM)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        build_llm(Settings(_env_file=None, gemini_api_key=None))
    with pytest.raises(RuntimeError, match="GEMINI_FAST_MODEL"):
        build_llm(Settings(_env_file=None, gemini_api_key=SecretStr("k"), gemini_fast_model=""))


async def test_gemini_structured_output(monkeypatch):
    llm = GeminiLLM(gemini_settings())
    seen = {}

    async def fake_generate(*, model, contents, config):
        seen.update(model=model, schema=config.response_schema, mime=config.response_mime_type)
        return SimpleNamespace(text='{"verdict": "CONSIDER", "score": 7}')

    monkeypatch.setattr(llm._client.aio.models, "generate_content", fake_generate)
    out = await llm.structured(tier="smart", system="s", prompt="p", schema=Answer)
    assert out == Answer(verdict="CONSIDER", score=7)
    assert seen == {"model": "pro-x", "schema": Answer, "mime": "application/json"}


@pytest.mark.parametrize("text", ["", '{"verdict": "CONSIDER"}', "not json"])
async def test_gemini_bad_output_is_llm_error(monkeypatch, text):
    llm = GeminiLLM(gemini_settings())

    async def fake_generate(**_):
        return SimpleNamespace(text=text)

    monkeypatch.setattr(llm._client.aio.models, "generate_content", fake_generate)
    with pytest.raises(LLMError):
        await llm.structured(tier="fast", system="s", prompt="p", schema=Answer)


async def test_anthropic_forced_tool_call(monkeypatch):
    llm = AnthropicLLM(Settings(llm_provider="anthropic", anthropic_api_key=SecretStr("k")))
    seen = {}

    async def fake_create(**kwargs):
        seen.update(kwargs)
        block = SimpleNamespace(type="tool_use", input={"verdict": "BUY", "score": 9})
        return SimpleNamespace(content=[block])

    monkeypatch.setattr(llm._client.messages, "create", fake_create)
    out = await llm.structured(tier="fast", system="s", prompt="p", schema=Answer)
    assert out.verdict == "BUY"
    assert seen["model"] == "claude-haiku-5-5"
    assert seen["tool_choice"] == {"type": "tool", "name": "respond"}
