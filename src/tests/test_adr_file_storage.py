"""Tests for ADR file storage."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest

from src.adr_file_storage import ADRFileStorage
from src.models import ADR


class TestADRFileStorage:
    """Test ADRFileStorage class."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create a temporary storage directory."""
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_adr(self):
        """Create a sample ADR for testing."""
        return ADR.create(
            title="Test ADR",
            context_and_problem="Test problem",
            decision_outcome="Test decision",
            consequences="Test consequences",
            author="Test Author",
        )

    def test_storage_initialization(self, temp_storage_dir):
        """Test storage initialization."""
        storage = ADRFileStorage(storage_path=str(temp_storage_dir))

        assert storage.storage_path == temp_storage_dir
        assert temp_storage_dir.exists()

    def test_storage_creates_directory_if_not_exists(self):
        """Test storage creates directory."""
        with TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "adrs"

            ADRFileStorage(storage_path=str(storage_path))

            assert storage_path.exists()

    def test_save_adr(self, temp_storage_dir, sample_adr):
        """Test saving an ADR."""
        storage = ADRFileStorage(storage_path=str(temp_storage_dir))

        storage.save_adr(sample_adr)

        # Check file was created
        file_path = temp_storage_dir / f"{sample_adr.metadata.id}.json"
        assert file_path.exists()

        # Check content
        with open(file_path, "r") as f:
            data = json.load(f)
        assert data["metadata"]["title"] == "Test ADR"

    def test_load_adr(self, temp_storage_dir, sample_adr):
        """Test loading an ADR."""
        storage = ADRFileStorage(storage_path=str(temp_storage_dir))

        # Save first
        storage.save_adr(sample_adr)

        # Load
        loaded_adr = storage.get_adr(str(sample_adr.metadata.id))

        assert loaded_adr.metadata.title == sample_adr.metadata.title
        assert loaded_adr.metadata.id == sample_adr.metadata.id

    def test_load_nonexistent_adr_returns_none(self, temp_storage_dir):
        """Test loading non-existent ADR returns None."""
        storage = ADRFileStorage(storage_path=str(temp_storage_dir))

        result = storage.get_adr(str(uuid4()))

        assert result is None

    def test_delete_adr(self, temp_storage_dir, sample_adr):
        """Test deleting an ADR."""
        storage = ADRFileStorage(storage_path=str(temp_storage_dir))

        # Save first
        storage.save_adr(sample_adr)

        # Delete
        success = storage.delete_adr(str(sample_adr.metadata.id))

        assert success is True

        # Verify file is gone
        file_path = temp_storage_dir / f"{sample_adr.metadata.id}.json"
        assert not file_path.exists()

    def test_delete_nonexistent_adr(self, temp_storage_dir):
        """Test deleting non-existent ADR."""
        storage = ADRFileStorage(storage_path=str(temp_storage_dir))

        success = storage.delete_adr(str(uuid4()))

        assert success is False

    def test_list_all_adrs(self, temp_storage_dir):
        """Test listing all ADRs."""
        storage = ADRFileStorage(storage_path=str(temp_storage_dir))

        # Save multiple ADRs
        adrs = [
            ADR.create(
                title=f"ADR {i}",
                context_and_problem="Problem",
                decision_outcome="Decision",
                consequences="Consequences",
            )
            for i in range(3)
        ]

        for adr in adrs:
            storage.save_adr(adr)

        # List
        all_adrs, total = storage.list_adrs()

        assert len(all_adrs) == 3
        assert total == 3
        assert all(isinstance(adr, ADR) for adr in all_adrs)

    def test_list_empty_directory(self, temp_storage_dir):
        """Test listing ADRs in empty directory."""
        storage = ADRFileStorage(storage_path=str(temp_storage_dir))

        all_adrs, total = storage.list_adrs()

        assert len(all_adrs) == 0
        assert total == 0

    def test_exists(self, temp_storage_dir, sample_adr):
        """Test checking if ADR exists."""
        storage = ADRFileStorage(storage_path=str(temp_storage_dir))

        # Check before saving
        assert storage.adr_exists(str(sample_adr.metadata.id)) is False

        # Save
        storage.save_adr(sample_adr)

        # Check after saving
        assert storage.adr_exists(str(sample_adr.metadata.id)) is True

    def test_update_adr(self, temp_storage_dir, sample_adr):
        """Test updating an existing ADR."""
        storage = ADRFileStorage(storage_path=str(temp_storage_dir))

        # Save original
        storage.save_adr(sample_adr)

        # Update
        sample_adr.update_content(decision_outcome="Updated decision")
        storage.save_adr(sample_adr)

        # Load and verify
        loaded = storage.get_adr(str(sample_adr.metadata.id))
        assert loaded.content.decision_outcome == "Updated decision"
