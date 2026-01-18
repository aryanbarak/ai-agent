"""
Dependency Injection Container for the application.

This module sets up all dependencies and their lifecycles.
"""
from __future__ import annotations

from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncIterator

from refactoring_examples.core.config import Settings
from refactoring_examples.infrastructure.llm.gemini import GeminiProvider
from refactoring_examples.infrastructure.llm.cache import LRUCache, SemanticCache
from refactoring_examples.infrastructure.database.sqlite_repository import AsyncSQLiteRepository
from refactoring_examples.application.services.fiae_service import FIAEAnalysisService


class Container:
    """
    Dependency container that holds all application dependencies.
    
    Benefits:
    - Centralized dependency management
    - Easy testing (can mock dependencies)
    - Clear lifecycle management
    - Proper resource cleanup
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # Will be initialized in startup
        self.llm_provider: GeminiProvider | None = None
        self.cache: SemanticCache | None = None
        self.repository: AsyncSQLiteRepository | None = None
        self.fiae_service: FIAEAnalysisService | None = None
    
    async def startup(self) -> None:
        """
        Initialize all dependencies.
        
        Called during application startup.
        """
        print("[Container] Initializing dependencies...")
        
        # 1. Initialize LLM provider
        self.llm_provider = GeminiProvider(
            api_key=self.settings.llm.api_key,
            model=self.settings.llm.model,
            max_retries=self.settings.llm.max_retries,
            timeout=self.settings.llm.timeout,
        )
        print(f"[Container] ✓ LLM Provider initialized (model: {self.settings.llm.model})")
        
        # 2. Initialize cache
        base_cache = LRUCache(
            max_size=self.settings.cache.max_size,
            default_ttl=self.settings.cache.default_ttl,
        )
        self.cache = SemanticCache(base_cache)
        print(f"[Container] ✓ Cache initialized (max_size: {self.settings.cache.max_size})")
        
        # 3. Initialize database
        self.repository = AsyncSQLiteRepository(self.settings.database.db_path)
        await self.repository.initialize()
        print(f"[Container] ✓ Database initialized (path: {self.settings.database.db_path})")
        
        # 4. Load prompt templates
        # (In production, load from prompt manager)
        system_prompt = self._get_default_prompt()
        
        # 5. Initialize services
        self.fiae_service = FIAEAnalysisService(
            llm_provider=self.llm_provider,
            cache=self.cache,
            repository=self.repository,
            system_prompt_template=system_prompt,
        )
        print("[Container] ✓ FIAE Service initialized")
        
        print("[Container] All dependencies initialized successfully!")
    
    async def shutdown(self) -> None:
        """
        Clean up all dependencies.
        
        Called during application shutdown.
        """
        print("[Container] Shutting down dependencies...")
        
        if self.llm_provider:
            await self.llm_provider.close()
            print("[Container] ✓ LLM Provider closed")
        
        if self.cache:
            await self.cache.clear()
            print("[Container] ✓ Cache cleared")
        
        print("[Container] Shutdown complete")
    
    def _get_default_prompt(self) -> str:
        """Get default system prompt (can be loaded from file in production)."""
        return """
Du bist ein strenger aber hilfreicher FIAE Prüfungscoach.

Fokus NUR auf:
- Algorithmisches Denken
- Problemanalyse
- Schritt-für-Schritt Reasoning

Regeln:
- Keine Begrüßungen und keine Füllsätze.
- Sei präzise; vermeide lange Einleitungen.
- Gib NICHT nur die fertige Lösung.
- Ausgabe NUR JSON.
- Alle Strings müssen in {lang} sein.

Ausgabeformat (JSON):
{{
  "summary": "string",
  "steps": ["string", ...],
  "example": "string or null",
  "pseudocode": "string or null",
  "visual": "string or null"
}}

Modell: {model_name}
"""


# ============================================================================
# Lifespan context manager for FastAPI
# ============================================================================

@asynccontextmanager
async def app_lifespan(container: Container) -> AsyncIterator[None]:
    """
    Lifespan context manager for FastAPI application.
    
    Usage in FastAPI:
    ```python
    from fastapi import FastAPI
    
    container = Container(settings)
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with app_lifespan(container):
            yield
    
    app = FastAPI(lifespan=lifespan)
    ```
    """
    # Startup
    await container.startup()
    
    try:
        yield
    finally:
        # Shutdown
        await container.shutdown()


# ============================================================================
# Factory functions for testing
# ============================================================================

def create_test_container(db_path: str = ":memory:") -> Container:
    """
    Create container for testing with in-memory database.
    
    Usage in tests:
    ```python
    async def test_fiae_service():
        container = create_test_container()
        await container.startup()
        
        try:
            result = await container.fiae_service.analyze_problem(
                "Erkläre Bubble Sort",
                language="de",
            )
            assert result["summary"]
        finally:
            await container.shutdown()
    ```
    """
    from refactoring_examples.core.config import (
        Settings,
        LLMSettings,
        CacheSettings,
        DatabaseSettings,
    )
    
    settings = Settings(
        env="test",
        llm=LLMSettings(
            api_key="test_key",
            model="gemini-2.5-flash",
        ),
        cache=CacheSettings(
            enabled=True,
            max_size=100,
        ),
        database=DatabaseSettings(
            db_path=Path(db_path),
        ),
    )
    
    return Container(settings)
