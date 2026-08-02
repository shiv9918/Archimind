"""LLM client for Grok (xAI), via its OpenAI-compatible API surface.

Kept provider-swappable: anything exposing the OpenAI chat-completions
schema (OpenAI itself, Grok/xAI, many local servers) works by changing
XAI_BASE_URL / XAI_MODEL / XAI_API_KEY in .env -- no code changes needed.
"""

from openai import OpenAI

from app.config import settings

_client: OpenAI | None = None


class LLMNotConfiguredError(Exception):
    pass


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.xai_api_key, base_url=settings.xai_base_url)
    return _client


def chat_completion(system_prompt: str, user_prompt: str, temperature: float = 0.2, max_tokens: int = 1200) -> str:
    if not settings.llm_configured:
        raise LLMNotConfiguredError(
            "XAI_API_KEY is not set. Add it to backend/.env to enable AI chat/reasoning features."
        )

    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=settings.xai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        raise RuntimeError(f"LLM request failed: {exc}") from exc

    return response.choices[0].message.content or ""
