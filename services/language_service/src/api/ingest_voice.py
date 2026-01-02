# /v1/language/ingest-voice
from __future__ import annotations

import base64
import re
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from fastapi import APIRouter, HTTPException

from .schemas import VoiceIngestRequest, VoiceIngestResponse
from ..pipeline.input_pipeline import InputPipeline
from ..voice.stt.assemblyai import AssemblyAIManager
from ..voice.stt.audio_loader import download_audio
from ..voice.stt.audio_normalizer import AudioNormalizer
from ..core.logging import get_logger

router = APIRouter()
logger = get_logger("language_service.ingest_voice")

pipe = InputPipeline()

# ✅ DO NOT instantiate AssemblyAIManager at import-time
def get_stt() -> AssemblyAIManager:
    return AssemblyAIManager()


_DATA_URL_RE = re.compile(
    r"^data:(?P<mime>[-\w.+/]+)?;base64,(?P<b64>.+)$",
    re.IGNORECASE,
)


def _strip_data_url(b64_or_dataurl: str) -> str:
    """Accept plain base64 OR data URL: data:audio/opus;base64,XXXX -> return pure base64."""
    m = _DATA_URL_RE.match((b64_or_dataurl or "").strip())
    if m:
        return m.group("b64")
    return b64_or_dataurl


def _parse_data_url(b64_or_dataurl: str) -> Tuple[Optional[str], str]:
    """Returns (mime, pure_base64). If not a data URL -> (None, original)."""
    s = (b64_or_dataurl or "").strip()
    m = _DATA_URL_RE.match(s)
    if not m:
        return None, s
    return m.group("mime"), m.group("b64")


def _best_suffix_from_mime(mime: Optional[str]) -> str:
    if not mime:
        return ".bin"
    mime = mime.lower()
    if "opus" in mime:
        return ".opus"
    if "ogg" in mime:
        return ".ogg"
    if "wav" in mime:
        return ".wav"
    if "mpeg" in mime or "mp3" in mime:
        return ".mp3"
    if "m4a" in mime or "mp4" in mime:
        return ".m4a"
    if "webm" in mime:
        return ".webm"
    return ".bin"


def _write_bytes_to_temp(data: bytes, suffix: str = ".bin") -> Path:
    f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        f.write(data)
        f.flush()
    finally:
        f.close()
    return Path(f.name)


@router.post("/ingest-voice", response_model=VoiceIngestResponse)
async def ingest_voice(req: VoiceIngestRequest):
    """
    JSON voice ingest:
      audio (base64 OR url) -> normalize -> STT -> text pipeline -> orchestrator
    """
    raw_audio_path: Optional[Path] = None
    norm_wav_path: Optional[Path] = None

    try:
        # 1) Load audio input
        if req.audio_url:
            raw_audio_path = await download_audio(req.audio_url)

        elif req.audio_base64:
            mime, pure_b64 = _parse_data_url(req.audio_base64)
            pure_b64 = _strip_data_url(pure_b64)

            try:
                raw_bytes = base64.b64decode(pure_b64, validate=False)
            except Exception as e:
                raise HTTPException(status_code=422, detail=f"Invalid base64 audio: {e}")

            suffix = _best_suffix_from_mime(mime)
            raw_audio_path = _write_bytes_to_temp(raw_bytes, suffix=suffix)

        else:
            raise HTTPException(status_code=422, detail="audio_url or audio_base64 is required")

        # 2) Normalize
        norm_wav_path = AudioNormalizer.normalize(raw_audio_path, sample_rate=16000, channels=1)

        # 3) STT (lazy init)
        stt = get_stt()
        tr = await stt.transcribe_file(
            session_id=req.session_id,
            wav_path=norm_wav_path,
            confidence_threshold=req.confidence_threshold,
        )

        transcript = (tr.text or "").strip()
        if not transcript:
            raise HTTPException(status_code=422, detail="Empty transcript from STT")

        # 4) Reuse text pipeline
        orch_json = await pipe.process_text(
            user_id=req.user_id,
            input_text=transcript,
            channel=req.channel,
            lang=req.lang,
            session_id=req.session_id,
            mode="voice",
        )

        # NOTE: if lang=="auto", true detected lang is inside InputPipeline (session_store).
        detected_lang = req.lang if req.lang != "auto" else "auto"

        return VoiceIngestResponse(
            session_id=req.session_id,
            transcript=transcript,
            detected_lang=detected_lang,
            orchestrator_response=orch_json,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"voice ingest failed session_id={req.session_id}")
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        for p in [norm_wav_path, raw_audio_path]:
            try:
                if p and p.exists():
                    p.unlink()
            except Exception:
                pass
