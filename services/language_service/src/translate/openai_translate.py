# OpenAI translator implementation

from __future__ import annotations

import httpx
from typing import Optional

from ..core.settings import settings
from ..core.errors import TranslationError

# Map your codes to readable names (helps the model)
LANG_NAME = {
    "en": "English",
    "si": "Sinhala",
    "ta": "Tamil",
    "hi": "Hindi",
    "fr": "French",
    "ru": "Russian",
}

DEFAULT_OPENAI_TRANSLATION_MODEL = "gpt-4o-mini"  # safe default

class OpenAITranslator:
    """
    Simple OpenAI Chat Completions translator using HTTP (no SDK required).
    """
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, timeout_s: float = 30.0):
        self.api_key = api_key or settings.OPENAI_API_KEY

        # avoid crashing if OPENAI_TRANSLATION_MODEL is missing
        self.model = model or getattr(settings, "OPENAI_TRANSLATION_MODEL", DEFAULT_OPENAI_TRANSLATION_MODEL)
        self.timeout_s = timeout_s

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not text or not text.strip():
            return ""

        if not self.api_key:
            raise TranslationError("OPENAI_API_KEY is not set")

        src = LANG_NAME.get(source_lang, source_lang)
        tgt = LANG_NAME.get(target_lang, target_lang)

        system = (
            "You are a precise translation engine. "
            "Translate meaning faithfully. Keep place names. "
            "Do NOT add explanations. Output only the translation."
        )

        user = f"Translate from {src} to {tgt}:\n\n{text}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            raise TranslationError(f"OpenAI translation failed: {e}") from e