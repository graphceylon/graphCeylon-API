# llm/factory.py
import os
from .base import BaseLLMClient
from .groq_client import GroqLLMClient
from .openai_client import OpenAILLMClient

def build_llm_client() -> BaseLLMClient | None:
    provider = os.getenv("LLM_PROVIDER", "none").strip().lower()

    if provider == "groq":
        key = os.getenv("GROQ_API_KEY", "").strip()
        if not key:
            return None
        return GroqLLMClient(
            api_key=key,
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        )

    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            return None
        return OpenAILLMClient(
            api_key=key,
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        )

    return None