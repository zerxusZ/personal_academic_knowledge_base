import logging
import time
from .base import BaseLLM
from config import get_settings

log = logging.getLogger("llm.anthropic")


class AnthropicService(BaseLLM):
    def __init__(self):
        self._settings = get_settings()
        self._client = None

    def _get_client(self):
        if not self._client:
            import anthropic
            log.debug("Initialising Anthropic async client")
            self._client = anthropic.AsyncAnthropic(api_key=self._settings.anthropic_api_key)
        return self._client

    def available(self) -> bool:
        return bool(self._settings.anthropic_api_key)

    async def chat(self, system: str, user: str) -> str:
        client = self._get_client()
        log.info(
            "LLM call | provider=anthropic model=claude-sonnet-4-6 "
            "system_len=%d user_len=%d",
            len(system), len(user),
        )
        log.debug("system_prompt=%s", system[:300])
        log.debug("user_prompt=%s", user[:500])
        t0 = time.perf_counter()
        try:
            msg = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            elapsed = (time.perf_counter() - t0) * 1000
            text = msg.content[0].text
            log.info(
                "LLM done  | provider=anthropic | %.0fms | "
                "input_tokens=%s output_tokens=%s | reply_len=%d",
                elapsed,
                msg.usage.input_tokens,
                msg.usage.output_tokens,
                len(text),
            )
            log.debug("reply_preview=%s", text[:300])
            return text
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            log.error("LLM error | provider=anthropic | %.0fms | %s", elapsed, exc, exc_info=True)
            raise
