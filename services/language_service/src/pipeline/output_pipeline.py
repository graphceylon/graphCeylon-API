# # render_output(session_id, orchestrator_json)
# # steps: load lang+mode → translate_from_en → optional TTS → return final payload to UI


from __future__ import annotations

from typing import Any, Dict, List

from ..translate.translator import Translator
from ..storage.session_store import session_store
from ..voice.tts.elevenlabs import ElevenLabsTTS


TRANSLATABLE_KEYS = {"final_answer", "answer", "text", "message", "summary", "explanation"}

def _translate_fields_in_dict(d: Dict[str, Any], translate_fn) -> Dict[str, Any]:
    """
    Translate known user-facing string fields, keep everything else unchanged.
    """
    out = dict(d)
    for k, v in d.items():
        if k in TRANSLATABLE_KEYS and isinstance(v, str):
            out[k] = translate_fn(v)
        elif isinstance(v, dict):
            out[k] = _translate_fields_in_dict(v, translate_fn)
        elif isinstance(v, list):
            out[k] = _translate_fields_in_list(v, translate_fn)
    return out

def _translate_fields_in_list(items: List[Any], translate_fn) -> List[Any]:
    out = []
    for x in items:
        if isinstance(x, str):
            out.append(translate_fn(x))
        elif isinstance(x, dict):
            out.append(_translate_fields_in_dict(x, translate_fn))
        elif isinstance(x, list):
            out.append(_translate_fields_in_list(x, translate_fn))
        else:
            out.append(x)
    return out


class OutputPipeline:
    def __init__(self):
        self.translator = Translator()
        self.tts = ElevenLabsTTS()

    async def render(self, *, session_id: str, orchestrator_output: dict) -> dict:
        lang = session_store.get_language(session_id) or "en"
        mode = session_store.get_mode(session_id) or "text"

        # If user language is English, return as-is
        if lang == "en":
            text_out = orchestrator_output.get("final_answer") or orchestrator_output.get("message") or str(orchestrator_output)
            result = {
                "session_id": session_id,
                "lang": lang,
                "mode": mode,
                "text": text_out,
                "voice_audio_base64": None,
            }
            if mode == "voice":
                audio = await self.tts.synthesize(text_out)
                result["voice_audio_base64"] = audio
            return result

        # Translate selected fields
        async def _t(s: str) -> str:
            return await self.translator.from_english(s, target_lang=lang)

        # Because our helper expects sync translate_fn, do a 2-pass:
        # 1) collect strings -> translate async
        # 2) rebuild
        to_translate = []

        def _collect(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if k in TRANSLATABLE_KEYS and isinstance(v, str):
                        to_translate.append(v)
                    else:
                        _collect(v)
            elif isinstance(d, list):
                for x in d:
                    _collect(x)

        _collect(orchestrator_output)

        translated_map = {}
        for s in to_translate:
            if s not in translated_map:
                translated_map[s] = await _t(s)

        def _translate_fn_sync(s: str) -> str:
            return translated_map.get(s, s)

        translated_output = _translate_fields_in_dict(orchestrator_output, _translate_fn_sync)

        # Choose what to show to UI as main text:
        text_user = (
            translated_output.get("final_answer")
            or translated_output.get("message")
            or str(translated_output)
        )

        result = {
            "session_id": session_id,
            "lang": lang,
            "mode": mode,
            "text": text_user,
            "voice_audio_base64": None,
        }

        if mode == "voice":
            audio = await self.tts.synthesize(text_user)
            result["voice_audio_base64"] = audio

        return result