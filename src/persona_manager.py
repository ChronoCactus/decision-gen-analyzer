"""Persona configuration management for ADR analysis."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class ModelConfig:
    """Configuration for the LLM model used by a persona."""

    name: str  # Model name (e.g., "gpt-oss:20b", "llama3:70b")
    provider: Optional[str] = (
        None  # Provider type: ollama, openai, openrouter, vllm, llama_cpp, custom
    )
    base_url: Optional[str] = None  # Base URL for the LLM API endpoint
    temperature: Optional[float] = None  # Temperature for generation (0.0 to 1.0)
    num_ctx: Optional[int] = None  # Context window size (Ollama-specific)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelConfig":
        """Create a ModelConfig from a dictionary."""
        return cls(
            name=data["name"],
            provider=data.get("provider"),
            base_url=data.get("base_url"),
            temperature=data.get("temperature"),
            num_ctx=data.get("num_ctx"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert ModelConfig to a dictionary."""
        result = {"name": self.name}
        if self.provider is not None:
            result["provider"] = self.provider
        if self.base_url is not None:
            result["base_url"] = self.base_url
        if self.temperature is not None:
            result["temperature"] = self.temperature
        if self.num_ctx is not None:
            result["num_ctx"] = self.num_ctx
        return result


@dataclass
class PersonaConfig:
    """Configuration for an analysis persona."""
    name: str
    description: str
    instructions: str
    focus_areas: List[str]
    evaluation_criteria: List[str]
    model_config: Optional[ModelConfig] = (
        None  # Optional per-persona model configuration
    )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PersonaConfig':
        """Create a PersonaConfig from a dictionary."""
        model_config = None
        # Support both 'llm_config' (new) and 'model_config' (legacy) for backward compatibility
        config_data = data.get("llm_config") or data.get("model_config")
        if config_data:
            model_config = ModelConfig.from_dict(config_data)

        return cls(
            name=data["name"],
            description=data["description"],
            instructions=data["instructions"],
            focus_areas=data.get("focus_areas", []),
            evaluation_criteria=data.get("evaluation_criteria", []),
            model_config=model_config,
        )


class PersonaManager:
    """Manages persona configurations dynamically from filesystem."""

    def __init__(self, config_dir: Optional[str] = None, include_defaults: bool = True):
        """
        Initialize the persona manager.

        Args:
            config_dir: Custom personas directory (defaults to config/personas)
            include_defaults: Whether to include default personas from defaults/ subdirectory
        """
        if config_dir is None:
            # Default to config/personas relative to the project root
            # From src/persona_manager.py: parent is src/, parent.parent is project root
            project_root = Path(__file__).parent.parent
            config_dir = project_root / "config" / "personas"

        self.config_dir = Path(config_dir)
        self.defaults_dir = self.config_dir / "defaults"
        self.include_defaults = include_defaults

    def _load_persona_from_file(self, file_path: Path) -> Optional[PersonaConfig]:
        """Load a single persona configuration from a JSON file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return PersonaConfig.from_dict(data)
        except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
            print(f"Warning: Failed to load persona config from {file_path}: {e}")
            return None

    def get_persona_config(self, persona_value: str) -> Optional[PersonaConfig]:
        """
        Get the configuration for a specific persona by value (reloads from filesystem each time).

        Args:
            persona_value: The persona identifier (e.g., 'technical_lead', 'data_engineer')

        Returns:
            PersonaConfig if found, None otherwise
        """
        # Try custom personas first
        config_file = self.config_dir / f"{persona_value}.json"
        if config_file.exists():
            config = self._load_persona_from_file(config_file)
            if config:
                return config

        # Try defaults if enabled
        if self.include_defaults:
            defaults_file = self.defaults_dir / f"{persona_value}.json"
            if defaults_file.exists():
                config = self._load_persona_from_file(defaults_file)
                if config:
                    return config

        return None

    def get_persona_instructions(self, persona_value: str) -> Optional[Dict[str, str]]:
        """Get instructions for a specific persona."""
        config = self.get_persona_config(persona_value)
        if config:
            return {"role": config.name, "instructions": config.instructions}
        return None

    def list_persona_values(self) -> List[str]:
        """List all available persona values (identifiers)."""
        return list(self.discover_all_personas().keys())

    def discover_all_personas(self) -> Dict[str, PersonaConfig]:
        """
        Discover all personas from JSON files in the config directory.
        Returns a dict mapping persona value (filename without .json) to PersonaConfig.

        Priority: Custom personas override defaults with the same name.
        """
        personas = {}

        # Load defaults first if enabled
        if self.include_defaults and self.defaults_dir.exists():
            for json_file in self.defaults_dir.glob("*.json"):
                persona_value = json_file.stem  # filename without extension
                config = self._load_persona_from_file(json_file)
                if config:
                    personas[persona_value] = config

        # Load custom personas (can override defaults)
        if self.config_dir.exists():
            for json_file in self.config_dir.glob("*.json"):
                persona_value = json_file.stem
                config = self._load_persona_from_file(json_file)
                if config:
                    personas[persona_value] = config

        return personas


# Global persona manager instance
_persona_manager: Optional[PersonaManager] = None


def get_persona_manager(include_defaults: Optional[bool] = None) -> PersonaManager:
    """
    Get the global persona manager instance.

    Args:
        include_defaults: Whether to include default personas. If None, reads from settings.
    """
    global _persona_manager
    if _persona_manager is None:
        if include_defaults is None:
            # Import here to avoid circular dependency
            from src.config import get_settings

            settings = get_settings()
            include_defaults = settings.include_default_personas

        _persona_manager = PersonaManager(include_defaults=include_defaults)
    return _persona_manager
