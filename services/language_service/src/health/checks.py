# This does real checks:
# STT REST: generates a tiny silence WAV in-memory → uploads to AssemblyAI → starts transcript → polls briefly
# STT Streaming: connects to AssemblyAI streaming WS and terminates cleanly
# Translator: does si→en→si roundtrip test (or whichever providers exist)
# Orchestrator: checks base URL and /health (if your orchestrator has it)

# services/language_service/src/health/checks.py
from __future__ import annotations

import asyncio
import io
import time
import wave
from typing import Any, Dict, Optional

import httpx
import websockets

from ..core.settings import settings
from ..core.errors import STTError, TranslationError
from ..core.logging import get_logger
from ..translate.google_translate import GoogleTranslator
from ..translate.openai_translate import OpenAITranslator

logger = get_logger("language_service.health.checks")


def _make_silence_wav_bytes(sample_rate: int = 16000, seconds: float = 0.6) -> bytes:
    """
    Create a short PCM16 mono WAV (silence). Used for STT REST smoke tests.
    """
    n = int(sample_rate * seconds)
    pcm16 = b"\x00\x00" * n  # 16-bit little-endian zeros
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16)
    return buf.getvalue()


async def check_stt_rest(timeout_s: float = 20.0) -> Dict[str, Any]:
    """
    Smoke test AssemblyAI REST: upload short audio -> create transcript -> poll briefly.
    This verifies key validity + endpoint reachability.
    """
    t0 = time.perf_counter()
    ok = False
    detail: Dict[str, Any] = {"provider": "assemblyai_rest"}

    if not settings.ASSEMBLYAI_API_KEY:
        return {"ok": False, "detail": {"error": "ASSEMBLYAI_API_KEY not set"}}

    headers_json = {"authorization": settings.ASSEMBLYAI_API_KEY, "content-type": "application/json"}
    base = "https://api.assemblyai.com/v2"

    wav_bytes = _make_silence_wav_bytes(settings.ASSEMBLYAI_SAMPLE_RATE, seconds=0.6)

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            # 1) upload
            up = await client.post(
                f"{base}/upload",
                headers={"authorization": settings.ASSEMBLYAI_API_KEY},
                content=wav_bytes,
            )
            up.raise_for_status()
            audio_url = up.json().get("upload_url")
            if not audio_url:
                raise STTError("upload_url missing in AssemblyAI upload response")

            # 2) transcript create
            tr = await client.post(
                f"{base}/transcript",
                headers=headers_json,
                json={"audio_url": audio_url, "punctuate": True, "format_text": True},
            )
            tr.raise_for_status()
            tid = tr.json().get("id")
            if not tid:
                raise STTError("transcript id missing in AssemblyAI transcript response")
            detail["transcript_id"] = tid

            # 3) poll a few times (don’t wait too long in health endpoint)
            status = None
            text = ""
            for _ in range(8):
                st = await client.get(f"{base}/transcript/{tid}", headers=headers_json)
                st.raise_for_status()
                data = st.json()
                status = data.get("status")
                if status == "completed":
                    text = (data.get("text") or "").strip()
                    ok = True
                    break
                if status == "error":
                    raise STTError(f"AssemblyAI transcript error: {data.get('error')}")
                await asyncio.sleep(0.6)

            detail["status"] = status
            detail["text_preview"] = (text[:60] + "…") if len(text) > 60 else text

    except Exception as e:
        detail["error"] = str(e)
        ok = False

    ms = int((time.perf_counter() - t0) * 1000)
    metrics.record("health_stt_rest", ms, ok=ok)

    return {"ok": ok, "ms": ms, "detail": detail}


async def check_stt_streaming(timeout_s: float = 10.0) -> Dict[str, Any]:
    """
    Smoke test AssemblyAI Streaming WS: connect -> terminate.
    Verifies streaming endpoint + key validity.
    """
    t0 = time.perf_counter()
    ok = False
    detail: Dict[str, Any] = {"provider": "assemblyai_streaming"}

    if not settings.ASSEMBLYAI_API_KEY:
        return {"ok": False, "detail": {"error": "ASSEMBLYAI_API_KEY not set"}}

    url = "wss://streaming.assemblyai.com/v3/ws?sample_rate=16000"
    headers = {"Authorization": settings.ASSEMBLYAI_API_KEY}

    try:
        async with websockets.connect(
            url,
            additional_headers=headers,
            ping_interval=20,
            open_timeout=timeout_s,
        ) as ws:
            # immediately terminate; if auth fails, connect will fail or server will send Error
            await ws.send('{"type":"Terminate"}')
            ok = True

    except Exception as e:
        detail["error"] = str(e)
        ok = False

    ms = int((time.perf_counter() - t0) * 1000)
    metrics.record("health_stt_streaming", ms, ok=ok)
    return {"ok": ok, "ms": ms, "detail": detail}


async def check_translator(roundtrip_text: str = "මට කෑන්ඩි යන්න itinerary එකක් recommend කරන්න") -> Dict[str, Any]:
    """
    Translator check:
      - If Google key present: si->en and en->si
      - Else if OpenAI key present: same
      - Else: reports unavailable
    """
    t0 = time.perf_counter()
    ok = False
    detail: Dict[str, Any] = {"providers": [], "roundtrip": {}}

    try:
        if settings.GOOGLE_TRANSLATE_API_KEY:
            gt = GoogleTranslator()
            detail["providers"].append("google")
            en = await gt.translate(text=roundtrip_text, source_lang="si", target_lang="en")
            back = await gt.translate(text=en, source_lang="en", target_lang="si")
            detail["roundtrip"] = {
                "source_lang": "si",
                "target_lang": "en",
                "input_preview": roundtrip_text[:60] + ("…" if len(roundtrip_text) > 60 else ""),
                "en_preview": en[:60] + ("…" if len(en) > 60 else ""),
                "back_preview": back[:60] + ("…" if len(back) > 60 else ""),
                "provider": "google",
            }
            ok = True

        elif settings.OPENAI_API_KEY:
            ot = OpenAITranslator()
            detail["providers"].append("openai")
            en = await ot.translate(roundtrip_text, source_lang="si", target_lang="en")
            back = await ot.translate(en, source_lang="en", target_lang="si")
            detail["roundtrip"] = {
                "source_lang": "si",
                "target_lang": "en",
                "input_preview": roundtrip_text[:60] + ("…" if len(roundtrip_text) > 60 else ""),
                "en_preview": en[:60] + ("…" if len(en) > 60 else ""),
                "back_preview": back[:60] + ("…" if len(back) > 60 else ""),
                "provider": "openai",
            }
            ok = True

        else:
            detail["error"] = "No translation provider configured (GOOGLE_TRANSLATE_API_KEY or OPENAI_API_KEY)."
            ok = False

    except Exception as e:
        detail["error"] = str(e)
        ok = False

    ms = int((time.perf_counter() - t0) * 1000)
    metrics.record("health_translator", ms, ok=ok)
    return {"ok": ok, "ms": ms, "detail": detail}


async def check_orchestrator(timeout_s: float = 5.0) -> Dict[str, Any]:
    """
    Orchestrator reachability check.
    Tries:
      GET {ORCHESTRATOR_BASE_URL}/health (if exists)
      else GET base URL
    """
    t0 = time.perf_counter()
    ok = False
    detail: Dict[str, Any] = {"base_url": settings.ORCHESTRATOR_BASE_URL}

    base = settings.ORCHESTRATOR_BASE_URL.rstrip("/")
    candidates = [f"{base}/health", base]

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            last_err = None
            for url in candidates:
                try:
                    r = await client.get(url)
                    detail["last_url"] = url
                    detail["status_code"] = r.status_code
                    if r.status_code < 500:
                        ok = True
                        # don’t blow up response size
                        try:
                            detail["response_preview"] = str(r.json())[:200]
                        except Exception:
                            detail["response_preview"] = (r.text or "")[:200]
                        break
                except Exception as e:
                    last_err = e
            if not ok and last_err:
                detail["error"] = str(last_err)

    except Exception as e:
        detail["error"] = str(e)
        ok = False

    ms = int((time.perf_counter() - t0) * 1000)
    metrics.record("health_orchestrator", ms, ok=ok)
    return {"ok": ok, "ms": ms, "detail": detail}
