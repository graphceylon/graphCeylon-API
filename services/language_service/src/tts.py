"""
Text-to-Speech using Google Cloud TTS.

Voice configurations are taken from the voice_test folder where
each language was tested and validated:
  - English:  en-US  / en-US-Neural2-C  (Neural2, highest quality)
  - Sinhala:  si-LK  / auto-select      (Standard, no named voices exist)
  - Tamil:    ta-IN  / ta-IN-Wavenet-A  (Wavenet, Neural2 unavailable)

Output: MP3 audio bytes.
"""

from __future__ import annotations

import logging

from google.cloud import texttospeech

from .config import TTS_VOICE_MAP

logger = logging.getLogger(__name__)

_client: texttospeech.TextToSpeechClient | None = None


def _get_client() -> texttospeech.TextToSpeechClient:
    global _client
    if _client is None:
        _client = texttospeech.TextToSpeechClient()
    return _client


def get_audio_mime_type(language: str) -> str:
    """
    Return the MIME type of the audio produced by synthesize_speech.

    Sinhala uses the local VITS model which outputs WAV;
    all other languages use Google Cloud TTS which outputs MP3.
    """
    return "audio/wav" if language.strip().lower() == "si" else "audio/mpeg"


def synthesize_speech(text: str, language: str) -> bytes:
    """
    Convert text to spoken audio.

    Args:
        text: The text to synthesize.
        language: Language code — "en", "si", or "ta".

    Returns:
        For "si": WAV bytes (22 050 Hz, mono) from the local VITS model.
        For "en" / "ta": MP3 bytes from Google Cloud TTS.

    Raises:
        ValueError: If text is empty.
        google.api_core.exceptions.GoogleAPICallError: On GCP TTS failure.
    """
    if not text or not text.strip():
        raise ValueError("Text for TTS cannot be empty.")

    language = language.strip().lower()

    # ── Sinhala: local VITS model ─────────────────────────────────────────────
    if language == "si":
        from .sinhala_tts import synthesize_sinhala
        return synthesize_sinhala(text)

    # ── English / Tamil: Google Cloud TTS ────────────────────────────────────
    tts_locale, voice_name = TTS_VOICE_MAP.get(language, ("en-US", "en-US-Neural2-C"))

    client = _get_client()

    synthesis_input = texttospeech.SynthesisInput(text=text)

    voice_params_kwargs: dict = {"language_code": tts_locale}
    if voice_name:  # None → let Google auto-select (e.g., si-LK has no named voices)
        voice_params_kwargs["name"] = voice_name

    voice_params = texttospeech.VoiceSelectionParams(**voice_params_kwargs)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
    )

    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice_params,
        audio_config=audio_config,
    )

    logger.info(
        "TTS synthesized %d bytes of MP3 for lang=%s, voice=%s",
        len(response.audio_content),
        tts_locale,
        voice_name or "auto",
    )

    return response.audio_content
