# custom exceptions for clean error responses

from __future__ import annotations


class LanguageServiceError(Exception):
    """Base exception for Language Service."""


class ValidationError(LanguageServiceError):
    pass


class TranslationError(LanguageServiceError):
    pass


class NormalizationError(LanguageServiceError):
    pass


class STTError(LanguageServiceError):
    pass


class TTSError(LanguageServiceError):
    pass


class OrchestratorError(LanguageServiceError):
    pass

class SessionStoreError(LanguageServiceError):
    """Errors related to session storage (memory / backup)."""
    pass