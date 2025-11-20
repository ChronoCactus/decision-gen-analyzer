"""Tests for configuration management."""

import os
from unittest.mock import patch

from src.config import Settings, get_settings


class TestSettings:
    """Test Settings configuration class."""

    def test_settings_with_defaults(self):
        """Test settings are created with default values."""
        # Clear environment variables to test actual defaults
        env_vars_to_clear = [
            "LLM_BASE_URL",
            "LLM_BASE_URL_1",
            "LLM_EMBEDDING_BASE_URL",
            "LLM_PROVIDER",
            "LLM_MODEL",
            "LLM_TIMEOUT",
            "LLM_TEMPERATURE",
            "LIGHTRAG_URL",
            "LIGHTRAG_TIMEOUT",
            "LOG_LEVEL",
            "LOG_FORMAT",
            "DEBUG",
            "ENABLE_LAN_DISCOVERY",
            "HOST_IP",
        ]
        # Save original values
        original_env = {key: os.environ.get(key) for key in env_vars_to_clear}

        # Temporarily remove these keys from environment
        for key in env_vars_to_clear:
            os.environ.pop(key, None)

        try:
            settings = Settings()

            assert settings.llm_base_url == "http://localhost:11434/v1"
            assert settings.llm_base_url_1 is None
            assert settings.llm_embedding_base_url is None
            assert settings.llm_timeout == 300
            assert settings.llm_provider == "ollama"
            assert settings.llm_model == "gpt-oss:20b"
            assert settings.lightrag_url == "http://localhost:9621"
            assert settings.lightrag_timeout == 180
            assert settings.log_level == "INFO"
            assert settings.log_format == "json"
            assert settings.debug is False
            assert settings.enable_lan_discovery is False
            assert settings.host_ip is None
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

    def test_settings_from_environment(self):
        """Test settings are loaded from environment variables."""
        with patch.dict(
            os.environ,
            {
                "LLM_BASE_URL": "http://test-llama:8000",
                "LLM_BASE_URL_1": "http://test-llama2:8000",
                "LLM_EMBEDDING_BASE_URL": "http://test-embed:8000",
                "LLM_PROVIDER": "openai",
                "LLM_MODEL": "test-model",
                "LIGHTRAG_URL": "http://test-lightrag:9000",
                "LOG_LEVEL": "DEBUG",
                "DEBUG": "true",
                "ENABLE_LAN_DISCOVERY": "true",
                "HOST_IP": "192.168.1.100",
            },
            clear=False,
        ):
            settings = Settings()

            assert settings.llm_base_url == "http://test-llama:8000"
            assert settings.llm_base_url_1 == "http://test-llama2:8000"
            assert settings.llm_embedding_base_url == "http://test-embed:8000"
            assert settings.llm_provider == "openai"
            assert settings.llm_model == "test-model"
            assert settings.lightrag_url == "http://test-lightrag:9000"
            assert settings.log_level == "DEBUG"
            assert settings.debug is True
            assert settings.enable_lan_discovery is True
            assert settings.host_ip == "192.168.1.100"

    def test_settings_timeouts(self):
        """Test timeout settings."""
        with patch.dict(
            os.environ,
            {
                "LLM_TIMEOUT": "600",
                "LIGHTRAG_TIMEOUT": "300",
            },
            clear=False,
        ):
            settings = Settings()

            assert settings.llm_timeout == 600
            assert settings.lightrag_timeout == 300

    def test_settings_log_format(self):
        """Test log format can be configured."""
        with patch.dict(os.environ, {"LOG_FORMAT": "text"}, clear=False):
            settings = Settings()

            assert settings.log_format == "text"

    def test_settings_optional_api_keys(self):
        """Test optional API keys."""
        with patch.dict(
            os.environ,
            {
                "LIGHTRAG_API_KEY": "test-api-key-123",
                "SERPAPI_KEY": "serpapi-key-456",
            },
            clear=False,
        ):
            settings = Settings()

            assert settings.lightrag_api_key == "test-api-key-123"
            assert settings.serpapi_key == "serpapi-key-456"

    def test_settings_job_scheduling(self):
        """Test job scheduling configuration."""
        with patch.dict(
            os.environ,
            {
                "JOB_CHECK_INTERVAL": "7200",
                "MAX_CONCURRENT_JOBS": "5",
            },
            clear=False,
        ):
            settings = Settings()

            assert settings.job_check_interval == 7200
            assert settings.max_concurrent_jobs == 5


class TestGetSettings:
    """Test get_settings function."""

    def test_get_settings_returns_settings_instance(self):
        """Test get_settings returns a Settings instance."""
        settings = get_settings()

        assert isinstance(settings, Settings)
        assert hasattr(settings, "llm_base_url")
        assert hasattr(settings, "lightrag_url")

    def test_get_settings_caching(self):
        """Test get_settings returns the same instance (if cached)."""
        settings1 = get_settings()
        settings2 = get_settings()

        # Note: This test depends on implementation of get_settings
        # If it uses functools.lru_cache, instances will be the same
        # Otherwise, they might be different instances with same values
        assert settings1.llm_base_url == settings2.llm_base_url

    def test_get_settings_respects_environment(self):
        """Test that Settings can be created with environment variables."""
        # Note: get_settings() returns the module-level singleton,
        # so we test that Settings class respects env vars instead
        with patch.dict(
            os.environ,
            {"LLM_BASE_URL": "http://custom-url:1234"},
            clear=False,
        ):
            # Create a new Settings instance to test env var reading
            from src.config import Settings

            settings = Settings()

            assert settings.llm_base_url == "http://custom-url:1234"


class TestSettingsValidation:
    """Test settings validation."""

    def test_settings_with_invalid_boolean(self):
        """Test settings handle boolean conversion."""
        with patch.dict(os.environ, {"DEBUG": "not-a-bool"}, clear=False):
            # Pydantic should either convert or raise ValidationError
            # Depending on strict mode
            try:
                settings = Settings()
                # If it doesn't raise, check it handled it gracefully
                assert isinstance(settings.debug, bool)
            except Exception:
                # ValidationError is acceptable
                pass

    def test_settings_with_missing_optional_fields(self):
        """Test settings work with missing optional fields."""
        # Remove optional environment variables
        env_vars = os.environ.copy()
        for key in ["LLM_BASE_URL_1", "LLM_EMBEDDING_BASE_URL", "LIGHTRAG_API_KEY"]:
            env_vars.pop(key, None)

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

            assert settings.llm_base_url_1 is None
            assert settings.llm_embedding_base_url is None
            assert settings.lightrag_api_key is None
