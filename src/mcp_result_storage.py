"""
MCP Tool Result Storage

Stores MCP tool execution results on local disk for later retrieval.
Results are stored as JSON files with unique IDs.
"""

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles

from src.config import get_settings
from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StoredMCPResult:
    """A stored MCP tool result with metadata."""

    id: str
    server_id: str
    server_name: str
    tool_name: str
    arguments: Dict[str, Any]
    result: Any
    success: bool
    error: Optional[str]
    created_at: str
    adr_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "server_id": self.server_id,
            "server_name": self.server_name,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self._serialize_result(self.result),
            "success": self.success,
            "error": self.error,
            "created_at": self.created_at,
            "adr_id": self.adr_id,
        }

    @staticmethod
    def _serialize_result(result: Any) -> Any:
        """Serialize tool result for JSON storage."""
        if result is None:
            return None

        # Handle FastMCP CallToolResult
        if hasattr(result, "content"):
            content_parts = []
            for item in result.content:
                if hasattr(item, "text"):
                    content_parts.append({"type": "text", "text": item.text})
                elif hasattr(item, "data"):
                    content_parts.append({"type": "data", "data": str(item.data)})
                else:
                    content_parts.append({"type": "unknown", "value": str(item)})
            return {"content": content_parts}

        # Handle dict/list results directly
        if isinstance(result, (dict, list, str, int, float, bool)):
            return result

        # Fallback to string representation
        return str(result)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoredMCPResult":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            server_id=data["server_id"],
            server_name=data["server_name"],
            tool_name=data["tool_name"],
            arguments=data.get("arguments", {}),
            result=data.get("result"),
            success=data.get("success", True),
            error=data.get("error"),
            created_at=data.get("created_at", ""),
            adr_id=data.get("adr_id"),
        )


class MCPResultStorage:
    """Storage for MCP tool execution results."""

    def __init__(self, storage_dir: Optional[str] = None):
        """Initialize storage.

        Args:
            storage_dir: Directory to store results. Defaults to data/mcp_results.
        """
        settings = get_settings()
        base_dir = getattr(settings, "DATA_DIR", "data")
        self.storage_dir = Path(storage_dir or os.path.join(base_dir, "mcp_results"))
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure storage directory exists."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_result_path(self, result_id: str) -> Path:
        """Get path to result file."""
        return self.storage_dir / f"{result_id}.json"

    async def save(
        self,
        server_id: str,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        success: bool,
        error: Optional[str] = None,
        adr_id: Optional[str] = None,
    ) -> StoredMCPResult:
        """Save a tool result to storage.

        Args:
            server_id: MCP server ID
            server_name: MCP server name (for display)
            tool_name: Name of the tool that was called
            arguments: Arguments passed to the tool
            result: Raw result from the tool
            success: Whether the tool call succeeded
            error: Error message if failed
            adr_id: Optional ADR ID this result is associated with

        Returns:
            StoredMCPResult with generated ID
        """
        result_id = str(uuid.uuid4())
        stored = StoredMCPResult(
            id=result_id,
            server_id=server_id,
            server_name=server_name,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            success=success,
            error=error,
            created_at=datetime.utcnow().isoformat(),
            adr_id=adr_id,
        )

        path = self._get_result_path(result_id)
        try:
            async with aiofiles.open(path, "w") as f:
                await f.write(json.dumps(stored.to_dict(), indent=2, default=str))
            logger.info(f"Saved MCP result {result_id} for {server_name}/{tool_name}")
        except Exception as e:
            logger.error(f"Failed to save MCP result: {e}")
            raise

        return stored

    async def get(self, result_id: str) -> Optional[StoredMCPResult]:
        """Retrieve a stored result by ID.

        Args:
            result_id: ID of the result to retrieve

        Returns:
            StoredMCPResult or None if not found
        """
        path = self._get_result_path(result_id)
        if not path.exists():
            logger.warning(f"MCP result {result_id} not found")
            return None

        try:
            async with aiofiles.open(path, "r") as f:
                data = json.loads(await f.read())
            return StoredMCPResult.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to read MCP result {result_id}: {e}")
            return None

    async def get_raw_json(self, result_id: str) -> Optional[Dict[str, Any]]:
        """Get the raw JSON for a stored result.

        Args:
            result_id: ID of the result

        Returns:
            Raw dict data or None if not found
        """
        path = self._get_result_path(result_id)
        if not path.exists():
            return None

        try:
            async with aiofiles.open(path, "r") as f:
                return json.loads(await f.read())
        except Exception as e:
            logger.error(f"Failed to read MCP result {result_id}: {e}")
            return None

    async def list_for_adr(self, adr_id: str) -> List[StoredMCPResult]:
        """List all results associated with an ADR.

        Args:
            adr_id: ADR ID to filter by

        Returns:
            List of stored results
        """
        results = []
        for path in self.storage_dir.glob("*.json"):
            try:
                async with aiofiles.open(path, "r") as f:
                    data = json.loads(await f.read())
                if data.get("adr_id") == adr_id:
                    results.append(StoredMCPResult.from_dict(data))
            except Exception as e:
                logger.warning(f"Failed to read {path}: {e}")
        return results

    async def delete(self, result_id: str) -> bool:
        """Delete a stored result.

        Args:
            result_id: ID of the result to delete

        Returns:
            True if deleted, False if not found
        """
        path = self._get_result_path(result_id)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted MCP result {result_id}")
            return True
        return False


# Singleton instance
_mcp_result_storage: Optional[MCPResultStorage] = None


def get_mcp_result_storage() -> MCPResultStorage:
    """Get the singleton MCP result storage instance."""
    global _mcp_result_storage
    if _mcp_result_storage is None:
        _mcp_result_storage = MCPResultStorage()
    return _mcp_result_storage
