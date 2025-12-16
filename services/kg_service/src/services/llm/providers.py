"""LLM provider implementations."""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Any

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def get_chat_model(self, model: str, temperature: float = 0) -> Any:
        """Get a chat model instance.
        
        Args:
            model: Model name/identifier
            temperature: Temperature for generation
            
        Returns:
            Chat model instance
        """
        pass
    
    @abstractmethod
    def supports_structured_output(self) -> bool:
        """Check if provider supports structured output.
        
        Returns:
            True if structured output is supported
        """
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider."""
    
    def __init__(self, api_key: str):
        """Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key
        """
        self.api_key = api_key
        logger.info("OpenAI provider initialized")
    
    def get_chat_model(self, model: str = "gpt-4o-mini", temperature: float = 0) -> Any:
        """Get OpenAI chat model.
        
        Args:
            model: OpenAI model name
            temperature: Temperature for generation
            
        Returns:
            ChatOpenAI instance
        """
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                api_key=self.api_key
            )
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI model: {e}")
            raise
    
    def supports_structured_output(self) -> bool:
        """OpenAI supports structured output."""
        return True


class GroqProvider(LLMProvider):
    """Groq LLM provider."""
    
    def __init__(self, api_key: str):
        """Initialize Groq provider.
        
        Args:
            api_key: Groq API key
        """
        self.api_key = api_key
        logger.info("Groq provider initialized")
    
    def get_chat_model(self, model: str = "llama-3.3-70b-versatile", temperature: float = 0) -> Any:
        """Get Groq chat model.
        
        Args:
            model: Groq model name
            temperature: Temperature for generation
            
        Returns:
            ChatGroq instance
        """
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(
                model=model,
                temperature=temperature,
                api_key=self.api_key
            )
        except Exception as e:
            logger.error(f"Failed to initialize Groq model: {e}")
            raise
    
    def supports_structured_output(self) -> bool:
        """Groq supports structured output."""
        return True
