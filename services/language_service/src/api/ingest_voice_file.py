# /v1/language/ingest-voice-file
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from .schemas import VoiceIngestResponse
from ..pipeline.input_pipeline import InputPipeline
from ..voice.stt.assemblyai import AssemblyAIManager
from ..voice.stt.audio_normalizer import AudioNormalizer
from ..core.logging import get_logger

router = APIRouter()
logger = get_logger("language_service.ingest_voice_file")

pipe = InputPipeline()

# ✅ Lazy init
def get_stt() -> AssemblyAIManager:
    return AssemblyAIManager()


def _safe_suffix(filename: str | None) -> str:
    if not filename:
        return ".bin"
    fn = filename.lower()
    if fn.endswith(".opus"):
        return ".opus"
    if fn.endswith(".ogg"):
        return ".ogg"
    if fn.endswith(".wav"):
        return ".wav"
    if fn.endswith(".mp3"):
        return ".mp3"
    if fn.endswith(".m4a") or fn.endswith(".mp4"):
        return ".m4a"
    if fn.endswith(".webm"):
        return ".webm"
    return Path(fn).suffix or ".bin"


async def _write_upload_to_temp(upload: UploadFile) -> Path:
    suffix = _safe_suffix(upload.filename)
    f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        data = await upload.read()  # ✅ async-safe
        if not data:
            raise HTTPException(status_code=422, detail="Empty uploaded audio file")
        f.write(data)
        f.flush()
    finally:
        f.close()
    return Path(f.name)


@router.post("/ingest-voice-file", response_model=VoiceIngestResponse)
async def ingest_voice_file(
    user_id: str = Form(...),
    session_id: str = Form(...),
    channel: str = Form("voice"),
    lang: str = Form("auto"),
    mode: str = Form("voice"),
    confidence_threshold: float = Form(0.3),
    file: UploadFile = File(...),
):
    """
    Multipart voice ingest:
      file (.opus/.ogg/...) -> normalize -> STT -> text pipeline -> orchestrator
    """
    raw_audio_path: Optional[Path] = None
    norm_wav_path: Optional[Path] = None

    try:
        raw_audio_path = await _write_upload_to_temp(file)

        norm_wav_path = AudioNormalizer.normalize(
            raw_audio_path,
            sample_rate=16000,
            channels=1,
        )

        stt = get_stt()
        tr = await stt.transcribe_file(
            session_id=session_id,
            wav_path=norm_wav_path,
            confidence_threshold=confidence_threshold,
        )

        transcript = (tr.text or "").strip()
        if not transcript:
            raise HTTPException(status_code=422, detail="Empty transcript from STT")

        orch_json = await pipe.process_text(
            user_id=user_id,
            input_text=transcript,
            channel=channel,
            lang=lang,
            session_id=session_id,
            mode="voice",
        )

        return VoiceIngestResponse(
            session_id=session_id,
            transcript=transcript,
            detected_lang=lang,  # if lang="auto", true detected is stored in session_store
            orchestrator_response=orch_json,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"voice ingest file failed session_id={session_id}")
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        for p in [norm_wav_path, raw_audio_path]:
            try:
                if p and p.exists():
                    p.unlink()
            except Exception:
                pass
