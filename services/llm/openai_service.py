import logging
import time
from .base import BaseLLM
from config import get_settings

log = logging.getLogger("llm.openai")


class OpenAIService(BaseLLM):
    def __init__(self):
        self._settings = get_settings()
        self._client = None

    def _get_client(self):
        if not self._client:
            from openai import AsyncOpenAI
            log.debug("Initialising OpenAI async client")
            self._client = AsyncOpenAI(api_key=self._settings.openai_api_key)
        return self._client

    def available(self) -> bool:
        return bool(self._settings.openai_api_key)

    async def chat(self, system: str, user: str) -> str:
        client = self._get_client()
        log.info(
            "LLM call | provider=openai model=gpt-4o-mini "
            "system_len=%d user_len=%d",
            len(system), len(user),
        )
        log.debug("system_prompt=%s", system[:300])
        log.debug("user_prompt=%s", user[:500])
        t0 = time.perf_counter()
        try:
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=1024,
            )
            elapsed = (time.perf_counter() - t0) * 1000
            text = resp.choices[0].message.content
            usage = resp.usage
            log.info(
                "LLM done  | provider=openai | %.0fms | "
                "prompt_tokens=%s completion_tokens=%s total=%s | reply_len=%d",
                elapsed,
                usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
                len(text),
            )
            log.debug("reply_preview=%s", text[:300])
            return text
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            log.error("LLM error | provider=openai | %.0fms | %s", elapsed, exc, exc_info=True)
            raise
