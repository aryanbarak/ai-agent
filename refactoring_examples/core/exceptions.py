"""
Custom exceptions for the AI Agent application.
Provides clear error hierarchy for better error handling.
"""
from __future__ import annotations

from typing import Any


# ============================================================================
# Base Exceptions
# ============================================================================

class AIAgentError(Exception):
    """Base exception for all AI Agent errors."""
    
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


# ============================================================================
# LLM Exceptions
# ============================================================================

class LLMError(AIAgentError):
    """Base exception for LLM-related errors."""
    pass


class LLMQuotaError(LLMError):
    """Raised when LLM API quota is exceeded."""
    
    def __init__(
        self,
        message: str = "API quota exceeded",
        retry_after_seconds: int | None = None,
    ):
        super().__init__(message, {"retry_after_seconds": retry_after_seconds})
        self.retry_after_seconds = retry_after_seconds


class LLMTimeoutError(LLMError):
    """Raised when LLM API request times out."""
    
    def __init__(self, message: str = "LLM request timed out", timeout: float = 0):
        super().__init__(message, {"timeout": timeout})
        self.timeout = timeout


class LLMValidationError(LLMError):
    """Raised when LLM response fails validation."""
    
    def __init__(self, message: str, response: str | None = None):
        super().__init__(message, {"response": response})
        self.response = response


class LLMLanguageMismatchError(LLMValidationError):
    """Raised when LLM responds in wrong language."""
    
    def __init__(self, expected: str, response: str):
        super().__init__(
            f"Expected language '{expected}' but got different language",
            response=response,
        )
        self.expected_language = expected


# ============================================================================
# Repository Exceptions
# ============================================================================

class RepositoryError(AIAgentError):
    """Base exception for repository/database errors."""
    pass


class DatabaseConnectionError(RepositoryError):
    """Raised when database connection fails."""
    pass


class DataIntegrityError(RepositoryError):
    """Raised when data integrity constraint is violated."""
    pass


# ============================================================================
# Cache Exceptions
# ============================================================================

class CacheError(AIAgentError):
    """Base exception for cache-related errors."""
    pass


class CacheConnectionError(CacheError):
    """Raised when cache backend is unavailable."""
    pass


# ============================================================================
# Validation Exceptions
# ============================================================================

class ValidationError(AIAgentError):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message, {"field": field})
        self.field = field


# ============================================================================
# Configuration Exceptions
# ============================================================================

class ConfigurationError(AIAgentError):
    """Raised when configuration is invalid or missing."""
    pass


class MissingAPIKeyError(ConfigurationError):
    """Raised when required API key is not configured."""
    
    def __init__(self, provider: str):
        super().__init__(
            f"API key for '{provider}' is not configured",
            {"provider": provider},
        )
        self.provider = provider
