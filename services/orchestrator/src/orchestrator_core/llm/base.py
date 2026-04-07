# llm/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseLLMClient(ABC):
    @abstractmethod
    def chat_json(self, *, system_prompt: str, user_prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def chat_text(self, *, system_prompt: str, user_prompt: str, model: Optional[str] = None) -> str:
        pass