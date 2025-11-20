"""Tests for ADR generation cleanup and validation logic."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.adr_generation import ADRGenerationService
from src.models import ADRGenerationOptions


class TestADRGenerationCleanup:
    """Test cleanup and validation functions."""

    @pytest.fixture
    def service(self):
        """Create service with mock clients."""
        llama_client = AsyncMock()
        lightrag_client = AsyncMock()
        persona_manager = MagicMock()
        return ADRGenerationService(llama_client, lightrag_client, persona_manager)

    def test_clean_list_items_with_concatenated_bullets(self, service):
        """Test cleaning items with concatenated bullet points."""
        items = [
            "- pro1 - pro2 - pro3",
            "normal item",
            "• bullet1 • bullet2",
        ]

        cleaned = service._clean_list_items(items)

        # Should split the first and third items
        assert "pro1" in cleaned
        assert "pro2" in cleaned
        assert "pro3" in cleaned
        assert "normal item" in cleaned
        assert "bullet1" in cleaned
        assert "bullet2" in cleaned
        # Should not have the concatenated originals
        assert not any("- pro2" in item for item in cleaned)

    def test_clean_list_items_removes_leading_bullets(self, service):
        """Test that leading bullet markers are removed."""
        items = [
            "- item with leading dash",
            "• item with bullet",
            "* item with asterisk",
            "normal item",
        ]

        cleaned = service._clean_list_items(items)

        # All should have bullets removed
        assert "item with leading dash" in cleaned
        assert "item with bullet" in cleaned
        assert "item with asterisk" in cleaned
        assert "normal item" in cleaned
        # Should not have leading markers
        assert not any(item.startswith("-") for item in cleaned)
        assert not any(item.startswith("•") for item in cleaned)
        assert not any(item.startswith("*") for item in cleaned)

    def test_clean_list_items_filters_empty_bullets(self, service):
        """Test that empty bullet points are filtered out."""
        items = [
            "valid item",
            " - ",  # Just a bullet with spaces
            "-",  # Just a bullet
            "  ",  # Just whitespace
            "",  # Empty string
            "• ",  # Just a bullet marker
            "another valid item",
        ]

        cleaned = service._clean_list_items(items)

        # Should only have valid items
        assert len(cleaned) == 2
        assert "valid item" in cleaned
        assert "another valid item" in cleaned
        # Should not have any empty or bullet-only items
        assert not any(item.strip() in ["-", "•", "*", ""] for item in cleaned)

    def test_validate_and_cleanup_synthesis_data_cleans_options(self, service):
        """Test validation cleans up pros/cons in options."""
        data = {
            "title": "Test ADR",
            "considered_options": [
                ADRGenerationOptions(
                    option_name="Option 1",
                    description="Description",
                    pros=["- pro1 - pro2", "normal pro"],
                    cons=["• con1 • con2"],
                )
            ],
            "context_and_problem": "Well formatted text",
            "decision_outcome": "Well formatted text",
            "consequences": "Well formatted text",
        }

        cleaned_data, sections_to_polish = service._validate_and_cleanup_synthesis_data(
            data
        )

        # Pros/cons should be cleaned
        option = cleaned_data["considered_options"][0]
        assert "pro1" in option.pros
        assert "pro2" in option.pros
        assert "normal pro" in option.pros
        assert "con1" in option.cons
        assert "con2" in option.cons
        # Should not need polishing if only list cleanup was needed
        assert not any(sections_to_polish.values())

    def test_validate_detects_formatting_issues(self, service):
        """Test validation detects text formatting issues in specific sections."""
        data = {
            "title": "Test ADR",
            "considered_options": [],
            "context_and_problem": "Text with GPU\nRAM split",
            "decision_outcome": "Well formatted text",
            "consequences": "Text with  multiple  spaces",
        }

        _, sections_to_polish = service._validate_and_cleanup_synthesis_data(data)

        # Should detect formatting issues in specific sections
        assert sections_to_polish["context_and_problem"] is True
        assert sections_to_polish["decision_outcome"] is False
        assert sections_to_polish["consequences"] is True

    def test_validate_accepts_well_formatted_data(self, service):
        """Test validation accepts well-formatted data."""
        data = {
            "title": "Test ADR",
            "considered_options": [
                ADRGenerationOptions(
                    option_name="Option 1",
                    description="Description",
                    pros=["Pro 1", "Pro 2"],
                    cons=["Con 1", "Con 2"],
                )
            ],
            "context_and_problem": "Well formatted text without issues.",
            "decision_outcome": "Well formatted decision text.",
            "consequences": "Well formatted consequences.",
        }

        cleaned_data, sections_to_polish = service._validate_and_cleanup_synthesis_data(
            data
        )

        # Should not need polishing for any section
        assert not any(sections_to_polish.values())
        # Data should be unchanged
        assert cleaned_data["context_and_problem"] == data["context_and_problem"]

    def test_parse_synthesis_response_cleans_consequences_dict(self, service):
        """Test that consequences dict with positive/negative arrays gets cleaned."""
        # Simulate LLM response with consequences as dict containing empty bullets
        response = """{
            "title": "Test ADR",
            "context_and_problem": "Test context",
            "considered_options": [],
            "decision_outcome": "Test outcome",
            "consequences": {
                "positive": ["Good thing 1", " - ", "Good thing 2"],
                "negative": ["Bad thing 1", "•", "Bad thing 2"]
            },
            "decision_drivers": ["Driver 1"],
            "confidence_score": 0.8
        }"""

        parsed = service._parse_synthesis_response(response)

        # Should have cleaned up the consequences
        assert parsed is not None
        assert "consequences" in parsed
        consequences = parsed["consequences"]

        # Should not contain empty bullets
        assert " - " not in consequences
        assert "•" not in consequences

        # Should contain the actual items
        assert "Good thing 1" in consequences
        assert "Good thing 2" in consequences
        assert "Bad thing 1" in consequences
        assert "Bad thing 2" in consequences

    def test_validate_skips_consequences_when_structured(self, service):
        """Test that validation skips consequences text when structured version exists."""
        data = {
            "title": "Test ADR",
            "considered_options": [],
            "context_and_problem": "Well formatted text.",
            "decision_outcome": "Well formatted decision.",
            "consequences": "Positive: item with non‑breaking hyphen\nNegative: another item",
            "consequences_structured": {
                "positive": ["Item 1", "Item 2"],
                "negative": ["Item 3"],
            },
        }

        cleaned_data, sections_to_polish = service._validate_and_cleanup_synthesis_data(
            data
        )

        # Should NOT need polishing even though consequences text has non-breaking hyphen
        # because consequences_structured exists
        assert sections_to_polish["consequences"] is False
        assert not any(sections_to_polish.values())
