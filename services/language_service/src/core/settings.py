from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

class Settings(BaseSettings):
    # =========================
    # Core Service Settings
    # =========================
    SERVICE_NAME: str = "language_service"
    SERVICE_PORT: int = 8001
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"

    # =========================
    # Models / Local Assets
    # =========================
    MODEL_PATH: str = "../../../models/language_service/"
    USE_GPU: bool = False

    # =========================
    # Orchestrator (add this)
    # =========================
    # Orchestrator
    ORCHESTRATOR_BASE_URL: str = Field(default="http://127.0.0.1:8002")

    # =========================
    # OpenAI (Translation + Normalization)
    # =========================
    OPENAI_API_KEY: str | None = None
    OPENAI_TRANSLATION_MODEL: str = "gpt-4o-mini"
    OPENAI_NORMALIZE_MODEL: str = "gpt-4o-mini"

    # =========================
    # STT (AssemblyAI)
    # =========================
    ASSEMBLYAI_API_KEY: str | None = None
    ASSEMBLYAI_SAMPLE_RATE: int = 16000
    ASSEMBLYAI_ENCODING: str = "pcm_s16le"
    ASSEMBLYAI_FORMAT_TURNS: bool = True
    ASSEMBLYAI_CONFIDENCE_THRESHOLD: float = 0.3
    ASSEMBLYAI_MIN_SILENCE: int = 160
    ASSEMBLYAI_MAX_SILENCE: int = 1200

    # =========================
    # TTS (ElevenLabs)
    # =========================
    ELEVENLABS_API_KEY: str | None = None
    ELEVENLABS_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"
    ELEVENLABS_MODEL: str = "eleven_multilingual_v2"
    ELEVENLABS_OUTPUT_FORMAT: str = "mp3_44100_128"

    # =========================
    # Session Language Store
    # =========================
    SESSION_STORE_BACKUP_PATH: str = "data/language_service/processed/session_lang_store.json"
    SESSION_STORE_BACKUP_EVERY_N_WRITES: int = 10

    # =========================
    # Optional: HuggingFace
    # =========================
    HUGGINGFACE_TOKEN: str | None = None

    # =========================
    # Google Translate
    # =========================
    GOOGLE_TRANSLATE_API_KEY: str | None = None
    GOOGLE_TRANSLATE_PROVIDER: str = "google"  # google|openai

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
