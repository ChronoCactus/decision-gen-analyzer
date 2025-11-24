"""Tests for persona refinement history tracking."""

from src.models import PersonaSynthesisInput


class TestPersonaRefinementHistory:
    """Test persona refinement history tracking."""

    def test_persona_synthesis_with_refinement_history(self):
        """Test PersonaSynthesisInput includes refinement_history field."""
        persona = PersonaSynthesisInput(
            persona="technical_lead",
            perspective="Test perspective",
            reasoning="Test reasoning",
            concerns=["concern1"],
            requirements=["req1"],
            refinement_history=[
                "First refinement prompt",
                "Second refinement prompt",
            ],
        )

        assert len(persona.refinement_history) == 2
        assert persona.refinement_history[0] == "First refinement prompt"
        assert persona.refinement_history[1] == "Second refinement prompt"

    def test_persona_synthesis_default_empty_history(self):
        """Test refinement_history defaults to empty list."""
        persona = PersonaSynthesisInput(
            persona="technical_lead",
            perspective="Test perspective",
            reasoning="Test reasoning",
        )

        assert persona.refinement_history == []
        assert isinstance(persona.refinement_history, list)

    def test_persona_synthesis_from_dict_with_history(self):
        """Test creating PersonaSynthesisInput from dict preserves history."""
        data = {
            "persona": "technical_lead",
            "perspective": "Test perspective",
            "reasoning": "Test reasoning",
            "concerns": [],
            "requirements": [],
            "refinement_history": ["Refine for security", "Add performance notes"],
        }

        persona = PersonaSynthesisInput(**data)

        assert len(persona.refinement_history) == 2
        assert persona.refinement_history[0] == "Refine for security"
        assert persona.refinement_history[1] == "Add performance notes"

    def test_persona_synthesis_from_dict_without_history(self):
        """Test creating PersonaSynthesisInput from dict without history field."""
        data = {
            "persona": "technical_lead",
            "perspective": "Test perspective",
            "reasoning": "Test reasoning",
            "concerns": [],
            "requirements": [],
        }

        persona = PersonaSynthesisInput(**data)

        # Should default to empty list
        assert persona.refinement_history == []

    def test_persona_model_dump_includes_history(self):
        """Test model_dump includes refinement_history."""
        persona = PersonaSynthesisInput(
            persona="technical_lead",
            perspective="Test perspective",
            reasoning="Test reasoning",
            refinement_history=["First refinement"],
        )

        persona_dict = persona.model_dump()

        assert "refinement_history" in persona_dict
        assert persona_dict["refinement_history"] == ["First refinement"]

    def test_persona_history_is_mutable(self):
        """Test refinement_history can be appended to."""
        persona = PersonaSynthesisInput(
            persona="technical_lead",
            perspective="Test perspective",
            reasoning="Test reasoning",
        )

        # Initially empty
        assert persona.refinement_history == []

        # Can be modified (though in practice we create new instances)
        test_history = persona.refinement_history + ["New refinement"]

        assert len(test_history) == 1
        assert test_history[0] == "New refinement"

    def test_refinement_deletion(self):
        """Test deleting refinements from history."""
        persona = PersonaSynthesisInput(
            persona="technical_lead",
            perspective="Test perspective",
            reasoning="Test reasoning",
            refinement_history=[
                "First refinement",
                "Second refinement",
                "Third refinement",
            ],
        )

        assert len(persona.refinement_history) == 3

        # Delete the second refinement (index 1)
        persona.refinement_history.pop(1)

        assert len(persona.refinement_history) == 2
        assert persona.refinement_history[0] == "First refinement"
        assert persona.refinement_history[1] == "Third refinement"

    def test_refinement_multiple_deletions(self):
        """Test deleting multiple refinements in reverse order."""
        persona = PersonaSynthesisInput(
            persona="technical_lead",
            perspective="Test perspective",
            reasoning="Test reasoning",
            refinement_history=[
                "Refinement 1",
                "Refinement 2",
                "Refinement 3",
                "Refinement 4",
            ],
        )

        # Delete indices 2 and 1 in reverse order (to avoid index shifting)
        for idx in [2, 1]:
            persona.refinement_history.pop(idx)

        assert len(persona.refinement_history) == 2
        assert persona.refinement_history[0] == "Refinement 1"
        assert persona.refinement_history[1] == "Refinement 4"

    def test_deletion_only_preserves_persona(self):
        """Test that deleting refinements without adding new ones preserves persona data."""
        persona = PersonaSynthesisInput(
            persona="technical_lead",
            perspective="Original perspective",
            reasoning="Original reasoning",
            concerns=["Concern 1", "Concern 2"],
            requirements=["Requirement 1"],
            refinement_history=[
                "First refinement",
                "Second refinement to delete",
                "Third refinement",
            ],
        )

        # Delete the middle refinement
        persona.refinement_history.pop(1)

        # Verify persona data is preserved
        assert persona.persona == "technical_lead"
        assert persona.perspective == "Original perspective"
        assert persona.reasoning == "Original reasoning"
        assert len(persona.concerns) == 2
        assert len(persona.requirements) == 1

        # Verify refinement history is updated
        assert len(persona.refinement_history) == 2
        assert persona.refinement_history[0] == "First refinement"
        assert persona.refinement_history[1] == "Third refinement"
