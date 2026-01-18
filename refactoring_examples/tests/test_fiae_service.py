"""
Example test suite demonstrating testability improvements.

Shows:
- Unit tests with mocked dependencies
- Integration tests
- Async testing
"""
import pytest
from unittest.mock import AsyncMock, Mock
from typing import Literal

from refactoring_examples.domain.protocols import LLMMessage, LLMResponse
from refactoring_examples.application.services.fiae_service import FIAEAnalysisService
from refactoring_examples.core.exceptions import ValidationError, LLMQuotaError


# ============================================================================
# Mock Implementations
# ============================================================================

class MockLLMProvider:
    """Mock LLM provider for testing."""
    
    def __init__(self, responses: list[str] | None = None):
        self.responses = responses or ['{"summary": "Test", "steps": ["Step 1"]}']
        self.call_count = 0
    
    def get_model_name(self) -> str:
        return "mock-model"
    
    async def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        timeout: float = 30.0,
    ) -> LLMResponse:
        """Return mocked response."""
        response = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        
        return {
            "content": response,
            "model": "mock-model",
            "cached": False,
            "tokens_used": 100,
        }


class MockCache:
    """Mock cache for testing."""
    
    def __init__(self):
        self.storage = {}
        self.get_count = 0
        self.set_count = 0
    
    async def get_response(self, messages, temperature, model):
        self.get_count += 1
        key = str(messages)
        return self.storage.get(key)
    
    async def set_response(self, messages, temperature, model, response, ttl=None):
        self.set_count += 1
        key = str(messages)
        self.storage[key] = response


class MockRepository:
    """Mock repository for testing."""
    
    def __init__(self):
        self.logs = []
    
    async def save(self, problem: str, answer: str, topic=None, language="de"):
        self.logs.append({
            "problem": problem,
            "answer": answer,
            "topic": topic,
            "language": language,
        })
        from refactoring_examples.domain.protocols import FIAELog
        return FIAELog(
            id=len(self.logs),
            created_at="2026-01-18T00:00:00Z",
            problem=problem,
            answer=answer,
        )


# ============================================================================
# Unit Tests
# ============================================================================

class TestFIAEAnalysisService:
    """Unit tests for FIAEAnalysisService."""
    
    @pytest.mark.asyncio
    async def test_analyze_success(self):
        """Test successful analysis."""
        # Arrange
        mock_llm = MockLLMProvider()
        mock_cache = MockCache()
        mock_repo = MockRepository()
        
        service = FIAEAnalysisService(
            llm_provider=mock_llm,
            cache=mock_cache,
            repository=mock_repo,
            system_prompt_template="Test prompt {lang} {model_name}",
        )
        
        # Act
        result = await service.analyze_problem(
            problem_text="Erkläre Bubble Sort",
            language="de",
        )
        
        # Assert
        assert result["summary"] == "Test"
        assert result["steps"] == ["Step 1"]
        assert result["meta"]["cached"] is False
        assert mock_llm.call_count == 1
        assert mock_cache.set_count == 1
    
    @pytest.mark.asyncio
    async def test_analyze_empty_input(self):
        """Test validation error for empty input."""
        # Arrange
        service = FIAEAnalysisService(
            llm_provider=MockLLMProvider(),
            cache=MockCache(),
            repository=MockRepository(),
            system_prompt_template="Test",
        )
        
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await service.analyze_problem(
                problem_text="",
                language="de",
            )
        
        assert "cannot be empty" in str(exc_info.value.message).lower()
    
    @pytest.mark.asyncio
    async def test_analyze_too_long_input(self):
        """Test validation error for too long input."""
        # Arrange
        service = FIAEAnalysisService(
            llm_provider=MockLLMProvider(),
            cache=MockCache(),
            repository=MockRepository(),
            system_prompt_template="Test",
        )
        
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await service.analyze_problem(
                problem_text="x" * 10000,  # Too long
                language="de",
            )
        
        assert "too long" in str(exc_info.value.message).lower()
    
    @pytest.mark.asyncio
    async def test_analyze_cache_hit(self):
        """Test that cache is used on second call."""
        # Arrange
        mock_llm = MockLLMProvider()
        mock_cache = MockCache()
        mock_repo = MockRepository()
        
        service = FIAEAnalysisService(
            llm_provider=mock_llm,
            cache=mock_cache,
            repository=mock_repo,
            system_prompt_template="Test {lang}",
        )
        
        # Act - First call
        result1 = await service.analyze_problem("Test problem", "de")
        
        # Act - Second call (should use cache)
        result2 = await service.analyze_problem("Test problem", "de")
        
        # Assert
        assert result1["meta"]["cached"] is False
        assert result2["meta"]["cached"] is True
        assert mock_llm.call_count == 1  # Only called once
        assert mock_cache.get_count == 2  # Checked twice
    
    @pytest.mark.asyncio
    async def test_analyze_language_validation(self):
        """Test language validation for Persian."""
        # Arrange - LLM returns Persian text
        mock_llm = MockLLMProvider(
            responses=['{"summary": "این یک تست است", "steps": ["گام یک"]}']
        )
        mock_cache = MockCache()
        mock_repo = MockRepository()
        
        service = FIAEAnalysisService(
            llm_provider=mock_llm,
            cache=mock_cache,
            repository=mock_repo,
            system_prompt_template="Test",
        )
        
        # Act
        result = await service.analyze_problem("Test", "fa")
        
        # Assert
        assert "این" in result["summary"]  # Persian text
        assert result["meta"]["lang"] == "fa"


# ============================================================================
# Integration Tests
# ============================================================================

class TestFIAEServiceIntegration:
    """Integration tests with real components."""
    
    @pytest.mark.asyncio
    async def test_full_flow_with_real_cache(self):
        """Test with real LRU cache implementation."""
        from refactoring_examples.infrastructure.llm.cache import LRUCache, SemanticCache
        
        # Arrange
        mock_llm = MockLLMProvider()
        base_cache = LRUCache(max_size=10)
        semantic_cache = SemanticCache(base_cache)
        mock_repo = MockRepository()
        
        service = FIAEAnalysisService(
            llm_provider=mock_llm,
            cache=semantic_cache,
            repository=mock_repo,
            system_prompt_template="Test",
        )
        
        # Act - Multiple calls
        results = []
        for _ in range(5):
            result = await service.analyze_problem("Same problem", "de")
            results.append(result)
        
        # Assert
        assert results[0]["meta"]["cached"] is False
        assert all(r["meta"]["cached"] for r in results[1:])  # All cached
        assert mock_llm.call_count == 1  # Only one API call


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Performance-related tests."""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling concurrent requests."""
        import asyncio
        
        # Arrange
        mock_llm = MockLLMProvider()
        mock_cache = MockCache()
        mock_repo = MockRepository()
        
        service = FIAEAnalysisService(
            llm_provider=mock_llm,
            cache=mock_cache,
            repository=mock_repo,
            system_prompt_template="Test",
        )
        
        # Act - 10 concurrent requests
        tasks = [
            service.analyze_problem(f"Problem {i}", "de")
            for i in range(10)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Assert
        assert len(results) == 10
        assert all("summary" in r for r in results)
        # With proper async, these should complete quickly
    
    @pytest.mark.asyncio
    async def test_cache_eviction(self):
        """Test that cache properly evicts old items."""
        from refactoring_examples.infrastructure.llm.cache import LRUCache
        
        # Arrange - Small cache
        cache = LRUCache(max_size=3)
        
        # Act - Add more items than capacity
        for i in range(5):
            await cache.set(f"key{i}", f"value{i}")
        
        # Assert - Only last 3 should remain
        assert await cache.get("key0") is None  # Evicted
        assert await cache.get("key1") is None  # Evicted
        assert await cache.get("key2") == "value2"  # Kept
        assert await cache.get("key3") == "value3"  # Kept
        assert await cache.get("key4") == "value4"  # Kept


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Tests for error scenarios."""
    
    @pytest.mark.asyncio
    async def test_llm_quota_error(self):
        """Test handling of quota errors."""
        from refactoring_examples.core.exceptions import LLMQuotaError
        
        # Arrange - LLM that raises quota error
        class QuotaErrorLLM:
            def get_model_name(self):
                return "mock"
            
            async def complete(self, messages, **kwargs):
                raise LLMQuotaError("Quota exceeded", retry_after_seconds=60)
        
        service = FIAEAnalysisService(
            llm_provider=QuotaErrorLLM(),
            cache=MockCache(),
            repository=MockRepository(),
            system_prompt_template="Test",
        )
        
        # Act & Assert
        with pytest.raises(LLMQuotaError) as exc_info:
            await service.analyze_problem("Test", "de")
        
        assert exc_info.value.retry_after_seconds == 60
    
    @pytest.mark.asyncio
    async def test_invalid_json_response(self):
        """Test handling of invalid JSON from LLM."""
        from refactoring_examples.core.exceptions import LLMValidationError
        
        # Arrange - LLM returns invalid JSON
        mock_llm = MockLLMProvider(responses=["invalid json {{{"])
        
        service = FIAEAnalysisService(
            llm_provider=mock_llm,
            cache=MockCache(),
            repository=MockRepository(),
            system_prompt_template="Test",
        )
        
        # Act & Assert
        with pytest.raises(LLMValidationError):
            await service.analyze_problem("Test", "de")


# ============================================================================
# Comparison: Old vs New
# ============================================================================

def test_old_code_not_testable():
    """
    Demonstrate that old code is NOT testable.
    
    ❌ Old code (fiaetutor.py):
    - Uses global `client`
    - Uses global `_CACHE`
    - Synchronous
    - Tightly coupled
    
    You CANNOT write unit tests for it without:
    - Mocking global variables (fragile)
    - Making actual API calls (slow, expensive)
    - Running full integration tests (complex)
    """
    pass  # This is just documentation


def test_new_code_fully_testable():
    """
    Demonstrate that new code IS fully testable.
    
    ✅ New code:
    - Dependency injection
    - Async/await
    - Interfaces (Protocols)
    - Loosely coupled
    
    You CAN easily write unit tests:
    - Mock any dependency
    - Test in isolation
    - Fast execution
    - No external dependencies
    """
    pass  # See actual tests above!
