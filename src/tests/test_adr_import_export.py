"""Tests for ADR import/export functionality with versioned schema support."""

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List
from uuid import uuid4

import pytest

from src.adr_import_export import (
    CURRENT_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    ADRImportExport,
    BulkADRExport,
    ExportSchemaMetadata,
    SingleADRExport,
)
from src.models import ADR


class TestVersionedSchemaModels:
    """Test the versioned schema Pydantic models."""

    def test_export_schema_metadata_defaults(self):
        """Test ExportSchemaMetadata creates with default values."""
        metadata = ExportSchemaMetadata()

        assert metadata.schema_version == CURRENT_SCHEMA_VERSION
        assert metadata.total_records == 1
        assert metadata.exported_at is not None
        assert metadata.exported_by is None

    def test_export_schema_metadata_custom(self):
        """Test ExportSchemaMetadata with custom values."""
        metadata = ExportSchemaMetadata(
            schema_version="1.0.0", exported_by="test_user", total_records=5
        )

        assert metadata.schema_version == "1.0.0"
        assert metadata.exported_by == "test_user"
        assert metadata.total_records == 5


class TestSingleADRExportImport:
    """Test single ADR export/import functionality."""

    @pytest.fixture
    def sample_adr(self) -> ADR:
        """Create a sample ADR for testing."""
        return ADR.create(
            title="Test ADR for Export",
            context_and_problem="We need to test export functionality",
            decision_outcome="Implement comprehensive tests",
            consequences="Better confidence in export/import features",
            considered_options=["Option A", "Option B", "Option C"],
            author="Test Author",
            tags=["test", "export"],
            decision_drivers=["Quality", "Reliability"],
        )

    def test_export_single_versioned(self, sample_adr):
        """Test exporting a single ADR to versioned format."""
        export = ADRImportExport.export_single_versioned(
            sample_adr, exported_by="test_user"
        )

        assert isinstance(export, SingleADRExport)
        assert export.schema.schema_version == CURRENT_SCHEMA_VERSION
        assert export.schema.exported_by == "test_user"
        assert export.schema.total_records == 1

        assert export.adr.title == sample_adr.metadata.title
        assert export.adr.author == sample_adr.metadata.author
        assert export.adr.tags == sample_adr.metadata.tags
        assert export.adr.status == sample_adr.metadata.status.value

    def test_export_import_roundtrip(self, sample_adr):
        """Test that export followed by import returns equivalent ADR."""
        # Export
        export = ADRImportExport.export_single_versioned(sample_adr)
        export_dict = export.model_dump(mode="json")

        # Import
        imported_adr = ADRImportExport.import_single_versioned(export_dict)

        # Verify equivalence
        assert imported_adr.metadata.title == sample_adr.metadata.title
        assert imported_adr.metadata.author == sample_adr.metadata.author
        assert imported_adr.metadata.tags == sample_adr.metadata.tags
        assert imported_adr.metadata.status == sample_adr.metadata.status
        assert (
            imported_adr.content.context_and_problem
            == sample_adr.content.context_and_problem
        )
        assert (
            imported_adr.content.decision_outcome == sample_adr.content.decision_outcome
        )
        assert imported_adr.content.consequences == sample_adr.content.consequences
        assert (
            imported_adr.content.considered_options
            == sample_adr.content.considered_options
        )

    def test_import_with_unsupported_schema_version(self):
        """Test that import rejects unsupported schema versions."""
        invalid_data = {
            "schema": {
                "schema_version": "99.0.0",
                "exported_at": datetime.now().isoformat(),
                "total_records": 1,
            },
            "adr": {
                "id": str(uuid4()),
                "title": "Test",
                "status": "proposed",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "context_and_problem": "Context",
                "decision_outcome": "Decision",
                "consequences": "Consequences",
            },
        }

        with pytest.raises(ValueError, match="Unsupported schema version"):
            ADRImportExport.import_single_versioned(invalid_data)


class TestBulkADRExportImport:
    """Test bulk ADR export/import functionality."""

    @pytest.fixture
    def sample_adrs(self) -> List[ADR]:
        """Create multiple sample ADRs for testing."""
        return [
            ADR.create(
                title=f"Test ADR {i}",
                context_and_problem=f"Problem {i}",
                decision_outcome=f"Decision {i}",
                consequences=f"Consequences {i}",
                author="Bulk Test",
                tags=[f"tag{i}"],
            )
            for i in range(5)
        ]

    def test_export_bulk_versioned(self, sample_adrs):
        """Test exporting multiple ADRs to versioned format."""
        export = ADRImportExport.export_bulk_versioned(
            sample_adrs, exported_by="bulk_test"
        )

        assert isinstance(export, BulkADRExport)
        assert export.schema.schema_version == CURRENT_SCHEMA_VERSION
        assert export.schema.exported_by == "bulk_test"
        assert export.schema.total_records == 5
        assert len(export.adrs) == 5

        # Verify all ADRs are present
        for i, adr_export in enumerate(export.adrs):
            assert adr_export.title == f"Test ADR {i}"

    def test_bulk_export_import_roundtrip(self, sample_adrs):
        """Test bulk export followed by import."""
        # Export
        export = ADRImportExport.export_bulk_versioned(sample_adrs)
        export_dict = export.model_dump(mode="json")

        # Import
        imported_adrs = ADRImportExport.import_bulk_versioned(export_dict)

        assert len(imported_adrs) == len(sample_adrs)

        # Verify all ADRs match
        for original, imported in zip(sample_adrs, imported_adrs):
            assert imported.metadata.title == original.metadata.title
            assert (
                imported.content.context_and_problem
                == original.content.context_and_problem
            )

    def test_export_empty_list(self):
        """Test exporting an empty list of ADRs."""
        export = ADRImportExport.export_bulk_versioned([])

        assert export.schema.total_records == 0
        assert len(export.adrs) == 0


class TestLegacyFormatSupport:
    """Test legacy (non-versioned) import/export formats."""

    @pytest.fixture
    def sample_adr(self):
        """Create sample ADR."""
        return ADR.create(
            title="Test ADR",
            context_and_problem="Problem",
            decision_outcome="Decision",
            consequences="Consequences",
        )

    def test_export_adr_to_json_legacy(self, sample_adr):
        """Test exporting ADR to legacy JSON format."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.json"
            ADRImportExport.export_to_json(sample_adr, str(output_path))

            # Verify file was created and contains correct data
            assert output_path.exists()
            with open(output_path, "r") as f:
                data = json.load(f)
            assert data["metadata"]["title"] == "Test ADR"

    def test_import_adr_from_json_legacy(self, sample_adr):
        """Test importing ADR from legacy JSON format."""
        with TemporaryDirectory() as tmpdir:
            # Export to file
            output_path = Path(tmpdir) / "test.json"
            ADRImportExport.export_to_json(sample_adr, str(output_path))

            # Import from file
            imported_adr = ADRImportExport.import_from_json(str(output_path))

            assert imported_adr.metadata.title == sample_adr.metadata.title


class TestSchemaVersioning:
    """Test schema versioning and compatibility."""

    def test_current_schema_version_is_supported(self):
        """Verify current schema version is in supported list."""
        assert CURRENT_SCHEMA_VERSION in SUPPORTED_SCHEMA_VERSIONS

    def test_supported_versions_list(self):
        """Verify supported versions list structure."""
        assert isinstance(SUPPORTED_SCHEMA_VERSIONS, list)
        assert len(SUPPORTED_SCHEMA_VERSIONS) > 0
        assert all(isinstance(v, str) for v in SUPPORTED_SCHEMA_VERSIONS)

    def test_export_includes_version_metadata(self):
        """Test that exports always include version metadata."""
        adr = ADR.create(
            title="Test",
            context_and_problem="Context",
            decision_outcome="Decision",
            consequences="Consequences",
        )

        export = ADRImportExport.export_single_versioned(adr)
        export_dict = export.model_dump(mode="json")

        assert "schema" in export_dict
        assert "schema_version" in export_dict["schema"]
        assert export_dict["schema"]["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_single_export_format_has_adr_field(self):
        """Test that single exports use 'adr' field (not 'adrs')."""
        adr = ADR.create(
            title="Test Single Export",
            context_and_problem="Testing single export format",
            decision_outcome="Should have adr field",
            consequences="Format verification",
        )

        export = ADRImportExport.export_single_versioned(adr)
        export_dict = export.model_dump(mode="json")

        # Single export should have 'adr' field
        assert "adr" in export_dict
        assert "adrs" not in export_dict
        assert export_dict["adr"]["title"] == "Test Single Export"

    def test_bulk_export_format_has_adrs_field(self):
        """Test that bulk exports use 'adrs' field (not 'adr')."""
        adrs = [
            ADR.create(
                title="Test 1",
                context_and_problem="Test",
                decision_outcome="Test",
                consequences="Test",
            ),
            ADR.create(
                title="Test 2",
                context_and_problem="Test",
                decision_outcome="Test",
                consequences="Test",
            ),
        ]

        export = ADRImportExport.export_bulk_versioned(adrs)
        export_dict = export.model_dump(mode="json")

        # Bulk export should have 'adrs' field
        assert "adrs" in export_dict
        assert "adr" not in export_dict
        assert len(export_dict["adrs"]) == 2
