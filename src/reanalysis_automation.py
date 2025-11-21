"""Re-analysis automation for periodic ADR review based on new data."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import structlog

from src.adr_contextual_analysis import ContextualAnalysisService
from src.config import Settings
from src.models import ADR
from src.web_search import DataProcessingPipeline, SearchResult, WebSearchService

logger = structlog.get_logger(__name__)


class ChangeDetectionResult:
    """Result of change detection analysis."""

    def __init__(
        self,
        adr_id: str,
        change_type: str,
        confidence: float,
        evidence: List[str],
        recommendations: List[str],
        detected_at: Optional[datetime] = None,
    ):
        self.adr_id = adr_id
        self.change_type = change_type
        self.confidence = confidence
        self.evidence = evidence
        self.recommendations = recommendations
        self.detected_at = detected_at or datetime.now(UTC)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "adr_id": self.adr_id,
            "change_type": self.change_type,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "recommendations": self.recommendations,
            "detected_at": self.detected_at.isoformat(),
        }


class ReanalysisAutomationService:
    """Service for automating ADR re-analysis based on new external data."""

    def __init__(
        self,
        settings: Settings,
        web_search_service: WebSearchService,
        contextual_analysis_service: ContextualAnalysisService,
    ):
        self.settings = settings
        self.web_search = web_search_service
        self.contextual_analysis = contextual_analysis_service
        self.data_pipeline = DataProcessingPipeline()
        self.logger = structlog.get_logger(__name__)

        # Track last analysis times and results
        self.last_analysis: Dict[str, datetime] = {}
        self.change_history: Dict[str, List[ChangeDetectionResult]] = {}

    async def analyze_adr_for_changes(
        self,
        adr: ADR,
        force_refresh: bool = False,
    ) -> Optional[ChangeDetectionResult]:
        """
        Analyze a single ADR for potential changes based on new external data.

        Args:
            adr: The ADR to analyze
            force_refresh: Force re-analysis even if recently done

        Returns:
            ChangeDetectionResult if changes detected, None otherwise
        """
        adr_id = str(adr.metadata.id)

        # Check if we should skip recent analysis
        if not force_refresh:
            last_analyzed = self.last_analysis.get(adr_id)
            if last_analyzed and (datetime.now(UTC) - last_analyzed) < timedelta(
                days=7
            ):
                self.logger.debug(
                    "Skipping recent ADR analysis",
                    adr_id=adr_id,
                    last_analyzed=last_analyzed.isoformat(),
                )
                return None

        try:
            self.logger.info(
                "Starting ADR change detection analysis",
                adr_id=adr_id,
                title=adr.metadata.title,
            )

            # Search for relevant external data
            search_results = await self._gather_external_data(adr)

            if not search_results:
                self.logger.info(
                    "No external data found for ADR",
                    adr_id=adr_id,
                )
                return None

            # Process and filter search results
            relevant_results = self._filter_relevant_data(adr, search_results)

            if not relevant_results:
                self.logger.info(
                    "No relevant external data found for ADR",
                    adr_id=adr_id,
                )
                return None

            # Analyze for changes
            change_result = await self._detect_changes(adr, relevant_results)

            # Update tracking
            self.last_analysis[adr_id] = datetime.now(UTC)

            if change_result:
                # Store change history
                if adr_id not in self.change_history:
                    self.change_history[adr_id] = []
                self.change_history[adr_id].append(change_result)

                self.logger.info(
                    "Change detected in ADR",
                    adr_id=adr_id,
                    change_type=change_result.change_type,
                    confidence=change_result.confidence,
                )

            return change_result

        except Exception as e:
            self.logger.error(
                "Error during ADR change detection",
                adr_id=adr_id,
                error=str(e),
            )
            return None

    async def _gather_external_data(self, adr: ADR) -> List[SearchResult]:
        """Gather external data relevant to the ADR."""
        # Extract key terms from ADR for search
        search_terms = self._extract_search_terms(adr)

        all_results = []

        # Search for each key term
        for term in search_terms[:3]:  # Limit to top 3 terms
            try:
                results = await self.web_search.search_adr_relevance(
                    adr_title=adr.metadata.title,
                    adr_context=term,
                    num_results=5,
                )
                all_results.extend(results)
            except Exception as e:
                self.logger.warning(
                    "Failed to search for term",
                    term=term,
                    error=str(e),
                )

        # Remove duplicates based on URL
        unique_results = []
        seen_urls = set()
        for result in all_results:
            if result.url not in seen_urls:
                unique_results.append(result)
                seen_urls.add(result.url)

        self.logger.debug(
            "Gathered external data",
            adr_id=str(adr.metadata.id),
            search_terms=len(search_terms),
            results_found=len(unique_results),
        )

        return unique_results

    def _extract_search_terms(self, adr: ADR) -> List[str]:
        """Extract key search terms from ADR content."""
        terms = []

        # Add title terms
        title_words = [w for w in adr.metadata.title.split() if len(w) > 3]
        terms.extend(title_words)

        # Add tags
        terms.extend(adr.metadata.tags)

        # Add key terms from context
        context_words = adr.content.context_and_problem.split()
        # Filter for meaningful terms (length > 4, not common words)
        common_words = {
            "that",
            "with",
            "have",
            "this",
            "will",
            "your",
            "from",
            "they",
            "know",
            "want",
            "been",
            "good",
            "much",
            "some",
            "time",
            "very",
            "when",
            "come",
            "here",
            "just",
            "like",
            "long",
            "make",
            "many",
            "over",
            "such",
            "take",
            "than",
            "them",
            "well",
            "were",
        }
        meaningful_words = [
            word
            for word in context_words
            if len(word) > 4 and word.lower() not in common_words
        ]
        terms.extend(meaningful_words[:10])  # Top 10 meaningful words

        # Add decision outcome terms
        decision_words = [
            word for word in adr.content.decision_outcome.split() if len(word) > 3
        ]
        terms.extend(decision_words[:5])

        # Remove duplicates and return unique terms
        return list(set(terms))

    def _filter_relevant_data(
        self,
        adr: ADR,
        search_results: List[SearchResult],
    ) -> List[SearchResult]:
        """Filter search results for relevance to the ADR."""
        # Extract keywords from ADR
        keywords = self._extract_search_terms(adr)

        # Use data processing pipeline to filter
        relevant_results = self.data_pipeline.filter_relevant_results(
            results=search_results,
            keywords=keywords,
            min_relevance_threshold=0.4,  # Require 40% relevance
        )

        return relevant_results

    async def _detect_changes(
        self,
        adr: ADR,
        relevant_data: List[SearchResult],
    ) -> Optional[ChangeDetectionResult]:
        """Detect potential changes in ADR validity based on external data."""
        # Extract insights from relevant data
        insights = self.data_pipeline.extract_key_insights(
            relevant_data, max_insights=10
        )

        if not insights:
            return None

        # Analyze insights for change indicators
        change_indicators = self._analyze_change_indicators(adr, insights)

        if not change_indicators:
            return None

        # Determine most significant change
        top_change = max(change_indicators, key=lambda x: x[1])  # Sort by confidence

        change_type, confidence, evidence, recommendations = top_change

        if confidence < 0.5:  # Minimum confidence threshold
            return None

        return ChangeDetectionResult(
            adr_id=str(adr.metadata.id),
            change_type=change_type,
            confidence=confidence,
            evidence=evidence,
            recommendations=recommendations,
        )

    def _analyze_change_indicators(
        self,
        adr: ADR,
        insights: List[Dict[str, Any]],
    ) -> List[Tuple[str, float, List[str], List[str]]]:
        """Analyze insights for indicators of ADR changes."""
        change_indicators = []

        # Keywords that might indicate changes
        change_keywords = {
            "deprecated": [
                "deprecated",
                "obsolete",
                "replaced",
                "superseded",
                "legacy",
            ],
            "alternative_better": [
                "better alternative",
                "superior option",
                "recommended instead",
                "prefer",
            ],
            "security_issue": [
                "security vulnerability",
                "security risk",
                "breach",
                "exploit",
            ],
            "performance_issue": [
                "performance problem",
                "slow",
                "bottleneck",
                "inefficient",
            ],
            "new_feature": ["new feature", "enhancement", "improvement", "update"],
            "cost_issue": [
                "expensive",
                "cost increase",
                "budget impact",
                "cheaper alternative",
            ],
        }

        for insight in insights:
            text = f"{insight['title']} {' '.join(insight['key_points'])}".lower()

            for change_type, keywords in change_keywords.items():
                matches = [kw for kw in keywords if kw in text]
                if matches:
                    confidence = min(
                        len(matches) * 0.2, 0.8
                    )  # Scale confidence by matches

                    # Adjust confidence based on recency
                    if insight.get("published_date"):
                        try:
                            published = datetime.fromisoformat(
                                insight["published_date"].replace("Z", "+00:00")
                            )
                            days_old = (datetime.now(UTC) - published).days
                            if days_old < 30:
                                confidence += 0.1
                            elif days_old > 365:
                                confidence -= 0.2
                        except (ValueError, AttributeError):
                            pass

                    evidence = [
                        f"Found in: {insight['title']}",
                        f"Source: {insight['domain']}",
                        f"Key points: {'; '.join(insight['key_points'])}",
                    ]

                    recommendations = self._generate_recommendations(change_type, adr)

                    change_indicators.append(
                        (
                            change_type,
                            confidence,
                            evidence,
                            recommendations,
                        )
                    )

        return change_indicators

    def _generate_recommendations(
        self,
        change_type: str,
        adr: ADR,
    ) -> List[str]:
        """Generate recommendations based on change type."""
        base_recommendations = [
            "Review ADR in current context",
            "Consider updating decision drivers",
            "Evaluate impact on dependent systems",
        ]

        type_specific = {
            "deprecated": [
                "Assess migration path to alternative solution",
                "Plan decommissioning timeline",
                "Identify replacement technology",
            ],
            "alternative_better": [
                "Compare current solution with new alternatives",
                "Evaluate migration costs and benefits",
                "Consider pilot implementation",
            ],
            "security_issue": [
                "Conduct security assessment",
                "Implement mitigation measures",
                "Review compliance requirements",
            ],
            "performance_issue": [
                "Monitor current performance metrics",
                "Identify performance bottlenecks",
                "Consider optimization or replacement",
            ],
            "new_feature": [
                "Evaluate feature fit with current architecture",
                "Assess integration complexity",
                "Consider enhancement opportunities",
            ],
            "cost_issue": [
                "Review current cost structure",
                "Compare with alternative solutions",
                "Assess ROI of potential changes",
            ],
        }

        recommendations = base_recommendations + type_specific.get(change_type, [])
        return recommendations

    async def run_periodic_reanalysis(
        self,
        adr_list: List[ADR],
        max_concurrent: int = 3,
    ) -> Dict[str, Any]:
        """
        Run periodic re-analysis on a list of ADRs.

        Args:
            adr_list: List of ADRs to analyze
            max_concurrent: Maximum concurrent analyses

        Returns:
            Summary of re-analysis results
        """
        self.logger.info(
            "Starting periodic ADR re-analysis",
            adr_count=len(adr_list),
            max_concurrent=max_concurrent,
        )

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_semaphore(adr: ADR) -> Optional[ChangeDetectionResult]:
            async with semaphore:
                return await self.analyze_adr_for_changes(adr)

        # Run analyses concurrently
        tasks = [analyze_with_semaphore(adr) for adr in adr_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        changes_detected = []
        errors = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append(f"ADR {i}: {str(result)}")
            elif result:
                changes_detected.append(result)

        summary = {
            "total_adrs": len(adr_list),
            "changes_detected": len(changes_detected),
            "errors": len(errors),
            "error_details": errors,
            "changes": [change.to_dict() for change in changes_detected],
            "completed_at": datetime.now(UTC).isoformat(),
        }

        self.logger.info(
            "Periodic re-analysis completed",
            **summary,
        )

        return summary

    def get_change_history(self, adr_id: str) -> List[ChangeDetectionResult]:
        """Get change history for an ADR."""
        return self.change_history.get(adr_id, [])

    def get_analysis_stats(self) -> Dict[str, Any]:
        """Get statistics about re-analysis activities."""
        total_changes = sum(len(changes) for changes in self.change_history.values())
        adrs_with_changes = len(self.change_history)

        change_types = {}
        for changes in self.change_history.values():
            for change in changes:
                change_types[change.change_type] = (
                    change_types.get(change.change_type, 0) + 1
                )

        return {
            "total_adrs_analyzed": len(self.last_analysis),
            "adrs_with_changes": adrs_with_changes,
            "total_changes_detected": total_changes,
            "change_types": change_types,
            "last_analysis_times": {
                adr_id: timestamp.isoformat()
                for adr_id, timestamp in self.last_analysis.items()
            },
        }
