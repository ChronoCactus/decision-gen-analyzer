"""Tests for ADR import/export functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, mock_open, patch
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.adr_import_export import ADRImportExport
from src.models import ADR


class TestADRImportExport:
    """Test ADRImportExport class."""

    @pytest.fixture
    def sample_adr(self):
        """Create sample ADR."""
        return ADR.create(
            title="Test ADR",
            context_and_problem="Problem",
            decision_outcome="Decision",
            consequences="Consequences",
        )

    def test_export_adr_to_json(self, sample_adr):
        """Test exporting ADR to JSON."""
        exporter = ADRImportExport()

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            exporter.export_to_json(sample_adr, str(output_path))

            # Verify file was created and contains correct data
            assert output_path.exists()
            with open(output_path, 'r') as f:
                data = json.load(f)
            assert data["metadata"]["title"] == "Test ADR"

    def test_import_adr_from_json(self, sample_adr):
        """Test importing ADR from JSON."""
        exporter = ADRImportExport()

        with TemporaryDirectory() as tmpdir:
            # Export to file
            output_path = Path(tmpdir) / "test.json"
            exporter.export_to_json(sample_adr, str(output_path))
            
            # Import from file
            imported_adr = exporter.import_from_json(str(output_path))

            assert imported_adr.metadata.title == sample_adr.metadata.title
            assert imported_adr.metadata.id == sample_adr.metadata.id

    def test_export_adr_to_markdown(self, sample_adr):
        """Test exporting ADR to Markdown."""
        exporter = ADRImportExport()

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.md"
            exporter.export_to_markdown(sample_adr, str(output_path))

            # Verify file was created and contains correct data
            assert output_path.exists()
            with open(output_path, 'r') as f:
                markdown = f.read()
            assert "# Test ADR" in markdown
            assert "Problem" in markdown

    def test_export_multiple_adrs(self, sample_adr):
        """Test exporting multiple ADRs to separate files."""
        exporter = ADRImportExport()

        with TemporaryDirectory() as tmpdir:
            adrs = [sample_adr]
            
            # Export each ADR
            for i, adr in enumerate(adrs):
                output_path = Path(tmpdir) / f"test_{i}.json"
                exporter.export_to_json(adr, str(output_path))
                assert output_path.exists()

    def test_import_handles_invalid_json(self):
        """Test import handles invalid JSON."""
        exporter = ADRImportExport()

        with pytest.raises(Exception):
            exporter.import_from_json("invalid json")
