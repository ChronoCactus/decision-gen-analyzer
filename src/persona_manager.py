"""Persona configuration management for ADR analysis."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from models import AnalysisPersona


@dataclass
class PersonaConfig:
    """Configuration for an analysis persona."""
    name: str
    description: str
    instructions: str
    focus_areas: List[str]
    evaluation_criteria: List[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PersonaConfig':
        """Create a PersonaConfig from a dictionary."""
        return cls(
            name=data['name'],
            description=data['description'],
            instructions=data['instructions'],
            focus_areas=data.get('focus_areas', []),
            evaluation_criteria=data.get('evaluation_criteria', [])
        )


class PersonaManager:
    """Manages persona configurations."""

    def __init__(self, config_dir: Optional[str] = None):
        """Initialize the persona manager."""
        if config_dir is None:
            # Default to config/personas relative to the project root
            project_root = Path(__file__).parent.parent.parent
            config_dir = project_root / "config" / "personas"

        self.config_dir = Path(config_dir)
        self._persona_configs: Dict[AnalysisPersona, PersonaConfig] = {}
        self._load_persona_configs()

    def _load_persona_configs(self):
        """Load persona configurations from JSON files."""
        if not self.config_dir.exists():
            # Fallback to hardcoded configs if directory doesn't exist
            self._load_fallback_configs()
            return

        for persona in AnalysisPersona:
            config_file = self.config_dir / f"{persona.value}.json"
            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self._persona_configs[persona] = PersonaConfig.from_dict(data)
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Warning: Failed to load persona config for {persona.value}: {e}")
                    # Use fallback for this persona
                    self._persona_configs[persona] = self._get_fallback_config(persona)
            else:
                # Use fallback if config file doesn't exist
                self._persona_configs[persona] = self._get_fallback_config(persona)

    def _load_fallback_configs(self):
        """Load hardcoded fallback configurations."""
        for persona in AnalysisPersona:
            self._persona_configs[persona] = self._get_fallback_config(persona)

    def _get_fallback_config(self, persona: AnalysisPersona) -> PersonaConfig:
        """Get fallback configuration for a persona."""
        fallbacks = {
            AnalysisPersona.TECHNICAL_LEAD: PersonaConfig(
                name="Technical Lead",
                description="Senior technical leadership perspective",
                instructions="Focus on technical feasibility, implementation complexity, maintainability, performance implications, and technical debt.",
                focus_areas=["Technical feasibility", "Implementation complexity", "Maintainability"],
                evaluation_criteria=["Can this be implemented?", "What is the complexity?", "Future maintenance impact?"]
            ),
            AnalysisPersona.BUSINESS_ANALYST: PersonaConfig(
                name="Business Analyst",
                description="Business value analysis",
                instructions="Focus on business value, cost implications, and stakeholder impact.",
                focus_areas=["Business value", "Cost implications", "Stakeholder impact"],
                evaluation_criteria=["What is the business value?", "Cost impact?", "Stakeholder benefits?"]
            ),
            AnalysisPersona.SECURITY_EXPERT: PersonaConfig(
                name="Security Expert",
                description="Security and risk assessment",
                instructions="Focus on security implications and risk mitigation.",
                focus_areas=["Security risks", "Compliance", "Threat mitigation"],
                evaluation_criteria=["Security vulnerabilities?", "Compliance requirements?", "Risk mitigation?"]
            ),
            AnalysisPersona.PHILOSOPHER: PersonaConfig(
                name="Philosopher",
                description="Philosophical analysis",
                instructions="Focus on fundamental principles and long-term implications.",
                focus_areas=["Principles", "Ethics", "Long-term impact"],
                evaluation_criteria=["Fundamental alignment?", "Ethical concerns?", "Long-term wisdom?"]
            )
        }

        # For personas without specific fallbacks, use a generic one
        if persona in fallbacks:
            return fallbacks[persona]
        else:
            return PersonaConfig(
                name=str(persona.value).replace('_', ' ').title(),
                description=f"{persona.value} perspective",
                instructions=f"Provide analysis from the {persona.value} perspective.",
                focus_areas=[f"{persona.value} considerations"],
                evaluation_criteria=[f"How does this affect {persona.value} concerns?"]
            )

    def get_persona_config(self, persona: AnalysisPersona) -> PersonaConfig:
        """Get the configuration for a specific persona."""
        return self._persona_configs.get(persona, self._get_fallback_config(persona))

    def get_persona_instructions(self, persona: AnalysisPersona) -> Dict[str, str]:
        """Get instructions for a specific persona (legacy compatibility)."""
        config = self.get_persona_config(persona)
        return {
            "role": config.name,
            "instructions": config.instructions
        }

    def list_personas(self) -> List[AnalysisPersona]:
        """List all available personas."""
        return list(AnalysisPersona)

    def get_all_persona_configs(self) -> Dict[AnalysisPersona, PersonaConfig]:
        """Get all persona configurations."""
        return self._persona_configs.copy()


# Global persona manager instance
_persona_manager: Optional[PersonaManager] = None


def get_persona_manager() -> PersonaManager:
    """Get the global persona manager instance."""
    global _persona_manager
    if _persona_manager is None:
        _persona_manager = PersonaManager()
    return _persona_manager
