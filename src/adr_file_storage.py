"""File-based storage for ADRs."""

import json
import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from src.models import ADR, ADRMetadata, ADRContent, ADRStatus
from src.logger import get_logger

logger = get_logger(__name__)


class ADRFileStorage:
    """Simple file-based storage for ADRs."""

    def __init__(self, storage_path: Optional[str] = None):
        """Initialize the file storage.
        
        Args:
            storage_path: Path to store ADR files. Defaults to /app/data/adrs
        """
        if storage_path is None:
            from src.config import get_settings

            settings = get_settings()
            storage_path = settings.adr_storage_path

        self.storage_path = Path(storage_path)
        self._ensure_storage_exists()

    def _ensure_storage_exists(self):
        """Ensure the storage directory exists."""
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"ADR storage initialized at {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to create storage directory: {e}")
            raise

    def _get_adr_file_path(self, adr_id: str) -> Path:
        """Get the file path for an ADR.
        
        Args:
            adr_id: The ADR ID
            
        Returns:
            Path to the ADR file
        """
        return self.storage_path / f"{adr_id}.json"

    def save_adr(self, adr: ADR) -> None:
        """Save an ADR to file storage.
        
        Args:
            adr: The ADR to save
        """
        try:
            file_path = self._get_adr_file_path(str(adr.metadata.id))

            # Convert ADR to dict for JSON serialization
            adr_dict = adr.model_dump(mode='json')

            with open(file_path, 'w') as f:
                json.dump(adr_dict, f, indent=2)

            logger.info(f"Saved ADR {adr.metadata.id} to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save ADR {adr.metadata.id}: {e}")
            raise

    def get_adr(self, adr_id: str) -> Optional[ADR]:
        """Retrieve an ADR by ID.
        
        Args:
            adr_id: The ADR ID
            
        Returns:
            The ADR if found, None otherwise
        """
        try:
            file_path = self._get_adr_file_path(adr_id)

            if not file_path.exists():
                return None

            with open(file_path, 'r') as f:
                adr_dict = json.load(f)

            return ADR(**adr_dict)
        except Exception as e:
            logger.error(f"Failed to load ADR {adr_id}: {e}")
            return None

    def list_adrs(self, limit: int = 50, offset: int = 0) -> tuple[List[ADR], int]:
        """List all ADRs with pagination.
        
        Args:
            limit: Maximum number of ADRs to return
            offset: Number of ADRs to skip
            
        Returns:
            Tuple of (list of ADRs, total count)
        """
        try:
            # Get all JSON files
            adr_files = sorted(
                self.storage_path.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True  # Most recent first
            )

            total = len(adr_files)

            # Apply pagination
            paginated_files = adr_files[offset:offset + limit]

            # Load ADRs
            adrs = []
            for file_path in paginated_files:
                try:
                    with open(file_path, 'r') as f:
                        adr_dict = json.load(f)
                    adrs.append(ADR(**adr_dict))
                except Exception as e:
                    logger.warning(f"Failed to load ADR from {file_path}: {e}")
                    continue

            return adrs, total
        except Exception as e:
            logger.error(f"Failed to list ADRs: {e}")
            return [], 0

    def delete_adr(self, adr_id: str) -> bool:
        """Delete an ADR by ID.
        
        Args:
            adr_id: The ADR ID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            file_path = self._get_adr_file_path(adr_id)

            if not file_path.exists():
                return False

            file_path.unlink()
            logger.info(f"Deleted ADR {adr_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete ADR {adr_id}: {e}")
            return False

    def adr_exists(self, adr_id: str) -> bool:
        """Check if an ADR exists.
        
        Args:
            adr_id: The ADR ID
            
        Returns:
            True if exists, False otherwise
        """
        return self._get_adr_file_path(adr_id).exists()


# Global storage instance
_storage_instance = None


def get_adr_storage() -> ADRFileStorage:
    """Get the global ADR storage instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = ADRFileStorage()
    return _storage_instance
