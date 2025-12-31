# handle_text_input(session_id, text)
# handle_voice_input(session_id, base64_audio)
# steps: STT(if voice) → normalize → detect_lang → translate_to_en → save(session lang+mode) → build JSON → send orchestrator

from __future__ import annotations

import time
from typing import Any, Dict

from ..language.detector import detect_language
from ..language.normalizer import normalize_text
from ..translate.translator import Translator
from ..storage.session_store import session_store
from ..orchestrator_client.client import OrchestratorClient
from ..orchestrator_client.schemas import OrchestratorRequest
from ..core.logging import get_logger

logger = get_logger("language_service.input_pipeline")

def _preview(s: str, n: int = 90) -> str:
    s = (s or "").replace("\n", " ").strip()
    return (s[:n] + "…") if len(s) > n else s

class InputPipeline:
    def __init__(self):
        self.translator = Translator()
        self.orch = OrchestratorClient()

    async def process_text(
        self,
        *,
        user_id: str,
        input_text: str,
        channel: str,
        lang: str,
        session_id: str,
        mode: str = "text",
    ) -> dict:
        t0 = time.perf_counter()

        raw_preview = _preview(input_text)
        logger.info(f"[{session_id}] USER-INPUT    lang={lang} mode={mode} channel={channel} text=\"{raw_preview}\"")

        # 1) detect language if auto/empty
        # if not lang or lang == "auto":
        #     lang, conf, p = detect_language(input_text, default="en")
        #     logger.info(f"[{session_id}] detected_lang={lang} conf={conf:.2f} perc={p}")
        # else:
        #     logger.info(f"[{session_id}] provided_lang={lang}")

        if not lang or lang == "auto":
            detected, conf, perc = detect_language(input_text, default="en")
            lang = detected
            logger.info(f"[{session_id}] LANG-DETECT   detected={lang} confidence={conf:.2f}")
            # If you want the full breakdown, keep it as DEBUG (not INFO)
            logger.debug(f"[{session_id}] LANG-SCORES   {perc}")
        else:
            logger.info(f"[{session_id}] LANG-PROVIDED lang={lang}")

        # 2) normalize
        # cleaned = normalize_text(input_text, lang)
        # logger.info(f"[{session_id}] normalized_text={cleaned}")
        
        cleaned = normalize_text(input_text, lang)
        logger.info(f"[{session_id}] NORMALIZED    text=\"{_preview(cleaned)}\"")

        # 3) translate -> English
        # text_en = await self.translator.to_english(cleaned, source_lang=lang)
        # logger.info(f"[{session_id}] translated_en={text_en}")

        t_tr0 = time.perf_counter()
        text_en = await self.translator.to_english(cleaned, source_lang=lang)
        tr_ms = int((time.perf_counter() - t_tr0) * 1000)

        logger.info(
            f"[{session_id}] TRANSLATED-EN text=\"{_preview(text_en)}\" (t={tr_ms}ms)"
        )

        # 4) save session
        # session_store.set_many(session_id, lang=lang, mode=mode)

        session_store.set_many(session_id, lang=lang, mode=mode)
        logger.info(f"[{session_id}] SESSION-SAVE  lang={lang} mode={mode}")

        # 5) payload to orchestrator
        payload = OrchestratorRequest(
            user_id=user_id,
            input_text=text_en,
            channel=channel,
            lang="en",
            session_id=session_id,
        )

        # logger.info(f"[{session_id}] orchestrator_payload={payload.model_dump()}")

        # orch_json = await self.orch.plan(payload.model_dump())
        # logger.info(f"[{session_id}] orchestrator_status=success")
        # return orch_json
    
        logger.info(
            f"[{session_id}] ORCH-SEND     user_id={user_id} lang=en channel={channel} text=\"{_preview(text_en)}\""
        )

        try:
            orch_json = await self.orch.plan(payload.model_dump())
        except Exception as e:
            logger.exception(f"[{session_id}] ORCH-FAIL     error={e}")
            raise

        total_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(f"[{session_id}] ORCH-OK       total={total_ms}ms")
        return orch_json