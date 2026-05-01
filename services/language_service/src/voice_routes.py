"""
Voice API routes for the Language Service.

Endpoints:
  POST /voice/pipeline   — Full voice pipeline (audio in → audio + metadata out)
  POST /voice/transcribe — STT only (audio in → text + language out)
  POST /voice/synthesize — TTS only (text + language in → audio out)
  POST /voice/translate  — Reverse translate only (English text → target language)
"""

from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from .stt import transcribe_and_translate
from .translation import detect_language, translate_from_english, translate_to_english
from .tts import get_audio_mime_type, synthesize_speech
from .voice_pipeline import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


# ── Request / Response models ─────────────────────────────────────────────────


class SynthesizeRequest(BaseModel):
    text: str
    language: str = "en"


class TranslateRequest(BaseModel):
    text: str
    target_language: str


class PipelineMetadata(BaseModel):
    transcript: str
    detected_language: str
    english_text: str
    final_message: str
    translated_response: str
    followups: list[str]


class PipelineResponse(BaseModel):
    """JSON response from /voice/pipeline — audio is base64-encoded MP3."""
    audio_base64: str
    metadata: PipelineMetadata


class TranscribeResponse(BaseModel):
    transcript: str
    detected_language: str
    english_text: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/pipeline", response_model=PipelineResponse)
async def voice_pipeline_endpoint(
    audio: UploadFile = File(...),
    user_id: str = Form("anonymous"),
    session_id: str = Form("default"),
):
    """
    Full voice pipeline: Audio → STT → Orchestrate → Translate → TTS.

    Expects raw PCM16-LE audio (16 kHz, mono) as a file upload.
    Returns base64-encoded MP3 audio + metadata JSON.
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio file is empty.")

    try:
        result = await run_pipeline(
            audio_bytes=audio_bytes,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception:
        logger.exception("Voice pipeline failed")
        raise HTTPException(status_code=500, detail="Voice pipeline processing failed.")

    return PipelineResponse(
        audio_base64=base64.b64encode(result.audio_bytes).decode("ascii"),
        metadata=PipelineMetadata(
            transcript=result.transcript,
            detected_language=result.detected_language,
            english_text=result.english_text,
            final_message=result.final_message,
            translated_response=result.translated_response,
            followups=result.followups,
        ),
    )


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_endpoint(
    audio: UploadFile = File(...),
):
    """
    STT only — transcribe audio and detect language via Gemini Live.

    Expects raw PCM16-LE audio (16 kHz, mono).
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio file is empty.")

    try:
        result = await transcribe_and_translate(audio_bytes)
    except Exception:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail="Transcription failed.")

    return TranscribeResponse(**result)


@router.post("/synthesize")
async def synthesize_endpoint(req: SynthesizeRequest):
    """
    TTS only — synthesize text to speech.

    Returns raw MP3 audio bytes as audio/mpeg.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    try:
        audio_bytes = synthesize_speech(req.text, req.language)
    except Exception:
        logger.exception("TTS synthesis failed")
        raise HTTPException(status_code=500, detail="Speech synthesis failed.")

    return Response(content=audio_bytes, media_type=get_audio_mime_type(req.language))


@router.post("/translate")
async def translate_endpoint(req: TranslateRequest):
    """
    Translate text to/from English.

    - target_language="en": auto-detects source language and translates TO English.
    - target_language="si"/"ta": assumes English input and translates to that language.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    target = req.target_language.strip().lower()

    if target == "en":
        # Translate arbitrary input language → English
        src_lang = detect_language(req.text)
        translated = translate_to_english(req.text, src_lang)
    else:
        # Translate English → target language
        translated = translate_from_english(req.text, target)

    return {"translated_text": translated, "target_language": req.target_language}
