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

# ✅ metrics store
from ..metrics.store import metrics

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

        logger.info(f"[{session_id}] LANG-INCOMING raw_lang={lang!r}")
        raw_preview = _preview(input_text)
        logger.info(
            f"[{session_id}] USER-INPUT    lang={lang} mode={mode} channel={channel} text=\"{raw_preview}\""
        )

        # -----------------------------------------
        # 1) detect language (if auto/empty)
        # -----------------------------------------
        t_det0 = time.perf_counter()
        try:
            if not lang or lang == "auto":
                detected, conf, perc = detect_language(input_text, default="en")
                lang = detected
                logger.info(f"[{session_id}] LANG-DETECT   detected={lang} confidence={conf:.2f}")
                logger.debug(f"[{session_id}] LANG-SCORES   {perc}")
            else:
                logger.info(f"[{session_id}] LANG-PROVIDED lang={lang}")

            det_ms = int((time.perf_counter() - t_det0) * 1000)
            metrics.record("detect_language_ms", det_ms, ok=True)
        except Exception as e:
            det_ms = int((time.perf_counter() - t_det0) * 1000)
            metrics.record("detect_language_ms", det_ms, ok=False)
            logger.exception(f"[{session_id}] LANG-DETECT-FAIL error={e}")
            raise

        # -----------------------------------------
        # 2) normalize
        # -----------------------------------------
        t_norm0 = time.perf_counter()
        try:
            cleaned = normalize_text(input_text, lang)
            logger.info(f"[{session_id}] NORMALIZED    text=\"{_preview(cleaned)}\"")

            norm_ms = int((time.perf_counter() - t_norm0) * 1000)
            metrics.record("normalize_text_ms", norm_ms, ok=True)
        except Exception as e:
            norm_ms = int((time.perf_counter() - t_norm0) * 1000)
            metrics.record("normalize_text_ms", norm_ms, ok=False)
            logger.exception(f"[{session_id}] NORMALIZE-FAIL error={e}")
            raise

        # -----------------------------------------
        # 3) translate -> English
        # -----------------------------------------
        t_tr0 = time.perf_counter()
        try:
            text_en = await self.translator.to_english(cleaned, source_lang=lang)
            tr_ms = int((time.perf_counter() - t_tr0) * 1000)
            metrics.record("translate_to_en_ms", tr_ms, ok=True)

            logger.info(f"[{session_id}] TRANSLATED-EN text=\"{_preview(text_en)}\" (t={tr_ms}ms)")
            logger.info(f"[{session_id}] LANG-PIPELINE input_lang={lang} → translated_to=en")
        except Exception as e:
            tr_ms = int((time.perf_counter() - t_tr0) * 1000)
            metrics.record("translate_to_en_ms", tr_ms, ok=False)
            logger.exception(f"[{session_id}] TRANSLATE-FAIL error={e}")
            raise

        # -----------------------------------------
        # 4) save session
        # -----------------------------------------
        try:
            session_store.set_many(session_id, lang=lang, mode=mode)
            logger.info(f"[{session_id}] SESSION-SAVE  lang={lang} mode={mode}")
        except Exception as e:
            # session store failures are important to track (affects output language)
            metrics.record("session_store_write_ms", 0, ok=False)
            logger.exception(f"[{session_id}] SESSION-SAVE-FAIL error={e}")
            raise

        # -----------------------------------------
        # 5) payload to orchestrator
        # -----------------------------------------
        payload = OrchestratorRequest(
            user_id=user_id,
            input_text=text_en,
            channel=channel,
            lang="en",
            session_id=session_id,
        )

        logger.info(
            f"[{session_id}] ORCH-SEND     user_id={user_id} lang=en channel={channel} text=\"{_preview(text_en)}\""
        )

        t_orch0 = time.perf_counter()
        try:
            orch_json = await self.orch.plan(payload.model_dump())
            orch_ms = int((time.perf_counter() - t_orch0) * 1000)
            metrics.record("call_orchestrator_ms", orch_ms, ok=True)
        except Exception as e:
            orch_ms = int((time.perf_counter() - t_orch0) * 1000)
            metrics.record("call_orchestrator_ms", orch_ms, ok=False)
            logger.exception(f"[{session_id}] ORCH-FAIL     error={e}")
            raise

        # -----------------------------------------
        # total
        # -----------------------------------------
        total_ms = int((time.perf_counter() - t0) * 1000)
        metrics.record("pipeline_total_ms", total_ms, ok=True)

        logger.info(f"[{session_id}] ORCH-OK       total={total_ms}ms")
        return orch_json
