# AssemblyAI streaming/batch STT (depending on your plan)
# services/language_service/src/voice/stt/assemblyai.py

from __future__ import annotations

import asyncio
import base64
import re
import json
import httpx
import websockets

from pathlib import Path
from typing import Optional
from typing import Callable, Awaitable

from ...core.settings import settings
from ...core.errors import STTError
from ...core.logging import get_logger

logger = get_logger("language_service.stt.assemblyai")

DATA_URL_RE = re.compile(r"^data:audio\/[a-zA-Z0-9.+-]+;base64,", re.IGNORECASE)


class TranscriptionResult:
    def __init__(self, text: str, confidence: float | None = None):
        self.text = text
        self.confidence = confidence


class AssemblyAIManager:
    """
    REST-based STT:
      bytes/file -> upload -> transcript -> poll -> final text
    """

    BASE = "https://api.assemblyai.com/v2"

    def __init__(self, api_key: Optional[str] = None, timeout_s: float = 60.0):
        self.api_key = api_key or settings.ASSEMBLYAI_API_KEY
        self.timeout_s = timeout_s
        if not self.api_key:
            raise STTError("ASSEMBLYAI_API_KEY is not set")

    async def transcribe_base64(
        self,
        *,
        session_id: str,
        audio_base64: str,
        confidence_threshold: float = 0.3,  # kept for compatibility (not used in REST)
    ) -> TranscriptionResult:
        if not audio_base64:
            raise STTError("audio_base64 is empty")

        # allow "data:audio/opus;base64,...."
        b64 = DATA_URL_RE.sub("", audio_base64.strip())

        try:
            audio_bytes = base64.b64decode(b64)
        except Exception as e:
            raise STTError(f"Invalid base64 audio: {e}") from e

        text = await self._transcribe_bytes(session_id=session_id, audio_bytes=audio_bytes)
        return TranscriptionResult(text=text, confidence=None)

    async def transcribe_file(
        self,
        *,
        session_id: str,
        wav_path: Path,
        confidence_threshold: float = 0.3,  # kept for compatibility
    ) -> TranscriptionResult:
        """
        Reads a local audio file (already normalized if you want) and transcribes it.
        """
        if not wav_path:
            raise STTError("wav_path is required")
        p = Path(wav_path)
        if not p.exists():
            raise STTError(f"Audio file not found: {p}")

        try:
            audio_bytes = p.read_bytes()
        except Exception as e:
            raise STTError(f"Failed to read audio file: {e}") from e

        text = await self._transcribe_bytes(session_id=session_id, audio_bytes=audio_bytes)
        return TranscriptionResult(text=text, confidence=None)

    async def _transcribe_bytes(self, *, session_id: str, audio_bytes: bytes) -> str:
        headers_json = {
            "authorization": self.api_key,
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            # 1) upload
            try:
                up = await client.post(
                    f"{self.BASE}/upload",
                    headers={"authorization": self.api_key},
                    content=audio_bytes,
                )
                up.raise_for_status()
                audio_url = up.json().get("upload_url")
                if not audio_url:
                    raise STTError(f"AssemblyAI upload_url missing: {up.text}")
                logger.info(f"[{session_id}] AAI-UPLOAD ok")
            except Exception as e:
                raise STTError(f"AssemblyAI upload failed: {e}") from e

            # 2) create transcript
            try:
                tr = await client.post(
                    f"{self.BASE}/transcript",
                    headers=headers_json,
                    json={
                        "audio_url": audio_url,
                        "punctuate": True,
                        "format_text": True,
                        # If you want better accuracy (sometimes slower):
                        # "speech_model": "best",
                    },
                )
                tr.raise_for_status()
                tid = tr.json().get("id")
                if not tid:
                    raise STTError(f"AssemblyAI transcript id missing: {tr.text}")
                logger.info(f"[{session_id}] AAI-TRANSCRIPT created id={tid}")
            except Exception as e:
                raise STTError(f"AssemblyAI transcript create failed: {e}") from e

            # 3) poll until completed
            # (increase retries to handle longer audio)
            for _ in range(180):  # ~180s max
                try:
                    st = await client.get(f"{self.BASE}/transcript/{tid}", headers=headers_json)
                    st.raise_for_status()
                    data = st.json()
                    status = data.get("status")

                    if status == "completed":
                        text = (data.get("text") or "").strip()
                        logger.info(f"[{session_id}] AAI-DONE chars={len(text)}")
                        return text

                    if status == "error":
                        raise STTError(f"AssemblyAI transcript error: {data.get('error')}")

                except STTError:
                    raise
                except Exception as e:
                    raise STTError(f"AssemblyAI polling failed: {e}") from e

                await asyncio.sleep(1)

            raise STTError("AssemblyAI transcript timeout (took too long)")

    STREAMING_WS = "wss://streaming.assemblyai.com/v3/ws"

    async def transcribe_stream(
        self,
        session_id: str,
        audio_queue: "asyncio.Queue[bytes]",
        stop_event: "asyncio.Event",
        on_partial: Callable[[str], Awaitable[None]],
        on_final: Callable[[str], Awaitable[None]],
        confidence_threshold: float = 0.3,  # kept for signature compatibility
    ) -> None:
        """
        Streaming STT over AssemblyAI Universal Streaming WebSocket.

        EXPECTATION:
          audio_queue contains raw PCM16LE frames at 16kHz mono (no WAV header).
          Each chunk ~50–500ms is ideal.

        on_partial: called for interim turns
        on_final: called when end_of_turn=True (utterance boundary)
        """

        url = f"{self.STREAMING_WS}?sample_rate=16000"

        async def _sender(ws):
            # send audio bytes as they arrive
            while True:
                if stop_event.is_set() and audio_queue.empty():
                    break
                try:
                    chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    continue

                try:
                    if chunk:
                        await ws.send(chunk)
                finally:
                    audio_queue.task_done()

            # Terminate gracefully
            try:
                await ws.send(json.dumps({"type": "Terminate"}))
            except Exception:
                pass

        async def _receiver(ws):
            # receive Turn messages
            async for msg in ws:
                # websockets returns str for text frames, bytes for binary frames
                if isinstance(msg, (bytes, bytearray)):
                    continue

                try:
                    data = json.loads(msg)
                except Exception:
                    continue

                msg_type = data.get("type")
                if msg_type == "Turn":
                    text = (data.get("transcript") or "").strip()
                    if not text:
                        continue

                    if bool(data.get("end_of_turn")):
                        await on_final(text)
                    else:
                        await on_partial(text)

                elif msg_type == "Error":
                    err = data.get("error") or data.get("message") or "Streaming STT error"
                    raise STTError(f"AssemblyAI streaming error: {err}")

                elif msg_type in ("SessionTerminated", "SessionEnded"):
                    # treat as clean shutdown unless an error is included
                    err = data.get("error") or data.get("message")
                    if err:
                        raise STTError(f"AssemblyAI session terminated: {err}")
                    return

        headers = {"Authorization": self.api_key}

        try:
            async with websockets.connect(url, 
                                          additional_headers=headers, 
                                          ping_interval=20
                                          ) as ws:
                logger.info(f"[{session_id}] AAI-STREAM connected")

                sender_task = asyncio.create_task(_sender(ws))
                receiver_task = asyncio.create_task(_receiver(ws))

                done, pending = await asyncio.wait(
                    {sender_task, receiver_task},
                    return_when=asyncio.FIRST_EXCEPTION,
                )

                # propagate exceptions
                for t in done:
                    exc = t.exception()
                    if exc:
                        raise exc

                for t in pending:
                    t.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

        except Exception as e:
            logger.exception(f"[{session_id}] AAI-STREAM failed")
            raise STTError(str(e)) from e
        finally:
            logger.info(f"[{session_id}] AAI-STREAM closed")