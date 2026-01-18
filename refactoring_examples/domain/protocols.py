"""
Domain protocols (interfaces) for the AI Agent.
These define the contracts that infrastructure implementations must follow.
"""
from __future__ import annotations

from typing import Protocol, TypedDict, Literal, Any
from dataclasses import dataclass


# ============================================================================
# LLM Provider Protocol
# ============================================================================

class LLMMessage(TypedDict):
    """A message in the LLM conversation."""
    role: Literal["system", "user", "assistant"]
    content: str


class LLMResponse(TypedDict):
    """Response from LLM provider."""
    content: str
    model: str
    cached: bool
    tokens_used: int | None


class LLMProvider(Protocol):
    """Protocol for LLM providers (Gemini, OpenAI, etc.)."""
    
    async def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        timeout: float = 30.0,
    ) -> LLMResponse:
        """
        Generate completion from messages.
        
        Args:
            messages: Conversation history
            temperature: Randomness in generation (0.0-1.0)
            timeout: Maximum wait time in seconds
            
        Raises:
            LLMQuotaError: When rate limit is hit
            LLMTimeoutError: When request times out
            LLMError: For other failures
        """
        ...
    
    def get_model_name(self) -> str:
        """Return the model identifier."""
        ...


# ============================================================================
# Cache Protocol
# ============================================================================

class CacheProvider(Protocol):
    """Protocol for caching strategies."""
    
    async def get(self, key: str) -> Any | None:
        """Retrieve value from cache."""
        ...
    
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store value in cache with optional TTL in seconds."""
        ...
    
    async def delete(self, key: str) -> None:
        """Remove value from cache."""
        ...
    
    async def clear(self) -> None:
        """Clear all cached values."""
        ...


# ============================================================================
# Repository Protocols
# ============================================================================

@dataclass
class FIAELog:
    """Domain model for FIAE interaction log."""
    id: int | None
    created_at: str
    problem: str
    answer: str


class FIAERepository(Protocol):
    """Protocol for FIAE log storage."""
    
    async def save(self, problem: str, answer: str) -> FIAELog:
        """Save a new FIAE interaction."""
        ...
    
    async def get_recent(self, limit: int = 10) -> list[FIAELog]:
        """Retrieve recent FIAE logs."""
        ...
    
    async def count_by_topic(self) -> dict[str, int]:
        """Count interactions grouped by detected topic."""
        ...


# ============================================================================
# Prompt Template Protocol
# ============================================================================

class PromptTemplate(Protocol):
    """Protocol for prompt management."""
    
    def render(self, **kwargs: Any) -> str:
        """Render template with provided variables."""
        ...
    
    def get_language(self) -> Literal["de", "fa", "en"]:
        """Return the language of this template."""
        ...
