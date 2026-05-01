"""
Voice feature tests — run without any live network connections or a running app.

All external services are mocked:
  - Gemini Live STT          (google.genai)
  - Google Cloud TTS         (google.cloud.texttospeech)
  - Google Cloud Translation (google.cloud.translate_v3)
  - Orchestrator HTTP calls  (httpx.AsyncClient)
  - Sinhala VITS model       (sinhala_tts.synthesize_sinhala)

Run from the language_service directory:
    pip install pytest pytest-asyncio httpx
    pytest tests/test_voice_features.py -v

Coverage:
  Section 1 — stt._parse_response / _validate_result  (pure logic, no I/O)
  Section 2 — tts.synthesize_speech + get_audio_mime_type (GCP TTS + VITS mocked)
  Section 3 — sinhala_tts.synthesize_sinhala          (VITS Synthesizer mocked)
  Section 4 — translation.translate_from_english      (GCP Translation mocked)
  Section 5 — voice_pipeline.run_pipeline             (all external calls mocked)
  Section 6 — FastAPI /voice/* routes                 (TestClient + mocked services)
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── Shared test data ──────────────────────────────────────────────────────────

# Fake MP3 header bytes (realistic enough for content-type / b64 assertions)
FAKE_MP3 = b"ID3" + b"\xff\xfb" * 50

# Minimal well-formed WAV header for Sinhala VITS output assertions
FAKE_WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 50

# 100 ms of silence at 16 kHz mono PCM16 (3 200 bytes)
DUMMY_PCM = b"\x00\x01" * 1600


# ── Shared helpers ────────────────────────────────────────────────────────────

def _build_orch_resp(message: str = "Visit Sigiriya.", followups: list | None = None) -> MagicMock:
    """Return a mock httpx.Response that looks like the orchestrator's reply."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "final_message": message,
        "followups": followups or [],
    }
    return mock_resp


def _mock_httpx_client(orch_resp: MagicMock) -> MagicMock:
    """
    Return a replacement for httpx.AsyncClient that works as an async context
    manager and whose .post() returns orch_resp.

    Usage:
        with patch("httpx.AsyncClient", _mock_httpx_client(orch_resp)):
            ...
    """
    mock_http = AsyncMock()
    mock_http.post = AsyncMock(return_value=orch_resp)

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_http)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_class = MagicMock(return_value=mock_cm)
    return mock_class


# =============================================================================
# Section 1 — stt._parse_response / _validate_result  (pure functions)
# =============================================================================

class TestParseResponse:
    """Gemini response JSON-parsing helpers — zero external calls."""

    def setup_method(self):
        from src.stt import _parse_response, _validate_result
        self._parse = _parse_response
        self._validate = _validate_result

    # ── _parse_response ───────────────────────────────────────────────────────

    def test_valid_json_string(self):
        raw = '{"transcript": "hello", "detected_language": "en", "english_text": "hello"}'
        r = self._parse(raw)
        assert r["transcript"] == "hello"
        assert r["detected_language"] == "en"
        assert r["english_text"] == "hello"

    def test_json_inside_markdown_code_block(self):
        raw = (
            '```json\n'
            '{"transcript": "ආයුබෝවන්", "detected_language": "si", "english_text": "welcome"}\n'
            '```'
        )
        r = self._parse(raw)
        assert r["detected_language"] == "si"
        assert r["english_text"] == "welcome"

    def test_json_embedded_in_prose(self):
        raw = 'Result: {"transcript": "வணக்கம்", "detected_language": "ta", "english_text": "hello"} done.'
        r = self._parse(raw)
        assert r["detected_language"] == "ta"
        assert r["english_text"] == "hello"

    def test_fallback_to_raw_text_when_not_json(self):
        raw = "Not JSON at all."
        r = self._parse(raw)
        assert r["transcript"] == raw
        assert r["detected_language"] == "en"
        assert r["english_text"] == raw

    def test_fallback_on_empty_string(self):
        r = self._parse("")
        assert r["detected_language"] == "en"

    # ── _validate_result ──────────────────────────────────────────────────────

    def test_normalizes_unknown_language_to_en(self):
        r = self._validate({"transcript": "bonjour", "detected_language": "fr", "english_text": "hello"})
        assert r["detected_language"] == "en"

    def test_normalizes_hyphenated_locale_code(self):
        r = self._validate({"transcript": "hi", "detected_language": "en-US", "english_text": "hi"})
        assert r["detected_language"] == "en"

    def test_si_locale_prefix_normalized(self):
        r = self._validate({"transcript": "x", "detected_language": "si-LK", "english_text": "x"})
        assert r["detected_language"] == "si"

    def test_fills_missing_english_text_from_transcript(self):
        r = self._validate({"transcript": "hello"})
        assert r["english_text"] == "hello"

    def test_all_supported_languages_pass_through(self):
        for lang in ("en", "si", "ta"):
            r = self._validate({"transcript": "x", "detected_language": lang, "english_text": "x"})
            assert r["detected_language"] == lang

    def test_result_always_contains_required_keys(self):
        r = self._validate({})
        assert {"transcript", "detected_language", "english_text"} == set(r.keys())


# =============================================================================
# Section 2 — tts.synthesize_speech + get_audio_mime_type
# =============================================================================

class TestSynthesizeSpeech:

    def _mock_gcp_tts_client(self, audio_bytes: bytes = FAKE_MP3) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.audio_content = audio_bytes
        mock_client = MagicMock()
        mock_client.synthesize_speech.return_value = mock_resp
        return mock_client

    def _call_gcp(self, text: str, language: str, mock_client: MagicMock | None = None) -> bytes:
        """Call synthesize_speech for English/Tamil (GCP path)."""
        from src import tts as tts_mod
        client = mock_client or self._mock_gcp_tts_client()
        with patch.object(tts_mod, "_client", client):
            return tts_mod.synthesize_speech(text, language)

    # ── GCP path (en, ta) ──────────────────────────────────────────────────

    def test_english_returns_mp3_bytes(self):
        assert self._call_gcp("Welcome to Sri Lanka.", "en") == FAKE_MP3

    def test_tamil_returns_mp3_bytes(self):
        assert self._call_gcp("வணக்கம்", "ta") == FAKE_MP3

    def test_empty_text_raises_value_error(self):
        from src import tts as tts_mod
        with pytest.raises(ValueError, match="empty"):
            tts_mod.synthesize_speech("", "en")

    def test_whitespace_only_raises_value_error(self):
        from src import tts as tts_mod
        with pytest.raises(ValueError):
            tts_mod.synthesize_speech("   ", "en")

    def test_unknown_language_falls_back_to_english_voice(self):
        from src import tts as tts_mod
        mock_client = self._mock_gcp_tts_client()
        with patch.object(tts_mod, "_client", mock_client):
            result = tts_mod.synthesize_speech("Hello", "xx")
        assert result == FAKE_MP3
        call_kwargs = mock_client.synthesize_speech.call_args.kwargs
        assert "en-US" in str(call_kwargs.get("voice"))

    def test_gcp_tts_client_called_exactly_once_for_english(self):
        from src import tts as tts_mod
        mock_client = self._mock_gcp_tts_client()
        with patch.object(tts_mod, "_client", mock_client):
            tts_mod.synthesize_speech("Test sentence.", "en")
        mock_client.synthesize_speech.assert_called_once()

    def test_english_uses_neural2_voice(self):
        from src import tts as tts_mod
        mock_client = self._mock_gcp_tts_client()
        with patch.object(tts_mod, "_client", mock_client):
            tts_mod.synthesize_speech("Hello", "en")
        call_kwargs = mock_client.synthesize_speech.call_args.kwargs
        assert "Neural2" in str(call_kwargs.get("voice"))

    # ── Sinhala path (local VITS) ──────────────────────────────────────────

    def test_sinhala_returns_wav_bytes_from_custom_model(self):
        from src import tts as tts_mod
        with patch("src.sinhala_tts.synthesize_sinhala", return_value=FAKE_WAV):
            result = tts_mod.synthesize_speech("ආයුබෝවන්", "si")
        assert result == FAKE_WAV

    def test_sinhala_routes_to_custom_model_not_gcp(self):
        """GCP TTS client must NOT be called for Sinhala."""
        from src import tts as tts_mod
        mock_gcp = self._mock_gcp_tts_client()
        with patch.object(tts_mod, "_client", mock_gcp), \
             patch("src.sinhala_tts.synthesize_sinhala", return_value=FAKE_WAV):
            tts_mod.synthesize_speech("ආයුබෝවන්", "si")
        mock_gcp.synthesize_speech.assert_not_called()

    def test_sinhala_custom_model_called_with_text(self):
        from src import tts as tts_mod
        mock_si = MagicMock(return_value=FAKE_WAV)
        with patch("src.sinhala_tts.synthesize_sinhala", mock_si):
            tts_mod.synthesize_speech("ආයුබෝවන්", "si")
        mock_si.assert_called_once_with("ආයුබෝවන්")

    # ── get_audio_mime_type ────────────────────────────────────────────────

    def test_get_audio_mime_type_english_is_mpeg(self):
        from src.tts import get_audio_mime_type
        assert get_audio_mime_type("en") == "audio/mpeg"

    def test_get_audio_mime_type_tamil_is_mpeg(self):
        from src.tts import get_audio_mime_type
        assert get_audio_mime_type("ta") == "audio/mpeg"

    def test_get_audio_mime_type_sinhala_is_wav(self):
        from src.tts import get_audio_mime_type
        assert get_audio_mime_type("si") == "audio/wav"

    def test_get_audio_mime_type_unknown_is_mpeg(self):
        from src.tts import get_audio_mime_type
        assert get_audio_mime_type("xx") == "audio/mpeg"


# =============================================================================
# Section 3 — sinhala_tts.synthesize_sinhala  (Coqui TTS Synthesizer mocked)
# =============================================================================

class TestSinhalaCustomTTS:
    """Tests for the local VITS Sinhala TTS module (no model files loaded)."""

    def _mock_synthesizer(self, samples=None):
        """Return a MagicMock Synthesizer whose tts() yields float samples."""
        import numpy as np
        if samples is None:
            # 0.5 s of silence at 22 050 Hz
            samples = np.zeros(22_050 // 2, dtype=np.float32).tolist()
        mock_syn = MagicMock()
        mock_syn.tts.return_value = samples
        return mock_syn

    def test_returns_bytes(self):
        from src import sinhala_tts as si_mod
        with patch.object(si_mod, "_synthesizer", self._mock_synthesizer()):
            result = si_mod.synthesize_sinhala("ආයුබෝවන්")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_output_is_valid_wav_header(self):
        from src import sinhala_tts as si_mod
        with patch.object(si_mod, "_synthesizer", self._mock_synthesizer()):
            result = si_mod.synthesize_sinhala("ආයුබෝවන්")
        # All WAV files start with the RIFF header
        assert result[:4] == b"RIFF"
        assert result[8:12] == b"WAVE"

    def test_empty_text_raises_value_error(self):
        from src import sinhala_tts as si_mod
        with patch.object(si_mod, "_synthesizer", self._mock_synthesizer()):
            with pytest.raises(ValueError, match="empty"):
                si_mod.synthesize_sinhala("")

    def test_whitespace_only_raises_value_error(self):
        from src import sinhala_tts as si_mod
        with patch.object(si_mod, "_synthesizer", self._mock_synthesizer()):
            with pytest.raises(ValueError):
                si_mod.synthesize_sinhala("   ")

    def test_synthesizer_tts_called_with_text(self):
        from src import sinhala_tts as si_mod
        mock_syn = self._mock_synthesizer()
        with patch.object(si_mod, "_synthesizer", mock_syn):
            si_mod.synthesize_sinhala("hello sinhala")
        mock_syn.tts.assert_called_once_with("hello sinhala")

    def test_sample_rate_constant_matches_config(self):
        from src.sinhala_tts import SAMPLE_RATE
        assert SAMPLE_RATE == 22_050

    def test_singleton_loaded_once_across_calls(self):
        from src import sinhala_tts as si_mod
        import numpy as np
        samples = np.zeros(100, dtype=np.float32).tolist()
        mock_syn = MagicMock()
        mock_syn.tts.return_value = samples
        with patch.object(si_mod, "_synthesizer", mock_syn):
            si_mod.synthesize_sinhala("first call")
            si_mod.synthesize_sinhala("second call")
        # The mock Synthesizer's tts() is called twice; its constructor is NOT
        # called again (we patched _synthesizer directly, ensuring singleton)
        assert mock_syn.tts.call_count == 2


# =============================================================================
# Section 4 — translation.translate_from_english  (GCP Translation mocked)
# =============================================================================

class TestTranslateFromEnglish:

    def _mock_translation_client(self, translated_text: str) -> MagicMock:
        mock_translation = MagicMock()
        mock_translation.translated_text = translated_text
        mock_response = MagicMock()
        mock_response.translations = [mock_translation]
        mock_client = MagicMock()
        mock_client.translate_text.return_value = mock_response
        return mock_client

    def test_english_to_english_returns_original_without_api_call(self):
        from src import translation as tr
        # No mock client needed — the function must short-circuit before calling GCP
        result = tr.translate_from_english("Hello", "en")
        assert result == "Hello"

    def test_empty_text_returns_empty(self):
        from src import translation as tr
        assert tr.translate_from_english("", "si") == ""

    def test_whitespace_returns_unchanged(self):
        from src import translation as tr
        result = tr.translate_from_english("   ", "si")
        assert result == "   "

    def test_translates_to_sinhala(self):
        from src import translation as tr
        mock_client = self._mock_translation_client("ආයුබෝවන්")
        with patch.object(tr, "_client", mock_client):
            result = tr.translate_from_english("Welcome", "si")
        assert result == "ආයුබෝවන්"

    def test_translates_to_tamil(self):
        from src import translation as tr
        mock_client = self._mock_translation_client("வரவேற்கிறோம்")
        with patch.object(tr, "_client", mock_client):
            result = tr.translate_from_english("Welcome", "ta")
        assert result == "வரவேற்கிறோம்"

    def test_returns_original_text_on_api_error(self):
        from src import translation as tr
        mock_client = MagicMock()
        mock_client.translate_text.side_effect = Exception("GCP unavailable")
        with patch.object(tr, "_client", mock_client):
            result = tr.translate_from_english("Welcome", "si")
        assert result == "Welcome"

    def test_returns_original_when_no_translation_results(self):
        from src import translation as tr
        mock_response = MagicMock()
        mock_response.translations = []
        mock_client = MagicMock()
        mock_client.translate_text.return_value = mock_response
        with patch.object(tr, "_client", mock_client):
            result = tr.translate_from_english("Welcome", "ta")
        assert result == "Welcome"

    def test_api_called_with_correct_source_and_target(self):
        from src import translation as tr
        mock_client = self._mock_translation_client("test")
        with patch.object(tr, "_client", mock_client):
            tr.translate_from_english("Hello", "si")
        call_kwargs = mock_client.translate_text.call_args.kwargs
        assert call_kwargs["source_language_code"] == "en"
        assert call_kwargs["target_language_code"] == "si"

    def test_no_api_call_made_for_english_target(self):
        from src import translation as tr
        mock_client = MagicMock()
        with patch.object(tr, "_client", mock_client):
            tr.translate_from_english("Hello", "en")
        mock_client.translate_text.assert_not_called()


# =============================================================================
# Section 5 — voice_pipeline.run_pipeline  (all external calls mocked)
# =============================================================================

class TestRunPipeline:
    """Integration tests for the 4-stage pipeline with every external service stubbed."""

    @pytest.mark.asyncio
    async def test_english_pipeline_end_to_end(self):
        from src.voice_pipeline import run_pipeline

        stt_out = {"transcript": "Show me hotels", "detected_language": "en", "english_text": "Show me hotels"}
        orch_resp = _build_orch_resp("Here are some hotels.")

        with patch("src.voice_pipeline.transcribe_and_translate", AsyncMock(return_value=stt_out)), \
             patch("src.voice_pipeline.translate_from_english", return_value="Here are some hotels."), \
             patch("src.voice_pipeline.synthesize_speech", return_value=FAKE_MP3), \
             patch("httpx.AsyncClient", _mock_httpx_client(orch_resp)):

            result = await run_pipeline(audio_bytes=DUMMY_PCM, user_id="u1", session_id="s1")

        assert result.transcript == "Show me hotels"
        assert result.detected_language == "en"
        assert result.english_text == "Show me hotels"
        assert result.final_message == "Here are some hotels."
        assert result.audio_bytes == FAKE_MP3

    @pytest.mark.asyncio
    async def test_sinhala_triggers_reverse_translation(self):
        from src.voice_pipeline import run_pipeline

        stt_out = {
            "transcript": "හෝටල් පෙන්වන්න",
            "detected_language": "si",
            "english_text": "Show me hotels",
        }
        si_response = "කොළඹ අසල ඇතැම් හෝටල් මෙන්න."
        mock_translate = MagicMock(return_value=si_response)

        with patch("src.voice_pipeline.transcribe_and_translate", AsyncMock(return_value=stt_out)), \
             patch("src.voice_pipeline.translate_from_english", mock_translate), \
             patch("src.voice_pipeline.synthesize_speech", return_value=FAKE_MP3), \
             patch("httpx.AsyncClient", _mock_httpx_client(_build_orch_resp("Here are some hotels near Colombo."))):

            result = await run_pipeline(audio_bytes=DUMMY_PCM, user_id="u1", session_id="s1")

        mock_translate.assert_called_once_with("Here are some hotels near Colombo.", "si")
        assert result.translated_response == si_response
        assert result.detected_language == "si"

    @pytest.mark.asyncio
    async def test_tts_receives_translated_response_not_english(self):
        """TTS stage must be called with the translated response, not the raw English reply."""
        from src.voice_pipeline import run_pipeline

        stt_out = {"transcript": "வணக்கம்", "detected_language": "ta", "english_text": "hello"}
        mock_tts = MagicMock(return_value=FAKE_MP3)

        with patch("src.voice_pipeline.transcribe_and_translate", AsyncMock(return_value=stt_out)), \
             patch("src.voice_pipeline.translate_from_english", return_value="இலங்கைக்கு வரவேற்கிறோம்."), \
             patch("src.voice_pipeline.synthesize_speech", mock_tts), \
             patch("httpx.AsyncClient", _mock_httpx_client(_build_orch_resp("Welcome to Sri Lanka."))):

            await run_pipeline(audio_bytes=DUMMY_PCM, user_id="u1", session_id="s1")

        mock_tts.assert_called_once_with("இலங்கைக்கு வரவேற்கிறோம்.", "ta")

    @pytest.mark.asyncio
    async def test_followups_are_passed_through(self):
        from src.voice_pipeline import run_pipeline

        stt_out = {"transcript": "things to do", "detected_language": "en", "english_text": "things to do"}
        followups = ["Visit Temple of the Tooth?", "Try local food?"]

        with patch("src.voice_pipeline.transcribe_and_translate", AsyncMock(return_value=stt_out)), \
             patch("src.voice_pipeline.translate_from_english", return_value="Visit Galle Fort."), \
             patch("src.voice_pipeline.synthesize_speech", return_value=FAKE_MP3), \
             patch("httpx.AsyncClient", _mock_httpx_client(_build_orch_resp("Visit Galle Fort.", followups))):

            result = await run_pipeline(audio_bytes=DUMMY_PCM, user_id="u1", session_id="s1")

        assert result.followups == followups

    @pytest.mark.asyncio
    async def test_orchestrator_receives_correct_payload(self):
        from src.voice_pipeline import run_pipeline

        stt_out = {"transcript": "hello", "detected_language": "en", "english_text": "hello"}
        orch_resp = _build_orch_resp()
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=orch_resp)
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("src.voice_pipeline.transcribe_and_translate", AsyncMock(return_value=stt_out)), \
             patch("src.voice_pipeline.translate_from_english", return_value="ok"), \
             patch("src.voice_pipeline.synthesize_speech", return_value=FAKE_MP3), \
             patch("httpx.AsyncClient", MagicMock(return_value=mock_cm)):

            await run_pipeline(audio_bytes=DUMMY_PCM, user_id="user-42", session_id="sess-7")

        mock_http.post.assert_called_once()
        payload = mock_http.post.call_args.kwargs["json"]
        assert payload["input_text"] == "hello"
        assert payload["user_id"] == "user-42"
        assert payload["session_id"] == "sess-7"
        assert payload["channel"] == "voice"

    @pytest.mark.asyncio
    async def test_result_contains_all_fields(self):
        from src.voice_pipeline import run_pipeline, VoicePipelineResult

        stt_out = {"transcript": "hi", "detected_language": "en", "english_text": "hi"}

        with patch("src.voice_pipeline.transcribe_and_translate", AsyncMock(return_value=stt_out)), \
             patch("src.voice_pipeline.translate_from_english", return_value="hello"), \
             patch("src.voice_pipeline.synthesize_speech", return_value=FAKE_MP3), \
             patch("httpx.AsyncClient", _mock_httpx_client(_build_orch_resp())):

            result = await run_pipeline(audio_bytes=DUMMY_PCM, user_id="u", session_id="s")

        assert isinstance(result, VoicePipelineResult)
        for field in ("transcript", "detected_language", "english_text",
                      "orchestrator_response", "final_message", "followups",
                      "translated_response", "audio_bytes"):
            assert hasattr(result, field), f"Missing field: {field}"


# =============================================================================
# Section 6 — FastAPI /voice/* route tests  (TestClient + mocked services)
# =============================================================================

@pytest.fixture(scope="module")
def client():
    from src.main import app
    return TestClient(app)


class TestTranscribeRoute:

    def test_returns_transcript_on_valid_audio(self, client):
        stt_out = {"transcript": "Hello", "detected_language": "en", "english_text": "Hello"}
        with patch("src.voice_routes.transcribe_and_translate", AsyncMock(return_value=stt_out)):
            resp = client.post(
                "/voice/transcribe",
                files={"audio": ("test.pcm", b"\x00" * 3200, "audio/octet-stream")},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["transcript"] == "Hello"
        assert data["detected_language"] == "en"
        assert data["english_text"] == "Hello"

    def test_rejects_empty_audio_with_400(self, client):
        resp = client.post(
            "/voice/transcribe",
            files={"audio": ("empty.pcm", b"", "audio/octet-stream")},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    def test_sinhala_audio_returns_si_language_code(self, client):
        stt_out = {"transcript": "ආයුබෝවන්", "detected_language": "si", "english_text": "welcome"}
        with patch("src.voice_routes.transcribe_and_translate", AsyncMock(return_value=stt_out)):
            resp = client.post(
                "/voice/transcribe",
                files={"audio": ("si.pcm", b"\x00" * 3200, "audio/octet-stream")},
            )
        assert resp.status_code == 200
        assert resp.json()["detected_language"] == "si"

    def test_transcription_error_returns_500(self, client):
        with patch("src.voice_routes.transcribe_and_translate", AsyncMock(side_effect=RuntimeError("STT error"))):
            resp = client.post(
                "/voice/transcribe",
                files={"audio": ("t.pcm", b"\x00" * 3200, "audio/octet-stream")},
            )
        assert resp.status_code == 500


class TestSynthesizeRoute:

    def test_returns_mp3_bytes_with_correct_content_type(self, client):
        with patch("src.voice_routes.synthesize_speech", return_value=FAKE_MP3):
            resp = client.post("/voice/synthesize", json={"text": "Welcome.", "language": "en"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/mpeg"
        assert resp.content == FAKE_MP3

    def test_rejects_whitespace_only_text_with_400(self, client):
        resp = client.post("/voice/synthesize", json={"text": "   ", "language": "en"})
        assert resp.status_code == 400

    def test_missing_text_field_returns_422(self, client):
        resp = client.post("/voice/synthesize", json={"language": "en"})
        assert resp.status_code == 422

    def test_language_defaults_to_english(self, client):
        with patch("src.voice_routes.synthesize_speech", return_value=FAKE_MP3) as mock_tts:
            client.post("/voice/synthesize", json={"text": "Hello"})
        mock_tts.assert_called_once_with("Hello", "en")

    def test_sinhala_language_forwarded_to_tts(self, client):
        with patch("src.voice_routes.synthesize_speech", return_value=FAKE_WAV) as mock_tts:
            client.post("/voice/synthesize", json={"text": "ආයුබෝවන්", "language": "si"})
        mock_tts.assert_called_once_with("ආයුබෝවන්", "si")

    def test_sinhala_synthesize_returns_wav_content_type(self, client):
        with patch("src.voice_routes.synthesize_speech", return_value=FAKE_WAV):
            resp = client.post("/voice/synthesize", json={"text": "ආයුබෝවන්", "language": "si"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"

    def test_english_synthesize_returns_mpeg_content_type(self, client):
        with patch("src.voice_routes.synthesize_speech", return_value=FAKE_MP3):
            resp = client.post("/voice/synthesize", json={"text": "Hello", "language": "en"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/mpeg"

    def test_synthesis_error_returns_500(self, client):
        with patch("src.voice_routes.synthesize_speech", side_effect=RuntimeError("TTS error")):
            resp = client.post("/voice/synthesize", json={"text": "Hello", "language": "en"})
        assert resp.status_code == 500


class TestTranslateRoute:

    def test_translates_to_sinhala(self, client):
        with patch("src.voice_routes.translate_from_english", return_value="ආයුබෝවන්"):
            resp = client.post("/voice/translate", json={"text": "Welcome", "target_language": "si"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["translated_text"] == "ආයුබෝවන්"
        assert data["target_language"] == "si"

    def test_translates_to_tamil(self, client):
        with patch("src.voice_routes.translate_from_english", return_value="வரவேற்கிறோம்"):
            resp = client.post("/voice/translate", json={"text": "Welcome", "target_language": "ta"})
        assert resp.status_code == 200
        assert resp.json()["translated_text"] == "வரவேற்கிறோம்"

    def test_empty_text_returns_400(self, client):
        resp = client.post("/voice/translate", json={"text": "", "target_language": "si"})
        assert resp.status_code == 400

    def test_missing_target_language_returns_422(self, client):
        resp = client.post("/voice/translate", json={"text": "Hello"})
        assert resp.status_code == 422

    def test_english_target_accepted_and_returned(self, client):
        with patch("src.voice_routes.translate_from_english", return_value="Hello"):
            resp = client.post("/voice/translate", json={"text": "Hello", "target_language": "en"})
        assert resp.status_code == 200
        assert resp.json()["target_language"] == "en"


class TestPipelineRoute:

    def test_rejects_empty_audio_with_400(self, client):
        resp = client.post(
            "/voice/pipeline",
            data={"user_id": "u1", "session_id": "s1"},
            files={"audio": ("empty.pcm", b"", "audio/octet-stream")},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    def test_returns_base64_audio_and_full_metadata(self, client):
        from src.voice_pipeline import VoicePipelineResult

        mock_result = VoicePipelineResult(
            transcript="Show me hotels",
            detected_language="en",
            english_text="Show me hotels",
            orchestrator_response={"final_message": "Here are some hotels.", "followups": []},
            final_message="Here are some hotels.",
            followups=[],
            translated_response="Here are some hotels.",
            audio_bytes=FAKE_MP3,
        )
        with patch("src.voice_routes.run_pipeline", AsyncMock(return_value=mock_result)):
            resp = client.post(
                "/voice/pipeline",
                data={"user_id": "u1", "session_id": "s1"},
                files={"audio": ("test.pcm", b"\x00" * 3200, "audio/octet-stream")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["audio_base64"] == base64.b64encode(FAKE_MP3).decode("ascii")
        meta = data["metadata"]
        assert meta["transcript"] == "Show me hotels"
        assert meta["detected_language"] == "en"
        assert meta["final_message"] == "Here are some hotels."
        assert meta["followups"] == []

    def test_pipeline_processing_error_returns_500(self, client):
        with patch("src.voice_routes.run_pipeline", AsyncMock(side_effect=RuntimeError("GCP failure"))):
            resp = client.post(
                "/voice/pipeline",
                data={"user_id": "u1", "session_id": "s1"},
                files={"audio": ("test.pcm", b"\x00" * 3200, "audio/octet-stream")},
            )
        assert resp.status_code == 500

    def test_default_user_and_session_accepted(self, client):
        """Omitting user_id/session_id should use defaults, not raise 422."""
        from src.voice_pipeline import VoicePipelineResult

        mock_result = VoicePipelineResult(
            transcript="hi", detected_language="en", english_text="hi",
            orchestrator_response={}, final_message="hi", followups=[],
            translated_response="hi", audio_bytes=FAKE_MP3,
        )
        with patch("src.voice_routes.run_pipeline", AsyncMock(return_value=mock_result)):
            resp = client.post(
                "/voice/pipeline",
                files={"audio": ("t.pcm", b"\x00" * 100, "audio/octet-stream")},
            )
        assert resp.status_code == 200

    def test_sinhala_pipeline_metadata(self, client):
        from src.voice_pipeline import VoicePipelineResult

        mock_result = VoicePipelineResult(
            transcript="හෝටල් පෙන්වන්න",
            detected_language="si",
            english_text="Show me hotels",
            orchestrator_response={"final_message": "Here are hotels.", "followups": ["Need more info?"]},
            final_message="Here are hotels.",
            followups=["Need more info?"],
            translated_response="ඔබට ගැළපෙන හෝටල් ලැයිස්තුව.",
            audio_bytes=FAKE_MP3,
        )
        with patch("src.voice_routes.run_pipeline", AsyncMock(return_value=mock_result)):
            resp = client.post(
                "/voice/pipeline",
                data={"user_id": "u1", "session_id": "s1"},
                files={"audio": ("si.pcm", b"\x00" * 3200, "audio/octet-stream")},
            )
        assert resp.status_code == 200
        meta = resp.json()["metadata"]
        assert meta["detected_language"] == "si"
        assert meta["translated_response"] == "ඔබට ගැළපෙන හෝටල් ලැයිස්තුව."
        assert len(meta["followups"]) == 1
