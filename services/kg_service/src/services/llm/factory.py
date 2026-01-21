"""LLM factory for creating provider instances."""

import logging
from typing import Optional
from enum import Enum

from .providers import LLMProvider, OpenAIProvider, GroqProvider

logger = logging.getLogger(__name__)


class LLMProviderType(str, Enum):
    """Supported LLM provider types."""
    OPENAI = "openai"
    GROQ = "groq"


class LLMFactory:
    """Factory for creating LLM provider instances."""
    
    @staticmethod
    def create_provider(
        provider_type: LLMProviderType,
        api_key: str
    ) -> LLMProvider:
        """Create an LLM provider instance.
        
        Args:
            provider_type: Type of provider to create
            api_key: API key for the provider
            
        Returns:
            LLM provider instance
            
        Raises:
            ValueError: If provider type is not supported
        """
        if provider_type == LLMProviderType.OPENAI:
            return OpenAIProvider(api_key)
        elif provider_type == LLMProviderType.GROQ:
            return GroqProvider(api_key)
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")
    
    @staticmethod
    def create_from_config(
        provider_name: str,
        api_key: str
    ) -> Optional[LLMProvider]:
        """Create provider from configuration string.
        
        Args:
            provider_name: Provider name (case-insensitive)
            api_key: API key for the provider
            
        Returns:
            LLM provider instance or None if invalid
        """
        try:
            provider_type = LLMProviderType(provider_name.lower())
            return LLMFactory.create_provider(provider_type, api_key)
        except ValueError as e:
            logger.error(f"Invalid provider name '{provider_name}': {e}")
            return None
