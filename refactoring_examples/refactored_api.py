"""
Refactored FastAPI application with clean architecture.

Key improvements:
- Async/await throughout
- Dependency injection
- Proper error handling
- Type safety
- Clean separation of concerns
"""
from __future__ import annotations

from typing import Literal
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from refactoring_examples.core.config import Settings, get_settings
from refactoring_examples.core.container import Container, app_lifespan
from refactoring_examples.core.exceptions import (
    AIAgentError,
    LLMQuotaError,
    LLMTimeoutError,
    ValidationError,
)


# ============================================================================
# Request/Response Models
# ============================================================================

class AnalyzeRequest(BaseModel):
    """Request model for FIAE analysis."""
    
    problem: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="The problem to analyze",
    )
    language: Literal["de", "fa", "en"] = Field(
        default="de",
        description="Target language for response",
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="LLM temperature (0.0-1.0)",
    )


class AnalyzeResponse(BaseModel):
    """Response model for FIAE analysis."""
    
    summary: str
    steps: list[str]
    example: str | None
    pseudocode: str | None
    visual: str | None
    meta: dict


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str
    version: str
    environment: str


class ErrorResponse(BaseModel):
    """Error response model."""
    
    error: str
    message: str
    details: dict | None = None


# ============================================================================
# Application setup
# ============================================================================

def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Application factory.
    
    Benefits:
    - Easy testing with different configurations
    - Clean initialization
    - Proper resource management
    """
    if settings is None:
        settings = get_settings()
    
    # Create container
    container = Container(settings)
    
    # Create lifespan context
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with app_lifespan(container):
            yield
    
    # Create FastAPI app
    app = FastAPI(
        title="Barakzai Personal AI Agent",
        version="2.0.0",
        description="FIAE exam preparation assistant with clean architecture",
        lifespan=lifespan,
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Store container in app state for dependency injection
    app.state.container = container
    
    return app


# ============================================================================
# Dependency injection
# ============================================================================

def get_container(request) -> Container:
    """Get container from app state."""
    return request.app.state.container


# ============================================================================
# Error handlers
# ============================================================================

def setup_error_handlers(app: FastAPI) -> None:
    """Setup global error handlers."""
    
    @app.exception_handler(ValidationError)
    async def validation_error_handler(request, exc: ValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "validation_error",
                "message": exc.message,
                "details": exc.details,
            },
        )
    
    @app.exception_handler(LLMQuotaError)
    async def quota_error_handler(request, exc: LLMQuotaError):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "quota_exceeded",
                "message": exc.message,
                "details": {
                    "retry_after_seconds": exc.retry_after_seconds,
                },
            },
            headers={
                "Retry-After": str(exc.retry_after_seconds or 60),
            },
        )
    
    @app.exception_handler(LLMTimeoutError)
    async def timeout_error_handler(request, exc: LLMTimeoutError):
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={
                "error": "timeout",
                "message": exc.message,
                "details": exc.details,
            },
        )
    
    @app.exception_handler(AIAgentError)
    async def agent_error_handler(request, exc: AIAgentError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": exc.message,
                "details": exc.details,
            },
        )


# ============================================================================
# Routes
# ============================================================================

app = create_app()
setup_error_handlers(app)


@app.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_settings)):
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "2.0.0",
        "environment": settings.env,
    }


@app.post("/api/fiae/analyze", response_model=AnalyzeResponse)
async def analyze_fiae_problem(
    request: AnalyzeRequest,
    container: Container = Depends(get_container),
):
    """
    Analyze FIAE problem and return structured response.
    
    - **problem**: The problem to analyze (max 5000 characters)
    - **language**: Target language (de, fa, en)
    - **temperature**: LLM creativity (0.0 = deterministic, 1.0 = creative)
    
    Returns structured analysis with:
    - Summary
    - Step-by-step solution
    - Example (if applicable)
    - Pseudocode (if applicable)
    - Visual representation (if applicable)
    """
    if not container.fiae_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not initialized",
        )
    
    result = await container.fiae_service.analyze_problem(
        problem_text=request.problem,
        language=request.language,
        temperature=request.temperature,
    )
    
    return AnalyzeResponse(**result)


@app.get("/api/fiae/history")
async def get_fiae_history(
    limit: int = 10,
    container: Container = Depends(get_container),
):
    """
    Get recent FIAE interaction history.
    
    - **limit**: Maximum number of entries to return (1-50)
    """
    if not container.repository:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Repository not initialized",
        )
    
    if limit < 1 or limit > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 50",
        )
    
    logs = await container.repository.get_recent(limit=limit)
    
    return {
        "items": [
            {
                "id": log.id,
                "created_at": log.created_at,
                "problem": log.problem,
                "answer": log.answer,
            }
            for log in logs
        ],
    }


@app.get("/api/fiae/stats")
async def get_fiae_stats(container: Container = Depends(get_container)):
    """
    Get statistics about FIAE interactions.
    
    Returns topic distribution and other metrics.
    """
    if not container.repository:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Repository not initialized",
        )
    
    topic_counts = await container.repository.count_by_topic()
    
    return {
        "topic_distribution": topic_counts,
    }


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "refactored_api:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
        log_level=settings.logging.level.lower(),
    )
