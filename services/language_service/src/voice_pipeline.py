#hinesha

"""
Full voice pipeline: Gemini Live STT → Orchestrate → Translate → TTS.

This module ties together the four stages of the voice flow:
  1. **Gemini Live STT** — transcribe audio, detect language, translate to English
  2. **Orchestrate** — send English text to the orchestrator for intent/response
  3. **Reverse translate** — translate English response back to detected language
  4. **TTS** — synthesize the translated response into spoken audio (MP3)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

from .config import ORCHESTRATOR_URL
from .stt import transcribe_and_translate
from .translation import translate_from_english
from .tts import synthesize_speech

logger = logging.getLogger(__name__)

# Symbols that look bad when read aloud or passed to TTS/translation
_SYMBOL_REPLACEMENTS = [
    ("↳", ""),          # sub-item arrow
    ("→", " to "),      # right arrow
    ("←", " from "),    # left arrow
    ("•", ""),          # bullet point
    ("◦", ""),          # white bullet
    ("‣", ""),          # triangular bullet
    ("—", ", "),        # em dash
    ("–", " to "),      # en dash (often used as range separator)
    ("|", ","),         # pipe separator
]


def _sanitize_for_speech(text: str) -> str:
    """Remove or replace markdown/Unicode formatting symbols unsuitable for TTS."""
    for symbol, replacement in _SYMBOL_REPLACEMENTS:
        text = text.replace(symbol, replacement)
    # Collapse multiple spaces / blank lines into a single space
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    # Strip leading/trailing whitespace on each line
    text = "\n".join(line.strip() for line in text.splitlines())
    return text.strip()


@dataclass
class VoicePipelineResult:
    """Holds all outputs from a full voice pipeline run."""

    # STT stage
    transcript: str              # original language text
    detected_language: str       # "en" | "si" | "ta"
    english_text: str            # English translation of transcript

    # Orchestrator stage
    orchestrator_response: dict  # full JSON from /orchestrate
    final_message: str           # English response text
    followups: list[str]

    # Reverse translation stage
    translated_response: str     # response in the user's language

    # TTS stage
    audio_bytes: bytes           # MP3 audio of the final spoken response


async def run_pipeline(
    *,
    audio_bytes: bytes,
    user_id: str,
    session_id: str,
) -> VoicePipelineResult:
    """
    Execute the full voice pipeline end-to-end.

    Args:
        audio_bytes: Raw PCM16-LE audio at 16 kHz, mono (from the client).
        user_id: User identifier for the orchestrator.
        session_id: Session identifier for conversational context.

    Returns:
        VoicePipelineResult with all intermediate and final outputs.
    """

    # ── Stage 1: Gemini Live STT (transcribe + detect lang + translate) ──────
    logger.info("Pipeline: Stage 1 — Gemini Live STT")
    stt_result = await transcribe_and_translate(audio_bytes)
    transcript = stt_result["transcript"]
    detected_language = stt_result["detected_language"]
    english_text = stt_result["english_text"]

    logger.info(
        "STT result: lang=%s, transcript='%s', english='%s'",
        detected_language,
        transcript[:80],
        english_text[:80],
    )

    # ── Stage 2: Orchestrate (send English text to the orchestrator) ──────────
    logger.info("Pipeline: Stage 2 — Orchestrate")
    orchestrator_payload = {
        "input_text": english_text,
        "user_id": user_id,
        "session_id": session_id,
        "channel": "voice",
        "lang": detected_language,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{ORCHESTRATOR_URL}/orchestrate",
            json=orchestrator_payload,
        )
        resp.raise_for_status()
        orchestrator_response = resp.json()

    final_message = orchestrator_response.get("final_message", "")
    followups = orchestrator_response.get("followups", [])

    # Strip formatting symbols that are unsuitable for TTS / translation
    final_message = _sanitize_for_speech(final_message)

    logger.info("Orchestrator reply: '%s'", final_message[:120])

    # ── Stage 3: Reverse translate (English → user's language) ────────────────
    logger.info("Pipeline: Stage 3 — Reverse translate (en → %s)", detected_language)
    translated_response = translate_from_english(final_message, detected_language)

    # ── Stage 4: TTS (synthesize translated response) ─────────────────────────
    logger.info("Pipeline: Stage 4 — TTS (lang=%s)", detected_language)
    tts_audio = synthesize_speech(translated_response, detected_language)

    return VoicePipelineResult(
        transcript=transcript,
        detected_language=detected_language,
        english_text=english_text,
        orchestrator_response=orchestrator_response,
        final_message=final_message,
        followups=followups,
        translated_response=translated_response,
        audio_bytes=tts_audio,
    )
