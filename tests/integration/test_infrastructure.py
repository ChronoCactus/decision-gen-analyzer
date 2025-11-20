"""Tests for infrastructure components."""

import os

from src.config import Settings
from src.models import ADR, ADRStatus


class TestSettings:
    """Test configuration settings."""

    def test_default_settings(self):
        """Test default settings values."""
        # Clear environment variables to test actual defaults
        env_vars_to_clear = [
            "LLM_BASE_URL", "LLM_BASE_URL_1", "LLM_EMBEDDING_BASE_URL",
            "LLM_PROVIDER", "LLM_MODEL", "LLM_TIMEOUT", "LLM_TEMPERATURE",
            "LIGHTRAG_URL", "LIGHTRAG_TIMEOUT", "LOG_LEVEL", "LOG_FORMAT",
            "DEBUG", "ENABLE_LAN_DISCOVERY", "HOST_IP"
        ]
        # Save original values
        original_env = {key: os.environ.get(key) for key in env_vars_to_clear}
        
        # Temporarily remove these keys from environment
        for key in env_vars_to_clear:
            os.environ.pop(key, None)
        
        try:
            settings = Settings()
            assert settings.llm_base_url == "http://localhost:11434/v1"
            # Accept either localhost or LAN IP for lightrag_url
            assert "9621" in settings.lightrag_url
            assert settings.log_level == "INFO"
            assert settings.debug is False
        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)

    def test_custom_settings(self, monkeypatch):
        """Test custom settings values via environment variables."""
        # Pydantic v2 Settings doesn't accept constructor params
        # Must use environment variables instead
        monkeypatch.setenv("LLM_BASE_URL", "http://custom:8080")
        monkeypatch.setenv("LIGHTRAG_URL", "http://custom:9090")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("DEBUG", "true")

        settings = Settings()
        assert settings.llm_base_url == "http://custom:8080"
        assert settings.lightrag_url == "http://custom:9090"
        assert settings.log_level == "DEBUG"
        assert settings.debug is True


class TestADRModel:
    """Test ADR data model."""

    def test_create_adr(self):
        """Test creating a new ADR."""
        adr = ADR.create(
            title="Test Decision",
            context_and_problem="We need to decide on architecture",
            decision_outcome="Use microservices",
            consequences="Better scalability",
            author="Test Author",
            tags=["architecture", "microservices"],
        )

        assert adr.metadata.title == "Test Decision"
        assert adr.metadata.status == ADRStatus.PROPOSED
        assert adr.metadata.author == "Test Author"
        assert "architecture" in adr.metadata.tags
        assert adr.content.context_and_problem == "We need to decide on architecture"
        assert adr.content.decision_outcome == "Use microservices"
        assert adr.content.consequences == "Better scalability"

    def test_adr_to_markdown(self):
        """Test converting ADR to markdown."""
        adr = ADR.create(
            title="Test ADR",
            context_and_problem="Context here",
            decision_outcome="Decision here",
            consequences="Consequences here",
        )

        markdown = adr.to_markdown()
        assert "# Test ADR" in markdown
        assert "## Context and Problem" in markdown
        assert "## Decision Outcome" in markdown
        assert "## Consequences" in markdown
        assert "Context here" in markdown

    def test_add_remove_tags(self):
        """Test adding and removing tags."""
        adr = ADR.create(
            title="Test",
            context_and_problem="Context",
            decision_outcome="Decision",
            consequences="Consequences",
        )

        adr.add_tag("test")
        assert "test" in adr.metadata.tags

        adr.remove_tag("test")
        assert "test" not in adr.metadata.tags
