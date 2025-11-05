"""Contextual ADR Analysis Service for analyzing ADRs in context of related decisions."""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC
import json

from src.models import (
    ADR,
    ADRAnalysisResult,
    ADRMetadata,
    ADRContent,
    ADRStatus,
    AnalysisReport,
    ContextualAnalysisResult,
    ADRConflict,
    ConflictType,
    ContinuityAssessment,
    ReassessmentRecommendation,
)
from llama_client import LlamaCppClient
from lightrag_client import LightRAGClient
from persona_manager import PersonaManager
from adr_validation import ADRAnalysisService
from logger import get_logger

logger = get_logger(__name__)


class ContextualAnalysisService:
    """Service for analyzing ADRs in the context of related decisions."""

    def __init__(
        self,
        llama_client: LlamaCppClient,
        lightrag_client: LightRAGClient,
        persona_manager: PersonaManager,
        analysis_service: ADRAnalysisService
    ):
        """Initialize the contextual analysis service.

        Args:
            llama_client: Client for LLM interactions
            lightrag_client: Client for vector database retrieval
            persona_manager: Manager for persona configurations
            analysis_service: Service for individual ADR analysis
        """
        self.llama_client = llama_client
        self.lightrag_client = lightrag_client
        self.persona_manager = persona_manager
        self.analysis_service = analysis_service

    async def analyze_adr_contextually(
        self,
        target_adr: ADR,
        personas: Optional[List[str]] = None,
        include_related_analysis: bool = True,
    ) -> ContextualAnalysisResult:
        """Perform comprehensive contextual analysis of an ADR.

        Args:
            target_adr: The ADR to analyze
            personas: List of persona values to involve in the analysis
            include_related_analysis: Whether to analyze related ADRs

        Returns:
            ContextualAnalysisResult: Complete analysis results
        """
        logger.info(
            "Starting contextual ADR analysis",
            adr_id=str(target_adr.metadata.id),
            title=target_adr.metadata.title,
            personas=personas or [],
        )

        start_time = datetime.now(UTC)

        # Default personas if none specified
        if not personas:
            personas = ["technical_lead", "architect", "risk_manager"]

        # Find related ADRs
        related_adrs = await self._find_related_adrs(target_adr)

        # Analyze target ADR with multiple personas
        persona_analyses = {}
        if include_related_analysis:
            for persona in personas:
                try:
                    analysis = await self.analysis_service.analyze_adr(
                        target_adr,
                        persona,
                        include_context=True
                    )
                    persona_analyses[persona.value] = analysis
                except Exception as e:
                    logger.warning(
                        "Failed to analyze ADR with persona",
                        persona=persona.value,
                        error=str(e)
                    )

        # Detect conflicts
        conflicts = await self._detect_conflicts(target_adr, related_adrs)

        # Assess continuity
        continuity_assessment = await self._assess_continuity(target_adr, related_adrs, persona_analyses)

        # Generate re-assessment recommendations
        reassessment_recommendations = await self._generate_reassessment_recommendations(
            target_adr, conflicts, continuity_assessment, persona_analyses
        )

        # Generate overall assessment
        overall_assessment = await self._generate_overall_assessment(
            target_adr, conflicts, continuity_assessment, persona_analyses
        )

        # Extract key findings and action items
        key_findings = self._extract_key_findings(conflicts, continuity_assessment, persona_analyses)
        action_items = self._extract_action_items(conflicts, reassessment_recommendations)

        analysis_duration = (datetime.now(UTC) - start_time).total_seconds()

        result = ContextualAnalysisResult(
            target_adr=target_adr,
            related_adrs=related_adrs,
            conflicts=conflicts,
            continuity_assessment=continuity_assessment,
            reassessment_recommendations=reassessment_recommendations,
            persona_analyses=persona_analyses,
            overall_assessment=overall_assessment,
            key_findings=key_findings,
            action_items=action_items,
            analyzed_at=datetime.now(UTC),
            analysis_duration=analysis_duration
        )

        logger.info(
            "Contextual ADR analysis completed",
            adr_id=str(target_adr.metadata.id),
            conflicts_found=len(conflicts),
            recommendations=len(reassessment_recommendations),
            duration=analysis_duration
        )

        return result

    async def _find_related_adrs(self, target_adr: ADR) -> List[ADR]:
        """Find ADRs related to the target ADR.

        Args:
            target_adr: The ADR to find relations for

        Returns:
            List of related ADRs
        """
        related_adrs = []

        try:
            # Create search query from ADR content
            search_terms = [
                target_adr.metadata.title,
                target_adr.content.context_and_problem,
                target_adr.content.decision_outcome
            ]
            if target_adr.metadata.tags:
                search_terms.extend(target_adr.metadata.tags)

            search_query = " ".join(search_terms)

            # Query vector database for related content
            async with self.lightrag_client:
                context_results = await self.lightrag_client.query(
                    query=search_query,
                    top_k=10
                )

            # For demo purposes, we'll create mock related ADRs based on the context
            # In production, this would retrieve actual ADRs from storage
            if context_results.get("data"):
                # Create mock related ADRs from search results
                for i, result in enumerate(context_results["data"][:3]):
                    mock_adr = ADR.create(
                        title=f"Related Decision {i+1}: {result.get('content', '')[:50]}...",
                        context_and_problem=result.get('content', ''),
                        decision_outcome=f"Decision related to {target_adr.metadata.title}",
                        consequences="Related consequences",
                        author="System",
                        tags=["related"]
                    )
                    related_adrs.append(mock_adr)

        except Exception as e:
            logger.warning(
                "Failed to find related ADRs",
                error=str(e)
            )

        return related_adrs

    async def _detect_conflicts(self, target_adr: ADR, related_adrs: List[ADR]) -> List[ADRConflict]:
        """Detect conflicts between the target ADR and related ADRs.

        Args:
            target_adr: The ADR being analyzed
            related_adrs: Related ADRs to check for conflicts

        Returns:
            List of detected conflicts
        """
        conflicts = []

        for related_adr in related_adrs:
            try:
                # Analyze potential conflicts using LLM
                conflict_analysis = await self._analyze_potential_conflict(target_adr, related_adr)

                if conflict_analysis.get("has_conflict", False):
                    conflict = ADRConflict(
                        conflict_type=ConflictType(conflict_analysis.get("conflict_type", "overlapping_scope")),
                        primary_adr_id=target_adr.metadata.id,
                        conflicting_adr_id=related_adr.metadata.id,
                        description=conflict_analysis.get("description", "Potential conflict detected"),
                        severity=conflict_analysis.get("severity", "medium"),
                        impact_areas=conflict_analysis.get("impact_areas", []),
                        resolution_suggestions=conflict_analysis.get("resolution_suggestions", [])
                    )
                    conflicts.append(conflict)

            except Exception as e:
                logger.warning(
                    "Failed to analyze conflict between ADRs",
                    target_id=str(target_adr.metadata.id),
                    related_id=str(related_adr.metadata.id),
                    error=str(e)
                )

        return conflicts

    async def _analyze_potential_conflict(self, adr1: ADR, adr2: ADR) -> Dict[str, Any]:
        """Analyze if two ADRs have conflicts.

        Args:
            adr1: First ADR
            adr2: Second ADR

        Returns:
            Conflict analysis results
        """
        prompt = f"""Analyze if these two Architectural Decision Records have conflicts or contradictions.

ADR 1:
Title: {adr1.metadata.title}
Context: {adr1.content.context_and_problem}
Decision: {adr1.content.decision_outcome}
Consequences: {adr1.content.consequences}

ADR 2:
Title: {adr2.metadata.title}
Context: {adr2.content.context_and_problem}
Decision: {adr2.content.decision_outcome}
Consequences: {adr2.content.consequences}

Respond with a JSON object containing:
{{
  "has_conflict": true/false,
  "conflict_type": "contradictory_decisions|overlapping_scope|inconsistent_assumptions|competing_technologies|resource_conflicts",
  "description": "Brief description of the conflict",
  "severity": "low|medium|high|critical",
  "impact_areas": ["list", "of", "affected", "areas"],
  "resolution_suggestions": ["list", "of", "resolution", "suggestions"]
}}

If no conflict, set has_conflict to false and provide minimal other details."""

        try:
            async with self.llama_client:
                response = await self.llama_client.generate(
                    prompt=prompt,
                    json_mode=True,
                    temperature=0.3,
                    max_tokens=1000
                )

            # Parse JSON response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                return {"has_conflict": False}

        except Exception as e:
            logger.warning("Failed to analyze conflict", error=str(e))
            return {"has_conflict": False}

    async def _assess_continuity(self, target_adr: ADR, related_adrs: List[ADR],
                                persona_analyses: Dict[str, ADRAnalysisResult]) -> ContinuityAssessment:
        """Assess the continuity of the target ADR with related decisions.

        Args:
            target_adr: The ADR being assessed
            related_adrs: Related ADRs
            persona_analyses: Analysis results from different personas

        Returns:
            ContinuityAssessment: Assessment results
        """
        # Calculate alignment score based on related ADRs
        alignment_score = 0.8  # Default good alignment
        if related_adrs:
            alignment_score = min(1.0, 0.5 + (len(related_adrs) * 0.1))

        # Calculate consistency score from persona analyses
        consistency_score = 0.7  # Default reasonable consistency
        if persona_analyses:
            scores = [analysis.score for analysis in persona_analyses.values() if analysis.score]
            if scores:
                consistency_score = sum(scores) / len(scores) / 10.0  # Convert to 0-1 scale

        # Calculate evolution score (simplified)
        evolution_score = 0.75

        # Overall score is weighted average
        overall_score = (alignment_score * 0.4 + consistency_score * 0.4 + evolution_score * 0.2)

        # Generate strengths, concerns, and recommendations
        strengths = []
        concerns = []
        recommendations = []

        if alignment_score > 0.7:
            strengths.append("Well-aligned with related architectural decisions")
        else:
            concerns.append("May not align well with existing architectural direction")

        if consistency_score > 0.7:
            strengths.append("Consistent analysis across different perspectives")
        else:
            concerns.append("Inconsistent viewpoints from different personas")

        if overall_score > 0.8:
            recommendations.append("Continue monitoring for changes in related decisions")
        else:
            recommendations.append("Consider re-assessment in light of recent changes")

        return ContinuityAssessment(
            adr_id=target_adr.metadata.id,
            overall_score=overall_score,
            alignment_score=alignment_score,
            consistency_score=consistency_score,
            evolution_score=evolution_score,
            strengths=strengths,
            concerns=concerns,
            recommendations=recommendations
        )

    async def _generate_reassessment_recommendations(
        self,
        target_adr: ADR,
        conflicts: List[ADRConflict],
        continuity_assessment: ContinuityAssessment,
        persona_analyses: Dict[str, ADRAnalysisResult]
    ) -> List[ReassessmentRecommendation]:
        """Generate recommendations for re-assessing the ADR.

        Args:
            target_adr: The ADR being analyzed
            conflicts: Detected conflicts
            continuity_assessment: Continuity assessment results
            persona_analyses: Analysis from different personas

        Returns:
            List of re-assessment recommendations
        """
        recommendations = []

        # High-priority recommendation if critical conflicts exist
        critical_conflicts = [c for c in conflicts if c.severity == "critical"]
        if critical_conflicts:
            recommendations.append(ReassessmentRecommendation(
                adr_id=target_adr.metadata.id,
                priority="urgent",
                reason="Critical conflicts detected with related decisions",
                triggers=["conflict_detection"],
                suggested_actions=[
                    "Immediate review of conflicting decisions",
                    "Stakeholder meeting to resolve conflicts",
                    "Potential revision of current decision"
                ],
                estimated_effort="large",
                business_impact="High - may affect system stability and compliance",
                recommended_by=["architect", "risk_manager"]
            ))

        # Medium-priority for continuity concerns
        if continuity_assessment.overall_score < 0.6:
            recommendations.append(ReassessmentRecommendation(
                adr_id=target_adr.metadata.id,
                priority="high",
                reason="Continuity assessment indicates potential issues",
                triggers=["continuity_assessment"],
                suggested_actions=[
                    "Review alignment with recent architectural changes",
                    "Update decision based on new requirements",
                    "Validate assumptions with current context"
                ],
                estimated_effort="medium",
                business_impact="Medium - may affect long-term maintainability",
                recommended_by=["technical_lead", "architect"]
            ))

        # Low-priority periodic review
        if not recommendations:
            recommendations.append(ReassessmentRecommendation(
                adr_id=target_adr.metadata.id,
                priority="low",
                reason="Periodic review recommended",
                triggers=["time_based"],
                suggested_actions=[
                    "Review decision in current context",
                    "Check for new technology options",
                    "Validate continued relevance"
                ],
                estimated_effort="small",
                business_impact="Low - routine maintenance",
                recommended_by=["business_analyst"]
            ))

        return recommendations

    async def _generate_overall_assessment(
        self,
        target_adr: ADR,
        conflicts: List[ADRConflict],
        continuity_assessment: ContinuityAssessment,
        persona_analyses: Dict[str, ADRAnalysisResult]
    ) -> str:
        """Generate an overall assessment summary.

        Args:
            target_adr: The ADR being analyzed
            conflicts: Detected conflicts
            continuity_assessment: Continuity assessment
            persona_analyses: Persona analysis results

        Returns:
            Overall assessment summary
        """
        assessment_parts = []

        # Assess conflicts
        if conflicts:
            critical_count = len([c for c in conflicts if c.severity == "critical"])
            if critical_count > 0:
                assessment_parts.append(f"CRITICAL: {critical_count} critical conflicts detected that require immediate attention.")
            else:
                assessment_parts.append(f"WARNING: {len(conflicts)} conflicts detected with related decisions.")
        else:
            assessment_parts.append("No significant conflicts detected with related decisions.")

        # Assess continuity
        continuity_pct = continuity_assessment.overall_score * 100
        if continuity_pct >= 80:
            assessment_parts.append(".1f")
        elif continuity_pct >= 60:
            assessment_parts.append(".1f")
        else:
            assessment_parts.append(".1f")

        # Assess persona consensus
        if persona_analyses:
            scores = [analysis.score for analysis in persona_analyses.values() if analysis.score]
            if scores:
                avg_score = sum(scores) / len(scores)
                if avg_score >= 8:
                    assessment_parts.append(".1f")
                elif avg_score >= 6:
                    assessment_parts.append(".1f")
                else:
                    assessment_parts.append(".1f")

        return " ".join(assessment_parts)

    def _extract_key_findings(
        self,
        conflicts: List[ADRConflict],
        continuity_assessment: ContinuityAssessment,
        persona_analyses: Dict[str, ADRAnalysisResult]
    ) -> List[str]:
        """Extract key findings from the analysis.

        Args:
            conflicts: Detected conflicts
            continuity_assessment: Continuity assessment
            persona_analyses: Persona analyses

        Returns:
            List of key findings
        """
        findings = []

        if conflicts:
            findings.append(f"Identified {len(conflicts)} potential conflicts with related decisions")

        if continuity_assessment.overall_score < 0.7:
            findings.append("Continuity assessment indicates potential misalignment with architectural direction")

        if persona_analyses:
            high_scores = len([a for a in persona_analyses.values() if a.score and a.score >= 8])
            low_scores = len([a for a in persona_analyses.values() if a.score and a.score < 6])
            if high_scores > low_scores:
                findings.append("Generally positive assessment across multiple personas")
            elif low_scores > high_scores:
                findings.append("Mixed to negative assessment requiring attention")

        return findings

    def _extract_action_items(
        self,
        conflicts: List[ADRConflict],
        recommendations: List[ReassessmentRecommendation]
    ) -> List[str]:
        """Extract action items from conflicts and recommendations.

        Args:
            conflicts: Detected conflicts
            recommendations: Re-assessment recommendations

        Returns:
            List of action items
        """
        actions = []

        # Actions from conflicts
        for conflict in conflicts:
            if conflict.severity in ["high", "critical"]:
                actions.extend(conflict.resolution_suggestions[:2])  # Limit to 2 per conflict

        # Actions from recommendations
        for rec in recommendations:
            if rec.priority in ["high", "urgent"]:
                actions.extend(rec.suggested_actions[:2])  # Limit to 2 per recommendation

        # Remove duplicates and limit total
        unique_actions = list(dict.fromkeys(actions))
        return unique_actions[:5]  # Limit to 5 total actions

    def generate_analysis_report(
        self,
        analysis_result: ContextualAnalysisResult,
        report_format: str = "markdown"
    ) -> AnalysisReport:
        """Generate a structured analysis report from contextual analysis results.

        Args:
            analysis_result: Results from contextual analysis
            report_format: Format for the report (markdown, html, json)

        Returns:
            Structured analysis report
        """
        import uuid
        report_id = f"analysis-{uuid.uuid4().hex[:8]}"

        # Create executive summary
        conflict_count = len(analysis_result.conflicts)
        continuity_score = analysis_result.continuity_assessment.overall_score

        if conflict_count == 0 and continuity_score >= 0.8:
            summary_status = "POSITIVE"
        elif conflict_count > 0 or continuity_score < 0.6:
            summary_status = "REQUIRES ATTENTION"
        else:
            summary_status = "NEUTRAL"

        executive_summary = f"""Contextual analysis of ADR "{analysis_result.target_adr.metadata.title}" completed with {summary_status} findings.

Key Results:
- Conflicts Detected: {conflict_count}
- Continuity Score: {continuity_score:.1%}
- Personas Analyzed: {len(analysis_result.persona_analyses)}
- Re-assessment Recommendations: {len(analysis_result.reassessment_recommendations)}

{analysis_result.overall_assessment}"""

        # Target ADR summary
        target_summary = {
            "title": analysis_result.target_adr.metadata.title,
            "status": analysis_result.target_adr.metadata.status.value,
            "author": analysis_result.target_adr.metadata.author,
            "created_at": analysis_result.target_adr.metadata.created_at.isoformat(),
            "tags": analysis_result.target_adr.metadata.tags
        }

        # Extract recommendations and next steps
        recommendations = []
        next_steps = []

        for rec in analysis_result.reassessment_recommendations:
            recommendations.append(f"{rec.priority.upper()}: {rec.reason}")
            next_steps.extend(rec.suggested_actions[:1])  # One action per recommendation

        next_steps.extend(analysis_result.action_items[:2])  # Add key action items

        return AnalysisReport(
            report_id=report_id,
            title=f"Contextual Analysis Report: {analysis_result.target_adr.metadata.title}",
            executive_summary=executive_summary,
            target_adr_summary=target_summary,
            contextual_analysis=analysis_result,
            recommendations=list(dict.fromkeys(recommendations)),  # Remove duplicates
            next_steps=list(dict.fromkeys(next_steps))[:5],  # Limit and remove duplicates
            report_format=report_format
        )
