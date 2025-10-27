"""Client for interacting with LightRAG server."""

import asyncio
from typing import Any, Dict, List, Optional

import httpx

from config import get_settings
from logger import get_logger

logger = get_logger(__name__)


class LightRAGClient:
    """Client for LightRAG server interactions."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        backoff_factor: float = 2.0,
        demo_mode: bool = True,
    ):
        """Initialize the LightRAG client."""
        settings = get_settings()
        self.base_url = base_url or settings.lightrag_url
        self.timeout = timeout or settings.lightrag_timeout
        self.api_key = api_key if api_key is not None else settings.lightrag_api_key
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_factor = backoff_factor
        self.demo_mode = demo_mode
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        else:
            logger.warning(
                "No LightRAG API key provided; proceeding without authentication."
            )

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=headers,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def store_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Store a document in LightRAG using the /documents/text endpoint."""
        # Demo mode: simulate successful storage
        if self.demo_mode:
            logger.info("Demo mode: Simulating document storage", doc_id=doc_id)
            await asyncio.sleep(0.5)  # Simulate processing time
            return {
                "status": "success",
                "doc_id": doc_id,
                "message": "Document stored successfully (demo mode)",
            }

        if not self._client:
            raise RuntimeError("Client not initialized. Use as async context manager.")

        # Create a virtual filename for the document
        # LightRAG expects documents to have file paths for its internal tracking
        filename = f"{doc_id}.txt"

        # LightRAG expects 'text' and optional 'description' fields
        payload = {
            "text": content,
            "file_source": filename,  # Add filename to help LightRAG track the document
        }

        # Use metadata as description if available
        if metadata:
            # Create a description from metadata
            description = f"ID: {doc_id}"
            if "title" in metadata:
                description += f" | Title: {metadata['title']}"
            if "type" in metadata:
                description += f" | Type: {metadata['type']}"
            if "status" in metadata:
                description += f" | Status: {metadata['status']}"
            if "tags" in metadata and metadata["tags"]:
                description += f" | Tags: {', '.join(metadata['tags'])}"
            payload["description"] = description

        try:
            logger.info(
                "Storing document in LightRAG", doc_id=doc_id, filename=filename
            )
            # Use the correct endpoint: /documents/text
            response = await self._client.post("/documents/text", json=payload)
            response.raise_for_status()

            result = response.json()
            logger.info("Document stored successfully", doc_id=doc_id, result=result)
            return result

        except httpx.HTTPError as e:
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "doc_id": doc_id,
            }
            if hasattr(e, "response") and e.response is not None:
                error_details["status_code"] = e.response.status_code
                error_details["response_text"] = e.response.text[:500]
            logger.error("HTTP error storing document", **error_details)
            raise
        except Exception as e:
            logger.error(
                "Unexpected error storing document",
                error_type=type(e).__name__,
                error_message=str(e),
                error_repr=repr(e),
                doc_id=doc_id,
            )
            raise

    async def retrieve_documents(
        self,
        query: str,
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve documents from LightRAG based on semantic search."""
        # Demo mode: return mock related documents
        if self.demo_mode:
            logger.info(
                "Demo mode: Simulating document retrieval", query=query, limit=limit
            )
            await asyncio.sleep(1.0)  # Simulate processing time

            # Return mock related documents
            mock_docs = [
                {
                    "id": "adr-2024-001",
                    "content": "Previous decision on database architecture that might be relevant to this new requirement.",
                    "title": "Database Architecture Selection",
                    "metadata": {"type": "adr", "tags": ["database", "architecture"]},
                    "score": 0.85,
                },
                {
                    "id": "adr-2024-002",
                    "content": "Historical context about microservices adoption and its challenges.",
                    "title": "Microservices Adoption Strategy",
                    "metadata": {
                        "type": "adr",
                        "tags": ["microservices", "scalability"],
                    },
                    "score": 0.72,
                },
            ]
            return mock_docs[:limit]

        if not self._client:
            raise RuntimeError("Client not initialized. Use as async context manager.")

        # LightRAG uses /query endpoint with mode parameter
        payload = {"query": query, "mode": "hybrid"}  # Use hybrid mode for best results

        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(
                    "Retrieving documents from LightRAG",
                    query=query[:100],
                    limit=limit,
                    attempt=attempt + 1,
                    max_attempts=self.max_retries + 1,
                )
                response = await self._client.post("/query/data", json=payload)
                response.raise_for_status()

                result = response.json()

                # Parse the LightRAG response data structure
                documents = []

                # Extract data from the response
                data = result.get("data", {}) if isinstance(result, dict) else {}
                chunks = data.get("chunks", [])

                if chunks:
                    # Group chunks by file_path and deduplicate
                    chunks_by_file = {}
                    for chunk in chunks:
                        file_path = chunk.get("file_path", "unknown")
                        content = chunk.get("content", "")
                        reference_id = chunk.get("reference_id", "")

                        if file_path not in chunks_by_file:
                            chunks_by_file[file_path] = {
                                "contents": [],
                                "reference_id": reference_id,
                            }

                        if content:
                            chunks_by_file[file_path]["contents"].append(content)

                    # Create documents from deduplicated chunks
                    for file_path, chunk_data in chunks_by_file.items():
                        # Extract document ID from file_path (e.g., "/documents/adr-2024-001.txt" -> "adr-2024-001")
                        import os

                        doc_id = os.path.splitext(os.path.basename(file_path))[0]

                        # Combine all content chunks for this document
                        combined_content = "\n\n".join(chunk_data["contents"])

                        # Create a title from the doc_id
                        title = doc_id.replace("_", " ").replace("-", " ").title()

                        documents.append(
                            {
                                "id": doc_id,
                                "content": combined_content,
                                "title": title,
                                "metadata": {
                                    "type": "adr",
                                    "file_path": file_path,
                                    "reference_id": chunk_data["reference_id"],
                                },
                            }
                        )

                # If no chunks found, fall back to creating a context document from the response text
                if not documents:
                    response_text = ""
                    if isinstance(result, dict):
                        response_text = result.get("response") or result.get(
                            "answer", ""
                        )
                    elif isinstance(result, str):
                        response_text = result

                    if response_text:
                        documents.append(
                            {
                                "id": "context",
                                "content": response_text,
                                "title": "Related Context",
                                "metadata": {"type": "query_response"},
                            }
                        )

                logger.info(
                    "Documents retrieved successfully",
                    count=len(documents),
                    doc_ids=[d["id"] for d in documents],
                    attempt=attempt + 1,
                )
                return documents[:limit]

            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(
                    "Timeout during document retrieval",
                    attempt=attempt + 1,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    query=query[:100],
                )
                if attempt < self.max_retries:
                    delay = self.retry_delay * (self.backoff_factor**attempt)
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)

            except httpx.HTTPError as e:
                last_exception = e
                status_code = e.response.status_code if e.response else None
                error_details = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "attempt": attempt + 1,
                    "status_code": status_code,
                    "query": query[:100],
                }
                if hasattr(e, "response") and e.response is not None:
                    error_details["response_text"] = e.response.text[:500]
                logger.warning("HTTP error retrieving documents", **error_details)

                # Don't retry on client errors (4xx), but do retry on server errors (5xx)
                if status_code and 400 <= status_code < 500:
                    break
                if attempt < self.max_retries:
                    delay = self.retry_delay * (self.backoff_factor**attempt)
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)

            except Exception as e:
                last_exception = e
                logger.warning(
                    "Unexpected error retrieving documents",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    error_repr=repr(e),
                    attempt=attempt + 1,
                    query=query[:100],
                )
                if attempt < self.max_retries:
                    delay = self.retry_delay * (self.backoff_factor**attempt)
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(
            "All document retrieval attempts failed",
            total_attempts=self.max_retries + 1,
            final_error_type=(
                type(last_exception).__name__ if last_exception else "Unknown"
            ),
            final_error=str(last_exception) if last_exception else "Unknown error",
            query=query[:100],
        )
        raise last_exception or RuntimeError(
            "Document retrieval failed after all retries"
        )

    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific document by ID."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use as async context manager.")

        try:
            response = await self._client.get(f"/documents/{doc_id}")
            if response.status_code == 404:
                return None

            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            if e.response and e.response.status_code == 404:
                return None
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "doc_id": doc_id,
            }
            if hasattr(e, "response") and e.response is not None:
                error_details["status_code"] = e.response.status_code
                error_details["response_text"] = e.response.text[:500]
            logger.error("HTTP error getting document", **error_details)
            raise
        except Exception as e:
            logger.error(
                "Unexpected error getting document",
                error_type=type(e).__name__,
                error_message=str(e),
                error_repr=repr(e),
                doc_id=doc_id,
            )
            raise

    async def update_document(
        self,
        doc_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update an existing document."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use as async context manager.")

        payload = {}
        if content is not None:
            payload["content"] = content
        if metadata is not None:
            payload["metadata"] = metadata

        try:
            logger.info("Updating document in LightRAG", doc_id=doc_id)
            response = await self._client.put(f"/documents/{doc_id}", json=payload)
            response.raise_for_status()

            result = response.json()
            logger.info("Document updated successfully", doc_id=doc_id)
            return result

        except httpx.HTTPError as e:
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "doc_id": doc_id,
            }
            if hasattr(e, "response") and e.response is not None:
                error_details["status_code"] = e.response.status_code
                error_details["response_text"] = e.response.text[:500]
            logger.error("HTTP error updating document", **error_details)
            raise
        except Exception as e:
            logger.error(
                "Unexpected error updating document",
                error_type=type(e).__name__,
                error_message=str(e),
                error_repr=repr(e),
                doc_id=doc_id,
            )
            raise

    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document from LightRAG.

        Note: LightRAG API does not support deleting individual documents.
        The only delete endpoint is DELETE /documents which clears ALL documents.
        This method returns True to indicate it was called, but no actual deletion occurs.

        Args:
            doc_id: Document ID (not used due to API limitation)

        Returns:
            bool: Always returns True to indicate the call was processed
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use as async context manager.")

        logger.warning(
            "LightRAG does not support individual document deletion",
            doc_id=doc_id,
            note="Document remains in LightRAG index",
        )

        # Return True to indicate the call was processed (even though no deletion occurred)
        return True

    async def health_check(self) -> bool:
        """Check if the LightRAG server is healthy."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use as async context manager.")

        try:
            response = await self._client.get("/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False
