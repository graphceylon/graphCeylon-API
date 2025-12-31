from __future__ import annotations

import httpx
from ..core.settings import settings
from ..core.errors import TranslationError

#  debug print to check if the google_translate.py is being imported from the exact path expected
# print("GOOGLE_TRANSLATE IMPORTED FROM:", __file__)

class GoogleTranslator:
    """
    Google Translate v2 API wrapper (API Key based).

    Uses:
      POST https://translation.googleapis.com/language/translate/v2
    """

    BASE_URL = "https://translation.googleapis.com/language/translate/v2"

    async def translate(self, *, text: str, source_lang: str | None, target_lang: str) -> str:
        if not settings.GOOGLE_TRANSLATE_API_KEY:
            raise TranslationError("GOOGLE_TRANSLATE_API_KEY is not set")

        if not text or not text.strip():
            return ""

        params = {
            "q": text,
            "target": target_lang,
            "format": "text",
            "key": settings.GOOGLE_TRANSLATE_API_KEY,
        }

        # If you want Google to auto-detect, keep source out
        if source_lang and source_lang not in ("auto", ""):
            params["source"] = source_lang

        # 🔐 SAFE DEBUG LOG (NO KEY)
        from urllib.parse import urlencode
        safe_params = {k: v for k, v in params.items() if k != "key"}
        debug_url = f"{self.BASE_URL}?{urlencode(safe_params)}"

        from ..core.logging import get_logger
        logger = get_logger("language_service.google_translate")

        preview_in = (text[:60] + "…") if len(text) > 60 else text
        logger.info(
            f"[google-translate-call] {source_lang or 'auto'} → {target_lang} | "
            f"in='{preview_in}' | url='{debug_url}'"
        )

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(self.BASE_URL, params=params)
        except Exception as e:
            raise TranslationError(f"Google Translate request failed: {e}") from e

        if resp.status_code != 200:
            raise TranslationError(f"Google Translate failed: {resp.status_code} {resp.text}")

        data = resp.json()
        try:
            out = data["data"]["translations"][0]["translatedText"]

            preview_out = (out[:60] + "…") if len(out) > 60 else out
            logger.info(
                f"[google-translate-result] out='{preview_out}'"
            )

            return out
        
        except Exception as e:
            raise TranslationError(f"Unexpected Google response: {data}") from e
