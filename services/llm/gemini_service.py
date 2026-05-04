import logging
import time
from .base import BaseLLM
from config import get_settings

log = logging.getLogger("llm.gemini")


class GeminiService(BaseLLM):
    def __init__(self):
        self._settings = get_settings()
        self._model = None

    def _get_model(self):
        if not self._model:
            import google.generativeai as genai
            log.debug("Initialising Gemini model gemini-1.5-flash")
            genai.configure(api_key=self._settings.gemini_api_key)
            self._model = genai.GenerativeModel("gemini-1.5-flash")
        return self._model

    def available(self) -> bool:
        return bool(self._settings.gemini_api_key)

    async def chat(self, system: str, user: str) -> str:
        model = self._get_model()
        prompt = f"{system}\n\n{user}"
        log.info(
            "LLM call | provider=gemini model=gemini-1.5-flash prompt_len=%d",
            len(prompt),
        )
        log.debug("prompt_preview=%s", prompt[:500])
        t0 = time.perf_counter()
        try:
            response = model.generate_content(prompt)
            elapsed = (time.perf_counter() - t0) * 1000
            text = response.text
            log.info("LLM done  | provider=gemini | %.0fms | reply_len=%d", elapsed, len(text))
            log.debug("reply_preview=%s", text[:300])
            return text
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            log.error("LLM error | provider=gemini | %.0fms | %s", elapsed, exc, exc_info=True)
            raise
