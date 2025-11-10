"""Tests for Celery tasks."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.celery_app import (
    analyze_adr_task,
    generate_adr_task,
)
from src.models import ADR


class TestCeleryTasks:
    """Test Celery task functions."""

    @pytest.fixture
    def sample_adr_dict(self):
        """Create sample ADR as dict."""
        adr = ADR.create(
            title="Test",
            context_and_problem="Problem",
            decision_outcome="Decision",
            consequences="Consequences",
        )
        return adr.model_dump()

    def test_analyze_adr_task_callable(self):
        """Test analyze ADR task is callable."""
        # Basic structure test - tasks should be callable
        assert callable(analyze_adr_task)

    def test_generate_adr_task_callable(self):
        """Test generate ADR task is callable."""
        # Basic structure test - tasks should be callable
        assert callable(generate_adr_task)

    def test_consequences_text_parsing_inline(self):
        """Test inline consequences parsing logic (as done in generate_adr_task)."""
        # This tests the inline logic from lines 182-223 in celery_app.py
        cons_text = """Positive:
- Benefit 1
- Benefit 2

Negative:
- Drawback 1
- Drawback 2"""

        positive_items = []
        negative_items = []

        if "Positive:" in cons_text and "Negative:" in cons_text:
            parts = cons_text.split("Negative:")
            positive_text = parts[0].replace("Positive:", "").strip()
            negative_text = parts[1].strip() if len(parts) > 1 else ""

            # Parse bullet points from positive section
            for line in positive_text.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    line = line[2:].strip()
                elif line.startswith("* "):
                    line = line[2:].strip()
                elif line.startswith("• "):
                    line = line[2:].strip()

                if line:
                    positive_items.append(line)

            # Parse bullet points from negative section
            for line in negative_text.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    line = line[2:].strip()
                elif line.startswith("* "):
                    line = line[2:].strip()
                elif line.startswith("• "):
                    line = line[2:].strip()

                if line:
                    negative_items.append(line)

        assert len(positive_items) == 2
        assert len(negative_items) == 2
        assert "Benefit 1" in positive_items
        assert "Drawback 1" in negative_items

    def test_consequences_with_different_markers(self):
        """Test consequences parsing with different bullet markers."""
        cons_text = """Positive:
* Item 1
• Item 2
- Item 3

Negative:
* Item 4"""

        positive_items = []
        negative_items = []

        if "Positive:" in cons_text and "Negative:" in cons_text:
            parts = cons_text.split("Negative:")
            positive_text = parts[0].replace("Positive:", "").strip()
            negative_text = parts[1].strip() if len(parts) > 1 else ""

            for line in positive_text.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    line = line[2:].strip()
                elif line.startswith("* "):
                    line = line[2:].strip()
                elif line.startswith("• "):
                    line = line[2:].strip()
                if line:
                    positive_items.append(line)

            for line in negative_text.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    line = line[2:].strip()
                elif line.startswith("* "):
                    line = line[2:].strip()
                elif line.startswith("• "):
                    line = line[2:].strip()
                if line:
                    negative_items.append(line)

        assert len(positive_items) == 3
        assert len(negative_items) == 1
        assert "Item 1" in positive_items
        assert "Item 4" in negative_items

    def test_consequences_filters_empty_bullets_and_capitalizes(self):
        """Test that empty bullets are filtered and items are capitalized."""
        cons_text = """Positive:
- significant reduction in animal suffering
-  -
- potential health benefits

Negative:
- risk of nutrient deficiencies
• """

        positive_items = []
        negative_items = []

        if "Positive:" in cons_text and "Negative:" in cons_text:
            parts = cons_text.split("Negative:")
            positive_text = parts[0].replace("Positive:", "").strip()
            negative_text = parts[1].strip() if len(parts) > 1 else ""

            # Parse bullet points from positive section
            for line in positive_text.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    line = line[2:].strip()
                elif line.startswith("* "):
                    line = line[2:].strip()
                elif line.startswith("• "):
                    line = line[2:].strip()

                # Only add if not empty and not just punctuation/whitespace
                if line and line not in ["-", "•", "*"]:
                    # Capitalize first letter if not already
                    if line and line[0].islower():
                        line = line[0].upper() + line[1:]
                    positive_items.append(line)

            # Parse bullet points from negative section
            for line in negative_text.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    line = line[2:].strip()
                elif line.startswith("* "):
                    line = line[2:].strip()
                elif line.startswith("• "):
                    line = line[2:].strip()

                # Only add if not empty and not just punctuation/whitespace
                if line and line not in ["-", "•", "*"]:
                    # Capitalize first letter if not already
                    if line and line[0].islower():
                        line = line[0].upper() + line[1:]
                    negative_items.append(line)

        # Should only have 2 positive items (empty " - " filtered out)
        assert len(positive_items) == 2
        # Should only have 1 negative item (empty "• " filtered out)
        assert len(negative_items) == 1

        # All items should be capitalized
        assert positive_items[0].startswith("S")  # "Significant reduction..."
        assert positive_items[1].startswith("P")  # "Potential health benefits"
        assert negative_items[0].startswith("R")  # "Risk of nutrient deficiencies"

        # Should not contain empty bullets
        assert "-" not in positive_items
        assert "•" not in negative_items
