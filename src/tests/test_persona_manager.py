"""Tests for persona manager."""

import json
import tempfile
from pathlib import Path
from tempfile import TemporaryDirectory

from src.persona_manager import PersonaConfig, PersonaManager


class TestPersonaConfig:
    """Test PersonaConfig dataclass."""

    def test_create_persona_config(self):
        """Test creating a PersonaConfig."""
        config = PersonaConfig(
            name="Technical Lead",
            description="Technical perspective",
            instructions="Focus on technical aspects",
            focus_areas=["architecture", "performance"],
            evaluation_criteria=["scalability", "maintainability"],
        )

        assert config.name == "Technical Lead"
        assert config.description == "Technical perspective"
        assert len(config.focus_areas) == 2
        assert len(config.evaluation_criteria) == 2

    def test_persona_config_from_dict(self):
        """Test creating PersonaConfig from dictionary."""
        data = {
            "name": "Business Analyst",
            "description": "Business perspective",
            "instructions": "Focus on business value",
            "focus_areas": ["ROI", "user impact"],
            "evaluation_criteria": ["cost effectiveness"],
        }

        config = PersonaConfig.from_dict(data)

        assert config.name == "Business Analyst"
        assert config.description == "Business perspective"
        assert "ROI" in config.focus_areas
        assert "cost effectiveness" in config.evaluation_criteria

    def test_persona_config_from_dict_missing_optional_fields(self):
        """Test PersonaConfig from dict with missing optional fields."""
        data = {
            "name": "Test Persona",
            "description": "Test description",
            "instructions": "Test instructions",
        }

        config = PersonaConfig.from_dict(data)

        assert config.name == "Test Persona"
        assert config.focus_areas == []
        assert config.evaluation_criteria == []


class TestPersonaManager:
    """Test PersonaManager class."""

    def test_persona_manager_initialization_with_custom_dir(self):
        """Test PersonaManager with custom config directory."""
        with TemporaryDirectory() as tmpdir:
            # Don't include defaults since temp dir doesn't have defaults/ subdirectory
            manager = PersonaManager(config_dir=tmpdir, include_defaults=False)

            assert manager.config_dir == Path(tmpdir)
            # With no defaults and empty custom dir, should be empty
            personas = manager.list_persona_values()
            assert len(personas) == 0

    def test_persona_manager_loads_default_configs(self):
        """Test PersonaManager loads default configs when include_defaults=True."""
        # Use the default config_dir (which has defaults/ subdirectory)
        manager = PersonaManager(include_defaults=True)

        # Should load default configs from defaults/ subdirectory
        config = manager.get_persona_config("technical_lead")

        assert config is not None
        assert config.name == "Technical Lead"
        assert len(config.focus_areas) > 0

    def test_persona_manager_loads_json_configs(self):
        """Test PersonaManager loads JSON configs from directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_file = config_dir / "technical_lead.json"
            config_file.write_text(
                json.dumps(
                    {
                        "name": "Technical Lead",
                        "description": "Test description",
                        "instructions": "Test instructions",
                        "focus_areas": ["Area1", "Area2"],
                        "evaluation_criteria": ["Criterion1"],
                    }
                )
            )

            manager = PersonaManager(config_dir=str(config_dir), include_defaults=False)

            config = manager.get_persona_config("technical_lead")
            assert config is not None
            assert config.name == "Technical Lead"
            assert config.description == "Test description"

    def test_get_config_returns_persona_config(self):
        """Test get_persona_config returns PersonaConfig."""
        manager = PersonaManager(include_defaults=True)

        config = manager.get_persona_config("business_analyst")

        assert isinstance(config, PersonaConfig)
        assert config.name is not None
        assert config.description is not None
        assert config.instructions is not None

    def test_get_config_for_all_personas(self):
        """Test get_persona_config works for all personas."""
        manager = PersonaManager(include_defaults=True)

        persona_values = manager.list_persona_values()
        for persona_value in persona_values:
            config = manager.get_persona_config(persona_value)
            assert config is not None
            assert isinstance(config, PersonaConfig)

    def test_get_all_personas(self):
        """Test list_persona_values returns list of persona strings."""
        manager = PersonaManager(include_defaults=True)

        personas = manager.list_persona_values()

        assert isinstance(personas, list)
        assert len(personas) > 0
        assert all(isinstance(p, str) for p in personas)
        assert "technical_lead" in personas

    def test_get_persona_names(self):
        """Test discover_all_personas returns dict of configs."""
        manager = PersonaManager(include_defaults=True)

        configs = manager.discover_all_personas()

        assert isinstance(configs, dict)
        assert len(configs) > 0
        assert all(isinstance(p, str) for p in configs.keys())
        assert all(isinstance(c, PersonaConfig) for c in configs.values())

    def test_invalid_json_falls_back_to_default(self):
        """Test invalid JSON returns None when defaults not enabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_file = config_dir / "technical_lead.json"
            config_file.write_text("invalid json {")

            manager = PersonaManager(config_dir=str(config_dir), include_defaults=False)

            # Should return None for invalid JSON when defaults not enabled
            config = manager.get_persona_config("technical_lead")
            assert config is None

    def test_missing_required_field_returns_none(self):
        """Test missing required field returns None."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_file = config_dir / "technical_lead.json"
            # Missing 'description' field
            config_file.write_text(
                json.dumps(
                    {
                        "name": "Technical Lead",
                        "instructions": "Test",
                    }
                )
            )

            manager = PersonaManager(config_dir=str(config_dir), include_defaults=False)

            config = manager.get_persona_config("technical_lead")
            assert config is None

    def test_persona_config_has_required_fields(self):
        """Test all persona configs have required fields."""
        manager = PersonaManager(include_defaults=True)

        persona_values = manager.list_persona_values()
        for persona_value in persona_values:
            config = manager.get_persona_config(persona_value)
            assert config.name
            assert config.description
            assert config.instructions
            assert isinstance(config.focus_areas, list)
            assert isinstance(config.evaluation_criteria, list)

    def test_default_config_dir_resolution(self):
        """Test that default config dir is resolved correctly."""
        manager = PersonaManager(include_defaults=True)

        assert manager.config_dir is not None
        assert isinstance(manager.config_dir, Path)
        # Should contain 'config' and 'personas' in path
        assert "config" in str(manager.config_dir).lower()
        assert "personas" in str(manager.config_dir).lower()

    def test_custom_persona_overrides_default(self):
        """Test that custom persona overrides default with same name."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "technical_lead.json"
            config_file.write_text(
                json.dumps(
                    {
                        "name": "Custom Technical Lead",
                        "description": "Custom description",
                        "instructions": "Custom instructions",
                        "focus_areas": ["CustomArea"],
                        "evaluation_criteria": ["CustomCriterion"],
                    }
                )
            )

            manager = PersonaManager(config_dir=str(config_dir), include_defaults=True)

            config = manager.get_persona_config("technical_lead")
            assert config is not None
            assert config.name == "Custom Technical Lead"
            assert config.description == "Custom description"
