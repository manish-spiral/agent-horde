"""Model providers.

Three API formats cover the major providers. Each provider is just a format,
an address, and the environment variable that holds its key.
"""

import os
from dataclasses import dataclass

import httpx

from horde.models.anthropic import AnthropicModel
from horde.models.base import Model
from horde.models.gemini import GeminiModel
from horde.models.openai_compat import OpenAICompatibleModel

ADAPTERS = {"openai": OpenAICompatibleModel, "anthropic": AnthropicModel, "gemini": GeminiModel}


@dataclass(frozen=True)
class Provider:
    api: str                       # which adapter: "openai", "anthropic" or "gemini"
    base_url: str | None           # None: must be given with --base-url
    key_env: str | None            # environment variable holding the API key
    default_model: str | None = None  # only set where verified; otherwise pass --model
    key_required: bool = True


PROVIDERS = {
    "groq": Provider("openai", "https://api.groq.com/openai/v1", "GROQ_API_KEY",
                     "openai/gpt-oss-120b"),
    "openai": Provider("openai", "https://api.openai.com/v1", "OPENAI_API_KEY"),
    "anthropic": Provider("anthropic", "https://api.anthropic.com/v1", "ANTHROPIC_API_KEY",
                          "claude-opus-5-5"),
    "gemini": Provider("gemini", "https://generativelanguage.googleapis.com/v1beta",
                       "GEMINI_API_KEY"),
    "openrouter": Provider("openai", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "deepseek": Provider("openai", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    "mistral": Provider("openai", "https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
    "xai": Provider("openai", "https://api.x.ai/v1", "XAI_API_KEY"),
    "together": Provider("openai", "https://api.together.xyz/v1", "TOGETHER_API_KEY"),
    "fireworks": Provider("openai", "https://api.fireworks.ai/inference/v1", "FIREWORKS_API_KEY"),
    "cerebras": Provider("openai", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY"),
    "ollama": Provider("openai", "http://localhost:11434/v1", None, key_required=False),
    # Any other OpenAI-compatible server: --base-url, optional key in HORDE_API_KEY.
    "custom": Provider("openai", None, "HORDE_API_KEY", key_required=False),
}


def create_model(provider: str = "groq", model: str | None = None,
                 base_url: str | None = None, client: httpx.Client | None = None) -> Model:
    if provider not in PROVIDERS:
        raise RuntimeError(f"unknown provider '{provider}' (choose from: {', '.join(PROVIDERS)})")
    settings = PROVIDERS[provider]

    model = model or os.environ.get("HORDE_MODEL") or settings.default_model
    if not model:
        raise RuntimeError(f"provider '{provider}' has no default model: "
                           "pass --model or set HORDE_MODEL")
    base_url = base_url or settings.base_url
    if not base_url:
        raise RuntimeError(f"provider '{provider}' needs --base-url")
    api_key = os.environ.get(settings.key_env) if settings.key_env else None
    if settings.key_required and not api_key:
        raise RuntimeError(f"{settings.key_env} is not set")

    return ADAPTERS[settings.api](name=f"{provider}:{model}", model=model,
                                  base_url=base_url.rstrip("/"), api_key=api_key, client=client)
