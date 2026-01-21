import os

PROFILE_DB_URL = os.getenv("PROFILE_DB_URL", "").strip()
EMBED_MODEL = os.getenv("PROFILE_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBED_DIM = int(os.getenv("PROFILE_EMBED_DIM", "384"))

EMBED_BATCH_SIZE = int(os.getenv("PROFILE_EMBED_BATCH_SIZE", "64"))
EMBED_EVENT_TYPES = os.getenv(
    "PROFILE_EMBED_EVENT_TYPES",
    "intent_parsed,prefs_merged,downstream_response"
).split(",")

DEFAULT_TOP_K = int(os.getenv("PROFILE_RECALL_TOP_K", "5"))

def psycopg_dsn() -> str:
    if not PROFILE_DB_URL:
        raise RuntimeError("PROFILE_DB_URL not set")
    return PROFILE_DB_URL.replace("postgresql+psycopg://", "postgresql://")
