from .base import BaseLLM
from .openai_service import OpenAIService
from .anthropic_service import AnthropicService
from .gemini_service import GeminiService
from config import get_settings


def get_llm(provider: str | None = None) -> BaseLLM:
    """Return the requested LLM, falling back to any available provider."""
    settings = get_settings()
    provider = provider or settings.default_llm
    candidates = {
        "openai": OpenAIService,
        "anthropic": AnthropicService,
        "gemini": GeminiService,
    }
    svc = candidates.get(provider, AnthropicService)()
    if svc.available():
        return svc
    # fallback: try any available
    for cls in candidates.values():
        s = cls()
        if s.available():
            return s
    raise RuntimeError("No LLM API key configured. Set at least one in .env")
