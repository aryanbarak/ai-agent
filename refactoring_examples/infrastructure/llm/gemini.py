"""
Gemini LLM provider implementation with retry logic and circuit breaker.
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any
from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError

from refactoring_examples.core.exceptions import (
    LLMError,
    LLMQuotaError,
    LLMTimeoutError,
    MissingAPIKeyError,
)
from refactoring_examples.domain.protocols import LLMMessage, LLMResponse


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    
    States:
    - CLOSED: Normal operation
    - OPEN: Blocking all requests (after failure threshold)
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float | None = None
        self.state: str = "closed"  # closed, open, half_open
    
    def call(self, func):
        """Decorator to protect a function with circuit breaker."""
        async def wrapper(*args, **kwargs):
            if self.state == "open":
                if time.time() - (self.last_failure_time or 0) > self.recovery_timeout:
                    self.state = "half_open"
                    self.success_count = 0
                else:
                    raise LLMError("Circuit breaker is OPEN. Service unavailable.")
            
            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise e
        
        return wrapper
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        
        if self.state == "half_open":
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = "closed"
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class GeminiProvider:
    """
    Async Gemini LLM provider with:
    - Automatic retries with exponential backoff
    - Circuit breaker pattern
    - Timeout handling
    - Quota error detection
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        max_retries: int = 3,
        timeout: float = 30.0,
    ):
        if not api_key:
            raise MissingAPIKeyError("gemini")
        
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            timeout=timeout,
            max_retries=0,  # We handle retries ourselves
        )
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout
        self.circuit_breaker = CircuitBreaker()
    
    def get_model_name(self) -> str:
        """Return the model identifier."""
        return self.model
    
    async def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        timeout: float | None = None,
    ) -> LLMResponse:
        """
        Generate completion with retry logic.
        
        Implements exponential backoff:
        - 1st retry: wait 1 second
        - 2nd retry: wait 2 seconds
        - 3rd retry: wait 4 seconds
        """
        timeout = timeout or self.timeout
        
        @self.circuit_breaker.call
        async def _make_request() -> LLMResponse:
            for attempt in range(self.max_retries):
                try:
                    completion = await self.client.chat.completions.create(
                        model=self.model,
                        temperature=temperature,
                        messages=messages,  # type: ignore
                        timeout=timeout,
                    )
                    
                    content = completion.choices[0].message.content or ""
                    
                    # Check if response was cached (Gemini specific)
                    cached = getattr(completion, "cached", False)
                    
                    return {
                        "content": content,
                        "model": self.model,
                        "cached": cached,
                        "tokens_used": completion.usage.total_tokens if completion.usage else None,
                    }
                
                except RateLimitError as e:
                    # Extract retry-after from error message
                    retry_after = self._extract_retry_after(str(e))
                    
                    if attempt < self.max_retries - 1:
                        wait_time = retry_after or (2 ** attempt)
                        await asyncio.sleep(wait_time)
                        continue
                    
                    raise LLMQuotaError(
                        "Rate limit exceeded",
                        retry_after_seconds=retry_after,
                    )
                
                except APITimeoutError as e:
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    
                    raise LLMTimeoutError(
                        f"Request timed out after {timeout}s",
                        timeout=timeout,
                    )
                
                except APIError as e:
                    # Check if it's a quota error
                    error_message = str(e).lower()
                    if "resource_exhausted" in error_message or "quota" in error_message:
                        retry_after = self._extract_retry_after(str(e))
                        raise LLMQuotaError(
                            "API quota exhausted",
                            retry_after_seconds=retry_after,
                        )
                    
                    # For other API errors, retry with backoff
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    
                    raise LLMError(f"LLM API error: {e}")
                
                except Exception as e:
                    # Don't retry on unexpected errors
                    raise LLMError(f"Unexpected error: {e}")
            
            raise LLMError("Max retries exceeded")
        
        return await _make_request()
    
    def _extract_retry_after(self, text: str) -> int | None:
        """Extract retry-after seconds from error message."""
        patterns = [
            r"retry[- ]after[:\s]+(\d+)",
            r"Retry-After:\s*(\d+)",
            r"in\s+(\d+)\s*seconds",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    pass
        return None
    
    async def close(self):
        """Close the client connection."""
        await self.client.close()
