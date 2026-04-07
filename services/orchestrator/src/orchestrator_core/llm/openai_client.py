# llm/openai_client.py
import json
from typing import Any, Dict, Optional
from openai import OpenAI
from .base import BaseLLMClient

class OpenAILLMClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4.1-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def chat_json(self, *, system_prompt: str, user_prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
        resp = self.client.chat.completions.create(
            model=model or self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)

    def chat_text(self, *, system_prompt: str, user_prompt: str, model: Optional[str] = None) -> str:
        resp = self.client.chat.completions.create(
            model=model or self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return (resp.choices[0].message.content or "").strip()