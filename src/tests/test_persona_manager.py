"""Tests for persona manager."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from tempfile import TemporaryDirectory

from src.persona_manager import PersonaManager, PersonaConfig
from src.models import AnalysisPersona


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
            manager = PersonaManager(config_dir=tmpdir)

            assert manager.config_dir == Path(tmpdir)
            # Should load fallback configs when directory is empty
            assert len(manager._persona_configs) > 0

    def test_persona_manager_loads_fallback_configs(self):
        """Test PersonaManager loads fallback configs when directory doesn't exist."""
        # Create manager with non-existent directory
        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_dir = Path(temp_dir) / "non_existent"
            manager = PersonaManager(config_dir=str(non_existent_dir))

            # Should load fallback configs
            config = manager.get_persona_config(AnalysisPersona.TECHNICAL_LEAD)

            assert config is not None
            assert config.name == "Technical Lead"
            assert len(config.focus_areas) > 0

    def test_persona_manager_loads_json_configs(self):
        """Test PersonaManager loads JSON configs from directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_file = config_dir / "technical_lead.json"
            config_file.write_text(json.dumps({
                "name": "Technical Lead",
                "description": "Test description",
                "instructions": "Test instructions",
                "focus_areas": ["Area1", "Area2"],
                "evaluation_criteria": ["Criterion1"]
            }))

            manager = PersonaManager(config_dir=str(config_dir))

            config = manager.get_persona_config(AnalysisPersona.TECHNICAL_LEAD)
            assert config.name == "Technical Lead"
            assert config.description == "Test description"

    def test_get_config_returns_persona_config(self):
        """Test get_persona_config returns PersonaConfig."""
        manager = PersonaManager()

        config = manager.get_persona_config(AnalysisPersona.BUSINESS_ANALYST)

        assert isinstance(config, PersonaConfig)
        assert config.name is not None
        assert config.description is not None
        assert config.instructions is not None

    def test_get_config_for_all_personas(self):
        """Test get_persona_config works for all personas."""
        manager = PersonaManager()

        for persona in AnalysisPersona:
            config = manager.get_persona_config(persona)
            assert config is not None
            assert isinstance(config, PersonaConfig)

    def test_get_all_personas(self):
        """Test list_personas returns list of personas."""
        manager = PersonaManager()

        personas = manager.list_personas()

        assert isinstance(personas, list)
        assert len(personas) > 0
        assert all(isinstance(p, AnalysisPersona) for p in personas)

    def test_get_persona_names(self):
        """Test get_all_persona_configs returns dict of configs."""
        manager = PersonaManager()

        configs = manager.get_all_persona_configs()

        assert isinstance(configs, dict)
        assert len(configs) > 0
        assert all(isinstance(p, AnalysisPersona) for p in configs.keys())
        assert all(isinstance(c, PersonaConfig) for c in configs.values())

    def test_invalid_json_falls_back_to_default(self):
        """Test invalid JSON falls back to default config."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_file = config_dir / "technical_lead.json"
            config_file.write_text("invalid json {")

            manager = PersonaManager(config_dir=str(config_dir))

            # Should fall back to default config
            config = manager.get_persona_config(AnalysisPersona.TECHNICAL_LEAD)
            assert config is not None
            assert config.name == "Technical Lead"

    def test_missing_required_field_falls_back(self):
        """Test missing required field falls back to default."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_file = config_dir / "technical_lead.json"
            # Missing 'description' field
            config_file.write_text(json.dumps({
                "name": "Technical Lead",
                "instructions": "Test",
            }))

            manager = PersonaManager(config_dir=str(config_dir))

            config = manager.get_persona_config(AnalysisPersona.TECHNICAL_LEAD)
            assert config is not None
            assert config.description is not None

    def test_persona_config_has_required_fields(self):
        """Test all persona configs have required fields."""
        manager = PersonaManager()

        for persona in AnalysisPersona:
            config = manager.get_persona_config(persona)
            assert config.name
            assert config.description
            assert config.instructions
            assert isinstance(config.focus_areas, list)
            assert isinstance(config.evaluation_criteria, list)

    def test_persona_manager_loads_json_configs(self):
        """Test PersonaManager loads JSON configuration files."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a test JSON config file
            test_config = {
                "name": "Test Lead",
                "description": "Test description",
                "instructions": "Test instructions",
                "focus_areas": ["test1", "test2"],
                "evaluation_criteria": ["criteria1"],
            }

            config_file = tmpdir_path / "technical_lead.json"
            with open(config_file, "w") as f:
                json.dump(test_config, f)

            manager = PersonaManager(config_dir=tmpdir)

            config = manager.get_persona_config(AnalysisPersona.TECHNICAL_LEAD)
            assert config.name == "Test Lead"
            assert config.description == "Test description"
            assert len(config.focus_areas) == 2

    def test_get_config_returns_persona_config(self):
        """Test get_persona_config returns a PersonaConfig."""
        manager = PersonaManager()

        config = manager.get_persona_config(AnalysisPersona.BUSINESS_ANALYST)

        assert isinstance(config, PersonaConfig)
        assert config.name is not None
        assert isinstance(config.focus_areas, list)
        assert isinstance(config.evaluation_criteria, list)

    def test_get_config_for_all_personas(self):
        """Test get_persona_config works for all persona types."""
        manager = PersonaManager()

        for persona in AnalysisPersona:
            config = manager.get_persona_config(persona)
            assert config is not None
            assert isinstance(config, PersonaConfig)

    def test_get_all_personas(self):
        """Test list_personas returns list of all personas."""
        manager = PersonaManager()

        personas = manager.list_personas()

        assert isinstance(personas, list)
        assert len(personas) == len(AnalysisPersona)
        # Check each persona type explicitly since enum isinstance can be tricky
        for p in personas:
            assert hasattr(p, 'value'), f"Persona {p} should be an enum with value attribute"
            assert p in AnalysisPersona, f"Persona {p} should be in AnalysisPersona enum"

    def test_get_persona_names(self):
        """Test getting all persona configs returns dict."""
        manager = PersonaManager()

        configs = manager.get_all_persona_configs()

        assert isinstance(configs, dict)
        assert len(configs) == len(AnalysisPersona)
        # Check keys are personas
        for p in configs.keys():
            assert hasattr(p, 'value'), f"Key {p} should be an enum with value attribute"
            assert p in AnalysisPersona, f"Key {p} should be in AnalysisPersona enum"
        # Check values are PersonaConfig
        assert all(isinstance(c, PersonaConfig) for c in configs.values())

    def test_invalid_json_falls_back_to_default(self):
        """Test that invalid JSON falls back to default config."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create an invalid JSON file
            config_file = tmpdir_path / "technical_lead.json"
            with open(config_file, "w") as f:
                f.write("invalid json {{{")

            manager = PersonaManager(config_dir=tmpdir)

            # Should still have a config (fallback)
            config = manager.get_persona_config(AnalysisPersona.TECHNICAL_LEAD)
            assert config is not None
            assert isinstance(config, PersonaConfig)

    def test_missing_required_field_falls_back(self):
        """Test that JSON missing required fields falls back."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create JSON with missing required fields
            test_config = {
                "name": "Test",
                # Missing 'description' and 'instructions'
            }

            config_file = tmpdir_path / "technical_lead.json"
            with open(config_file, "w") as f:
                json.dump(test_config, f)

            manager = PersonaManager(config_dir=tmpdir)

            # Should still have a config (fallback)
            config = manager.get_persona_config(AnalysisPersona.TECHNICAL_LEAD)
            assert config is not None
            assert config.instructions is not None

    def test_persona_config_has_required_fields(self):
        """Test that all persona configs have required fields."""
        manager = PersonaManager()

        for persona in AnalysisPersona:
            config = manager.get_persona_config(persona)
            
            assert config.name, f"Persona {persona} missing name"
            assert config.description, f"Persona {persona} missing description"
            assert config.instructions, f"Persona {persona} missing instructions"
            assert isinstance(config.focus_areas, list)
            assert isinstance(config.evaluation_criteria, list)

    def test_default_config_dir_resolution(self):
        """Test that default config dir is resolved correctly."""
        manager = PersonaManager()

        assert manager.config_dir is not None
        assert isinstance(manager.config_dir, Path)
        # Should contain 'config' and 'personas' in path
        assert "config" in str(manager.config_dir).lower()
        assert "personas" in str(manager.config_dir).lower()
