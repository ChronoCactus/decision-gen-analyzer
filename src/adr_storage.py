"""ADR storage and retrieval service using LightRAG."""

import json
from typing import Dict, List, Optional, Any
from uuid import UUID

from src.lightrag_client import LightRAGClient
from src.models import ADR, ADRStatus
from src.logger import get_logger

logger = get_logger(__name__)


class ADRStorageService:
    """Service for storing and retrieving ADRs using LightRAG."""

    def __init__(self, lightrag_client: Optional[LightRAGClient] = None):
        """Initialize the ADR storage service."""
        self.lightrag_client = lightrag_client

    async def store_adr(self, adr: ADR) -> str:
        """Store an ADR in LightRAG."""
        if not self.lightrag_client:
            raise RuntimeError("LightRAG client not initialized")

        # Convert ADR to searchable content
        content = self._adr_to_content(adr)
        metadata = self._adr_to_metadata(adr)

        doc_id = str(adr.metadata.id)

        try:
            result = await self.lightrag_client.store_document(
                doc_id=doc_id,
                content=content,
                metadata=metadata
            )
            logger.info("ADR stored successfully", adr_id=doc_id, title=adr.metadata.title)
            return doc_id
        except Exception as e:
            logger.error("Failed to store ADR", adr_id=doc_id, error=str(e))
            raise

    async def get_adr(self, adr_id: str) -> Optional[ADR]:
        """Retrieve an ADR by ID."""
        if not self.lightrag_client:
            raise RuntimeError("LightRAG client not initialized")

        try:
            doc = await self.lightrag_client.get_document(adr_id)
            if not doc:
                return None

            return self._document_to_adr(doc)
        except Exception as e:
            logger.error("Failed to retrieve ADR", adr_id=adr_id, error=str(e))
            raise

    async def update_adr(self, adr: ADR) -> None:
        """Update an existing ADR."""
        if not self.lightrag_client:
            raise RuntimeError("LightRAG client not initialized")

        content = self._adr_to_content(adr)
        metadata = self._adr_to_metadata(adr)
        doc_id = str(adr.metadata.id)

        try:
            await self.lightrag_client.update_document(
                doc_id=doc_id,
                content=content,
                metadata=metadata
            )
            logger.info("ADR updated successfully", adr_id=doc_id, title=adr.metadata.title)
        except Exception as e:
            logger.error("Failed to update ADR", adr_id=doc_id, error=str(e))
            raise

    async def delete_adr(self, adr_id: str) -> bool:
        """Delete an ADR."""
        if not self.lightrag_client:
            raise RuntimeError("LightRAG client not initialized")

        try:
            deleted = await self.lightrag_client.delete_document(adr_id)
            if deleted:
                logger.info("ADR deleted successfully", adr_id=adr_id)
            else:
                logger.warning("ADR not found for deletion", adr_id=adr_id)
            return deleted
        except Exception as e:
            logger.error("Failed to delete ADR", adr_id=adr_id, error=str(e))
            raise

    async def search_adrs(
        self,
        query: str,
        limit: int = 10,
        status_filter: Optional[ADRStatus] = None,
        tag_filter: Optional[List[str]] = None,
        author_filter: Optional[str] = None
    ) -> List[ADR]:
        """Search for ADRs using semantic search."""
        if not self.lightrag_client:
            raise RuntimeError("LightRAG client not initialized")

        # Build metadata filter
        metadata_filter = {}
        if status_filter:
            metadata_filter["status"] = status_filter.value
        if tag_filter:
            metadata_filter["tags"] = tag_filter
        if author_filter:
            metadata_filter["author"] = author_filter

        try:
            documents = await self.lightrag_client.retrieve_documents(
                query=query,
                limit=limit,
                metadata_filter=metadata_filter if metadata_filter else None
            )

            adrs = []
            for doc in documents:
                try:
                    adr = self._document_to_adr(doc)
                    adrs.append(adr)
                except Exception as e:
                    logger.warning("Failed to parse ADR document", doc_id=doc.get("id"), error=str(e))
                    continue

            logger.info("ADR search completed", query=query, results=len(adrs))
            return adrs

        except Exception as e:
            logger.error("Failed to search ADRs", query=query, error=str(e))
            raise

    async def find_related_adrs(self, adr: ADR, limit: int = 5) -> List[ADR]:
        """Find ADRs related to the given ADR."""
        # Create a search query from the ADR content
        query_parts = [
            adr.metadata.title,
            adr.content.context[:200],  # First 200 chars of context
            " ".join(adr.metadata.tags) if adr.metadata.tags else "",
        ]
        query = " ".join(query_parts)

        # Exclude the current ADR from results
        related_adrs = await self.search_adrs(query, limit=limit + 1)

        # Filter out the current ADR
        filtered_adrs = [a for a in related_adrs if a.metadata.id != adr.metadata.id]

        return filtered_adrs[:limit]

    def _adr_to_content(self, adr: ADR) -> str:
        """Convert ADR to searchable content string."""
        content_parts = [
            f"Title: {adr.metadata.title}",
            f"Status: {adr.metadata.status.value}",
            f"Context and Problem: {adr.content.context_and_problem}",
            f"Decision Outcome: {adr.content.decision_outcome}",
            f"Consequences: {adr.content.consequences}",
        ]

        if adr.content.considered_options:
            content_parts.append(f"Considered Options: {'; '.join(adr.content.considered_options)}")

        if adr.content.decision_drivers:
            content_parts.append(f"Decision Drivers: {'; '.join(adr.content.decision_drivers)}")

        if adr.content.confirmation:
            content_parts.append(f"Confirmation: {adr.content.confirmation}")

        if adr.content.more_information:
            content_parts.append(f"More Information: {adr.content.more_information}")

        if adr.metadata.tags:
            content_parts.append(f"Tags: {', '.join(adr.metadata.tags)}")

        if adr.metadata.author:
            content_parts.append(f"Author: {adr.metadata.author}")

        return "\n".join(content_parts)

    def _adr_to_metadata(self, adr: ADR) -> Dict[str, Any]:
        """Convert ADR metadata for storage."""
        return {
            "id": str(adr.metadata.id),
            "title": adr.metadata.title,
            "status": adr.metadata.status.value,
            "created_at": adr.metadata.created_at.isoformat(),
            "updated_at": adr.metadata.updated_at.isoformat(),
            "author": adr.metadata.author,
            "tags": adr.metadata.tags or [],
            "related_adrs": [str(adr_id) for adr_id in adr.metadata.related_adrs],
        }

    def _document_to_adr(self, document: Dict[str, Any]) -> ADR:
        """Convert stored document back to ADR object."""
        metadata = document.get("metadata", {})
        content_str = document.get("content", "")

        # Parse metadata
        from models import ADRMetadata, ADRContent

        metadata_obj = ADRMetadata(
            id=UUID(metadata["id"]),
            title=metadata["title"],
            status=ADRStatus(metadata["status"]),
            created_at=metadata["created_at"],
            updated_at=metadata["updated_at"],
            author=metadata.get("author"),
            tags=metadata.get("tags", []),
            related_adrs=[UUID(adr_id) for adr_id in metadata.get("related_adrs", [])],
        )

        # Parse content from the stored string
        # This is a simple parser - in production you might want something more robust
        content_lines = content_str.split("\n")
        context_and_problem = ""
        considered_options = []
        decision_outcome = ""
        consequences = ""
        decision_drivers = None
        confirmation = None
        more_information = None

        for line in content_lines:
            if line.startswith("Context and Problem: "):
                context_and_problem = line[21:]
            elif line.startswith("Considered Options: "):
                opt_str = line[19:]
                if opt_str:
                    considered_options = [opt.strip() for opt in opt_str.split(";")]
            elif line.startswith("Decision Outcome: "):
                decision_outcome = line[17:]
            elif line.startswith("Consequences: "):
                consequences = line[14:]
            elif line.startswith("Decision Drivers: "):
                drv_str = line[18:]
                if drv_str:
                    decision_drivers = [drv.strip() for drv in drv_str.split(";")]
            elif line.startswith("Confirmation: "):
                confirmation = line[14:]
            elif line.startswith("More Information: "):
                more_information = line[18:]

        content_obj = ADRContent(
            context_and_problem=context_and_problem,
            considered_options=considered_options,
            decision_outcome=decision_outcome,
            consequences=consequences,
            decision_drivers=decision_drivers,
            confirmation=confirmation,
            more_information=more_information,
        )

        return ADR(metadata=metadata_obj, content=content_obj)
