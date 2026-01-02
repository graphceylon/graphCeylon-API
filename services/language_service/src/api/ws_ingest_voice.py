# language_service/src/api/ws_ingest_voice.py
from __future__ import annotations

import asyncio
import base64
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from ..pipeline.input_pipeline import InputPipeline
from ..voice.stt.assemblyai import AssemblyAIManager
from ..core.logging import get_logger

router = APIRouter()
logger = get_logger("language_service.ws_ingest_voice")

pipe = InputPipeline()

# ✅ Lazy init (important so app boots without ASSEMBLYAI_API_KEY)
def get_stt() -> AssemblyAIManager:
    return AssemblyAIManager()


async def ws_send(ws: WebSocket, obj: dict):
    # don't send if socket already closing/closed
    if ws.client_state != WebSocketState.CONNECTED:
        return
    try:
        await ws.send_text(json.dumps(obj, ensure_ascii=False))
    except RuntimeError:
        # happens if close raced with send
        return

@router.websocket("/ws/ingest-voice")
async def ws_ingest_voice(ws: WebSocket):
    await ws.accept()

    user_id: Optional[str] = None
    session_id: Optional[str] = None
    lang: str = "auto"
    channel: str = "voice"
    confidence_threshold: float = 0.3

    audio_q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
    stop_event = asyncio.Event()

    async def on_partial(text: str):
        await ws_send(ws, {"type": "stt_partial", "text": text})

    async def on_final(text: str):
        await ws_send(ws, {"type": "stt_final", "text": text})

        # Only run pipeline on final utterances
        try:
            if not user_id or not session_id:
                await ws_send(ws, {"type": "error", "detail": "Missing user_id/session_id. Send 'start' first."})
                return

            orch_json = await pipe.process_text(
                user_id=user_id,
                input_text=text,
                channel=channel,
                lang=lang,
                session_id=session_id,
                mode="voice",
            )
            await ws_send(ws, {"type": "orchestrator", "payload": orch_json})
        except Exception as e:
            logger.exception("pipeline failed")
            await ws_send(ws, {"type": "error", "detail": str(e)})

    async def stt_task():
        """
        Consumes audio bytes from audio_q and sends to AssemblyAI streaming.
        """
        try:
            if not session_id:
                raise RuntimeError("session_id is not set. Send 'start' first.")

            stt = get_stt()  # ✅ lazy init
            await stt.transcribe_stream(
                session_id=session_id,
                audio_queue=audio_q,
                stop_event=stop_event,
                on_partial=on_partial,
                on_final=on_final,
                confidence_threshold=confidence_threshold,
            )
        except Exception as e:
            logger.exception("stt stream failed")
            await ws_send(ws, {"type": "error", "detail": str(e)})

    task: Optional[asyncio.Task] = None

    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)

            t = data.get("type")
            if t == "start":
                user_id = data["user_id"]
                session_id = data["session_id"]
                lang = data.get("lang", "auto")
                channel = data.get("channel", "voice")
                confidence_threshold = float(data.get("confidence_threshold", 0.3))

                stop_event.clear()

                # Start STT stream task
                task = asyncio.create_task(stt_task())
                await ws_send(ws, {"type": "started", "session_id": session_id})

            elif t == "audio":
                # Expect PCM16 16k mono base64 chunks
                b64 = data.get("audio_b64")
                if not b64:
                    continue

                chunk = base64.b64decode(b64, validate=False)

                try:
                    audio_q.put_nowait(chunk)
                except asyncio.QueueFull:
                    await ws_send(ws, {"type": "warning", "detail": "audio queue full; dropping chunk"})

            elif t == "stop":
                stop_event.set()
                await ws_send(ws, {"type": "stopping"})
                break

            else:
                await ws_send(ws, {"type": "error", "detail": f"Unknown message type: {t}"})

    except WebSocketDisconnect:
        stop_event.set()

    finally:
        stop_event.set()
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
