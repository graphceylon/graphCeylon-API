"""
Translation helpers using Google Cloud Translation API v3.

- translate_from_english: English → user's detected language (for TTS response).
- detect_language: detect the BCP-47 language code of arbitrary text.
- translate_to_english: any supported language → English (for STT pipeline).
"""

from __future__ import annotations

import logging

from google.cloud import translate_v3 as translate

from .config import GOOGLE_CLOUD_PROJECT, TRANSLATION_LOCATION

logger = logging.getLogger(__name__)

_client: translate.TranslationServiceClient | None = None


def _get_client() -> translate.TranslationServiceClient:
    global _client
    if _client is None:
        _client = translate.TranslationServiceClient()
    return _client


def translate_from_english(text: str, target_lang: str) -> str:
    """
    Translate English text to the target language.

    Args:
        text: English text to translate.
        target_lang: Target language code — "si" (Sinhala), "ta" (Tamil), or "en".

    Returns:
        Translated text string. Returns original text if target is English.
    """
    if not text or not text.strip():
        return text

    target_lang = target_lang.strip().lower()

    # No translation needed
    if target_lang == "en":
        return text

    try:
        client = _get_client()
        parent = f"projects/{GOOGLE_CLOUD_PROJECT}/locations/{TRANSLATION_LOCATION}"

        response = client.translate_text(
            parent=parent,
            contents=[text],
            source_language_code="en",
            target_language_code=target_lang,
            mime_type="text/plain",
        )

        if response.translations:
            translated = response.translations[0].translated_text
            logger.info("Translated en→%s: '%s' → '%s'", target_lang, text[:80], translated[:80])
            return translated

        logger.warning("Translation returned no results, returning original text")
        return text

    except Exception:
        logger.exception("Translation failed (en→%s), returning original text", target_lang)
        return text


# Supported language codes for this service
_SUPPORTED_LANGS = {"en", "si", "ta"}


def detect_language(text: str) -> str:
    """
    Detect the BCP-47 language code of the given text.

    Returns one of "en", "si", "ta". Falls back to "en" for unrecognised languages.
    """
    if not text or not text.strip():
        return "en"

    try:
        client = _get_client()
        parent = f"projects/{GOOGLE_CLOUD_PROJECT}/locations/{TRANSLATION_LOCATION}"

        response = client.detect_language(
            parent=parent,
            content=text,
            mime_type="text/plain",
        )

        if response.languages:
            code = response.languages[0].language_code.lower()
            # Normalise BCP-47 variants (e.g. "si-LK" → "si")
            base = code.split("-")[0]
            detected = base if base in _SUPPORTED_LANGS else "en"
            logger.info("Detected language: %s (raw: %s)", detected, code)
            return detected

    except Exception:
        logger.exception("Language detection failed, defaulting to 'en'")

    return "en"


def translate_to_english(text: str, source_lang: str) -> str:
    """
    Translate text to English.

    Args:
        text: Text in any language.
        source_lang: BCP-47 source language code, e.g. "si" or "ta".

    Returns:
        English translation. Returns original text if already English or on error.
    """
    if not text or not text.strip():
        return text

    source_lang = source_lang.strip().lower().split("-")[0]

    if source_lang == "en":
        return text

    try:
        client = _get_client()
        parent = f"projects/{GOOGLE_CLOUD_PROJECT}/locations/{TRANSLATION_LOCATION}"

        response = client.translate_text(
            parent=parent,
            contents=[text],
            source_language_code=source_lang,
            target_language_code="en",
            mime_type="text/plain",
        )

        if response.translations:
            translated = response.translations[0].translated_text
            logger.info("Translated %s→en: '%s' → '%s'", source_lang, text[:80], translated[:80])
            return translated

        logger.warning("Translation returned no results, returning original text")
        return text

    except Exception:
        logger.exception("Translation failed (%s→en), returning original text", source_lang)
        return text
