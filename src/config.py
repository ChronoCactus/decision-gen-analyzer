"""Configuration management for Decision Analyzer."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Configuration - LangChain-based with OpenAI-compatible providers
    # Primary LLM configuration
    llm_provider: str = Field(
        default="ollama",
        description="LLM provider: ollama, openai, openrouter, vllm, llama_cpp, or custom",
        alias="LLM_PROVIDER",
    )
    llm_base_url: str = Field(
        default="http://localhost:11434/v1",
        description="Base URL for OpenAI-compatible API endpoint",
        alias="LLM_BASE_URL",
    )
    llm_model: str = Field(
        default="gpt-oss:20b",
        description="Model name to use for generation",
        alias="LLM_MODEL",
    )
    llm_api_key: Optional[str] = Field(
        default=None,
        description="API key for LLM provider (optional for local providers)",
        alias="LLM_API_KEY",
    )
    llm_temperature: float = Field(
        default=0.7,
        description="Default temperature for LLM generation",
        alias="LLM_TEMPERATURE",
    )
    llm_timeout: int = Field(
        default=300,
        description="Timeout for LLM requests in seconds",
        alias="LLM_TIMEOUT",
    )

    # Parallel Processing Configuration
    llm_parallel_requests_enabled: bool = Field(
        default=False,
        description="Enable parallel requests for the primary provider",
        alias="LLM_PARALLEL_REQUESTS_ENABLED",
    )
    llm_max_parallel_requests: int = Field(
        default=2,
        description="Maximum number of parallel requests for the primary provider",
        alias="LLM_MAX_PARALLEL_REQUESTS",
    )

    # Ollama-specific parameters (only used when llm_provider is "ollama")
    ollama_num_ctx: int = Field(
        default=64000,
        description="Context window size for Ollama models (num_ctx parameter)",
        alias="OLLAMA_NUM_CTX",
    )
    ollama_num_predict: Optional[int] = Field(
        default=None,
        description="Maximum number of tokens to generate (num_predict parameter)",
        alias="OLLAMA_NUM_PREDICT",
    )

    # Secondary LLM for parallel processing (optional)
    llm_base_url_1: Optional[str] = Field(
        default=None,
        description="Secondary base URL for parallel processing",
        alias="LLM_BASE_URL_1",
    )

    # Dedicated embedding LLM (optional)
    llm_embedding_base_url: Optional[str] = Field(
        default=None,
        description="Dedicated base URL for embedding requests",
        alias="LLM_EMBEDDING_BASE_URL",
    )
    llm_embedding_model: Optional[str] = Field(
        default=None,
        description="Model name for embeddings (if different from main model)",
        alias="LLM_EMBEDDING_MODEL",
    )

    # Provider-specific settings
    openrouter_api_key: Optional[str] = Field(
        default=None,
        description="OpenRouter API key (alternative to LLM_API_KEY)",
        alias="OPENROUTER_API_KEY",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key (alternative to LLM_API_KEY)",
        alias="OPENAI_API_KEY",
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

    # Storage Configuration
    adr_storage_path: str = Field(
        default="/app/data/adrs",
        description="Path to ADR storage directory",
        alias="ADR_STORAGE_PATH",
    )

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
    api_base_url: Optional[str] = Field(
        default=None,
        description="Explicit API base URL for frontend (e.g., https://mysite.com for production). "
        "If not set, falls back to LAN discovery (http://{host_ip}:8000) or localhost:8000",
        alias="API_BASE_URL",
    )

    # Web Search Configuration
    serpapi_key: Optional[str] = Field(
        default=None, description="SerpAPI key for web search"
    )

    # Job Scheduling Configuration
    job_check_interval: int = Field(
        default=3600, description="Interval to check for scheduled jobs in seconds"
    )
    max_concurrent_jobs: int = Field(
        default=3, description="Maximum number of concurrent jobs"
    )

    # Persona Configuration
    include_default_personas: bool = Field(
        default=True,
        description="Include default personas from config/personas/defaults/ directory",
        alias="INCLUDE_DEFAULT_PERSONAS",
    )
    personas_config_dir: Optional[str] = Field(
        default=None,
        description="Custom personas configuration directory (defaults to config/personas)",
        alias="PERSONAS_CONFIG_DIR",
    )

    # Encryption Configuration
    encryption_salt: str = Field(
        default="decision_analyzer_default_salt_change_me",
        description="Salt for encrypting API credentials in storage",
        alias="ENCRYPTION_SALT",
    )

    class Config:
        """Pydantic configuration."""

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            env_prefix="",  # No prefix, use exact env var names
            populate_by_name=True,  # Allow populating by field name or alias
        )

    def model_post_init(self, __context) -> None:
        """Handle post-initialization configuration."""
        # Handle provider-specific API keys
        if self.openrouter_api_key and not self.llm_api_key:
            object.__setattr__(self, "llm_api_key", self.openrouter_api_key)
        elif self.openai_api_key and not self.llm_api_key:
            object.__setattr__(self, "llm_api_key", self.openai_api_key)

    def get_llm_config(self) -> dict:
        """Get LangChain LLM configuration dictionary."""
        config = {
            "provider": self.llm_provider,
            "model": self.llm_model,
            "base_url": self.llm_base_url,
            "timeout": self.llm_timeout,
            "temperature": self.llm_temperature,
        }

        if self.llm_api_key:
            config["api_key"] = self.llm_api_key

        # Add Ollama-specific parameters if provider is Ollama
        if self.llm_provider.lower() == "ollama":
            config["num_ctx"] = self.ollama_num_ctx
            if self.ollama_num_predict:
                config["num_predict"] = self.ollama_num_predict

        return config

    def get_secondary_llm_config(self) -> Optional[dict]:
        """Get secondary LLM configuration for parallel processing."""
        if not self.llm_base_url_1:
            return None

        config = {
            "provider": self.llm_provider,
            "model": self.llm_model,
            "base_url": self.llm_base_url_1,
            "timeout": self.llm_timeout,
            "temperature": self.llm_temperature,
        }

        if self.llm_api_key:
            config["api_key"] = self.llm_api_key

        # Add Ollama-specific parameters if provider is Ollama
        if self.llm_provider.lower() == "ollama":
            config["num_ctx"] = self.ollama_num_ctx
            if self.ollama_num_predict:
                config["num_predict"] = self.ollama_num_predict

        return config

    def get_embedding_llm_config(self) -> Optional[dict]:
        """Get dedicated embedding LLM configuration."""
        if not self.llm_embedding_base_url:
            return None

        config = {
            "provider": self.llm_provider,
            "model": self.llm_embedding_model or self.llm_model,
            "base_url": self.llm_embedding_base_url,
            "timeout": self.llm_timeout,
        }

        if self.llm_api_key:
            config["api_key"] = self.llm_api_key

        # Add Ollama-specific parameters if provider is Ollama
        if self.llm_provider.lower() == "ollama":
            config["num_ctx"] = self.ollama_num_ctx
            if self.ollama_num_predict:
                config["num_predict"] = self.ollama_num_predict

        return config


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
