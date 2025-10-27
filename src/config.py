"""Configuration management for Decision Analyzer."""

import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Configuration
    llama_cpp_url: str = Field(
        default="http://localhost:11434",
        description="Primary Ollama server URL",
        alias="LLAMA_CPP_URL",
    )
    llama_cpp_url_1: Optional[str] = Field(
        default=None,
        description="Secondary Ollama server URL for parallel processing",
        alias="LLAMA_CPP_URL_1",
    )
    llama_cpp_url_embedding: Optional[str] = Field(
        default=None,
        description="Dedicated Ollama server URL for embedding requests",
        alias="LLAMA_CPP_URL_EMBEDDING",
    )
    llama_cpp_timeout: int = Field(
        default=300,
        description="Timeout for LLM requests in seconds",
        alias="LLAMA_CPP_TIMEOUT",
    )

    # LightRAG Configuration
    lightrag_url: str = Field(
        default="http://localhost:9621",
        description="LightRAG server URL",
        alias="LIGHTRAG_URL",
    )
    lightrag_timeout: int = Field(
        default=180,
        description="Timeout for LightRAG requests in seconds",
        alias="LIGHTRAG_TIMEOUT",
    )
    lightrag_api_key: Optional[str] = Field(
        default=None,
        description="LightRAG API key for authentication",
        alias="LIGHTRAG_API_KEY",
    )

    # Application Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or text)")

    # Development settings
    debug: bool = Field(default=False, description="Enable debug mode")

    # LAN Discovery Configuration
    enable_lan_discovery: bool = Field(
        default=False,
        description="Enable LAN discovery to allow access from other machines on the network",
        alias="ENABLE_LAN_DISCOVERY",
    )
    host_ip: Optional[str] = Field(
        default=None,
        description="Host IP address for LAN discovery (e.g., 192.168.0.2)",
        alias="HOST_IP",
    )

    # Web Search Configuration
    serpapi_key: Optional[str] = Field(default=None, description="SerpAPI key for web search")

    # Job Scheduling Configuration
    job_check_interval: int = Field(default=3600, description="Interval to check for scheduled jobs in seconds")
    max_concurrent_jobs: int = Field(default=3, description="Maximum number of concurrent jobs")

    class Config:
        """Pydantic configuration."""
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            env_prefix="",  # No prefix, use exact env var names
            populate_by_name=True,  # Allow populating by field name or alias
        )


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the current application settings."""
    return settings


def update_settings(**kwargs) -> None:
    """Update settings dynamically."""
    global settings
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
