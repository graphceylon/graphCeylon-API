# services/language_service/src/translate/translator.py

from __future__ import annotations

from ..core.settings import settings
from ..core.logging import get_logger
from ..core.errors import TranslationError

from .openai_translate import OpenAITranslator
from .google_translate import GoogleTranslator
from .fallback import (
    fallback_translate_to_english,
    fallback_translate_from_english,
)

logger = get_logger("language_service.translator")


class Translator:
    """
    High-level translator API used by pipelines.

    Priority:
      1) Google Translate (if key present)
      2) OpenAI Translate (if key present)
      3) Fallback (last resort)
    """

    def __init__(self):
        self._google = GoogleTranslator() if settings.GOOGLE_TRANSLATE_API_KEY else None
        self._openai = OpenAITranslator() if settings.OPENAI_API_KEY else None

    # ------------------------------------------------------------------
    # TO ENGLISH (USER INPUT → ORCHESTRATOR)
    # ------------------------------------------------------------------
    async def to_english(self, text: str, source_lang: str) -> str:
        if not text or not text.strip():
            return ""

        if source_lang == "en":
            return text

        preview_in = (text[:60] + "…") if len(text) > 60 else text

        # 1) Google Translate
        if self._google:
            try:
                out = await self._google.translate(
                    text=text,
                    source_lang=source_lang,
                    target_lang="en",
                )

                preview_out = (out[:60] + "…") if len(out) > 60 else out
                logger.info(
                    f"[translate-google] {source_lang} -> en | "
                    f"in='{preview_in}' | out='{preview_out}'"
                )

                return out

            except TranslationError as e:
                logger.warning(
                    f"Google to_english failed, trying OpenAI/fallback: {e}"
                )

        # 2) OpenAI fallback
        if self._openai:
            try:
                out = await self._openai.translate(
                    text=text,
                    source_lang=source_lang,
                    target_lang="en",
                )

                preview_out = (out[:60] + "…") if len(out) > 60 else out
                logger.info(
                    f"[translate-openai] {source_lang} -> en | "
                    f"in='{preview_in}' | out='{preview_out}'"
                )

                return out

            except TranslationError as e:
                logger.warning(
                    f"OpenAI to_english failed, using fallback: {e}"
                )

        # 3) Last resort fallback
        logger.warning(
            f"No translator available; using fallback for to_english | in='{preview_in}'"
        )
        return fallback_translate_to_english(text, source_lang)

    # ------------------------------------------------------------------
    # FROM ENGLISH (ORCHESTRATOR → USER)
    # ------------------------------------------------------------------
    async def from_english(self, text: str, target_lang: str) -> str:
        if not text or not text.strip():
            return ""

        if target_lang == "en":
            return text

        preview_in = (text[:60] + "…") if len(text) > 60 else text

        # 1) Google Translate
        if self._google:
            try:
                out = await self._google.translate(
                    text=text,
                    source_lang="en",
                    target_lang=target_lang,
                )

                preview_out = (out[:60] + "…") if len(out) > 60 else out
                logger.info(
                    f"[translate-google] en -> {target_lang} | "
                    f"in='{preview_in}' | out='{preview_out}'"
                )

                return out

            except TranslationError as e:
                logger.warning(
                    f"Google from_english failed, trying OpenAI/fallback: {e}"
                )

        # 2) OpenAI fallback
        if self._openai:
            try:
                out = await self._openai.translate(
                    text=text,
                    source_lang="en",
                    target_lang=target_lang,
                )

                preview_out = (out[:60] + "…") if len(out) > 60 else out
                logger.info(
                    f"[translate-openai] en -> {target_lang} | "
                    f"in='{preview_in}' | out='{preview_out}'"
                )

                return out

            except TranslationError as e:
                logger.warning(
                    f"OpenAI from_english failed, using fallback: {e}"
                )

        # 3) Last resort fallback
        logger.warning(
            f"No translator available; using fallback for from_english | in='{preview_in}'"
        )
        return fallback_translate_from_english(text, target_lang)
