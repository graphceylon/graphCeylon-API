"""
Speech-to-Text via Gemini generateContent — reliable multimodal transcription.

Uses `gemini-2.5-flash` (standard content generation, NOT Live API) with audio
input. This model reliably transcribes pre-recorded audio without hallucination.

Pipeline:
  1. Normalise audio → WAV mono 16 kHz (Gemini accepts WAV directly).
  2. Send to Gemini via generateContent with a transcription prompt.
  3. Detect language of transcript via Cloud Translation API.
  4. Translate to English if needed.
"""

from __future__ import annotations

import io
import logging
import wave
from typing import Any

import numpy as np
import scipy.signal
import google.genai as genai
from google.genai import types

from .config import GEMINI_LOCATION, GOOGLE_CLOUD_PROJECT, SEND_SAMPLE_RATE
from .translation import detect_language, translate_to_english

logger = logging.getLogger(__name__)

# Standard Gemini model for multimodal transcription (supports audio input natively)
_STT_MODEL = "gemini-2.5-flash"

_TRANSCRIBE_PROMPT = (
    "Transcribe the speech in this audio file exactly as spoken. "
    "Output ONLY the transcribed text with no additional commentary, "
    "explanations, or formatting. If the audio is silent or inaudible, "
    "output an empty string."
)

# ── Audio format detection & normalisation ────────────────────────────────────

# Formats that Gemini natively supports — send as-is with the correct MIME type.
# (https://ai.google.dev/gemini-api/docs/audio)
_MIME_SIGNATURES: list[tuple[bytes, int, bytes, str]] = [
    # (magic_bytes, offset, mask_or_empty, mime_type)
    # WAV  — handled separately (normalised to 16 kHz mono)
    (b"RIFF", 0, b"WAVE", "audio/wav"),
    # MP3
    (b"\xff\xfb", 0, b"", "audio/mp3"),
    (b"\xff\xf3", 0, b"", "audio/mp3"),
    (b"\xff\xf2", 0, b"", "audio/mp3"),
    (b"ID3",      0, b"", "audio/mp3"),
    # AAC / ADTS
    (b"\xff\xf1", 0, b"", "audio/aac"),
    (b"\xff\xf9", 0, b"", "audio/aac"),
    # FLAC
    (b"fLaC", 0, b"", "audio/flac"),
    # OGG (covers Opus-in-OGG too)
    (b"OggS", 0, b"", "audio/ogg"),
    # WebM / Matroska
    (b"\x1a\x45\xdf\xa3", 0, b"", "audio/webm"),
]


def _detect_mime_type(audio_bytes: bytes) -> str:
    """Return the MIME type inferred from the file magic bytes, defaulting to audio/wav."""
    for magic, offset, secondary, mime in _MIME_SIGNATURES:
        if audio_bytes[offset: offset + len(magic)] == magic:
            if secondary and mime == "audio/wav":
                # Extra check: bytes 8-12 must be 'WAVE'
                if audio_bytes[8:12] != secondary:
                    continue
            return mime
    # Unknown format — assume WAV (Gemini will error if truly unsupported)
    return "audio/wav"


def _to_mono_16khz_wav(audio_bytes: bytes) -> bytes:
    """
    Convert a WAV file to mono 16 kHz WAV.
    Only called for WAV input; other formats are passed directly to Gemini.
    Returns raw WAV bytes.
    """
    try:
        with wave.open(io.BytesIO(audio_bytes)) as wf:
            channels = wf.getnchannels()
            rate = wf.getframerate()
            sampwidth = wf.getsampwidth()
            raw_frames = wf.readframes(wf.getnframes())

        logger.debug("WAV input: %d ch, %d Hz, %d bit", channels, rate, sampwidth * 8)

        dtype = np.int16 if sampwidth == 2 else np.int32
        samples = np.frombuffer(raw_frames, dtype=dtype).astype(np.float32)

        if sampwidth == 2:
            samples /= 32768.0
        elif sampwidth == 4:
            samples /= 2147483648.0

        # Stereo → mono
        if channels == 2:
            samples = samples.reshape(-1, 2).mean(axis=1)
        elif channels > 2:
            samples = samples.reshape(-1, channels).mean(axis=1)

        # Resample to 16 kHz
        if rate != 16_000:
            num_out = int(round(len(samples) * 16_000 / rate))
            samples = scipy.signal.resample(samples, num_out)

        # Convert back to int16
        samples = np.clip(samples * 32767.0, -32768.0, 32767.0).astype(np.int16)

        # Write as WAV
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wout:
            wout.setnchannels(1)
            wout.setsampwidth(2)
            wout.setframerate(16_000)
            wout.writeframes(samples.tobytes())
        return buf.getvalue()

    except Exception:
        logger.warning("WAV normalisation failed; sending audio as-is")
        return audio_bytes


# ── Gemini client (module-level singleton) ────────────────────────────────────

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(
            vertexai=True,
            project=GOOGLE_CLOUD_PROJECT,
            location=GEMINI_LOCATION,
        )
    return _client


# ── Public API ────────────────────────────────────────────────────────────────

async def transcribe_and_translate(audio_bytes: bytes) -> dict[str, Any]:
    """
    Transcribe audio and return transcript, detected language, and English translation.

    Args:
        audio_bytes: WAV file bytes OR raw PCM16-LE @ 16 kHz mono.

    Returns:
        {
            "transcript": str,        # original language text
            "detected_language": str,  # "en" | "si" | "ta"
            "english_text": str,       # English translation
        }
    """
    client = _get_client()

    mime_type = _detect_mime_type(audio_bytes)
    if mime_type == "audio/wav":
        # Normalise WAV to mono 16 kHz for best transcription accuracy
        audio_bytes = _to_mono_16khz_wav(audio_bytes)
        logger.info("Audio prepared: %d WAV bytes (normalised) for transcription", len(audio_bytes))
    else:
        logger.info("Audio prepared: %d bytes, format=%s for transcription", len(audio_bytes), mime_type)

    response = client.models.generate_content(
        model=_STT_MODEL,
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
            types.Part(text=_TRANSCRIBE_PROMPT),
        ],
    )

    transcript = (response.text or "").strip()
    logger.info("Gemini transcription: %s", transcript)

    if not transcript:
        logger.warning("Empty transcription received")
        return {"transcript": "", "detected_language": "en", "english_text": ""}

    detected_language = detect_language(transcript)
    english_text = translate_to_english(transcript, detected_language)

    return {
        "transcript": transcript,
        "detected_language": detected_language,
        "english_text": english_text,
    }

