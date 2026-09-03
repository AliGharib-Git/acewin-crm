"""
Provider-agnostic AI configuration for the ACEWIN Copilot.

This module intentionally knows nothing about any specific AI vendor
(OpenAI, Anthropic, Azure, local models, ...). It only reads generic
settings from the environment. Swapping providers later means adding a
new AIClient implementation in `client.py` and pointing AI_PROVIDER at
it -- no changes to CRM Core, the Copilot router, or the tool registry.

Environment variables (see backend/.env.example):
    AI_PROVIDER      "none" | "openai" | "openrouter" | "avalai" | "gapgpt" |
                      "groq" | "gemini" | "claude" | "custom"
    AI_API_KEY       secret key for whichever provider is selected
    AI_MODEL         model name for that provider (falls back to a sensible
                      per-provider default -- see app/ai/client.py -- except
                      for AI_PROVIDER=custom, where it is mandatory)
    AI_BASE_URL      optional custom endpoint override; mandatory only for
                      AI_PROVIDER=custom
    AI_TEMPERATURE   sampling temperature (default 0.2 -- CRM advice should be consistent)
    AI_MAX_TOKENS    response length cap

Every provider above ends up behind the same `AIClient` interface (see
app/ai/client.py), so switching providers -- or adding a brand new one --
never requires touching the Copilot router, the tool registry, or the
frontend. Only backend/.env changes.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # "none" means the Copilot architecture is wired up but not connected to a
    # real model yet. Set ai_provider to a real provider key + ai_api_key to
    # go live -- see _PROVIDER_REGISTRY in app/ai/client.py for the full list.
    ai_provider: str = "none"
    ai_api_key: str | None = None
    # Left unset by default so each adapter's own DEFAULT_MODEL applies.
    # Set explicitly to override, or when AI_PROVIDER=custom (mandatory there).
    ai_model: str | None = None
    ai_base_url: str | None = None
    ai_temperature: float = 0.2
    ai_max_tokens: int = 1024

    @property
    def is_configured(self) -> bool:
        """True once a real provider + key are supplied. Everything downstream
        (the router, the UI) should branch on this rather than on ai_provider
        directly, so adding new providers never requires touching call sites."""
        return self.ai_provider.lower() != "none" and bool(self.ai_api_key)


@lru_cache
def get_ai_settings() -> AISettings:
    return AISettings()
