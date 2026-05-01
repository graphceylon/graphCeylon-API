"""Configuration for the Language Service voice pipeline."""

import os
from pathlib import Path

# ── Google Cloud credentials ─────────────────────────────────────────────────

_DEFAULT_CREDS = str(
    Path(__file__).resolve().parent.parent / "credentials" / "epic-language-dfcc-8f92b1c7e088.json"
)

GOOGLE_APPLICATION_CREDENTIALS = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_CREDS
)

# Set env var so all Google client libraries pick it up automatically
if os.path.isfile(GOOGLE_APPLICATION_CREDENTIALS):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS

GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "epic-language-dfcc")

# ── Orchestrator ─────────────────────────────────────────────────────────────

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "https://api.graphceylon.live/api/orchestrator")

# ── Gemini Live STT ──────────────────────────────────────────────────────────

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-live-2.5-flash-native-audio")
GEMINI_LOCATION = os.getenv("GEMINI_LOCATION", "us-central1")

# PCM audio settings (must match what the Flutter app records)
SEND_SAMPLE_RATE = 16_000  # 16 kHz mono PCM16

# ── Google Cloud TTS ─────────────────────────────────────────────────────────
# Proven voice configurations from voice_test testing

TTS_VOICE_MAP: dict[str, tuple[str, str | None]] = {
    # language_key -> (tts_locale, voice_name_or_None)
    "en": ("en-US", "en-US-Neural2-C"),      # Neural2 (highest quality)
    "si": ("si-LK", None),                    # Standard (auto-select; no named si-LK voices)
    "ta": ("ta-IN", "ta-IN-Wavenet-A"),       # Wavenet (Neural2 unavailable for ta-IN)
}

# ── Google Cloud Translation ─────────────────────────────────────────────────

TRANSLATION_LOCATION = os.getenv("TRANSLATION_LOCATION", "global")

# ── Sinhala custom VITS TTS model ─────────────────────────────────────────────
# Default: models/sinhala_tts/ inside the language service (one level up from src/)

_DEFAULT_SINHALA_TTS_DIR = str(
    Path(__file__).resolve().parents[1] / "models" / "sinhala_tts"
)

SINHALA_TTS_MODEL_PATH = os.getenv(
    "SINHALA_TTS_MODEL_PATH",
    str(Path(_DEFAULT_SINHALA_TTS_DIR) / "sinhala_tts_model.pth"),
)

SINHALA_TTS_CONFIG_PATH = os.getenv(
    "SINHALA_TTS_CONFIG_PATH",
    str(Path(_DEFAULT_SINHALA_TTS_DIR) / "config.json"),
)
