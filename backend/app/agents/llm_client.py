"""LLM client for Groq (api.groq.com), via its OpenAI-compatible API surface.

Kept provider-swappable: anything exposing the OpenAI chat-completions
schema (OpenAI itself, Groq, xAI, many local servers) works by changing
GROQ_BASE_URL / GROQ_MODEL / GROQ_API_KEY in .env -- no code changes needed.
"""

from openai import OpenAI

from app.config import settings

_client: OpenAI | None = None


class LLMNotConfiguredError(Exception):
    pass


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
    return _client


def chat_completion(system_prompt: str, user_prompt: str, temperature: float = 0.2, max_tokens: int = 1200) -> str:
    if not settings.llm_configured:
        raise LLMNotConfiguredError(
            "GROQ_API_KEY is not set. Add it to backend/.env to enable AI chat/reasoning features."
        )

    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
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
