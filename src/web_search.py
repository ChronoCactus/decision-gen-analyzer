"""Web search service for collecting external data for ADR re-analysis."""

from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
import structlog

from src.config import Settings

logger = structlog.get_logger(__name__)


class SearchResult:
    """Represents a single web search result."""

    def __init__(
        self,
        title: str,
        url: str,
        snippet: str,
        domain: str,
        published_date: Optional[str] = None,
        relevance_score: float = 0.0,
    ):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.domain = domain
        self.published_date = published_date
        self.relevance_score = relevance_score

    @classmethod
    def from_serpapi_result(cls, result: Dict[str, Any]) -> "SearchResult":
        """Create SearchResult from SerpAPI response."""
        url = result.get("link", "")
        domain = urlparse(url).netloc.replace("www.", "")

        return cls(
            title=result.get("title", ""),
            url=url,
            snippet=result.get("snippet", ""),
            domain=domain,
            published_date=result.get("date"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "domain": self.domain,
            "published_date": self.published_date,
            "relevance_score": self.relevance_score,
        }


class WebSearchService:
    """Service for performing web searches using SerpAPI."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"User-Agent": "Decision-Analyzer/1.0"},
        )
        self.base_url = "https://serpapi.com/search"
        self.api_key = getattr(settings, "serpapi_key", None)

        if not self.api_key:
            logger.warning("SerpAPI key not configured - web search will be disabled")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()

    async def search(
        self,
        query: str,
        num_results: int = 10,
        time_range: Optional[str] = None,
        domain_filter: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """
        Perform web search using SerpAPI.

        Args:
            query: Search query
            num_results: Number of results to return (max 100)
            time_range: Time filter ("qdr:h" for past hour, "qdr:d" for past day, etc.)
            domain_filter: List of domains to restrict search to

        Returns:
            List of SearchResult objects
        """
        if not self.api_key:
            logger.warning("SerpAPI key not configured, returning empty results")
            return []

        try:
            params = {
                "api_key": self.api_key,
                "engine": "google",
                "q": query,
                "num": min(num_results, 100),  # SerpAPI max is 100
            }

            if time_range:
                params["tbs"] = time_range

            if domain_filter:
                # Add site: operator for domain filtering
                site_queries = [f"site:{domain}" for domain in domain_filter]
                params["q"] += " " + " OR ".join(site_queries)

            logger.info(
                "Performing web search",
                query=query,
                num_results=num_results,
                time_range=time_range,
                domain_filter=domain_filter,
            )

            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()

            data = response.json()

            results = []
            if "organic_results" in data:
                for result in data["organic_results"][:num_results]:
                    search_result = SearchResult.from_serpapi_result(result)
                    results.append(search_result)

            logger.info(
                "Web search completed",
                query=query,
                results_found=len(results),
            )

            return results

        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error during web search",
                status_code=e.response.status_code,
                response_text=e.response.text[:500],
            )
            return []
        except Exception as e:
            logger.error(
                "Unexpected error during web search",
                error=str(e),
                query=query,
            )
            return []

    async def search_related_technologies(
        self,
        technology: str,
        context: str = "",
        num_results: int = 5,
    ) -> List[SearchResult]:
        """
        Search for information about a specific technology in context.

        Args:
            technology: Technology name to search for
            context: Additional context for the search
            num_results: Number of results to return

        Returns:
            List of relevant search results
        """
        query_parts = [technology]

        if context:
            query_parts.append(context)

        # Add terms to find recent developments and alternatives
        query_parts.extend(
            [
                "alternatives",
                "comparison",
                "trends",
                "updates",
            ]
        )

        query = " ".join(query_parts)

        # Search for results from the past year
        return await self.search(
            query=query,
            num_results=num_results,
            time_range="qdr:y",  # Past year
        )

    async def search_adr_relevance(
        self,
        adr_title: str,
        adr_context: str,
        num_results: int = 5,
    ) -> List[SearchResult]:
        """
        Search for information relevant to an ADR's continued validity.

        Args:
            adr_title: Title of the ADR
            adr_context: Context/problem statement from the ADR
            num_results: Number of results to return

        Returns:
            List of potentially relevant search results
        """
        # Create a focused search query based on ADR content
        query_parts = [
            f'"{adr_title}"',
            "alternatives",
            "challenges",
            "updates",
            "best practices",
        ]

        # Add key terms from context
        context_terms = adr_context.split()[:10]  # First 10 words
        query_parts.extend(context_terms)

        query = " ".join(query_parts)

        return await self.search(
            query=query,
            num_results=num_results,
            time_range="qdr:m",  # Past month for recent developments
        )


class DataProcessingPipeline:
    """Pipeline for processing and filtering web search results."""

    def __init__(self):
        self.logger = structlog.get_logger(__name__)

    def filter_relevant_results(
        self,
        results: List[SearchResult],
        keywords: List[str],
        min_relevance_threshold: float = 0.3,
    ) -> List[SearchResult]:
        """
        Filter search results based on relevance to given keywords.

        Args:
            results: Raw search results
            keywords: Keywords to match against
            min_relevance_threshold: Minimum relevance score to include

        Returns:
            Filtered list of relevant results
        """
        filtered_results = []

        for result in results:
            relevance_score = self._calculate_relevance_score(result, keywords)

            if relevance_score >= min_relevance_threshold:
                result.relevance_score = relevance_score
                filtered_results.append(result)

        # Sort by relevance score
        filtered_results.sort(key=lambda x: x.relevance_score, reverse=True)

        self.logger.info(
            "Filtered search results",
            total_results=len(results),
            filtered_results=len(filtered_results),
            min_threshold=min_relevance_threshold,
        )

        return filtered_results

    def _calculate_relevance_score(
        self,
        result: SearchResult,
        keywords: List[str],
    ) -> float:
        """
        Calculate relevance score based on keyword matches.

        Args:
            result: Search result to score
            keywords: Keywords to match against

        Returns:
            Relevance score between 0.0 and 1.0
        """
        text = f"{result.title} {result.snippet}".lower()
        keywords_lower = [kw.lower() for kw in keywords]

        # Count keyword matches
        matches = 0
        total_keywords = len(keywords)

        for keyword in keywords_lower:
            if keyword in text:
                matches += 1

        # Base score from keyword matches
        base_score = matches / total_keywords if total_keywords > 0 else 0.0

        # Boost score for exact title matches
        title_lower = result.title.lower()
        if any(kw in title_lower for kw in keywords_lower):
            base_score += 0.3

        # Boost score for recent results (if date available)
        if result.published_date:
            try:
                # Simple heuristic: boost recent results
                published = datetime.fromisoformat(
                    result.published_date.replace("Z", "+00:00")
                )
                days_old = (datetime.now(UTC) - published).days

                if days_old < 30:
                    base_score += 0.2
                elif days_old < 90:
                    base_score += 0.1
            except (ValueError, AttributeError):
                pass

        # Cap at 1.0
        return min(base_score, 1.0)

    def extract_key_insights(
        self,
        results: List[SearchResult],
        max_insights: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Extract key insights from search results.

        Args:
            results: Filtered search results
            max_insights: Maximum number of insights to extract

        Returns:
            List of insight dictionaries
        """
        insights = []

        for result in results[:max_insights]:
            insight = {
                "title": result.title,
                "url": result.url,
                "domain": result.domain,
                "key_points": self._extract_key_points(result.snippet),
                "relevance_score": result.relevance_score,
                "published_date": result.published_date,
            }
            insights.append(insight)

        self.logger.info(
            "Extracted key insights",
            results_processed=len(results),
            insights_extracted=len(insights),
        )

        return insights

    def _extract_key_points(self, text: str) -> List[str]:
        """
        Extract key points from text snippet.

        Args:
            text: Text to analyze

        Returns:
            List of key points (sentences or phrases)
        """
        # Simple extraction: split by sentences and take first few
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        return sentences[:3]  # Return up to 3 key points
