"""
Configuration management using Pydantic Settings.
Supports environment variables with validation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM provider configuration."""
    
    provider: Literal["gemini", "openai"] = "gemini"
    api_key: str = Field(..., description="API key for LLM provider")
    model: str = Field("gemini-2.5-flash", description="Model name")
    max_retries: int = Field(3, ge=1, le=10, description="Maximum retry attempts")
    timeout: float = Field(30.0, ge=5.0, le=120.0, description="Request timeout in seconds")
    temperature: float = Field(0.2, ge=0.0, le=1.0, description="Default temperature")
    
    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("API key cannot be empty")
        return v.strip()
    
    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        case_sensitive=False,
    )


class CacheSettings(BaseSettings):
    """Cache configuration."""
    
    enabled: bool = Field(True, description="Enable caching")
    max_size: int = Field(1000, ge=100, le=10000, description="Maximum cache entries")
    default_ttl: int = Field(3600, ge=60, description="Default TTL in seconds")
    cleanup_interval: int = Field(300, ge=60, description="Cleanup interval in seconds")
    
    model_config = SettingsConfigDict(
        env_prefix="CACHE_",
        case_sensitive=False,
    )


class DatabaseSettings(BaseSettings):
    """Database configuration."""
    
    db_path: Path = Field(
        default=Path("data/db.sqlite"),
        description="Path to SQLite database",
    )
    enable_wal: bool = Field(
        True,
        description="Enable Write-Ahead Logging for better concurrency",
    )
    
    @field_validator("db_path")
    @classmethod
    def create_parent_dir(cls, v: Path) -> Path:
        v.parent.mkdir(parents=True, exist_ok=True)
        return v
    
    model_config = SettingsConfigDict(
        env_prefix="DB_",
        case_sensitive=False,
    )


class APISettings(BaseSettings):
    """API server configuration."""
    
    host: str = Field("0.0.0.0", description="API host")
    port: int = Field(8000, ge=1024, le=65535, description="API port")
    reload: bool = Field(False, description="Enable auto-reload (dev only)")
    workers: int = Field(1, ge=1, le=16, description="Number of worker processes")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:8080"],
        description="Allowed CORS origins",
    )
    
    model_config = SettingsConfigDict(
        env_prefix="API_",
        case_sensitive=False,
    )


class LoggingSettings(BaseSettings):
    """Logging configuration."""
    
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Path | None = None
    
    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        case_sensitive=False,
    )


class Settings(BaseSettings):
    """
    Application settings.
    
    Load from:
    1. Environment variables
    2. .env file (if exists)
    3. Default values
    
    Example .env file:
    ```
    LLM_API_KEY=your_gemini_key_here
    LLM_MODEL=gemini-2.5-flash
    LLM_MAX_RETRIES=3
    
    CACHE_ENABLED=true
    CACHE_MAX_SIZE=1000
    
    DB_PATH=data/production.sqlite
    
    API_HOST=0.0.0.0
    API_PORT=8000
    API_CORS_ORIGINS=["https://app.example.com"]
    
    LOG_LEVEL=INFO
    ```
    """
    
    # Environment name
    env: Literal["development", "production", "test"] = "development"
    
    # Sub-configurations
    llm: LLMSettings = Field(default_factory=LLMSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    api: APISettings = Field(default_factory=APISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    
    # Prompts directory
    prompts_dir: Path = Field(
        default=Path("prompts"),
        description="Directory containing prompt templates",
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # Use __ for nested: LLM__API_KEY
        case_sensitive=False,
    )
    
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.env == "production"
    
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.env == "development"


# ============================================================================
# Global settings instance
# ============================================================================

def get_settings() -> Settings:
    """
    Get application settings.
    
    This function can be used with FastAPI's Depends() for dependency injection.
    """
    return Settings()


# Example usage:
# ```python
# from refactoring_examples.core.config import get_settings
#
# settings = get_settings()
# print(f"Using model: {settings.llm.model}")
# print(f"Cache enabled: {settings.cache.enabled}")
# ```
